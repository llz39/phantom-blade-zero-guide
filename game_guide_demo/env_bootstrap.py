# -*- coding: utf-8 -*-
"""环境变量引导（所有入口的第一步）。

为什么需要这个文件
------------------
1. **两套变量名要能互通**
   项目内部统一用 `MILVUS_URI / MILVUS_TOKEN`；
   Zilliz 控制台和 `test.py` 用的是 `ZILLIZ_CLOUD_URI / ZILLIZ_CLOUD_TOKEN`。
   不打通的话，同一份配置在「脚本」和「服务」里行为不一致，很难排查。

2. **`setx` 写的变量对已打开的终端不生效**
   Windows 上 `setx` / 系统属性写入的是注册表，只有**新开**的进程才能读到。
   所以脚本自己也要读 `.env`，否则会出现「我明明配了，程序却读到 None」。

3. **本机代理会劫持 127.0.0.1**
   开着 Clash 之类时，访问 http://127.0.0.1:8000 会被当作代理请求发出去，
   FastAPI 收到的是 `POST http%3A//127.0.0.1...` → 404。这里补 NO_PROXY 兜底。

加载优先级（高 → 低）
--------------------
真实环境变量  >  game_guide_demo/.env  >  仓库根目录/.env  >  代码里的默认值

用法
----
    from env_bootstrap import load_env
    env = load_env()            # 只需在进程入口调用一次
    print(env["milvus_uri"])
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

PROJECT_DIR = Path(__file__).resolve().parent      # game_guide_demo/
REPO_ROOT = PROJECT_DIR.parent                     # 仓库根目录

# 本地地址，用来判断「这是本机 Milvus 还是云端 Zilliz」
_LOCAL_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0")

_loaded = False


def _read_env_file(path: Path) -> Dict[str, str]:
    """极简 .env 解析：只处理 KEY=VALUE / # 注释 / 引号，够用且不引入副作用。"""
    data: Dict[str, str] = {}
    if not path.exists():
        return data
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # 去掉成对引号；保留值里的空格
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        data[key] = value
    return data


def load_env(override: bool = False) -> Dict[str, Any]:
    """加载 .env、打通变量别名、补齐代理例外。

    Args:
        override: True 时 .env 覆盖已有的真实环境变量（默认 False，
            遵循 12-factor：环境变量优先于文件）。

    Returns:
        当前生效的关键配置摘要，便于打日志时脱敏输出。
    """
    global _loaded

    # ---- 1. 读 .env：先根目录，再项目目录（后者更具体，后写覆盖前者）----
    merged: Dict[str, str] = {}
    merged.update(_read_env_file(REPO_ROOT / ".env"))
    merged.update(_read_env_file(PROJECT_DIR / ".env"))

    for key, value in merged.items():
        if override or not os.environ.get(key):
            os.environ[key] = value

    # ---- 2. Zilliz Cloud 变量名互通 ----
    # 显式写了 MILVUS_URI 就以它为准（方便本地 Docker 时切回 127.0.0.1）；
    # 否则用 Zilliz 的 URI，这样用户只配 ZILLIZ_CLOUD_* 也能直接跑。
    if not os.environ.get("MILVUS_URI") and os.environ.get("ZILLIZ_CLOUD_URI"):
        os.environ["MILVUS_URI"] = os.environ["ZILLIZ_CLOUD_URI"]
    if not os.environ.get("MILVUS_TOKEN") and os.environ.get("ZILLIZ_CLOUD_TOKEN"):
        os.environ["MILVUS_TOKEN"] = os.environ["ZILLIZ_CLOUD_TOKEN"]

    # 反向也补一次：某些脚本（如用户自写的 test.py）只认 ZILLIZ_CLOUD_*
    if not os.environ.get("ZILLIZ_CLOUD_URI") and os.environ.get("MILVUS_URI"):
        os.environ["ZILLIZ_CLOUD_URI"] = os.environ["MILVUS_URI"]
    if not os.environ.get("ZILLIZ_CLOUD_TOKEN") and os.environ.get("MILVUS_TOKEN"):
        os.environ["ZILLIZ_CLOUD_TOKEN"] = os.environ["MILVUS_TOKEN"]

    # ---- 3. 本机地址不要走代理 ----
    no_proxy = os.environ.get("NO_PROXY") or ""
    missing = [host for host in _LOCAL_HOSTS if host not in no_proxy]
    if missing:
        joined = ",".join([item for item in no_proxy.split(",") if item] + missing + ["::1"])
        os.environ["NO_PROXY"] = joined
        os.environ["no_proxy"] = joined

    _loaded = True
    return milvus_target()


def milvus_target() -> Dict[str, Any]:
    """返回当前 Milvus 目标摘要（不打印 token 明文）。"""
    uri = os.environ.get("MILVUS_URI", "")
    token = os.environ.get("MILVUS_TOKEN", "")
    return {
        "milvus_uri": uri,
        "milvus_is_cloud": bool(uri) and not any(host in uri for host in _LOCAL_HOSTS),
        "milvus_token_set": bool(token),
        "milvus_collection": os.environ.get("MILVUS_COLLECTION", "game_guide_chunks"),
        "env_file_loaded": _loaded,
    }


def mask(value: str, keep: int = 6) -> str:
    """脱敏：保留前 keep 位，其余打码。日志里永远不要出现完整 token。"""
    if not value:
        return ""
    if len(value) <= keep:
        return "***"
    return value[:keep] + "***"


if __name__ == "__main__":
    # 直接运行可快速确认「到底读到了什么」
    info = load_env()
    for key, value in info.items():
        print(f"{key:22} = {value}")
    print(f"{'tmp:QWEN_API_KEY':22} = {mask(os.environ.get('QWEN_API_KEY', ''))}")
    print(f"{'tmp:MYSQL_PASSWORD':22} = {'已设置' if os.environ.get('MYSQL_PASSWORD') else '(空)'}")
