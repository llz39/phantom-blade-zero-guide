# -*- coding: utf-8 -*-
"""
FastAPI 应用服务器（《影之刃零》攻略客服）

在保留原框架接口的前提下新增：

1. ``GET /``                 匿名聊天页（chat.html）
2. ``GET /api/chat/session`` 创建/读取匿名会话
3. ``POST /api/chat``        匿名问答（JSON），返回文本 + 来源卡片
4. ``POST /api/feedback``    回答反馈（写入 MySQL feedback 表）
5. ``GET /health``           健康检查

安全约束（限制文档 11.2 / 0.2）：
- 限流 10 次/分钟/IP，100 次/天/IP；
- 输入长度上限、每日请求预算；
- CORS 白名单；
- ``/inspect``、``/api/domain``、``/api/flows``、``/api/tracker`` 默认关闭；
- 不建用户表、不做登录。
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, TYPE_CHECKING

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from customer_service_system.shared.constants import (
    DEFAULT_SERVER_HOST,
    DEFAULT_SERVER_PORT,
)

if TYPE_CHECKING:
    from customer_service_system.agent.agent import Agent

logger = logging.getLogger(__name__)

SESSION_COOKIE = "pbz_session"
SESSION_PREFIX = "anon:"
SESSION_MAX_AGE = 7 * 24 * 3600


# =============================================================================
# 请求/响应模型
# =============================================================================
class ChatRequest(BaseModel):
    """匿名聊天请求。"""

    message: str = Field(..., description="用户问题")
    session_id: Optional[str] = Field(default=None, description="匿名会话 ID")


class SourceCard(BaseModel):
    """来源卡片。"""

    title: str = ""
    source: str = ""
    source_level: str = ""
    entity_id: str = ""
    doc_type: str = ""
    version: str = ""
    updated_at: str = ""


class ChatResponse(BaseModel):
    """匿名聊天响应。"""

    session_id: str
    text: str
    sources: List[SourceCard] = Field(default_factory=list)
    unknown: bool = False
    elapsed_ms: int = 0


class FeedbackRequest(BaseModel):
    """反馈请求。"""

    session_id: str
    message_id: Optional[str] = None
    rating: int = Field(..., ge=-1, le=1, description="1 有用 / -1 无用")
    comment: Optional[str] = Field(default=None, max_length=512)


class HealthResponse(BaseModel):
    """健康检查响应。"""

    status: str
    version: str
    agent_ready: bool
    retriever_ready: bool = False


# =============================================================================
# 限流
# =============================================================================
class RateLimiter:
    """进程内滑动窗口限流。

    单实例够用；多实例部署应换 Redis，本 Demo 保持零外部依赖。
    """

    def __init__(self, per_minute: int = 10, per_day: int = 100, daily_budget: int = 300) -> None:
        self.per_minute = max(1, per_minute)
        self.per_day = max(1, per_day)
        self.daily_budget = max(1, daily_budget)
        self._minute_hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._day_hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._day_key = self._today()
        self._day_total = 0

    @staticmethod
    def _today() -> str:
        return time.strftime("%Y-%m-%d")

    def _rollover(self) -> None:
        today = self._today()
        if today != self._day_key:
            self._day_key = today
            self._day_hits.clear()
            self._day_total = 0

    def check(self, identity: str) -> tuple[bool, str]:
        """返回 (是否放行, 拒绝原因)。"""
        self._rollover()
        now = time.time()

        minute = self._minute_hits[identity]
        while minute and now - minute[0] > 60:
            minute.popleft()
        if len(minute) >= self.per_minute:
            return False, "请求过于频繁，请稍后再试（每分钟 10 次）"

        day = self._day_hits[identity]
        while day and now - day[0] > 86400:
            day.popleft()
        if len(day) >= self.per_day:
            return False, "今日提问次数已达上限（每天 100 次）"

        if self._day_total >= self.daily_budget:
            return False, "今日服务配额已用完，明天再来"

        minute.append(now)
        day.append(now)
        self._day_total += 1
        return True, ""


# =============================================================================
# 反馈落库（MySQL）
# =============================================================================
def _db_connection():
    """统一的 MySQL 连接构造（feedback / cost_log 共用）。

    优先 DATABASE_URL；没有就用 MYSQL_* 拼，和 endpoints.yml 保持一致。
    """
    from urllib.parse import urlparse

    import pymysql

    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url:
        user = os.getenv("MYSQL_USER", "root")
        password = os.getenv("MYSQL_PASSWORD", "")
        host = os.getenv("MYSQL_HOST", "127.0.0.1")
        port = os.getenv("MYSQL_PORT", "3306")
        database = os.getenv("MYSQL_DB", "game_guide")
        db_url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"

    parsed = urlparse(db_url.replace("mysql+pymysql://", "mysql://"))
    return pymysql.connect(
        host=parsed.hostname or "127.0.0.1",
        port=parsed.port or 3306,
        user=parsed.username or "root",
        password=parsed.password or "",
        database=(parsed.path or "/game_guide").lstrip("/"),
        charset="utf8mb4",
        connect_timeout=5,
    )


def _write_cost_log(session_id: str, usage: Dict[str, Any], elapsed_ms: int) -> None:
    """把一次请求的 token 用量写进 cost_log，用于成本护栏与逐日报表。"""
    try:
        from customer_service_system.shared.metrics import estimate_cost_cny

        prompt_tokens = int(usage.get("prompt_tokens", 0))
        completion_tokens = int(usage.get("completion_tokens", 0))
        cost = estimate_cost_cny(prompt_tokens, completion_tokens)

        conn = _db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO cost_log (day, session_id, kind, input_tokens, output_tokens, cost_cny)"
                    " VALUES (CURDATE(), %s, %s, %s, %s, %s)",
                    (session_id, "chat", prompt_tokens, completion_tokens, cost),
                )
            conn.commit()
        finally:
            conn.close()
        logger.info(
            "[cost] session=%s in=%s out=%s cost=%.6f elapsed=%sms",
            session_id, prompt_tokens, completion_tokens, cost, elapsed_ms,
        )
    except Exception as exc:  # noqa: BLE001 - 记账失败不能影响回答
        logger.warning("[cost] 写入失败: %s", exc)


def _save_feedback(payload: FeedbackRequest) -> bool:
    """把反馈写入 MySQL feedback 表；失败只记日志，不影响用户体验。

    连接参数优先读 DATABASE_URL，没有则用 MYSQL_* 拼（与 endpoints.yml 同一套变量）。
    """
    try:
        conn = _db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO feedback (session_id, message_id, rating, comment, created_at)"
                    " VALUES (%s, %s, %s, %s, NOW())",
                    (payload.session_id, payload.message_id, payload.rating, payload.comment),
                )
            conn.commit()
            return True
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[feedback] 写入失败: %s", exc)
        return False


# =============================================================================
# 服务器
# =============================================================================
class AgentServer:
    """FastAPI 应用服务器。"""

    def __init__(
        self,
        agent: Optional["Agent"] = None,
        cors_origins: Optional[List[str]] = None,
        enable_inspect: bool = False,
    ):
        self.agent = agent
        self.cors_origins = cors_origins or ["http://localhost:8000"]
        # 调试接口默认关闭（限制文档 0.2）
        self.enable_inspect = enable_inspect
        self.max_input_chars = int(os.getenv("MAX_INPUT_CHARS", "300"))

        self.limiter = RateLimiter(
            per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "10")),
            per_day=int(os.getenv("RATE_LIMIT_PER_DAY", "100")),
            daily_budget=int(os.getenv("DAILY_REQUEST_LIMIT", "300")),
        )

        self.app = self._create_app()

    # ------------------------------------------------------------------ 构建
    def _create_app(self) -> FastAPI:
        app = FastAPI(
            title="影之刃零 · 影境攻略",
            description="《影之刃零》单游戏攻略问答 Demo（不登录，匿名会话）",
            version="1.0.0",
            docs_url="/docs" if self.enable_inspect else None,
            redoc_url=None,
            openapi_url="/openapi.json" if self.enable_inspect else None,
        )

        app.add_middleware(
            CORSMiddleware,
            allow_origins=self.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "X-Session-Id"],
        )

        self._register_routes(app)
        return app

    # ------------------------------------------------------------------ 工具
    @staticmethod
    def _client_ip(request: Request) -> str:
        """取客户端 IP 用于限流。

        只有显式配置 TRUST_PROXY_HEADERS=true（部署在 Render/Nginx 等反代后面）时才信
        X-Forwarded-For；否则任何人都能伪造该头，等于把限流关掉。
        """
        if os.getenv("TRUST_PROXY_HEADERS", "false").lower() == "true":
            forwarded = request.headers.get("x-forwarded-for", "")
            if forwarded:
                return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    @staticmethod
    def _resolve_session(request: Request, explicit: Optional[str] = None) -> tuple[str, bool]:
        """解析匿名会话 ID，返回 (session_id, 是否新建)。"""
        candidate = (
            explicit
            or request.headers.get("x-session-id")
            or request.cookies.get(SESSION_COOKIE)
        )
        if candidate:
            candidate = candidate.strip()
            # 只接受 uuid 形态，避免把任意字符串写进 trackers 主键
            try:
                return str(uuid.UUID(candidate)), False
            except (ValueError, AttributeError, TypeError):
                pass
        return str(uuid.uuid4()), True

    @staticmethod
    def _sender_id(session_id: str) -> str:
        return f"{SESSION_PREFIX}{session_id}"

    def _load_page(self, filename: str) -> str:
        template_path = Path(__file__).parent / "templates" / filename
        with open(template_path, "r", encoding="utf-8") as handle:
            return handle.read()

    # ------------------------------------------------------------------ 路由
    def _register_routes(self, app: FastAPI) -> None:

        @app.get("/ready")
        async def readiness():
            """就绪检查：依赖真的能连上才算 ready。

            和 /health 的区别：/health 只证明进程活着（给平台探活用，必须便宜）；
            /ready 会真的 ping MySQL 与 Milvus（给监控用，失败返回 503）。
            """
            checks: Dict[str, bool] = {"agent": self.agent is not None}

            try:
                conn = _db_connection()
                try:
                    conn.ping(reconnect=False)
                    checks["mysql"] = True
                finally:
                    conn.close()
            except Exception:  # noqa: BLE001
                checks["mysql"] = False

            milvus_ok = False
            if self.agent:
                for policy in getattr(self.agent.policy_ensemble, "policies", []):
                    retriever = getattr(policy, "_retriever", None)
                    if retriever is not None and hasattr(retriever, "ping"):
                        try:
                            milvus_ok = bool(retriever.ping())
                        except Exception:  # noqa: BLE001
                            milvus_ok = False
                        break
            checks["milvus"] = milvus_ok

            ready = all(checks.values())
            return JSONResponse(status_code=200 if ready else 503, content={"ready": ready, **checks})

        @app.get("/health", response_model=HealthResponse)
        async def health_check():
            """健康检查。"""
            from customer_service_system import __version__

            return {
                "status": "ok",
                "version": __version__,
                "agent_ready": self.agent is not None,
                "retriever_ready": bool(getattr(self.agent, "retriever_ready", False)),
            }

        @app.get("/", response_class=HTMLResponse)
        async def chat_page(request: Request):
            """匿名聊天页。"""
            session_id, _ = self._resolve_session(request)
            response = HTMLResponse(content=self._load_page("chat.html"))
            response.set_cookie(
                SESSION_COOKIE,
                session_id,
                max_age=SESSION_MAX_AGE,
                httponly=True,
                samesite="lax",
                secure=request.url.scheme == "https",
            )
            return response

        @app.get("/api/chat/session")
        async def create_session(request: Request):
            """创建或读取匿名会话 ID（前端首次进入调用）。"""
            session_id, created = self._resolve_session(request)
            response = JSONResponse(
                {
                    "session_id": session_id,
                    "created": created,
                    "sender_id": self._sender_id(session_id),
                }
            )
            response.set_cookie(
                SESSION_COOKIE,
                session_id,
                max_age=SESSION_MAX_AGE,
                httponly=True,
                samesite="lax",
                secure=request.url.scheme == "https",
            )
            return response

        @app.post("/api/chat", response_model=ChatResponse)
        async def chat(payload: ChatRequest, request: Request):
            """匿名问答。"""
            if not self.agent:
                raise HTTPException(status_code=503, detail="服务尚未就绪")

            ip = self._client_ip(request)
            allowed, reason = self.limiter.check(ip)
            if not allowed:
                raise HTTPException(status_code=429, detail=reason)

            message = (payload.message or "").strip()
            if not message:
                raise HTTPException(status_code=400, detail="问题不能为空")
            if len(message) > self.max_input_chars:
                raise HTTPException(
                    status_code=400,
                    detail=f"问题过长，请控制在 {self.max_input_chars} 字以内",
                )

            session_id, _ = self._resolve_session(request, payload.session_id)
            started = time.perf_counter()

            # 清掉可能的残留计数，保证本次成本只算这次请求
            from customer_service_system.shared.metrics import USAGE

            USAGE.drain()

            # 一次请求的完整链路：
            #   匿名 session → Agent.handle_message
            #   → LangGraph：understand(LLM 出命令) → policy(是否检索/走 Flow)
            #     → action(执行) → guard → response
            #   → 策略内 Milvus 检索 → LLM 按规则生成 → 带回 sources
            # 这里只做协议转换与脱敏，不参与业务判断。
            try:
                result = await self.agent.handle_message(
                    message=message,
                    sender_id=self._sender_id(session_id),
                    metadata={"session_id": session_id, "channel": "web"},
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("[chat] 处理失败: %s", exc, exc_info=True)
                raise HTTPException(status_code=500, detail="服务处理异常，请稍后再试") from exc

            texts: List[str] = []
            sources: List[Dict[str, Any]] = []
            unknown = False
            # 一个回合可能产生多条消息（例如 Flow 先追问再回答），
            # 这里按顺序拼接文本，并把各自的来源去重合并。
            for item in result.messages:
                text = (item.get("text") or "").strip()
                if text:
                    texts.append(text)
                custom = item.get("custom") or {}
                for source in custom.get("sources") or []:
                    if source not in sources:
                        sources.append(source)
                if custom.get("unknown"):
                    unknown = True

            answer = "\n\n".join(texts)
            if not answer:
                answer = "暂未收录：这个问题没有检索到可核验的资料。"
                unknown = True
            # 只有「没有来源 + 拒答话术」才算整体未知。
            # 有来源但答案里包含“某项暂未收录”属于部分未知，不应打上整体未知标签。
            if not sources and any(
                marker in answer
                for marker in ("暂未收录", "没有找到可靠来源", "不在《影之刃零》", "只回答本作")
            ):
                unknown = True

            elapsed_ms = int((time.perf_counter() - started) * 1000)
            usage = USAGE.drain()
            body = ChatResponse(
                session_id=session_id,
                text=answer,
                sources=sources[:6],
                unknown=unknown,
                elapsed_ms=elapsed_ms,
            )
            # 记账放到响应之后做（BackgroundTask）：
            # 写库慢时不能拖慢回答，写失败也不影响用户体验。
            response = JSONResponse(
                body.model_dump(),
                background=BackgroundTask(_write_cost_log, session_id, usage, elapsed_ms),
            )
            response.set_cookie(
                SESSION_COOKIE,
                session_id,
                max_age=SESSION_MAX_AGE,
                httponly=True,
                samesite="lax",
                secure=request.url.scheme == "https",
            )
            logger.info(
                "[chat] ip=%s session=%s len=%s elapsed=%sms sources=%s",
                ip, session_id, len(message), elapsed_ms, len(sources),
            )
            return response

        @app.post("/api/feedback")
        async def feedback(payload: FeedbackRequest):
            """回答反馈。"""
            return {"status": "ok", "saved": _save_feedback(payload)}

        # ---------------------------------------------------------- 调试接口
        if self.enable_inspect:

            @app.get("/inspect", response_class=HTMLResponse)
            async def inspect_page():
                """调试入口（仅在 ENABLE_DEBUG_ROUTES=true 时注册）。

                旧电商调试页已下线，这里只留一个索引页。
                """
                return HTMLResponse(
                    "<!doctype html><meta charset='utf-8'>"
                    "<title>debug</title>"
                    "<body style=\"font-family:serif;padding:32px;background:#E8DFC8;color:#12100E\">"
                    "<h1>调试接口已启用</h1>"
                    "<p>可用：<code>/api/domain</code>、<code>/api/flows</code>、"
                    "<code>/api/tracker/{session_id}</code>、<code>/docs</code></p>"
                    "<p>公网部署请保持 <code>ENABLE_DEBUG_ROUTES=false</code>。</p>"
                    "</body>"
                )

            @app.get("/api/domain")
            async def get_domain():
                if not self.agent:
                    raise HTTPException(status_code=503, detail="服务尚未就绪")
                return self.agent.domain.as_dict()

            @app.get("/api/flows")
            async def get_flows():
                if not self.agent:
                    raise HTTPException(status_code=503, detail="服务尚未就绪")
                return [flow.as_dict() for flow in (self.agent.flows or [])]

            @app.get("/api/tracker/{session_id}")
            async def get_tracker(session_id: str):
                if not self.agent:
                    raise HTTPException(status_code=503, detail="服务尚未就绪")
                tracker = await self.agent.get_tracker(self._sender_id(session_id))
                if not tracker:
                    raise HTTPException(status_code=404, detail="会话不存在")
                return {
                    "sender_id": tracker.sender_id,
                    "slots": tracker.get_all_slots(),
                    "events_count": len(tracker.dialogue_turns),
                }

    # ------------------------------------------------------------------ 运行
    def set_agent(self, agent: "Agent") -> None:
        self.agent = agent

    def run(self, host: str = DEFAULT_SERVER_HOST, port: int = DEFAULT_SERVER_PORT) -> None:
        import uvicorn

        logger.info("Starting server on %s:%s", host, port)
        uvicorn.run(self.app, host=host, port=port, log_level="info")


def create_app(
    agent: Optional["Agent"] = None,
    cors_origins: Optional[List[str]] = None,
    enable_inspect: bool = False,
) -> FastAPI:
    """创建 FastAPI 应用。"""
    return AgentServer(
        agent=agent,
        cors_origins=cors_origins,
        enable_inspect=enable_inspect,
    ).app


__all__ = [
    "AgentServer",
    "create_app",
    "ChatRequest",
    "ChatResponse",
    "FeedbackRequest",
    "HealthResponse",
    "RateLimiter",
]
