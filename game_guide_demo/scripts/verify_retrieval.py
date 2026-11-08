# -*- coding: utf-8 -*-
"""Milvus 检索验收脚本（M4 证据）。

分两段执行：
1. 离线自测：过滤表达式、槽位取值、异常兜底、结果映射（不需要 Milvus 与 API Key）；
2. 在线检索：连上 Milvus 后跑 20 条查询，输出命中实体与耗时（用于 p95 判断）。

用法：
    python scripts/verify_retrieval.py --offline
    python scripts/verify_retrieval.py --online --out data/retrieval_report.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent
for extra in (str(BASE_DIR), str(REPO_ROOT)):
    if extra not in sys.path:
        sys.path.insert(0, extra)

from env_bootstrap import load_env  # noqa: E402

load_env()

# 20 条真实问题，覆盖武器 / Boss / 材料 / 剧情 / FAQ / 越界
QUERIES = [
    "白山风雷剑怎么获得",
    "白山风雷剑的升级材料是什么",
    "灵蛇软剑在哪拿",
    "天玄青铜剑是谁掉的",
    "残钢刃有什么用",
    "破军怎么得",
    "白影的解锁条件",
    "别离残钩在哪",
    "玉璧怎么打",
    "沐小葵掉什么",
    "斩骑在哪",
    "勾魂在哪打",
    "强化武器需要什么材料",
    "什么时候能强化武器",
    "升级材料能退吗",
    "一共几章",
    "一共有多少把武器",
    "魔渊是谁",
    "主角是谁",
    "游戏多少钱",
]


def _load_retriever():
    from customer_service_system.shared.config import EndpointsConfig

    from addons.milvus_retrieval import MilvusRetriever

    endpoints = EndpointsConfig.load(BASE_DIR / "endpoints.yml")
    cfg = endpoints.vector_store.to_connect_config()
    embeddings = endpoints.get_embeddings_config("default")
    if embeddings:
        cfg["embedding"] = {
            "model": embeddings.model,
            "api_key": embeddings.api_key,
            "api_base": embeddings.api_base,
            "dimension": embeddings.dimensions,
        }
    retriever = MilvusRetriever()
    retriever.connect(cfg)
    return retriever


# =============================================================================
# 离线自测
# =============================================================================
def offline_tests() -> Dict[str, Any]:
    from addons.milvus_retrieval import MilvusRetriever, _slot_values

    results: List[Dict[str, Any]] = []
    retriever = MilvusRetriever()
    retriever.game_id = "phantom_blade_zero"

    # 1) 槽位取值：{name,type,value} 必须取 value
    tracker_state = {
        "slots": {
            "boss_name": {"name": "boss_name", "type": "text", "value": "玉璧"},
            "doc_type": {"name": "doc_type", "type": "text", "value": "boss"},
            "version": {"name": "version", "type": "text", "value": ""},
        }
    }
    slots = _slot_values(tracker_state)
    ok = slots.get("boss_name") == "玉璧" and slots.get("doc_type") == "boss"
    results.append({"case": "槽位取值取 value", "pass": ok, "detail": slots})

    # 2) 过滤表达式：game_id + doc_type + 实体提示
    expr, hint = retriever._build_expr(tracker_state)  # noqa: SLF001
    ok = (
        'game_id == "phantom_blade_zero"' in expr
        and 'doc_type == "boss"' in expr
        and hint == "玉璧"
    )
    results.append({"case": "过滤表达式", "pass": ok, "detail": {"expr": expr, "hint": hint}})

    # 3) 只按 game_id 过滤（无槽位）
    expr, hint = retriever._build_expr(None)  # noqa: SLF001
    ok = expr == 'game_id == "phantom_blade_zero"' and hint == ""
    results.append({"case": "无槽位时只过滤 game_id", "pass": ok, "detail": expr})

    # 4) 表达式注入转义
    expr, _ = retriever._build_expr({"slots": {"entity_id": {"value": 'x" or "1'}}})  # noqa: SLF001
    ok = '\\"' in expr
    results.append({"case": "表达式转义", "pass": ok, "detail": expr})

    # 5) 无客户端时 search 返回空列表，不抛异常
    try:
        out = asyncio.run(retriever.search("白山风雷剑", top_k=5))
        results.append({"case": "未连接时返回空列表", "pass": out == [], "detail": len(out)})
    except Exception as exc:  # noqa: BLE001
        results.append({"case": "未连接时返回空列表", "pass": False, "detail": str(exc)})

    # 6) 结果映射：fake client + fake embedding
    class FakeEmbedding:
        def embed(self, texts):
            return [[0.1] * 8 for _ in texts]

    class FakeClient:
        def search(self, **kwargs):
            return [[
                {
                    "id": "doc#0", "distance": 0.81,
                    "entity": {
                        "doc_id": "phantom_blade_zero:weapon:weapon_bai_shan_feng_lei_jian:1.0302256",
                        "game_id": "phantom_blade_zero", "doc_type": "weapon",
                        "entity_id": "weapon_bai_shan_feng_lei_jian", "title": "白山风雷剑",
                        "content": "击败廿一号剑偶玉璧获得。", "source": "https://example.com/a",
                        "source_level": "S3", "version": "1.0302256",
                        "chunk_index": 0, "updated_at": "2026-11-08",
                    },
                },
                {
                    "id": "doc#1", "distance": 0.77,
                    "entity": {
                        "doc_id": "phantom_blade_zero:weapon:weapon_bai_shan_feng_lei_jian:1.0302256",
                        "game_id": "phantom_blade_zero", "doc_type": "weapon",
                        "entity_id": "weapon_bai_shan_feng_lei_jian", "title": "白山风雷剑",
                        "content": "第二块内容。", "source": "https://example.com/a",
                        "source_level": "S3", "version": "1.0302256",
                        "chunk_index": 1, "updated_at": "2026-11-08",
                    },
                },
                {
                    "id": "doc#2", "distance": 0.76,
                    "entity": {
                        "doc_id": "phantom_blade_zero:weapon:weapon_bai_shan_feng_lei_jian:1.0302256",
                        "game_id": "phantom_blade_zero", "doc_type": "weapon",
                        "entity_id": "weapon_bai_shan_feng_lei_jian", "title": "白山风雷剑",
                        "content": "第三块内容。", "source": "https://example.com/a",
                        "source_level": "S3", "version": "1.0302256",
                        "chunk_index": 2, "updated_at": "2026-11-08",
                    },
                },
            ]]

    retriever._client = FakeClient()  # noqa: SLF001
    retriever.embedding_client = FakeEmbedding()  # type: ignore[assignment]
    out = asyncio.run(
        retriever.search("白山风雷剑", top_k=5, tracker_state={"slots": {"weapon_name": {"value": "白山风雷剑"}}})
    )
    ok = (
        len(out) >= 1
        and out[0].metadata["title"] == "白山风雷剑"
        and out[0].metadata["source_level"] == "S3"
        and 0.0 <= (out[0].score or 0) <= 1.0
    )
    results.append({"case": "结果映射与实体加权", "pass": ok, "detail": [r.metadata["title"] for r in out]})

    ok = len(out) <= 2  # 同文档最多 2 个 chunk
    results.append({"case": "同文档最多 2 个 chunk", "pass": ok, "detail": len(out)})

    # 7) 客户端抛错时返回空列表
    class BrokenClient:
        def search(self, **kwargs):
            raise RuntimeError("milvus down")

    retriever._client = BrokenClient()  # noqa: SLF001
    out = asyncio.run(retriever.search("白山风雷剑", top_k=5))
    results.append({"case": "Milvus 异常不冒泡", "pass": out == [], "detail": len(out)})

    passed = sum(1 for item in results if item["pass"])
    return {"total": len(results), "passed": passed, "failed": len(results) - passed, "cases": results}


# =============================================================================
# 在线检索
# =============================================================================
async def online_tests(retriever, top_k: int = 5) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    latencies: List[float] = []

    # 先打一次“冷启动”：首次调用会把 embedding 客户端、gRPC 连接、collection 加载
    # 全部建立起来，把这 1-2 秒算进 p95 会失真。冷启动单独记录，指标只统计热态。
    cold_started = time.perf_counter()
    await retriever.search("预热查询", top_k=1)
    cold_ms = (time.perf_counter() - cold_started) * 1000

    for query in QUERIES:
        started = time.perf_counter()
        results = await retriever.search(query, top_k=top_k)
        elapsed = (time.perf_counter() - started) * 1000
        latencies.append(elapsed)
        rows.append(
            {
                "query": query,
                "hits": len(results),
                "elapsed_ms": round(elapsed, 1),
                "top": [
                    {
                        "title": r.metadata.get("title"),
                        "entity_id": r.metadata.get("entity_id"),
                        "doc_type": r.metadata.get("doc_type"),
                        "score": round(float(r.score or 0), 4),
                        "source": r.metadata.get("source"),
                    }
                    for r in results[:3]
                ],
            }
        )

    latencies.sort()
    p95 = latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))]
    misses = [row["query"] for row in rows if row["hits"] == 0]
    return {
        "queries": len(rows),
        "empty_results": len(misses),
        "empty_queries": misses,
        "cold_start_ms": round(cold_ms, 1),
        "avg_ms": round(statistics.mean(latencies), 1),
        "p95_ms": round(p95, 1),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="只跑离线自测")
    parser.add_argument("--online", action="store_true", help="跑真实检索（需要 Milvus + API Key）")
    parser.add_argument("--out", default="", help="报告路径；默认按模式区分，避免互相覆盖")
    args = parser.parse_args()

    if not args.out:
        suffix = "online" if args.online else "offline"
        args.out = str(BASE_DIR / "data" / f"retrieval_report_{suffix}.json")

    report: Dict[str, Any] = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}

    if args.offline or not args.online:
        report["offline"] = offline_tests()
        print(json.dumps(report["offline"], ensure_ascii=False, indent=2))

    if args.online:
        retriever = _load_retriever()
        report["online"] = asyncio.run(online_tests(retriever))
        retriever.close()
        print(json.dumps({k: v for k, v in report["online"].items() if k != "rows"}, ensure_ascii=False, indent=2))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告: {out_path}")

    # 离线用例有失败时返回非 0，方便上游脚本汇总
    offline_failed = report.get("offline", {}).get("failed", 0)
    return 0 if offline_failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
