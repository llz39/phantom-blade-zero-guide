# -*- coding: utf-8 -*-
"""
运行服务命令

启动对话服务器。
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional, List

import click

from customer_service_system.shared.constants import (
    DEFAULT_SERVER_HOST,
    DEFAULT_SERVER_PORT,
)

logger = logging.getLogger(__name__)


@click.command("run", help="运行对话服务")
@click.option(
    "--model", "-m",
    type=click.Path(),
    default="game_guide_demo",
    help="项目目录（默认 game_guide_demo）或模型文件路径",
)
@click.option(
    "--endpoints",
    type=click.Path(exists=True),
    default=None,
    help="端点配置文件路径",
)
@click.option(
    "--host", "-H",
    type=str,
    default=None,
    help="服务器监听地址（默认读 HOST 环境变量）",
)
@click.option(
    "--port", "-p",
    type=int,
    default=None,
    help="服务器监听端口（默认读 PORT 环境变量）",
)
@click.option(
    "--cors",
    type=str,
    multiple=True,
    default=None,
    help="CORS允许的源 (可多次指定，默认读 CORS_ORIGINS)",
)
@click.option(
    "--enable-api/--disable-api",
    default=True,
    help="启用/禁用REST API",
)
@click.option(
    "--enable-inspect/--disable-inspect",
    default=False,
    help="启用/禁用调试接口（默认关闭）",
)
@click.option(
    "--channel",
    type=click.Choice(["rest", "socketio", "all"]),
    default="all",
    help="启用的通道类型",
)
@click.pass_context
def run_command(
    ctx: click.Context,
    model: str,
    endpoints: Optional[str],
    host: str,
    port: int,
    cors: tuple,
    enable_api: bool,
    enable_inspect: bool,
    channel: str,
) -> None:
    """运行对话服务。
    
    启动FastAPI服务器，提供对话API和WebSocket接口。
    
    示例:
        llz_agent run
        llz_agent run --model ./models/latest
        llz_agent run --port 8080 --enable-inspect
    """
    ctx_obj = ctx.obj or {}
    verbose = ctx_obj.get("verbose", False)
    debug = ctx_obj.get("debug", False)

    # 默认值从环境变量读（12-factor），命令行参数优先
    host = host or os.getenv("HOST", DEFAULT_SERVER_HOST)
    port = port or int(os.getenv("PORT", str(DEFAULT_SERVER_PORT)))
    if not cors:
        env_cors = os.getenv("CORS_ORIGINS", "")
        cors = tuple(item.strip() for item in env_cors.split(",") if item.strip())
    if not cors:
        cors = ("http://localhost:8000",)

    click.echo("=" * 50)
    click.echo("影之刃零 · 影境攻略")
    click.echo("=" * 50)
    
    model_path = Path(model)
    
    click.echo(f"项目路径: {model_path.absolute()}")
    click.echo(f"服务地址: http://{host}:{port}")
    click.echo(f"调试接口: {'启用' if enable_inspect else '关闭'}")
    click.echo(f"CORS来源: {list(cors)}")
    click.echo()
    
    try:
        # 导入必要模块
        from customer_service_system.agent.agent import Agent
        from customer_service_system.api.server import AgentServer
        
        # 加载Agent
        click.echo("加载Agent...")

        # 读取项目内 .env（不覆盖已存在的环境变量）
        try:
            from dotenv import load_dotenv

            env_file = (model_path / ".env") if model_path.is_dir() else (model_path.parent / ".env")
            if env_file.exists():
                load_dotenv(env_file, override=False)
                click.echo(f"已加载环境变量: {env_file}")
        except ImportError:
            pass
        
        # 检查是否存在打包的模型或项目目录
        if model_path.is_dir():
            if (model_path / "config.yml").exists():
                # 项目目录模式（domain/ 或 domain.yml 均可）
                agent = Agent.load(str(model_path))
            else:
                model_files = list(model_path.glob("*.tar.gz"))
                if model_files:
                    latest_model = max(model_files, key=lambda p: p.stat().st_mtime)
                    agent = Agent.load(str(latest_model))
                else:
                    click.echo(f"目录 {model_path} 下没有 config.yml，请检查 --model 参数", err=True)
                    raise SystemExit(1)
        else:
            # 模型文件模式
            agent = Agent.load(str(model_path))
        else:
            # 模型文件模式
            agent = Agent.load(str(model_path))
        
        click.echo("Agent加载完成")
        
        # 创建服务器
        click.echo("启动服务器...")
        server = AgentServer(
            agent=agent,
            cors_origins=list(cors),
            enable_inspect=enable_inspect,
        )
        
        click.echo()
        click.echo(f"服务已启动: http://{host}:{port}")
        click.echo(f"聊天页面: http://{host}:{port}/")
        if enable_inspect:
            click.echo(f"调试页面: http://{host}:{port}/inspect")
            click.echo(f"API文档: http://{host}:{port}/docs")
        click.echo("按 Ctrl+C 停止服务")
        click.echo()
        
        # 运行服务器
        server.run(host=host, port=port)
        
    except KeyboardInterrupt:
        click.echo("\n服务已停止")
    except ImportError as e:
        click.echo(f"导入错误: {e}", err=True)
        if debug:
            raise
        raise SystemExit(1)
    except Exception as e:
        click.echo(f"运行失败: {e}", err=True)
        if debug:
            raise
        raise SystemExit(1)


# 导出
__all__ = ["run_command"]
