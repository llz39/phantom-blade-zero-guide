# -*- coding: utf-8 -*-
"""Zilliz Cloud / Milvus 连通性自测。

这个文件只做一件事：确认「endpoint + token 能用、能列出 collection」。
它读的是 `env_bootstrap`，所以下面几种配置方式都能跑：

    MILVUS_URI / MILVUS_TOKEN                    （项目内口径）
    ZILLIZ_CLOUD_URI / ZILLIZ_CLOUD_TOKEN        （Zilliz 控制台口径）
    game_guide_demo/.env                          （本地文件）
    Windows 系统环境变量（setx / 系统属性）        （机器级，新进程才生效）

用法：
    python test.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 让脚本既能从仓库根运行，也能从 game_guide_demo 里运行
ROOT = Path(__file__).resolve().parent
for path in (str(ROOT), str(ROOT / "game_guide_demo")):
    if path not in sys.path:
        sys.path.insert(0, path)

from env_bootstrap import load_env  # noqa: E402

info = load_env()

uri = os.getenv("MILVUS_URI", "")
token = os.getenv("MILVUS_TOKEN", "")

if not uri:
    raise SystemExit(
        "没有读到 Milvus 地址。请确认：\n"
        "  1) game_guide_demo/.env 里有 MILVUS_URI 或 ZILLIZ_CLOUD_URI；或\n"
        "  2) 系统环境变量里配了 ZILLIZ_CLOUD_URI，并且用新开的终端运行。"
    )

print(f"目标      : {uri}")
print(f"云端      : {info['milvus_is_cloud']}")
print(f"token     : {'已设置' if token else '(空，本地 Docker 可留空)'}")
print(f"collection: {info['milvus_collection']}")

try:
    from pymilvus import MilvusClient

    # timeout 给短一点，连不上时不要卡住
    client = MilvusClient(uri=uri, token=token or None, timeout=10)
    collections = client.list_collections()
    print(f"连接成功，现有 collections: {collections}")
    client.close()
except Exception as exc:  # noqa: BLE001
    print(f"连接失败: {type(exc).__name__}: {exc}")
    print("排查：endpoint 是否带 https://、token 是否过期、本机代理是否劫持（NO_PROXY）")
    sys.exit(1)
