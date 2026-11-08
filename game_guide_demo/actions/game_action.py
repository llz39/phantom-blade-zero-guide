# -*- coding: utf-8 -*-
"""《影之刃零》攻略 Action。

只有一个 Action：``action_guide_lookup``。
Flow 收集到 Boss / 材料 / 任务名之后调用它，走与 EnterpriseSearchPolicy
完全相同的检索 + 生成链路，保证 Flow 与自由问答的回答口径一致。
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from customer_service_system.agent.actions import Action, ActionResult
from customer_service_system.core.domain import Domain
from customer_service_system.core.tracker import DialogueStateTracker

logger = logging.getLogger(__name__)

# 兜底话术：找不到可靠来源时的统一口径
UNKNOWN_TEXT = (
    "这个信息我暂时没有找到可靠来源，不能凭印象给你一个数值。\n"
    "已知的是：知识库里没有这条记录。如果你有游戏内截图，可以发我，我按截图帮你核对。"
)


def _build_retriever() -> Any:
    """按环境变量构建 Milvus 检索器（失败返回 None，不影响对话）。"""
    try:
        from addons.milvus_retrieval import build_retriever_from_env
    except Exception as exc:  # noqa: BLE001
        try:
            from game_guide_demo.addons.milvus_retrieval import build_retriever_from_env
        except Exception:  # noqa: BLE001
            logger.warning("导入 MilvusRetriever 失败: %s", exc)
            return None
    return build_retriever_from_env()


def _build_policy() -> Any:
    """构建一个仅用于 Flow 收尾的 EnterpriseSearchPolicy。"""
    from customer_service_system.policies import (
        EnterpriseSearchPolicy,
        EnterpriseSearchPolicyConfig,
    )
    from customer_service_system.shared.llm import create_llm_client

    config = EnterpriseSearchPolicyConfig(
        llm_type="openai",
        llm_model=os.getenv("LLM_MODEL", "qwen3.8-flash"),
        chitchat_enabled=False,
    )
    config.retrieval.top_k = int(os.getenv("RAG_TOP_K", "5"))
    config.retrieval.similarity_threshold = float(os.getenv("RAG_THRESHOLD", "0.42"))

    llm_client = create_llm_client(
        type="openai",
        model=os.getenv("LLM_MODEL", "qwen3.8-flash"),
        api_key=os.getenv("QWEN_API_KEY", ""),
        api_base=os.getenv("LLM_API_BASE"),
        temperature=0.1,
    )
    return EnterpriseSearchPolicy(
        config=config,
        llm_client=llm_client,
        retriever=_build_retriever(),
    )


class ActionGuideLookup(Action):
    """检索攻略知识库并回答。"""

    _policy: Optional[Any] = None

    @property
    def name(self) -> str:
        return "action_guide_lookup"

    @classmethod
    def _get_policy(cls) -> Any:
        if cls._policy is None:
            cls._policy = _build_policy()
        return cls._policy

    async def run(
        self,
        tracker: DialogueStateTracker,
        domain: Optional[Domain] = None,
        **kwargs: Any,
    ) -> ActionResult:
        result = ActionResult()

        question = kwargs.get("question") or ""
        if not question and tracker.latest_message:
            question = tracker.latest_message.text
        if not question:
            result.add_response(UNKNOWN_TEXT)
            return result

        try:
            policy = self._get_policy()
            answer, sources = await policy.answer(question, tracker)
        except Exception as exc:  # noqa: BLE001 - Action 不允许把异常抛给对话层
            logger.warning("[action_guide_lookup] 检索失败: %s", exc)
            answer, sources = None, []

        if not answer:
            # 无可靠结果：给“暂未收录”，并把可能的线索留给用户判断
            result.add_response(
                UNKNOWN_TEXT,
                custom={"sources": sources, "unknown": True},
            )
            return result

        result.add_response(answer, custom={"sources": sources, "unknown": False})
        return result


__all__ = ["ActionGuideLookup"]
