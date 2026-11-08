# -*- coding: utf-8 -*-
"""ASGI 入口。

本地：
    uvicorn app:app --host 127.0.0.1 --port 8000

容器：
    uvicorn app:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

# 环境必须在 import Agent 之前准备好：
# endpoints.yml 里的 ${VAR} 是在 Agent.load() 时展开的，晚一步就会读到空值。
BASE_DIR = Path(__file__).resolve().parent
from env_bootstrap import load_env  # noqa: E402  (放在 BASE_DIR 之后，便于同目录导入)

ENV_INFO = load_env()
# 启动日志里只打印脱敏摘要，避免 token 进日志
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("app")
logger.info(
    "Milvus 目标: %s (cloud=%s, token=%s)",
    ENV_INFO["milvus_uri"],
    ENV_INFO["milvus_is_cloud"],
    "已设置" if ENV_INFO["milvus_token_set"] else "缺失",
)

from customer_service_system.agent.agent import Agent  # noqa: E402
from customer_service_system.api.server import AgentServer  # noqa: E402

logger.info("加载 Agent: %s", BASE_DIR)
agent = Agent.load(str(BASE_DIR))

cors_origins = [
    item.strip()
    for item in os.getenv("CORS_ORIGINS", "http://localhost:8000").split(",")
    if item.strip()
]

server = AgentServer(
    agent=agent,
    cors_origins=cors_origins,
    enable_inspect=os.getenv("ENABLE_DEBUG_ROUTES", "false").lower() == "true",
)
app = server.app
