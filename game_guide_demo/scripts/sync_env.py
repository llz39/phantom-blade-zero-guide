# -*- coding: utf-8 -*-
"""把「系统环境变量」里的密钥同步进 game_guide_demo/.env。

适用场景
--------
用 Windows 的 `setx` 或「系统属性 → 环境变量」配了 Zilliz / Qwen 的凭据，
但脚本读不到（`setx` 只对新开的进程生效）。这个脚本直接从注册表读出来写进 .env，
不用重启终端。

做三件事
--------
1. 把 ZILLIZ_CLOUD_URI / ZILLIZ_CLOUD_TOKEN / QWEN_API_KEY / MYSQL_PASSWORD
   从「用户变量 → 机器变量」合并进 .env（.env 里已有非空值则不覆盖）；
2. 把 Zilliz 的 URI/Token 同时写成 MILVUS_URI / MILVUS_TOKEN，
   保证项目内所有脚本用的是同一套值；
3. 保留 .env 里其它自定义项，只重写这四个 + 两个 Milvus 项。

用法
----
    python scripts/sync_env.py            # 同步并显示摘要（不打印明文）
    python scripts/sync_env.py --dry-run  # 只看会改成什么
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, Optional

BASE_DIR = Path(__file__).resolve().parent.parent      # game_guide_demo/
ENV_PATH = BASE_DIR / ".env"

# 需要从系统环境同步的键
SYNC_KEYS = ["ZILLIZ_CLOUD_URI", "ZILLIZ_CLOUD_TOKEN", "QWEN_API_KEY", "MYSQL_PASSWORD"]


def read_windows_env(name: str) -> Optional[str]:
    """按 进程 → 用户 → 机器 的顺序读取环境变量。

    进程变量优先；用户/机器变量直接读注册表，
    这样即使当前终端是 `setx` 之前打开的，也能拿到最新值。
    """
    if os.environ.get(name):
        return os.environ[name]
    if os.name != "nt":
        return None
    try:
        import winreg
    except ImportError:
        return None

    locations = [
        (winreg.HKEY_CURRENT_USER, r"Environment"),
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
    ]
    for root, path in locations:
        try:
            with winreg.OpenKey(root, path) as key:
                value, _ = winreg.QueryValueEx(key, name)
                if value:
                    return str(value)
        except OSError:
            continue
    return None


def parse_env(text: str) -> Dict[str, str]:
    """保留注释与顺序的简易解析（只取值，用于合并）。"""
    data: Dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def mask(value: str) -> str:
    if not value:
        return "(空)"
    return value[:8] + "***" if len(value) > 10 else "***"


def is_placeholder(key: str, value: str) -> bool:
    """判断 .env 里的是不是「占位符」而不是真值。

    常见占位形态：
        KEY=KEY                （把变量名当值填了，批量替换最容易踩）
        KEY=your_qwen_api_key
        KEY=<your-token>
        KEY=xxx
    这些都要视为「没配」，否则同步脚本会以为已经填好而跳过。
    """
    if not value:
        return True
    low = value.strip().lower()
    if low == key.lower():
        return True
    if low.startswith("your") or low.startswith("<") or low.startswith("${"):
        return True
    if low in {"xxx", "xxxx", "todo", "changeme", "none", "null"}:
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--legacy-env",
        default="",
        help="从旧项目 .env 补齐缺失项（一次性迁移用），例如 ..\\ecs_demo\\.env",
    )
    args = parser.parse_args()

    if not ENV_PATH.exists():
        print(f".env 不存在：{ENV_PATH}")
        print("先复制模板：copy .env.example .env")
        return 1

    current = parse_env(ENV_PATH.read_text(encoding="utf-8"))

    legacy: Dict[str, str] = {}
    if args.legacy_env:
        legacy_path = Path(args.legacy_env)
        if legacy_path.exists():
            legacy = parse_env(legacy_path.read_text(encoding="utf-8", errors="ignore"))
            print(f"已读取旧配置：{legacy_path}")
        else:
            print(f"警告：旧配置不存在 {legacy_path}")

    # ---- 1. 合并系统环境变量（.env 里是占位符或空值时才算“缺”）----
    changed: Dict[str, str] = {}
    for key in SYNC_KEYS:
        if not is_placeholder(key, current.get(key, "")):
            continue
        value = read_windows_env(key) or legacy.get(key)
        if value and not is_placeholder(key, value):
            changed[key] = value

    merged = {**current, **changed}

    # ---- 2. Zilliz → 项目口径 ----
    zilliz_uri = merged.get("ZILLIZ_CLOUD_URI", "")
    zilliz_token = merged.get("ZILLIZ_CLOUD_TOKEN", "")
    if zilliz_uri and not zilliz_uri.startswith("http"):
        print(f"警告：ZILLIZ_CLOUD_URI 不像 URL（{zilliz_uri[:20]}…），请检查")
    if zilliz_uri:
        merged["MILVUS_URI"] = zilliz_uri
    if zilliz_token:
        merged["MILVUS_TOKEN"] = zilliz_token

    # ---- 3. 回写（统一顺序 + 注释，密钥留空则写占位符）----
    lines = [
        "# ============================================================",
        "# 《影之刃零》攻略客服 Demo · 本地环境变量",
        "# 由 scripts/sync_env.py 生成/更新；本文件不得提交到 Git",
        "# 模板见 .env.example（那里只有占位符，没有真实密钥）",
        "# ============================================================",
        "",
        "# ---------- LLM（命令生成 + 回答） ----------",
        f"QWEN_API_KEY={merged.get('QWEN_API_KEY', '')}",
        f"LLM_MODEL={merged.get('LLM_MODEL', 'qwen3.8-flash')}",
        f"LLM_API_BASE={merged.get('LLM_API_BASE', 'https://dashscope.aliyuncs.com/compatible-mode/v1')}",
        "",
        "# ---------- Embedding（建库 + 查询） ----------",
        f"EMBEDDING_MODEL={merged.get('EMBEDDING_MODEL', 'text-embedding-v4')}",
        f"EMBEDDING_API_BASE={merged.get('EMBEDDING_API_BASE', 'https://dashscope.aliyuncs.com/compatible-mode/v1')}",
        f"EMBEDDING_DIM={merged.get('EMBEDDING_DIM', '1024')}",
        "",
        "# ---------- Milvus / Zilliz Cloud ----------",
        "# 两套名字都能用：项目读 MILVUS_*，Zilliz 控制台给的是 ZILLIZ_CLOUD_*",
        f"ZILLIZ_CLOUD_URI={merged.get('ZILLIZ_CLOUD_URI', '')}",
        f"ZILLIZ_CLOUD_TOKEN={merged.get('ZILLIZ_CLOUD_TOKEN', '')}",
        f"MILVUS_URI={merged.get('MILVUS_URI', '')}",
        f"MILVUS_TOKEN={merged.get('MILVUS_TOKEN', '')}",
        f"MILVUS_COLLECTION={merged.get('MILVUS_COLLECTION', 'game_guide_chunks')}",
        "",
        "# ---------- MySQL ----------",
        f"MYSQL_HOST={merged.get('MYSQL_HOST', '127.0.0.1')}",
        f"MYSQL_PORT={merged.get('MYSQL_PORT', '3306')}",
        f"MYSQL_USER={merged.get('MYSQL_USER', 'root')}",
        f"MYSQL_PASSWORD={merged.get('MYSQL_PASSWORD', '')}",
        f"MYSQL_DB={merged.get('MYSQL_DB', 'game_guide')}",
        "",
        "# ---------- 会话存储 ----------",
        f"TRACKER_STORE_TYPE={merged.get('TRACKER_STORE_TYPE', 'mysql')}",
        f"TRACKER_STORE_PATH={merged.get('TRACKER_STORE_PATH', 'trackers')}",
        "",
        "# ---------- 服务与安全 ----------",
        f"HOST={merged.get('HOST', '127.0.0.1')}",
        f"PORT={merged.get('PORT', '8000')}",
        f"CORS_ORIGINS={merged.get('CORS_ORIGINS', 'http://localhost:8000,http://127.0.0.1:8000')}",
        f"ENABLE_DEBUG_ROUTES={merged.get('ENABLE_DEBUG_ROUTES', 'false')}",
        f"RATE_LIMIT_PER_MINUTE={merged.get('RATE_LIMIT_PER_MINUTE', '10')}",
        f"RATE_LIMIT_PER_DAY={merged.get('RATE_LIMIT_PER_DAY', '100')}",
        f"DAILY_REQUEST_LIMIT={merged.get('DAILY_REQUEST_LIMIT', '300')}",
        f"MAX_INPUT_CHARS={merged.get('MAX_INPUT_CHARS', '300')}",
        # 反代相关：Render/Nginx 后面必须 true，本地直连保持 false
        f"TRUST_PROXY_HEADERS={merged.get('TRUST_PROXY_HEADERS', 'false')}",
        "",
        "# ---------- 成本估算单价（元/千 token） ----------",
        f"LLM_PRICE_IN_PER_K={merged.get('LLM_PRICE_IN_PER_K', '0.0008')}",
        f"LLM_PRICE_OUT_PER_K={merged.get('LLM_PRICE_OUT_PER_K', '0.002')}",
        "",
        "# 本机代理例外：不加这两行，127.0.0.1 的请求会被代理劫持成 404",
        "NO_PROXY=localhost,127.0.0.1,::1",
        "no_proxy=localhost,127.0.0.1,::1",
        "",
    ]

    print("将写入的 Milvus 目标：")
    print(f"  MILVUS_URI   = {merged.get('MILVUS_URI', '(空)')}")
    print(f"  MILVUS_TOKEN = {mask(merged.get('MILVUS_TOKEN', ''))}")
    print(f"  collection   = {merged.get('MILVUS_COLLECTION', 'game_guide_chunks')}")
    print(f"  QWEN_API_KEY = {mask(merged.get('QWEN_API_KEY', ''))}")
    print(f"  本次新增同步：{list(changed) or '无（.env 已有值）'}")

    # 仍然缺失的关键项给提示（不打印任何明文）
    missing = [key for key in ("QWEN_API_KEY", "ZILLIZ_CLOUD_URI", "ZILLIZ_CLOUD_TOKEN", "MYSQL_PASSWORD")
               if is_placeholder(key, merged.get(key, ""))]
    if missing:
        print(f"  仍缺：{missing} —— 请手动填，或用 setx 配好后重跑本脚本")

    if zilliz_uri:
        print("  提示：已切到 Zilliz Cloud。若要用本地 Docker，把 MILVUS_URI 改成 http://127.0.0.1:19530 即可。")

    if args.dry_run:
        print("\n--dry-run：未写入")
        return 0

    ENV_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n已写入 {ENV_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
