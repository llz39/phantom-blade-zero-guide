# -*- coding: utf-8 -*-
"""清理过期匿名会话。

限制文档要求：会话 7 天过期，由定时任务清理。
云上可以用平台 cron / 计划任务；本地直接跑这个脚本。

用法：
    python scripts/cleanup_sessions.py                # 删 7 天前的 trackers
    python scripts/cleanup_sessions.py --days 30      # 自定义保留天数
    python scripts/cleanup_sessions.py --dry-run      # 只统计，不删
    python scripts/cleanup_sessions.py --feedback     # 顺带清理 90 天前的反馈

建议 crontab（每天凌晨 3:10）：
    10 3 * * * cd /app/game_guide_demo && python scripts/cleanup_sessions.py >> /var/log/pbz-cleanup.log 2>&1
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
for extra in (str(BASE_DIR), str(BASE_DIR.parent)):
    if extra not in sys.path:
        sys.path.insert(0, extra)

from env_bootstrap import load_env  # noqa: E402

load_env()

from customer_service_system.api.server import _db_connection  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7, help="会话保留天数")
    parser.add_argument("--feedback", action="store_true", help="同时清理 90 天前的反馈")
    parser.add_argument("--dry-run", action="store_true", help="只统计不删除")
    args = parser.parse_args()

    conn = _db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM trackers WHERE updated_at < NOW() - INTERVAL %s DAY",
                (args.days,),
            )
            stale = cursor.fetchone()[0]
            print(f"待清理会话（>{args.days} 天）：{stale}")

            if stale and not args.dry_run:
                cursor.execute(
                    "DELETE FROM trackers WHERE updated_at < NOW() - INTERVAL %s DAY",
                    (args.days,),
                )
                print(f"已删除：{cursor.rowcount}")

            if args.feedback:
                cursor.execute(
                    "SELECT COUNT(*) FROM feedback WHERE created_at < NOW() - INTERVAL 90 DAY"
                )
                old_fb = cursor.fetchone()[0]
                print(f"待清理反馈（>90 天）：{old_fb}")
                if old_fb and not args.dry_run:
                    cursor.execute(
                        "DELETE FROM feedback WHERE created_at < NOW() - INTERVAL 90 DAY"
                    )
                    print(f"已删除反馈：{cursor.rowcount}")

            # 成本记录保留：它是报表依据，不自动删
            cursor.execute("SELECT COUNT(*), COALESCE(SUM(cost_cny),0) FROM cost_log")
            rows, total = cursor.fetchone()
            print(f"cost_log：{rows} 行，累计 {float(total):.4f} 元")

        if not args.dry_run:
            conn.commit()
        else:
            conn.rollback()
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
