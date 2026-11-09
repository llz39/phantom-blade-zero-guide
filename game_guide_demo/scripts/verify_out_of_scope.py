# -*- coding: utf-8 -*-
"""越界回复回归检查（离线，不依赖 MySQL / Milvus / LLM / YAML 库）。

验证：现实话题等范围外问题在检索之前短路，回复只声明产品边界，
不出现「暂未收录 / 无可核验来源 / 截图」、不带来源卡片、不打未知标签。

用法：
    cd game_guide_demo && ..\\.venv\\Scripts\\python.exe scripts\\verify_out_of_scope.py
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock

DEMO = Path(__file__).resolve().parents[1]
REPO = DEMO.parent
sys.path.insert(0, str(REPO))

from customer_service_system.policies.enterprise_search_policy import (  # noqa: E402
    EnterpriseSearchPolicy,
    EnterpriseSearchPolicyConfig,
)

PASS = 0
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS
    if ok:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL.append(f"{name}: {detail}")
        print(f"[FAIL] {name} {detail}")


def utter_text(source: str, key: str) -> str:
    """从 domain_game.yml 纯文本里取话术，避免依赖第三方 YAML 库。"""
    match = re.search(rf"^\s*{key}:\s*\n\s*-\s*text:\s*\"([^\"]+)\"", source, re.M)
    return match.group(1) if match else ""


BOUNDARY_FILE = DEMO / "eval" / "boundary_questions.jsonl"


def load_boundary_cases() -> list[dict]:
    """十道边界题；本脚本只对「前置短路」类做离线断言，其余作为回归清单。"""
    return [
        json.loads(line)
        for line in BOUNDARY_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


BOUNDARY_CASES = load_boundary_cases()
OUT_OF_SCOPE_QUESTIONS = [
    case["question"]
    for case in BOUNDARY_CASES
    if case["expected_branch"] == "out_of_scope_shortcut"
]
IN_SCOPE_QUESTIONS = [
    "白山风雷剑怎么获得",
    "玉璧怎么打",
    "强化武器要什么材料",
    "一共几章",
    "魔渊是谁",
]


def static_checks() -> None:
    # 边界题清单本身
    ids = [case.get("id") for case in BOUNDARY_CASES]
    check("边界题共 10 道且编号唯一", len(BOUNDARY_CASES) == 10 and len(set(ids)) == 10)
    check(
        "每道题字段齐全",
        all(
            all(
                k in case
                for k in ("id", "category", "question", "expected_branch", "expected_behavior", "assertions")
            )
            for case in BOUNDARY_CASES
        ),
    )
    check(
        "覆盖 4 类边界",
        len({case["category"].split("·")[0] for case in BOUNDARY_CASES}) >= 4,
    )
    check(
        "前置短路类题都能被识别",
        len(OUT_OF_SCOPE_QUESTIONS) >= 5
        and all(EnterpriseSearchPolicy._looks_out_of_scope(q) for q in OUT_OF_SCOPE_QUESTIONS),
    )

    domain_src = (DEMO / "domain" / "domain_game.yml").read_text(encoding="utf-8")
    default_text = utter_text(domain_src, "utter_default")
    scope_text = utter_text(domain_src, "utter_out_of_scope")

    check("utter_default 已定义", bool(default_text))
    check("utter_out_of_scope 已定义", bool(scope_text))
    check("utter_out_of_scope 不含「暂未收录」", "暂未收录" not in scope_text)
    check(
        "utter_out_of_scope 不提资料/来源/截图/可核验",
        not any(w in scope_text for w in ("资料", "来源", "截图", "可核验")),
        scope_text[:60],
    )
    check(
        "utter_default 不再把「不在范围」写成资料缺失",
        "不在《影之刃零》攻略范围内" not in default_text and "超出范围" not in default_text,
        default_text[:60],
    )

    server_src = (REPO / "customer_service_system" / "api" / "server.py").read_text(encoding="utf-8")
    check(
        "unknown 判定不再含范围类 marker",
        '"不在《影之刃零》"' not in server_src and '"只回答本作"' not in server_src,
    )

    policy_src = (
        REPO / "customer_service_system" / "policies" / "enterprise_search_policy.py"
    ).read_text(encoding="utf-8")
    frame_src = policy_src.split("async def _handle_search_frame", 1)[1].split(
        "async def _handle_chitchat_frame", 1
    )[0]
    check(
        "越界短路位于检索调用之前",
        0 <= frame_src.find("_looks_out_of_scope") < frame_src.find("await self._search"),
    )
    check(
        "cannot_handle 分支也有前置短路",
        "_looks_out_of_scope(user_message)"
        in policy_src.split("async def _handle_cannot_handle_frame", 1)[1].split(
            "async def _handle_completed_frame", 1
        )[0],
    )

    check(
        "越界问句全部命中",
        all(EnterpriseSearchPolicy._looks_out_of_scope(q) for q in OUT_OF_SCOPE_QUESTIONS),
    )
    check(
        "本作问句不误伤",
        not any(EnterpriseSearchPolicy._looks_out_of_scope(q) for q in IN_SCOPE_QUESTIONS),
    )


def runtime_checks() -> None:
    retriever = MagicMock()
    llm = MagicMock()
    policy = EnterpriseSearchPolicy(
        config=EnterpriseSearchPolicyConfig(), retriever=retriever, llm_client=llm
    )

    async def run_search(question: str) -> None:
        tracker = MagicMock()
        tracker.latest_message.text = question
        pred = await policy._handle_search_frame(tracker, question, None)
        meta = getattr(pred, "metadata", {}) or {}
        text = meta.get("text", "")
        check(f"[search:{question}] 只声明边界", "超出范围" in text and "暂未收录" not in text, text[:60])
        check(
            f"[search:{question}] 无来源/无未知标签",
            not meta.get("sources") and not meta.get("unknown"),
        )
        check(
            f"[search:{question}] 未触发检索与生成",
            not retriever.mock_calls and not llm.mock_calls,
            f"retriever={retriever.mock_calls[:1]} llm={llm.mock_calls[:1]}",
        )
        retriever.reset_mock()
        llm.reset_mock()

    async def run_cannot(question: str) -> None:
        tracker = MagicMock()
        tracker.latest_message.text = question
        pred = await policy._handle_cannot_handle_frame(tracker, MagicMock(reason=""), None)
        meta = getattr(pred, "metadata", {}) or {}
        text = meta.get("text", "")
        check(
            f"[cannot_handle:{question}] 只声明边界",
            "超出范围" in text and "暂未收录" not in text,
            text[:60],
        )
        check(
            f"[cannot_handle:{question}] 未触发检索与生成",
            not retriever.mock_calls and not llm.mock_calls,
        )
        retriever.reset_mock()
        llm.reset_mock()

    async def runner() -> None:
        for question in OUT_OF_SCOPE_QUESTIONS:
            await run_search(question)
        for question in OUT_OF_SCOPE_QUESTIONS[:3]:
            await run_cannot(question)

    asyncio.run(runner())


def main() -> int:
    static_checks()
    runtime_checks()
    print(f"\n=== 越界回归：{PASS} PASS / {len(FAIL)} FAIL ===")
    for item in FAIL:
        print("  -", item)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
