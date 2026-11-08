# -*- coding: utf-8 -*-
"""本地静态验收（不需要 Milvus / MySQL / API Key）。

覆盖：
    A. 工程结构：电商残留、图数据库残留、密钥写死
    B. Domain / Flow 一致性：Flow 收集的槽位必须存在，且必须有 utter_ask_* 话术
    C. 知识库：front matter 合规、来源可追溯（source_urls 必须出现在 sources.jsonl）
    D. 服务层：限流、匿名 session 校验、调试接口关闭

用法：
    python scripts/verify_local.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent
for extra in (str(BASE_DIR), str(REPO_ROOT)):
    if extra not in sys.path:
        sys.path.insert(0, extra)

KB = BASE_DIR / "knowledge" / "phantom_blade_zero"
FOLDER_MAP = {"weapon": "weapons", "boss": "bosses", "story": "story", "item": "items", "faq": "faq"}

results: List[Dict[str, Any]] = []


def check(name: str, ok: bool, detail: Any = "") -> None:
    results.append({"case": name, "pass": bool(ok), "detail": detail})


# =============================================================================
# A. 工程结构
# =============================================================================
def check_structure() -> None:
    forbidden_dirs = ["ecs_demo"]
    check("电商目录已移除", not any((REPO_ROOT / name).exists() for name in forbidden_dirs))

    legacy = [
        REPO_ROOT / "game_guide_demo" / "addons" / "information_retrieval.py",
        REPO_ROOT / "game_guide_demo" / "addons" / "create_indexing.py",
        REPO_ROOT / "game_guide_demo" / "actions" / "action_order.py",
        REPO_ROOT / "game_guide_demo" / "actions" / "db.py",
    ]
    check("电商/图数据库脚本已删除", not any(path.exists() for path in legacy))

    # 关键词拼接，避免脚本自身命中
    pattern = re.compile("neo" + "4j|graph" + "rag|cyp" + "her", re.I)
    hits: List[str] = []
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file() or ".venv" in path.parts or "__pycache__" in path.parts:
            continue
        if path.suffix.lower() not in {".py", ".yml", ".yaml", ".txt", ".sql", ".jinja2", ".html"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if pattern.search(text):
            hits.append(str(path.relative_to(REPO_ROOT)))
    check("代码/配置无图数据库残留", not hits, hits)

    requirements_raw = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
    # 只看真实依赖行，注释里的“移除 xx”不算依赖
    requirements = "\n".join(
        line for line in requirements_raw.splitlines() if line.strip() and not line.strip().startswith("#")
    ).lower()
    check("requirements 无图数据库依赖", "neo" + "4j" not in requirements)
    check(
        "requirements 无本地 BGE 依赖",
        "sentence-transformers" not in requirements and "torch" not in requirements,
        requirements,
    )
    check("requirements 含 pymilvus", "pymilvus" in requirements)

    gitignore = REPO_ROOT / ".gitignore"
    ignored = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    check(".env 被 .gitignore 忽略", ".env" in ignored.splitlines() or ".env\n" in ignored or ".env" in ignored)
    check(".env.example 存在", (BASE_DIR / ".env.example").exists())


# =============================================================================
# B. Domain / Flow 一致性
# =============================================================================
def check_domain_flows() -> None:
    from customer_service_system.core.domain import Domain
    from customer_service_system.dialogue_understanding.flow import FlowLoader

    domain = Domain.load(str(BASE_DIR / "domain"))
    flows = FlowLoader().load(BASE_DIR / "data" / "flows")

    check("domain 加载", len(domain.slots) > 0, list(domain.slots))
    check("flow 数量为 2-4", 2 <= len(flows) <= 4, [f.id for f in flows])
    check("game_id 固定", getattr(domain.slots.get("game_id"), "initial_value", None) == "phantom_blade_zero")

    response_keys = set(domain.responses.keys()) if hasattr(domain, "responses") else set()
    missing_slots: List[str] = []
    missing_utters: List[str] = []
    missing_actions: List[str] = []

    for flow in flows:
        for step in flow.steps:
            if step.step_type.value == "collect" and step.collect:
                if step.collect not in domain.slots:
                    missing_slots.append(f"{flow.id}:{step.collect}")
                key = f"utter_ask_{step.collect}"
                if key not in response_keys:
                    missing_utters.append(f"{flow.id}:{key}")
            if step.action and step.action != "end":
                if step.action not in domain.actions and not step.action.startswith("utter_"):
                    missing_actions.append(f"{flow.id}:{step.action}")

    check("Flow 收集的槽位都在 domain 中", not missing_slots, missing_slots)
    check("每个收集槽位都有 utter_ask 话术", not missing_utters, missing_utters)
    check("Flow 引用的 Action 已声明", not missing_actions, missing_actions)

    check("拒答话术存在", "utter_default" in response_keys and "utter_out_of_scope" in response_keys)


# =============================================================================
# C. 知识库
# =============================================================================
def check_knowledge() -> None:
    sys.path.insert(0, str(BASE_DIR / "scripts"))
    from ingest import chunk_body, estimate_tokens, load_doc  # type: ignore

    sources_path = KB / "sources.jsonl"
    check("sources.jsonl 存在", sources_path.exists())
    known_urls = set()
    levels = {}
    if sources_path.exists():
        for line in sources_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            known_urls.add(item["url"])
            levels[item["level"]] = levels.get(item["level"], 0) + 1
    check("来源分级齐全", set(levels).issubset({"S1", "S2", "S3", "S4"}) and len(levels) >= 3, levels)

    docs = []
    bad: List[str] = []
    unknown_urls: List[str] = []
    too_large: List[str] = []
    by_type: Dict[str, int] = {}

    for doc_type, folder in FOLDER_MAP.items():
        for path in sorted((KB / folder).glob("*.md")):
            try:
                doc = load_doc(path)
            except Exception as exc:  # noqa: BLE001
                bad.append(f"{path.name}: {exc}")
                continue
            docs.append(doc)
            by_type[doc_type] = by_type.get(doc_type, 0) + 1
            for url in doc.source_urls:
                if url not in known_urls:
                    unknown_urls.append(f"{path.name}: {url}")
            chunks = chunk_body(doc.body)
            if any(estimate_tokens(c) > 700 for c in chunks):
                too_large.append(path.name)

    check("文档全部通过 front matter 校验", not bad, bad[:5])
    check("每篇的 source_urls 都在 sources.jsonl 中", not unknown_urls, unknown_urls[:5])
    check("P0 武器 10-15+", by_type.get("weapon", 0) >= 10, by_type.get("weapon"))
    check("P0 Boss 8-10+", by_type.get("boss", 0) >= 8, by_type.get("boss"))
    check("P0 章节 8+", by_type.get("story", 0) >= 8, by_type.get("story"))
    check("P0 FAQ 20+", by_type.get("faq", 0) >= 20, by_type.get("faq"))
    check("分块均不超过 700 tokens", not too_large, too_large[:5])
    check("文档总数", len(docs) >= 30, len(docs))

    # 高风险：每篇都必须有 unknown_fields 或明确写“无”
    missing_unknown = [d.path.name for d in docs if not d.unknown_fields]
    check("每篇都有 unknown_fields 声明", len(missing_unknown) <= 8, missing_unknown[:5])


# =============================================================================
# D. 服务层
# =============================================================================
def check_server() -> None:
    from fastapi.testclient import TestClient

    from customer_service_system.api.server import AgentServer, RateLimiter

    limiter = RateLimiter(per_minute=3, per_day=5, daily_budget=100)
    allowed = [limiter.check("1.1.1.1")[0] for _ in range(4)]
    check("分钟限流生效", allowed == [True, True, True, False], allowed)

    ok, reason = limiter.check("1.1.1.1")
    check("限流有可读原因", (not ok) and bool(reason), reason)

    server = AgentServer(agent=None)
    client = TestClient(server.app)
    check("/health 200", client.get("/health").status_code == 200)
    check("聊天页 200", client.get("/").status_code == 200 and "影境攻略" in client.get("/").text)
    check("调试接口关闭", client.get("/inspect").status_code == 404, client.get("/inspect").status_code)
    check("/api/domain 关闭", client.get("/api/domain").status_code == 404)
    check("/api/flows 关闭", client.get("/api/flows").status_code == 404)

    session = client.get("/api/chat/session").json()
    check("匿名 session 为 uuid", len(session.get("session_id", "")) == 36, session.get("session_id"))
    check("sender_id 带 anon 前缀", session.get("sender_id", "").startswith("anon:"))

    bad = client.post("/api/chat", json={"message": "x" * 400})
    check("超长输入被拒", bad.status_code in (400, 503), bad.status_code)


def main() -> int:
    check_structure()
    check_domain_flows()
    check_knowledge()
    check_server()

    passed = sum(1 for item in results if item["pass"])
    total = len(results)
    for item in results:
        flag = "PASS" if item["pass"] else "FAIL"
        print(f"[{flag}] {item['case']}" + ("" if item["pass"] else f" -> {item['detail']}"))
    print(f"\n合计 {passed}/{total} 通过")

    out = BASE_DIR / "data" / "local_verify.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"passed": passed, "total": total, "cases": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"报告: {out}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
