# -*- coding: utf-8 -*-
"""验收前置自检（preflight）。

在每次验收/演示之前跑一遍，确认“配置齐了、服务通了”，避免把环境问题误判成模型问题。

检查项：
    1. 依赖包
    2. .env 与关键环境变量
    3. MySQL 连接 + 4 张表 + 行数
    4. Milvus 连接 + collection + 向量条数 + 维度
    5. Embedding API（1 条短文本，校验维度）
    6. LLM API（8 tokens 探活）
    7. 领域工程装配（domain / flows / 知识库 / 检索器类）

用法：
    python scripts/preflight.py                 # 全量
    python scripts/preflight.py --offline       # 只查本地装配与依赖，不联网
    python scripts/preflight.py --skip-llm      # 不花 LLM 的钱
    python scripts/preflight.py --json out.json # 机器可读结果
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent
for extra in (str(BASE_DIR), str(REPO_ROOT), str(BASE_DIR / "scripts")):
    if extra not in sys.path:
        sys.path.insert(0, extra)

from env_bootstrap import load_env  # noqa: E402

# 先加载环境，再读 endpoints.yml：否则 ${VAR} 会展开成空字符串
load_env()

ROWS: List[Tuple[str, str, str]] = []   # (级别, 名称, 说明)
BLOCKER = 0
WARN = 0


def record(level: str, name: str, detail: str) -> None:
    global BLOCKER, WARN
    if level == "FAIL":
        BLOCKER += 1
    elif level == "WARN":
        WARN += 1
    ROWS.append((level, name, detail))
    icon = {"PASS": "OK  ", "WARN": "WARN", "FAIL": "FAIL", "SKIP": "SKIP"}[level]
    print(f"[{icon}] {name}" + (f" — {detail}" if detail else ""))


# =============================================================================
# 1. 依赖
# =============================================================================
def check_deps() -> None:
    modules = {
        "fastapi": "Web 框架",
        "uvicorn": "ASGI 服务器",
        "pymilvus": "Milvus 客户端",
        "sqlalchemy": "ORM",
        "pymysql": "MySQL 驱动",
        "openai": "LLM/Embedding 客户端",
        "yaml": "配置解析",
        "jinja2": "Prompt 模板",
    }
    missing = []
    for name, desc in modules.items():
        try:
            importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001
            missing.append(f"{name}({desc}): {exc}")
    if missing:
        record("FAIL", "依赖包", "缺少: " + "; ".join(missing))
    else:
        record("PASS", "依赖包", f"{len(modules)} 个全部可导入")

    record("PASS", "Python", sys.version.split()[0])


# =============================================================================
# 2. 环境变量
# =============================================================================
def check_env() -> None:
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        record("PASS", ".env", str(env_file))
    else:
        record("FAIL", ".env", "不存在，先 cp .env.example .env 并填写")

    required = {
        "QWEN_API_KEY": "LLM 与 embedding 共用",
        "MILVUS_URI": "Milvus 地址（Zilliz 用 ZILLIZ_CLOUD_URI 也会自动映射）",
    }
    for key, why in required.items():
        value = os.getenv(key, "").strip()
        if not value:
            record("FAIL", f"env:{key}", f"缺失（{why}）")
        else:
            masked = value[:4] + "***" if len(value) > 6 else "***"
            record("PASS", f"env:{key}", masked)

    for key, default_hint in (("MYSQL_HOST", "127.0.0.1"), ("MYSQL_DB", "game_guide")):
        value = os.getenv(key, "").strip()
        record("PASS" if value else "WARN", f"env:{key}", value or f"未设置，将用默认 {default_hint}")

    embed_dim = os.getenv("EMBEDDING_DIM", "1024")
    record("PASS", "env:EMBEDDING_DIM", embed_dim)


# =============================================================================
# 3. MySQL
# =============================================================================
def check_mysql() -> None:
    try:
        from customer_service_system.shared.config import EndpointsConfig

        endpoints = EndpointsConfig.load(BASE_DIR / "endpoints.yml")
        url = endpoints.tracker_store.url
    except Exception as exc:  # noqa: BLE001
        record("FAIL", "MySQL", f"读取 endpoints.yml 失败: {exc}")
        return

    if not url:
        record("FAIL", "MySQL", "endpoints.yml 里没有 database/tracker_store.url")
        return

    try:
        from ingest import connect_mysql  # type: ignore

        conn = connect_mysql(url)
    except Exception as exc:  # noqa: BLE001
        record("FAIL", "MySQL 连接", f"{type(exc).__name__}: {exc}")
        return

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT DATABASE()")
            db = (cursor.fetchone() or ["?"])[0]
            expected = ["guide_doc", "trackers", "feedback", "cost_log"]
            cursor.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = DATABASE()"
            )
            tables = {row[0] for row in cursor.fetchall()}
            missing = [name for name in expected if name not in tables]
            if missing:
                record("FAIL", "MySQL 表", f"{db} 缺表: {missing}（执行 scripts/init_mysql.sql）")
            else:
                record("PASS", "MySQL 表", f"{db}: {sorted(tables & set(expected))}")

            for table in ("guide_doc", "trackers", "feedback"):
                if table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
                    count = cursor.fetchone()[0]
                    level = "PASS" if count > 0 or table != "guide_doc" else "WARN"
                    record(level, f"MySQL {table}", f"{count} 行" + ("" if count else "（空，需跑 ingest）"))
    finally:
        conn.close()


# =============================================================================
# 4. Milvus
# =============================================================================
def check_milvus() -> None:
    uri = os.getenv("MILVUS_URI", "http://localhost:19530")
    token = os.getenv("MILVUS_TOKEN", "")
    collection = os.getenv("MILVUS_COLLECTION", "game_guide_chunks")
    try:
        from pymilvus import MilvusClient

        client = MilvusClient(uri=uri, token=token or None, timeout=5)
    except Exception as exc:  # noqa: BLE001
        record("FAIL", "Milvus 连接", f"{uri} -> {type(exc).__name__}: {exc}")
        return

    try:
        if not client.has_collection(collection):
            record("FAIL", f"Milvus collection", f"{collection} 不存在（跑 ingest.py）")
            return
        record("PASS", "Milvus collection", collection)

        desc = client.describe_collection(collection)
        dim = None
        for field in desc.get("fields", []):
            if field.get("name") == "embedding":
                dim = (field.get("params") or {}).get("dim")
        expected_dim = int(os.getenv("EMBEDDING_DIM", "1024"))
        if dim and int(dim) != expected_dim:
            record("FAIL", "Milvus 维度", f"collection={dim}, 配置={expected_dim}（必须重建）")
        else:
            record("PASS", "Milvus 维度", str(dim))

        # Zilliz Serverless 的 get_collection_stats 常返回 0，不能作为准确条数；
        # 用 query 的 count(*) 才是真实写入量。
        try:
            result = client.query(
                collection,
                filter='game_id == "phantom_blade_zero"',
                output_fields=["count(*)"],
            )
            rows = 0
            for item in result:
                rows += int(item.get("count(*)", 0))
            record("PASS" if rows > 0 else "WARN", "Milvus 向量条数", f"{rows} 行" + ("" if rows else "（空，跑 ingest.py）"))
        except Exception as exc:  # noqa: BLE001
            record("WARN", "Milvus 向量条数", f"读取失败: {exc}")
    finally:
        try:
            client.close()
        except Exception:  # noqa: BLE001
            pass


# =============================================================================
# 5. Embedding
# =============================================================================
def check_embedding() -> None:
    try:
        from addons.milvus_retrieval import HttpEmbeddingClient
    except Exception as exc:  # noqa: BLE001
        record("FAIL", "Embedding", f"导入失败: {exc}")
        return

    client = HttpEmbeddingClient(
        model=os.getenv("EMBEDDING_MODEL", "text-embedding-v4"),
        api_key=os.getenv("QWEN_API_KEY"),
        api_base=os.getenv("EMBEDDING_API_BASE"),
        dimension=int(os.getenv("EMBEDDING_DIM", "1024")),
    )
    try:
        vectors = client.embed(["白山风雷剑"])
        record("PASS", "Embedding API", f"{len(vectors)} 条，维度 {len(vectors[0])}")
    except Exception as exc:  # noqa: BLE001
        record("FAIL", "Embedding API", f"{type(exc).__name__}: {exc}")


# =============================================================================
# 6. LLM
# =============================================================================
def check_llm() -> None:
    api_key = os.getenv("QWEN_API_KEY", "")
    if not api_key:
        record("FAIL", "LLM API", "缺少 QWEN_API_KEY")
        return
    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
            base_url=os.getenv("LLM_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            timeout=20,
        )
        resp = client.chat.completions.create(
            model=os.getenv("LLM_MODEL", "qwen3.8-flash"),
            messages=[{"role": "user", "content": "只回复两个字：在的"}],
            max_tokens=8,
            temperature=0,
        )
        text = (resp.choices[0].message.content or "").strip()
        record("PASS", "LLM API", f"{os.getenv('LLM_MODEL', 'qwen3.8-flash')} -> {text[:20]}")
    except Exception as exc:  # noqa: BLE001
        record("FAIL", "LLM API", f"{type(exc).__name__}: {exc}")


# =============================================================================
# 7. 领域工程装配
# =============================================================================
def check_project() -> None:
    try:
        from customer_service_system.core.domain import Domain
        from customer_service_system.dialogue_understanding.flow import FlowLoader

        domain = Domain.load(str(BASE_DIR / "domain"))
        flows = FlowLoader().load(BASE_DIR / "data" / "flows")
        record("PASS", "Domain", f"{len(domain.slots)} 个槽位")
        record("PASS", "Flows", ", ".join(f.id for f in flows))
    except Exception as exc:  # noqa: BLE001
        record("FAIL", "Domain/Flows", f"{type(exc).__name__}: {exc}")

    kb = BASE_DIR / "knowledge" / "phantom_blade_zero"
    folders = {"weapons": "weapon", "bosses": "boss", "story": "story", "items": "item", "faq": "faq"}
    counts: Dict[str, int] = {}
    for folder, name in folders.items():
        counts[name] = len(list((kb / folder).glob("*.md"))) if (kb / folder).exists() else 0
    total = sum(counts.values())
    record("PASS" if total > 0 else "FAIL", "知识库", f"{total} 篇 {counts}")
    record("PASS" if (kb / "sources.jsonl").exists() else "FAIL", "来源清单", "sources.jsonl")

    try:
        from addons.milvus_retrieval import MilvusRetriever  # noqa: F401
        from customer_service_system.shared.config import EndpointsConfig

        cfg = EndpointsConfig.load(BASE_DIR / "endpoints.yml")
        path = cfg.vector_store.config.get("collection", "")
        record("PASS", "检索器类", f"MilvusRetriever, collection={path}")
    except Exception as exc:  # noqa: BLE001
        record("FAIL", "检索器类", f"{type(exc).__name__}: {exc}")


# =============================================================================
# 主流程
# =============================================================================
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="不联网/不连库")
    parser.add_argument("--skip-llm", action="store_true", help="跳过 LLM 探活（省钱）")
    parser.add_argument("--skip-embed", action="store_true", help="跳过 embedding 探活")
    parser.add_argument("--json", default="", help="把结果写到 JSON")
    args = parser.parse_args()

    print("=" * 58)
    print("《影之刃零》攻略客服 · 验收前置自检")
    print("=" * 58)

    check_deps()
    check_project()

    if args.offline:
        print("\n（--offline：跳过 .env / MySQL / Milvus / API 检查）")
    else:
        check_env()
        check_mysql()
        check_milvus()
        if not args.skip_embed:
            check_embedding()
        if not args.skip_llm:
            check_llm()

    print("-" * 58)
    print(f"阻塞项 {BLOCKER} 个，警告 {WARN} 个，共 {len(ROWS)} 项检查")

    if BLOCKER:
        print("\n有阻塞项，先按上面的提示处理；处理完重跑本脚本。")
    else:
        print("\n环境就绪，可以进入验收流程。")

    if args.json:
        Path(args.json).write_text(
            json.dumps(
                {
                    "blocker": BLOCKER,
                    "warning": WARN,
                    "checks": [{"level": l, "name": n, "detail": d} for l, n, d in ROWS],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"结果已写入 {args.json}")

    return 0 if BLOCKER == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
