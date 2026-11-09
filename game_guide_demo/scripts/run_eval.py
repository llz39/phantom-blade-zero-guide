# -*- coding: utf-8 -*-
"""120 题评测（限制文档 11）。

指标：
    Recall@5         期望实体出现在 top-5 检索结果里的比例
    引用覆盖率        回答带至少 1 个来源的比例（仅 answer 类题目）
    未知识别率        对抗题被判为“拒答/暂未收录”的比例
    答案准确率        需要人工复核，脚本只导出 answer 供打分（--full）

用法：
    python scripts/run_eval.py --retrieval-only      # 只测召回（需 Milvus + embedding）
    python scripts/run_eval.py --full                # 端到端（需服务或 Agent 可跑）
    python scripts/run_eval.py --dry-run             # 用构造结果验证评分逻辑
    python scripts/run_eval.py --boundary           # 10 道边界题回归（独立题集与报告）
"""

from __future__ import annotations

import argparse
import asyncio
import json
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

QUESTIONS = BASE_DIR / "eval" / "questions.jsonl"
REPORT = BASE_DIR / "eval" / "eval_report.json"

# 拒答/未知的表达（用于自动判定，最终仍需人工抽检）
REFUSAL_MARKERS = (
    "暂未收录",
    "未收录",
    "没有找到可靠来源",
    "未找到可靠来源",
    "无法提供帮助",
    "无法确认",
    "只回答《影之刃零》",
    "只回答影之刃零",
    "不能凭印象",
    "不建议",
)

# 对抗题的正确处理不一定是否认，也可能是“纠正”。
# 例如「攻击力是 1337 对吧」→「不能确认…312~1217」，这属于正确行为，不能算失败。
CORRECTION_MARKERS = (
    "不能确认",
    "不能按",
    "没有可证明",
    "不是",
    "未收录",
    "无法给出",
    "没有可靠",
    "知识库没有",
    # 剧透题的正确处理是「先给无剧透版」，不是拒答
    "无剧透",
    "不剧透",
)


def load_questions() -> List[Dict[str, Any]]:
    with QUESTIONS.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def is_refusal(text: str) -> bool:
    return any(marker in (text or "") for marker in REFUSAL_MARKERS)


def is_refusal_at_head(text: str, head_chars: int = 80) -> bool:
    """只看开头判断是否拒答，理由见调用处注释。

    开头 80 字符约等于「结论」那一句 + 少许关键信息，
    足够覆盖「暂未收录」「结论：知识库中未收录…」「这个信息我暂时没有找到…」这几种写法。
    """
    head = (text or "").strip()[:head_chars]
    return any(marker in head for marker in REFUSAL_MARKERS)


def is_adversarial_safe(text: str) -> bool:
    """对抗题是否被安全处理：拒答 OR 明确纠正。

    注意不能要求“没有来源”：正确回答“不是，应该是舞者丝带”本身会带来源，
    但那已经是安全行为。
    """
    text = text or ""
    if is_refusal(text):
        return True
    return any(marker in text for marker in CORRECTION_MARKERS)


def score(items: List[Dict[str, Any]], rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """根据每题的检索/回答结果计算指标。"""
    hit = 0
    answer_total = 0
    cited = 0
    attack_total = 0
    refused = 0
    details: List[Dict[str, Any]] = []

    for item, row in zip(items, rows):
        expected = set(item.get("expected_entity_ids") or [])
        retrieved = row.get("retrieved_entity_ids") or []
        top5 = retrieved[:5]
        recall_hit = bool(expected & set(top5)) if expected else None

        detail = {
            "id": item["id"],
            "type": item["type"],
            "question": item["question"],
            "recall_hit": recall_hit,
            "retrieved": top5,
            "answer": row.get("answer", ""),
            "sources": len(row.get("sources") or []),
            # 判「拒答」只看开头，不再要求"无来源"。
            #
            # 原因：对抗题常常会检索到东西（比如拿一个真武器名+假数值来问），
            # 系统的正确行为是「有来源但结论是否定/纠正」，这类回答带 sources，
            # 用"无来源"作为必要条件就会把它误判成"没拒答"，指标虚低且掩盖真实表现。
            # RAG 提示词要求"结论→关键信息"的结构，所以开头是否定句就足以判定。
            "refused": is_refusal_at_head(row.get("answer", "")),
            # 对抗题：拒答或纠正都算安全
            "safe": is_adversarial_safe(row.get("answer", "")),
        }

        if expected:
            if recall_hit:
                hit += 1
            answer_total += 1
            if row.get("sources"):
                cited += 1
        else:
            attack_total += 1
            if detail["safe"]:
                refused += 1

        details.append(detail)

    recall = hit / answer_total if answer_total else 0.0
    citation = cited / answer_total if answer_total else 0.0
    unknown = refused / attack_total if attack_total else 0.0

    return {
        "total": len(items),
        "answer_questions": answer_total,
        "adversarial_questions": attack_total,
        "recall_at_5": round(recall, 4),
        "citation_coverage": round(citation, 4),
        "unknown_identification": round(unknown, 4),
        "details": details,
    }


def retrieval_only(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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

    rows: List[Dict[str, Any]] = []
    try:
        for item in items:
            results = asyncio.run(retriever.search(item["question"], top_k=5))
            rows.append(
                {
                    "retrieved_entity_ids": [r.metadata.get("entity_id") for r in results],
                    "answer": "",
                    "sources": [r.metadata.get("source") for r in results],
                }
            )
            time.sleep(0.05)
    finally:
        retriever.close()
    return rows


async def full(items: List[Dict[str, Any]], concurrency: int = 3) -> List[Dict[str, Any]]:
    """端到端跑题。

    串行跑 120 题要 20 分钟以上，这里用信号量控制并发（默认 3）：
    每个题一个独立 sender_id，互不干扰；再高会撞上 DashScope 的限流。
    """
    from datetime import datetime

    from customer_service_system.agent.agent import Agent

    agent = Agent.load(str(BASE_DIR))
    semaphore = asyncio.Semaphore(max(1, concurrency))
    done = {"n": 0}
    total = len(items)

    # 每次运行换一个会话前缀。
    # 复用固定的 sender_id（如 eval:Q059）会把上一次跑评测时残留的 flow / 槽位状态带进来，
    # 造成"上次已修好的问题这次又失败"的假阳性——排查时会白费很多时间。
    run_id = datetime.now().strftime("%m%d%H%M%S")

    async def one(item: Dict[str, Any]) -> Dict[str, Any]:
        async with semaphore:
            response = await agent.handle_message(
                message=item["question"], sender_id=f"eval:{run_id}:{item['id']}"
            )
            texts = [msg.get("text", "") for msg in response.messages if msg.get("text")]
            sources: List[str] = []
            entities: List[str] = []
            for msg in response.messages:
                custom = msg.get("custom") or {}
                for source in custom.get("sources") or []:
                    sources.append(source.get("source") or source.get("title") or "")
                    entity_id = source.get("entity_id")
                    if entity_id and entity_id not in entities:
                        entities.append(entity_id)
            done["n"] += 1
            print(f"[{done['n']}/{total}] {item['id']} {item['question'][:24]}…", flush=True)
            return {
                "retrieved_entity_ids": entities,
                "answer": "\n".join(texts),
                "sources": sources,
            }

    results = await asyncio.gather(*(one(item) for item in items))
    return list(results)


def dry_run(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """用构造结果验证评分逻辑（不依赖 Milvus / LLM）。"""
    rows: List[Dict[str, Any]] = []
    for item in items:
        expected = item.get("expected_entity_ids") or []
        if expected:
            rows.append(
                {
                    "retrieved_entity_ids": expected + ["noise"],
                    "answer": "结论：按知识库回答。",
                    "sources": ["https://example.com"],
                }
            )
        else:
            rows.append(
                {
                    "retrieved_entity_ids": [],
                    "answer": "这个信息我暂时没有找到可靠来源，暂未收录。",
                    "sources": [],
                }
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--retrieval-only", action="store_true")
    group.add_argument("--full", action="store_true")
    group.add_argument("--dry-run", action="store_true")
    group.add_argument(
        "--boundary",
        action="store_true",
        help="跑 10 道边界题回归（独立题集与报告，不覆盖 120 题全量口径）",
    )
    # 冒烟时只跑前 N 题，避免一次烧掉全部预算
    parser.add_argument("--limit", type=int, default=0, help="只跑前 N 题（0 = 全部）")
    # 抽样：按固定步长在 120 题里均匀取，保证覆盖武器/Boss/剧情/对抗
    parser.add_argument("--sample", type=int, default=0, help="均匀抽取 N 题做冒烟")
    # 定向验证用：知识库改动后只跑相关题，比全量 120 题快得多，也便于复现
    parser.add_argument("--ids", default="", help="只跑指定题号，逗号分隔，如 Q001,Q012,Q101")
    parser.add_argument("--concurrency", type=int, default=3, help="端到端并发数（默认 3，别超过 5）")
    args = parser.parse_args()

    if args.boundary:
        # 边界题与 120 题口径完全隔离：独立题集、独立报告、独立判定逻辑。
        sys.path.insert(0, str(BASE_DIR / "scripts"))
        from boundary_eval import run_boundary

        return run_boundary()

    items = load_questions()
    # --ids 优先：精确指定题号时不再做均匀抽样，避免选出别的题
    if args.ids:
        wanted = {part.strip().upper() for part in args.ids.split(",") if part.strip()}
        items = [item for item in items if str(item["id"]).upper() in wanted]
        missing = wanted - {str(item["id"]).upper() for item in items}
        if missing:
            print(f"警告：题集中找不到这些题号：{sorted(missing)}")
    elif args.sample:
        step = max(1, len(items) // args.sample)
        items = items[::step][: args.sample]
    if args.limit:
        items = items[: args.limit]
    if len(items) < 120 and not (args.limit or args.sample or args.ids):
        print(f"警告：评测集只有 {len(items)} 题，少于要求的 120 题")

    if args.full:
        rows = asyncio.run(full(items, concurrency=args.concurrency))
    elif args.retrieval_only:
        rows = retrieval_only(items)
    else:
        rows = dry_run(items)

    result = score(items, rows)
    result["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    result["mode"] = "full" if args.full else ("retrieval-only" if args.retrieval_only else "dry-run")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        f"题目 {result['total']} / 可答 {result['answer_questions']} / 对抗 {result['adversarial_questions']}\n"
        f"Recall@5 {result['recall_at_5']:.2%} · 引用覆盖 {result['citation_coverage']:.2%} · "
        f"未知识别 {result['unknown_identification']:.2%}"
    )
    print(f"报告: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
