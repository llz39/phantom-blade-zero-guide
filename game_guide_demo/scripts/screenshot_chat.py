# -*- coding: utf-8 -*-
"""带交互的页面截图（UI 验收用）。

用 Playwright 拦截 `/api/chat`，返回一份固定的示例回答与来源卡片，
用来检查气泡、来源卡片、未知标记的排版。**不修改任何产品代码**，
也不代表真实模型输出。

用法：
    python scripts/screenshot_chat.py --url http://127.0.0.1:8077/ --out docs/screenshots
"""

from __future__ import annotations

import json
import argparse
from pathlib import Path

DEMO_ANSWER = {
    "session_id": "00000000-0000-4000-8000-000000000000",
    "text": (
        "结论：白山风雷剑通过击败「正道大营」的章节首领「廿一号剑偶·玉璧」获得，"
        "属于首领奖励，无需另找宝箱。\n\n"
        "关键信息：\n"
        "· 区域：正道大营（Mandate Encampment）上层\n"
        "· 类型：双持，风/雷双状态叠加后进入「白山护佑」\n"
        "· 该区域另一把武器「灵蛇软剑」来自支线首领乌冷霜\n\n"
        "不确定项：攻击力与升级材料数量暂未收录可靠数值，不建议凭印象补全。"
    ),
    "sources": [
        {
            "title": "白山风雷剑 · 影之刃零 Wiki",
            "source": "https://wiki.biligame.com/yingzhiren/白山风雷剑",
            "source_level": "S3",
            "entity_id": "weapon_bai_shan_feng_lei_jian",
            "doc_type": "weapon",
            "version": "1.0302256",
            "updated_at": "2026-11-08",
        },
        {
            "title": "影之刃零白山风雷剑怎么获得 玉璧掉落与风雷双剑用法",
            "source": "https://www.18183.com/gonglue/202611/9076289.html",
            "source_level": "S3",
            "entity_id": "weapon_bai_shan_feng_lei_jian",
            "doc_type": "weapon",
            "version": "1.0302256",
            "updated_at": "2026-11-08",
        },
    ],
    "unknown": False,
    "elapsed_ms": 1420,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000/")
    parser.add_argument("--out", default="docs/screenshots")
    args = parser.parse_args()

    from playwright.sync_api import sync_playwright

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(channel="msedge", headless=True)
        except Exception:
            browser = playwright.chromium.launch(headless=True)

        def prepare(context):
            page = context.new_page()
            page.route(
                "**/api/chat",
                lambda route: route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(DEMO_ANSWER, ensure_ascii=False),
                ),
            )
            page.goto(args.url, wait_until="networkidle")
            page.wait_for_timeout(400)
            page.fill("#input", "白山风雷剑怎么获得？")
            page.click("#send")
            page.wait_for_timeout(900)
            return page

        desktop = browser.new_context(viewport={"width": 1440, "height": 960}, locale="zh-CN")
        page = prepare(desktop)
        page.screenshot(path=str(out_dir / "desktop_chat.png"))

        mobile = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
            locale="zh-CN",
        )
        mpage = prepare(mobile)
        mpage.screenshot(path=str(out_dir / "mobile_chat.png"))

        browser.close()

    print(f"截图完成: {out_dir / 'desktop_chat.png'} / {out_dir / 'mobile_chat.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
