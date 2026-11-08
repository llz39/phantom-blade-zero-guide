# -*- coding: utf-8 -*-
"""运行期用量统计（token / 调用次数）。

为什么单独一个模块
----------------
LLM 客户端分布在命令生成、RAG 回答、闲聊等多处调用，
如果每处各自打点，很容易漏。这里做成一个进程级累加器：
客户端只负责 `record()`，HTTP 层在每个请求结束时 `drain()` 一次落库。

注意：
- 进程内计数，单 worker 下准确；多 worker 会各算一份（部署文档要求单 worker）。
- 只记录数字，不记录 prompt / 回答内容，避免把用户问题写进日志。
"""

from __future__ import annotations

import threading
from typing import Any, Dict


class UsageRecorder:
    """线程安全的用量累加器。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._calls = 0
        self._prompt_tokens = 0
        self._completion_tokens = 0
        self._by_model: Dict[str, int] = {}

    def record(
        self,
        model: str = "",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        kind: str = "llm",
    ) -> None:
        """记一次调用。usage 缺失时按 0 记，仍然统计调用次数。"""
        with self._lock:
            self._calls += 1
            self._prompt_tokens += max(0, int(prompt_tokens or 0))
            self._completion_tokens += max(0, int(completion_tokens or 0))
            if model:
                self._by_model[model] = self._by_model.get(model, 0) + 1

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "calls": self._calls,
                "prompt_tokens": self._prompt_tokens,
                "completion_tokens": self._completion_tokens,
                "by_model": dict(self._by_model),
            }

    def drain(self) -> Dict[str, Any]:
        """取走累计值并清零（每个请求结束时调用）。"""
        with self._lock:
            data = {
                "calls": self._calls,
                "prompt_tokens": self._prompt_tokens,
                "completion_tokens": self._completion_tokens,
                "by_model": dict(self._by_model),
            }
            self._calls = 0
            self._prompt_tokens = 0
            self._completion_tokens = 0
            self._by_model = {}
            return data


# 进程级单例
USAGE = UsageRecorder()


def estimate_cost_cny(prompt_tokens: int, completion_tokens: int) -> float:
    """按环境变量里的单价折算成本（元/千 token）。

    LLM_PRICE_IN_PER_K / LLM_PRICE_OUT_PER_K 未配置时用保守估价，
    真实账单以云厂商控制台为准；这里只用于成本护栏。
    """
    import os

    price_in = float(os.getenv("LLM_PRICE_IN_PER_K", "0.0008"))
    price_out = float(os.getenv("LLM_PRICE_OUT_PER_K", "0.002"))
    cost = (prompt_tokens / 1000.0) * price_in + (completion_tokens / 1000.0) * price_out
    return round(cost, 6)


__all__ = ["UsageRecorder", "USAGE", "estimate_cost_cny"]
