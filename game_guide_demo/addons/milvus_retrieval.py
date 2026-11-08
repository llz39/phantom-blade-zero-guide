# -*- coding: utf-8 -*-
"""
Milvus 检索器（《影之刃零》攻略知识库）

替换原电商项目的图数据库方案：
    向量召回由 Milvus 负责，结构化登记与业务数据由 MySQL 负责。

设计约束（见《影之刃零客服_开发限制文档》8.3 / 6.1）：
1. collection 固定 ``game_guide_chunks``，维度默认 1024，必须与 embedding API 一致；
2. 索引 HNSW + COSINE，M=16，efConstruction=200，efSearch=64；
3. 强制按 ``game_id`` 过滤，避免跨游戏串答案；有实体时优先按 ``entity_id`` 过滤；
4. ``search()`` 内的同步 Milvus 调用放到 ``asyncio.to_thread``；
5. 任何异常只记录日志并返回空列表，不把异常抛到对话层。

用法：
    retriever = MilvusRetriever()
    retriever.connect(endpoints["vector_store"])
    results = await retriever.search("白山风雷剑怎么获得", top_k=5)
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional, Sequence

from customer_service_system.retrieval.base_retriever import (
    InformationRetrieval,
    SearchResult,
)

logger = logging.getLogger(__name__)

DEFAULT_COLLECTION = "game_guide_chunks"
DEFAULT_GAME_ID = "phantom_blade_zero"
DEFAULT_DIMENSION = 1024

# Milvus 中允许作为标量的 doc_type（与知识库目录一致）
ALLOWED_DOC_TYPES = ("weapon", "boss", "story", "item", "faq")

# 检索命中后需要回传给策略/前端的字段
OUTPUT_FIELDS = [
    "doc_id",
    "game_id",
    "doc_type",
    "entity_id",
    "title",
    "content",
    "source",
    "source_level",
    "version",
    "chunk_index",
    "updated_at",
]


# =============================================================================
# Embedding（OpenAI 兼容 API，统一走接口，禁止本地 BGE）
# =============================================================================
class HttpEmbeddingClient:
    """OpenAI 兼容的 embedding 客户端（同步实现，供 to_thread 调用）。

    维度校验是硬约束：返回维度与 collection 不一致时直接报错，
    不允许“硬塞”进另一个维度的 collection。
    """

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        dimension: int = DEFAULT_DIMENSION,
        batch_size: int = 10,
        timeout: int = 30,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.getenv("QWEN_API_KEY", "")
        self.api_base = api_base or os.getenv(
            "EMBEDDING_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        self.dimension = int(dimension)
        self.batch_size = max(1, int(batch_size))
        self.timeout = timeout
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI

            if not self.api_key:
                raise RuntimeError("缺少 embedding api_key（QWEN_API_KEY）")
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.api_base,
                timeout=self.timeout,
            )
        return self._client

    def _call(self, batch: Sequence[str]) -> List[List[float]]:
        client = self._get_client()
        kwargs: Dict[str, Any] = {"model": self.model, "input": list(batch)}
        # DashScope text-embedding-v3/v4 支持 dimensions；不支持时回退重试
        try:
            resp = client.embeddings.create(dimensions=self.dimension, **kwargs)
        except Exception as exc:  # noqa: BLE001 - 兼容不支持 dimensions 的服务
            logger.debug("embedding 带 dimensions 调用失败(%s)，回退默认维度", exc)
            resp = client.embeddings.create(**kwargs)
        vectors = [list(map(float, item.embedding)) for item in resp.data]
        for vector in vectors:
            if len(vector) != self.dimension:
                raise ValueError(
                    f"embedding 维度不匹配：接口返回 {len(vector)}，"
                    f"collection 期望 {self.dimension}。请重建 collection 或修改配置。"
                )
        return vectors

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        """批量向量化；批大小控制在 10，避免单次请求过大。"""
        results: List[List[float]] = []
        items = [t for t in texts]
        for start in range(0, len(items), self.batch_size):
            results.extend(self._call(items[start:start + self.batch_size]))
        return results


# =============================================================================
# 工具函数
# =============================================================================
def _slot_values(tracker_state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """从 tracker_state 中取槽位真实值。

    注意：``tracker.to_dict()["slots"]`` 的结构是
    ``{槽位名: {"name":..., "type":..., "value":...}}``，
    必须取 ``["value"]``，不能把整个槽位字典当字符串用。
    """
    if not tracker_state:
        return {}
    slots = tracker_state.get("slots") or {}
    values: Dict[str, Any] = {}
    for name, slot in slots.items():
        if isinstance(slot, dict):
            values[name] = slot.get("value")
        else:
            values[name] = getattr(slot, "value", slot)
    return values


def _escape(value: str) -> str:
    """转义 Milvus 表达式中的双引号，避免表达式注入。"""
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


# =============================================================================
# 检索器
# =============================================================================
class MilvusRetriever(InformationRetrieval):
    """Milvus 向量检索器，继承框架的 ``InformationRetrieval``。"""

    def __init__(self, embeddings: Any = None) -> None:
        super().__init__(embeddings)
        self._client = None
        self.collection = DEFAULT_COLLECTION
        self.uri: Optional[str] = None
        self.token: Optional[str] = None
        self.dimension = DEFAULT_DIMENSION
        self.metric_type = "COSINE"
        self.ef_search = 64
        self.game_id = DEFAULT_GAME_ID
        self.max_context_chars = 6000
        self.embedding_client: Optional[HttpEmbeddingClient] = None

    # ------------------------------------------------------------------ 连接
    def connect(self, config: Optional[Dict[str, Any]] = None) -> None:
        """连接 Milvus，必要时创建 collection。

        Args:
            config: 来自 endpoints.yml 的 ``vector_store`` 段，
                可包含 uri / token / collection / dimension /
                index_type / hnsw_m / hnsw_ef_construction / ef_search /
                game_id / embedding（model、api_key、api_base、dimension）。
        """
        config = config or {}

        self.uri = config.get("uri") or os.getenv("MILVUS_URI", "http://localhost:19530")
        self.token = config.get("token") or os.getenv("MILVUS_TOKEN") or ""
        self.collection = config.get("collection") or os.getenv(
            "MILVUS_COLLECTION", DEFAULT_COLLECTION
        )
        self.dimension = int(config.get("dimension") or os.getenv("EMBEDDING_DIM", DEFAULT_DIMENSION))
        self.metric_type = str(config.get("metric_type", "COSINE")).upper()
        self.ef_search = int(config.get("ef_search", 64))
        self.game_id = str(config.get("game_id", DEFAULT_GAME_ID))
        self.max_context_chars = int(config.get("max_context_chars", 6000))

        embedding_cfg = config.get("embedding") or {}
        self.embedding_client = HttpEmbeddingClient(
            model=embedding_cfg.get("model")
            or os.getenv("EMBEDDING_MODEL", "text-embedding-v4"),
            api_key=embedding_cfg.get("api_key") or os.getenv("QWEN_API_KEY"),
            api_base=embedding_cfg.get("api_base")
            or os.getenv("EMBEDDING_API_BASE"),
            dimension=self.dimension,
        )

        from pymilvus import MilvusClient  # 延迟导入：未安装时由 agent 层捕获

        self._client = MilvusClient(uri=self.uri, token=self.token or None)
        self._ensure_collection(
            index_type=str(config.get("index_type", "HNSW")),
            m=int(config.get("hnsw_m", 16)),
            ef_construction=int(config.get("hnsw_ef_construction", 200)),
        )
        logger.info(
            "MilvusRetriever 已连接 uri=%s collection=%s dim=%s",
            self.uri,
            self.collection,
            self.dimension,
        )

    def _ensure_collection(self, index_type: str, m: int, ef_construction: int) -> None:
        """collection 不存在则创建；存在则校验维度并加载。"""
        from pymilvus import DataType, MilvusClient

        if self._client.has_collection(self.collection):
            desc = self._client.describe_collection(self.collection)
            for field in desc.get("fields", []):
                if field.get("name") == "embedding":
                    params = field.get("params") or {}
                    existing_dim = params.get("dim")
                    if existing_dim and int(existing_dim) != self.dimension:
                        raise ValueError(
                            f"collection {self.collection} 维度为 {existing_dim}，"
                            f"与配置 {self.dimension} 不一致；collection 建好后维度不可改，"
                            "请换 embedding 模型并重建 collection。"
                        )
            self._client.load_collection(self.collection)
            logger.info("复用已有 collection: %s", self.collection)
            return

        schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field("id", DataType.VARCHAR, is_primary=True, max_length=64)
        schema.add_field("doc_id", DataType.VARCHAR, max_length=64)
        schema.add_field("game_id", DataType.VARCHAR, max_length=64)
        schema.add_field("doc_type", DataType.VARCHAR, max_length=32)
        schema.add_field("entity_id", DataType.VARCHAR, max_length=128)
        schema.add_field("title", DataType.VARCHAR, max_length=512)
        schema.add_field("content", DataType.VARCHAR, max_length=8192)
        schema.add_field("source", DataType.VARCHAR, max_length=512)
        schema.add_field("source_level", DataType.VARCHAR, max_length=8)
        schema.add_field("version", DataType.VARCHAR, max_length=32)
        schema.add_field("chunk_index", DataType.INT64)
        schema.add_field("updated_at", DataType.VARCHAR, max_length=32)
        schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=self.dimension)

        index_params = MilvusClient.prepare_index_params()
        index_params.add_index(
            field_name="embedding",
            index_type=index_type,
            metric_type=self.metric_type,
            params={"M": m, "efConstruction": ef_construction},
        )

        self._client.create_collection(
            collection_name=self.collection,
            schema=schema,
            index_params=index_params,
        )
        self._client.load_collection(self.collection)
        logger.info("已创建 collection: %s (dim=%s)", self.collection, self.dimension)

    # ------------------------------------------------------------------ 检索
    async def search(
        self,
        query: str,
        top_k: int = 5,
        tracker_state: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """语义检索。

        Args:
            query: 已拼接槽位上下文的查询文本
            top_k: 返回条数（限制文档要求 4-6）
            tracker_state: 会话状态，用于读取实体/文档类型过滤条件

        Returns:
            SearchResult 列表；任何异常均返回空列表并记录日志。
        """
        query = (query or "").strip()
        if not query or self._client is None or self.embedding_client is None:
            return []
        top_k = max(1, min(int(top_k or 5), 6))
        try:
            return await asyncio.to_thread(self._search_sync, query, top_k, tracker_state)
        except Exception as exc:  # noqa: BLE001 - 不向对话层抛异常
            logger.warning("[MilvusRetriever] 检索失败，返回空结果: %s", exc)
            return []

    def _search_sync(
        self,
        query: str,
        top_k: int,
        tracker_state: Optional[Dict[str, Any]],
    ) -> List[SearchResult]:
        # 1) 查询向量化（走 API，失败会在外层 catch 掉并返回空）
        vector = self.embedding_client.embed([query])[0]

        # 2) 标量过滤：先锁 game_id，避免跨游戏串答案
        expr, hint = self._build_expr(tracker_state)

        # 3) 多取一些候选再截断：同文档可能命中多个 chunk，
        #    limit 放大 3 倍是为了在去重后仍然凑得够 top_k。
        raw = self._client.search(
            collection_name=self.collection,
            data=[vector],
            anns_field="embedding",
            search_params={
                "metric_type": self.metric_type,
                "params": {"ef": self.ef_search},
            },
            limit=max(top_k * 3, top_k),
            filter=expr,
            output_fields=OUTPUT_FIELDS,
        )

        hits = raw[0] if raw else []
        results: List[SearchResult] = []
        seen_doc_count: Dict[str, int] = {}

        for hit in hits:
            entity = hit.get("entity") or {}
            doc_id = entity.get("doc_id") or ""
            # 同一文档最多取 2 个 chunk，避免单实体挤占全部上下文
            if doc_id and seen_doc_count.get(doc_id, 0) >= 2:
                continue
            score = float(hit.get("distance", 0.0))
            title = entity.get("title") or ""
            # 实体提示命中时加权，保证“问谁就答谁”，不跨实体串答案
            # （COSINE 已经是 0-1 相似度，加 0.08 足够把同名实体顶到第一）
            if hint and hint in title:
                score = min(1.0, score + 0.08)

            metadata = {
                "source": entity.get("source") or "",
                "title": title,
                "doc_id": doc_id,
                "entity_id": entity.get("entity_id") or "",
                "doc_type": entity.get("doc_type") or "",
                "source_level": entity.get("source_level") or "",
                "version": entity.get("version") or "",
                "updated_at": entity.get("updated_at") or "",
                "game_id": entity.get("game_id") or self.game_id,
            }
            results.append(
                SearchResult(text=(entity.get("content") or "")[: self.max_context_chars],
                             metadata=metadata,
                             score=score)
            )
            if doc_id:
                seen_doc_count[doc_id] = seen_doc_count.get(doc_id, 0) + 1
            if len(results) >= top_k:
                break

        results.sort(key=lambda item: item.score or 0.0, reverse=True)
        logger.info(
            "[MilvusRetriever] query=%r filter=%s 命中=%s",
            query[:60], expr, len(results),
        )
        return results

    def _build_expr(self, tracker_state: Optional[Dict[str, Any]]) -> tuple[str, str]:
        """构造标量过滤表达式，并返回用于加权的实体提示。"""
        parts = [f'game_id == "{_escape(self.game_id)}"']
        slots = _slot_values(tracker_state)

        doc_type = (slots.get("doc_type") or "").strip()
        if doc_type in ALLOWED_DOC_TYPES:
            parts.append(f'doc_type == "{_escape(doc_type)}"')

        entity_id = (slots.get("entity_id") or "").strip()
        if entity_id:
            parts.append(f'entity_id == "{_escape(entity_id)}"')

        # 版本：仅在明确指定时过滤，避免旧补丁文档被误排（限制文档 6.1）
        version = (slots.get("version") or "").strip()
        if version:
            parts.append(f'version == "{_escape(version)}"')

        hint = ""
        for slot_name in ("entity_name", "boss_name", "item_name", "weapon_name", "quest_name"):
            value = (slots.get(slot_name) or "").strip()
            if value:
                hint = value
                break
        return " and ".join(parts), hint

    # ------------------------------------------------------------------ 其它
    def ping(self) -> bool:
        """轻量健康检查：collection 还在且可访问。

        给 /ready 用。不查数据、不做 embedding，代价低，能反映“Milvus 掉线”。
        """
        if self._client is None:
            return False
        try:
            return bool(self._client.has_collection(self.collection))
        except Exception as exc:  # noqa: BLE001
            logger.warning("[MilvusRetriever] ping 失败: %s", exc)
            return False

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:  # noqa: BLE001
                pass
            self._client = None


def build_retriever_from_env() -> Optional[MilvusRetriever]:
    """按环境变量构造检索器（供自定义 Action / 脚本复用）。"""
    try:
        retriever = MilvusRetriever()
        retriever.connect(
            {
                "uri": os.getenv("MILVUS_URI", "http://localhost:19530"),
                "token": os.getenv("MILVUS_TOKEN", ""),
                "collection": os.getenv("MILVUS_COLLECTION", DEFAULT_COLLECTION),
                "dimension": int(os.getenv("EMBEDDING_DIM", DEFAULT_DIMENSION)),
                "embedding": {
                    "model": os.getenv("EMBEDDING_MODEL", "text-embedding-v4"),
                    "api_key": os.getenv("QWEN_API_KEY"),
                    "api_base": os.getenv("EMBEDDING_API_BASE"),
                },
            }
        )
        return retriever
    except Exception as exc:  # noqa: BLE001
        logger.warning("按环境变量构建 MilvusRetriever 失败: %s", exc)
        return None


# 导出
__all__ = [
    "MilvusRetriever",
    "HttpEmbeddingClient",
    "build_retriever_from_env",
    "DEFAULT_COLLECTION",
    "DEFAULT_GAME_ID",
    "DEFAULT_DIMENSION",
]
