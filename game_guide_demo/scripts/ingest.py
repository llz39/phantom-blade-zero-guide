# -*- coding: utf-8 -*-
"""攻略知识库入库脚本。

流程（限制文档 5.5）：
    读取 Markdown → 校验 front matter → 清洗 → 分块（300-700 tokens，10-20% overlap）
    → embedding → MySQL guide_doc 登记 → Milvus upsert

用法：
    cd game_guide_demo
    python scripts/ingest.py --dry-run            # 只分块，不调 API、不写库
    python scripts/ingest.py                      # 全量入库（幂等）
    python scripts/ingest.py --doc-type weapon    # 只处理武器
    python scripts/ingest.py --rebuild            # 删除 collection 后重建
    python scripts/ingest.py --limit 5            # 抽样调试

幂等：
    doc_id = "{game_id}:{doc_type}:{entity_id}:{version}"
    重新入库时先按 doc_id 删除旧 chunk，再写新 chunk；MySQL 按 doc_id 做 UPSERT。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent          # game_guide_demo
REPO_ROOT = BASE_DIR.parent                                # 仓库根目录
for extra in (str(BASE_DIR), str(REPO_ROOT)):
    if extra not in sys.path:
        sys.path.insert(0, extra)

# 与 app.py 共用同一套环境加载逻辑（含 ZILLIZ_CLOUD_* → MILVUS_* 的别名映射）
from env_bootstrap import load_env  # noqa: E402

load_env()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ingest")

GAME_ID = "phantom_blade_zero"
KNOWLEDGE_DIR = BASE_DIR / "knowledge" / GAME_ID
REPORT_PATH = BASE_DIR / "ingest_report.json"

DOC_TYPES = ("weapon", "boss", "story", "item", "faq")
MIN_TOKENS = 300
MAX_TOKENS = 700
OVERLAP_RATIO = 0.15

FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)
HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.M)


# =============================================================================
# 数据结构
# =============================================================================
@dataclass
class GuideDoc:
    """一篇攻略文档。"""

    path: Path
    doc_id: str
    game_id: str
    doc_type: str
    entity_id: str
    title: str
    version: str
    source_level: str
    source_urls: List[str]
    updated_at: str
    confidence: str
    unknown_fields: List[str]
    body: str
    chunks: List[str] = field(default_factory=list)


# =============================================================================
# 解析
# =============================================================================
def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_front_matter(text: str, path: Path) -> Tuple[Dict[str, Any], str]:
    """解析 YAML front matter（不依赖 PyYAML 的复杂结构，够用即可）。"""
    match = FRONT_MATTER_RE.match(text)
    if not match:
        raise ValueError("缺少 front matter（--- ... ---）")

    meta: Dict[str, Any] = {}
    current_list: Optional[str] = None
    for raw_line in match.group(1).splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if line.lstrip().startswith("- ") and current_list:
            meta.setdefault(current_list, []).append(_strip_quotes(line.lstrip()[2:]))
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if value == "":
                current_list = key
                meta[key] = []
            else:
                current_list = None
                if value.startswith("[") and value.endswith("]"):
                    items = [item for item in value[1:-1].split(",") if item.strip()]
                    meta[key] = [_strip_quotes(item) for item in items]
                else:
                    meta[key] = _strip_quotes(value)

    return meta, text[match.end():]


def load_doc(path: Path) -> GuideDoc:
    """读取并校验一篇文档。"""
    text = path.read_text(encoding="utf-8")
    meta, body = parse_front_matter(text, path)

    game_id = str(meta.get("game_id") or GAME_ID)
    doc_type = str(meta.get("doc_type") or "")
    entity_id = str(meta.get("entity_id") or "")
    title = str(meta.get("title") or "")
    version = str(meta.get("version") or "")
    source_level = str(meta.get("source_level") or "")

    if game_id != GAME_ID:
        raise ValueError(f"game_id 非法: {game_id}（本项目只做 {GAME_ID}）")
    if doc_type not in DOC_TYPES:
        raise ValueError(f"doc_type 非法: {doc_type}")
    if not entity_id:
        raise ValueError("缺少 entity_id")
    if not title:
        raise ValueError("缺少 title")
    if not version:
        raise ValueError("缺少 version")
    if not re.fullmatch(r"S[1-4]", source_level):
        raise ValueError(f"source_level 非法: {source_level}")

    source_urls = meta.get("source_urls") or []
    if isinstance(source_urls, str):
        source_urls = [source_urls] if source_urls else []
    if not source_urls:
        raise ValueError("source_urls 为空：每个实体至少 1 个来源")
    for url in source_urls:
        if not url.startswith("http"):
            raise ValueError(f"来源不是 URL: {url}")

    confidence = str(meta.get("confidence") or "low")
    if confidence not in ("high", "medium", "low"):
        raise ValueError(f"confidence 非法: {confidence}")

    unknown_fields = meta.get("unknown_fields") or []
    if isinstance(unknown_fields, str):
        unknown_fields = [item.strip() for item in unknown_fields.split(",") if item.strip()]

    # doc_id 是幂等键，同时要落进 Milvus 的 VARCHAR(64) 字段。
    # 曾经用 "game_id:doc_type:entity_id:version"，遇到
    # weapon_white_serpent_crimson_viper 这类长实体名会到 70 字节、直接写入失败。
    # 所以收敛为 "pbz:类型:实体"，version 单独作为标量字段存；
    # 换版本时按 doc_id 先删旧 chunk，语义上仍然是「最新版本覆盖」。
    doc_id = f"pbz:{doc_type}:{entity_id}"
    if len(doc_id) > 64:  # 兜底：极端长的实体名退化为哈希，保证可写
        doc_id = "pbz:" + hashlib.sha1(doc_id.encode("utf-8")).hexdigest()[:40]
    return GuideDoc(
        path=path,
        doc_id=doc_id,
        game_id=game_id,
        doc_type=doc_type,
        entity_id=entity_id,
        title=title,
        version=version,
        source_level=source_level,
        source_urls=[str(u) for u in source_urls],
        updated_at=str(meta.get("updated_at") or ""),
        confidence=confidence,
        unknown_fields=[str(u) for u in unknown_fields],
        body=body.strip(),
    )


# =============================================================================
# 分块
# =============================================================================
def estimate_tokens(text: str) -> int:
    """粗略估算 token 数：中文按 1 字 ≈ 1 token，其他按 3.5 字符 ≈ 1 token。"""
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    other = max(0, len(text) - cjk)
    return int(cjk + other / 3.5) + 1


def split_sections(body: str) -> List[str]:
    """按 #/##/### 标题切分，标题随正文保留。"""
    positions = [m.start() for m in HEADING_RE.finditer(body)]
    if not positions:
        return [body.strip()] if body.strip() else []

    sections: List[str] = []
    # 标题前的内容（如有）作为第一段
    if positions[0] > 0:
        head = body[: positions[0]].strip()
        if head:
            sections.append(head)
    for index, start in enumerate(positions):
        end = positions[index + 1] if index + 1 < len(positions) else len(body)
        chunk = body[start:end].strip()
        if chunk:
            sections.append(chunk)
    return sections


def split_paragraphs(section: str) -> List[str]:
    """按空行切段；表格/列表作为整体，不在中间断开。"""
    parts = [part.strip() for part in re.split(r"\n\s*\n", section) if part.strip()]
    return parts or [section.strip()]


def _tail_by_tokens(text: str, tokens: int) -> str:
    """取文本尾部约 tokens 个 token，用于 overlap。"""
    if tokens <= 0:
        return ""
    # 中文 1 字 ≈ 1 token，按长度近似截取
    approx_chars = int(tokens * 1.3)
    tail = text[-approx_chars:] if len(text) > approx_chars else text
    # 尽量从段落开头起步，避免半句
    newline = tail.find("\n\n")
    if 0 <= newline < len(tail) - 20:
        tail = tail[newline:].strip()
    return tail


def _hard_split(part: str, max_tokens: int) -> List[str]:
    """单段超长时按行切，行仍超长则按字符切。"""
    lines = part.splitlines()
    pieces: List[str] = []
    buffer: List[str] = []
    buffer_tokens = 0
    for line in lines:
        line_tokens = estimate_tokens(line)
        if line_tokens > max_tokens:
            if buffer:
                pieces.append("\n".join(buffer))
                buffer, buffer_tokens = [], 0
            step = max(200, int(max_tokens * 1.2))
            for i in range(0, len(line), step):
                pieces.append(line[i:i + step])
            continue
        if buffer and buffer_tokens + line_tokens > max_tokens:
            pieces.append("\n".join(buffer))
            buffer, buffer_tokens = [], 0
        buffer.append(line)
        buffer_tokens += line_tokens
    if buffer:
        pieces.append("\n".join(buffer))
    return [piece for piece in pieces if piece.strip()]


def chunk_body(body: str) -> List[str]:
    """把正文切成 300-700 tokens 的块，块间保留约 15% overlap。

    步骤：
    1. 按 `#/##/###` 切小节（标题跟着正文走，检索时能带上上下文）；
    2. 单节超 700 就先按行硬切，避免一节撑爆；
    3. 顺序装箱到 700，装满就落一块，并用上一块的尾巴做 15% 重叠
       —— 重叠是为了避免“答案正好被切在缝里”；
    4. 最后把过小的块往上一块合并，减少碎片。

    注意：实体卡片式语料单条常在 200-290 tokens，
    这里**不做填充式扩写**，宁可块小也不塞套话（限制文档 0.2）。
    """
    sections = split_sections(body)
    parts: List[str] = []
    for section in sections:
        if estimate_tokens(section) <= MAX_TOKENS:
            parts.append(section)
        else:
            parts.extend(_hard_split(section, MAX_TOKENS))

    if not parts:
        return []

    overlap_tokens = int(MAX_TOKENS * OVERLAP_RATIO)
    chunks: List[str] = []
    buffer: List[str] = []
    buffer_tokens = 0

    for part in parts:
        part_tokens = estimate_tokens(part)
        if buffer and buffer_tokens + part_tokens > MAX_TOKENS:
            text = "\n\n".join(buffer).strip()
            chunks.append(text)
            tail = _tail_by_tokens(text, overlap_tokens)
            buffer = [tail, part] if tail else [part]
            buffer_tokens = estimate_tokens("\n\n".join(buffer))
        else:
            buffer.append(part)
            buffer_tokens += part_tokens

    if buffer:
        text = "\n\n".join(buffer).strip()
        if text:
            chunks.append(text)

    # 合并过小的块，保证单块尽量 ≥ MIN_TOKENS
    merged: List[str] = []
    for chunk in chunks:
        if merged and estimate_tokens(chunk) < MIN_TOKENS:
            candidate = f"{merged[-1]}\n\n{chunk}"
            if estimate_tokens(candidate) <= MAX_TOKENS:
                merged[-1] = candidate
                continue
        merged.append(chunk)

    return merged


# =============================================================================
# MySQL
# =============================================================================
def connect_mysql(url: str):
    """建立 pymysql 连接。"""
    from urllib.parse import urlparse

    import pymysql

    parsed = urlparse(url.replace("mysql+pymysql://", "mysql://"))
    return pymysql.connect(
        host=parsed.hostname or "127.0.0.1",
        port=parsed.port or 3306,
        user=parsed.username or "root",
        password=parsed.password or "",
        database=(parsed.path or "/game_guide").lstrip("/"),
        charset="utf8mb4",
        connect_timeout=8,
        autocommit=False,
    )


def upsert_guide_doc(conn, doc: GuideDoc, chunk_count: int) -> None:
    """按 doc_id UPSERT 文档登记。"""
    sql = """
        INSERT INTO guide_doc
            (doc_id, game_id, doc_type, entity_id, title, source, source_level,
             source_urls, version, confidence, unknown_fields, chunk_count, status, created_at, updated_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,NOW(),NOW())
        ON DUPLICATE KEY UPDATE
            title=VALUES(title),
            source=VALUES(source),
            source_level=VALUES(source_level),
            source_urls=VALUES(source_urls),
            confidence=VALUES(confidence),
            unknown_fields=VALUES(unknown_fields),
            chunk_count=VALUES(chunk_count),
            status=1,
            updated_at=NOW()
    """
    with conn.cursor() as cursor:
        cursor.execute(
            sql,
            (
                doc.doc_id,
                doc.game_id,
                doc.doc_type,
                doc.entity_id,
                doc.title,
                doc.source_urls[0],
                doc.source_level,
                json.dumps(doc.source_urls, ensure_ascii=False),
                doc.version,
                doc.confidence,
                json.dumps(doc.unknown_fields, ensure_ascii=False),
                chunk_count,
            ),
        )
    conn.commit()


# =============================================================================
# Milvus
# =============================================================================
def build_retriever():
    """复用运行时同一套配置构造 MilvusRetriever（含 collection 校验）。"""
    from customer_service_system.shared.config import EndpointsConfig

    from addons.milvus_retrieval import MilvusRetriever

    endpoints = EndpointsConfig.load(BASE_DIR / "endpoints.yml")
    vector_cfg = endpoints.vector_store.to_connect_config()
    embeddings = endpoints.get_embeddings_config("default")
    if embeddings:
        vector_cfg["embedding"] = {
            "model": embeddings.model,
            "api_key": embeddings.api_key,
            "api_base": embeddings.api_base,
            "dimension": embeddings.dimensions,
        }
    retriever = MilvusRetriever()
    retriever.connect(vector_cfg)
    return retriever


def write_to_milvus(retriever, doc: GuideDoc, texts: List[str]) -> int:
    """先删旧 chunk，再批量写入；返回写入条数。

    主键用 sha1(doc_id#chunk_index) 而不是拼接原文：
    Milvus 的 VARCHAR 主键上限 64 字节，长 entity_id（如
    weapon_white_serpent_crimson_viper）拼上 doc_id 会超长直接报错。
    sha1 十六进制固定 40 位，既稳定又幂等。
    """
    if not texts:
        return 0
    vectors = retriever.embedding_client.embed(texts)
    rows = []
    for index, (text, vector) in enumerate(zip(texts, vectors)):
        chunk_key = f"{doc.doc_id}#{index}"
        rows.append(
            {
                "id": hashlib.sha1(chunk_key.encode("utf-8")).hexdigest(),
                "doc_id": doc.doc_id,
                "game_id": doc.game_id,
                "doc_type": doc.doc_type,
                "entity_id": doc.entity_id,
                "title": doc.title[:500],
                "content": text[:8000],
                "source": doc.source_urls[0][:500],
                "source_level": doc.source_level,
                "version": doc.version,
                "chunk_index": index,
                "updated_at": doc.updated_at[:30],
                "embedding": vector,
            }
        )

    client = retriever._client  # noqa: SLF001 - 同一模块内的写入路径
    try:
        client.delete(
            collection_name=retriever.collection,
            filter=f'doc_id == "{doc.doc_id}"',
        )
    except Exception as exc:  # noqa: BLE001 - 首次入库无旧数据
        logger.debug("删除旧 chunk 失败（可忽略）: %s", exc)

    client.insert(collection_name=retriever.collection, data=rows)
    return len(rows)


# =============================================================================
# 主流程
# =============================================================================
def collect_files(doc_type: Optional[str]) -> List[Path]:
    if not KNOWLEDGE_DIR.exists():
        raise SystemExit(f"知识库目录不存在: {KNOWLEDGE_DIR}")
    folder_map = {
        "weapon": "weapons",
        "boss": "bosses",
        "story": "story",
        "item": "items",
        "faq": "faq",
    }
    types = [doc_type] if doc_type else list(DOC_TYPES)
    files: List[Path] = []
    for name in types:
        folder = KNOWLEDGE_DIR / folder_map[name]
        if not folder.exists():
            logger.warning("目录不存在，跳过: %s", folder)
            continue
        files.extend(sorted(folder.glob("*.md")))
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description="《影之刃零》攻略知识库入库")
    parser.add_argument("--game_id", default=GAME_ID)
    parser.add_argument("--doc-type", default=None, choices=list(DOC_TYPES))
    parser.add_argument("--rebuild", action="store_true", help="删除 collection 后重建")
    parser.add_argument("--dry-run", action="store_true", help="只分块，不调 API、不写库")
    parser.add_argument("--limit", type=int, default=0, help="只处理前 N 篇")
    args = parser.parse_args()

    if args.game_id != GAME_ID:
        raise SystemExit(f"本项目只做 {GAME_ID}，拒绝处理 {args.game_id}")

    files = collect_files(args.doc_type)
    if args.limit:
        files = files[: args.limit]
    if not files:
        raise SystemExit("没有找到任何 Markdown 文档")

    logger.info("待处理文档: %s 篇", len(files))

    retriever = None
    mysql_conn = None
    if not args.dry_run:
        retriever = build_retriever()
        if args.rebuild:
            logger.warning("重建 collection: %s", retriever.collection)
            retriever._client.drop_collection(retriever.collection)  # noqa: SLF001
            retriever._ensure_collection("HNSW", 16, 200)  # noqa: SLF001

        from customer_service_system.shared.config import EndpointsConfig

        endpoints = EndpointsConfig.load(BASE_DIR / "endpoints.yml")
        if endpoints.tracker_store.url:
            mysql_conn = connect_mysql(endpoints.tracker_store.url)

    report: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "game_id": GAME_ID,
        "dry_run": args.dry_run,
        "rebuild": args.rebuild,
        "total_files": len(files),
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "total_chunks": 0,
        "total_tokens": 0,
        "documents": [],
        "failures": [],
    }

    try:
        for path in files:
            relative = str(path.relative_to(KNOWLEDGE_DIR))
            try:
                doc = load_doc(path)
                chunks = chunk_body(doc.body)
                if not chunks:
                    report["skipped"] += 1
                    report["failures"].append({"file": relative, "error": "正文为空"})
                    continue

                tokens = sum(estimate_tokens(chunk) for chunk in chunks)
                too_small = [i for i, c in enumerate(chunks) if estimate_tokens(c) < MIN_TOKENS]
                too_large = [i for i, c in enumerate(chunks) if estimate_tokens(c) > MAX_TOKENS]

                entry = {
                    "file": relative,
                    "doc_id": doc.doc_id,
                    "doc_type": doc.doc_type,
                    "entity_id": doc.entity_id,
                    "chunks": len(chunks),
                    "tokens": tokens,
                    "chunk_tokens": [estimate_tokens(c) for c in chunks],
                    "sources": doc.source_urls,
                }
                if too_large:
                    entry["warning"] = f"超过 {MAX_TOKENS} tokens 的块: {too_large}"
                if too_small and len(chunks) > 1:
                    entry["note"] = f"小于 {MIN_TOKENS} tokens 的块: {too_small}（标题短段无法合并）"

                if not args.dry_run:
                    written = write_to_milvus(retriever, doc, chunks)
                    if mysql_conn:
                        upsert_guide_doc(mysql_conn, doc, written)
                    entry["milvus_rows"] = written

                report["documents"].append(entry)
                report["success"] += 1
                report["total_chunks"] += len(chunks)
                report["total_tokens"] += tokens
                logger.info("[OK] %s -> %s chunks", relative, len(chunks))

            except Exception as exc:  # noqa: BLE001 - 单篇失败不影响其它
                report["failed"] += 1
                report["failures"].append({"file": relative, "error": str(exc)})
                logger.error("[FAIL] %s: %s", relative, exc)
    finally:
        if mysql_conn:
            mysql_conn.close()
        if retriever:
            retriever.close()

    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(
        "完成: 成功 %s / 失败 %s / 跳过 %s，chunks=%s，tokens≈%s",
        report["success"], report["failed"], report["skipped"],
        report["total_chunks"], report["total_tokens"],
    )
    logger.info("报告: %s", REPORT_PATH)
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
