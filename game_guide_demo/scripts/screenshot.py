# -*- coding: utf-8 -*-
"""页面截图（M7 证据）。

用 Playwright + 本机 Edge（channel=msedge）截图，避免下载 Chromium。

用法：
    python scripts/screenshot.py --url http://127.0.0.1:8077/ --out docs/screenshots
"""

from __future__ import annotations

import argparse
from pathlib import Path


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

        # 桌面端
        desktop = browser.new_context(viewport={"width": 1440, "height": 960}, locale="zh-CN")
        page = desktop.new_page()
        page.goto(args.url, wait_until="networkidle")
        page.wait_for_timeout(600)
        page.screenshot(path=str(out_dir / "desktop.png"), full_page=False)

        # 移动端
        mobile = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
            locale="zh-CN",
        )
        mpage = mobile.new_page()
        mpage.goto(args.url, wait_until="networkidle")
        mpage.wait_for_timeout(600)
        mpage.screenshot(path=str(out_dir / "mobile.png"), full_page=False)

        browser.close()

    print(f"截图完成: {out_dir / 'desktop.png'} / {out_dir / 'mobile.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
