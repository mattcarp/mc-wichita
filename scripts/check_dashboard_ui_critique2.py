#!/usr/bin/env python3
"""Playwright screenshots for UI critique 2 (uses Python playwright, no new npm deps)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
base = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("WICHITA_DASHBOARD_URL", "http://127.0.0.1:8765/")
out_dir = Path(os.environ.get("WICHITA_UI_SCREENSHOT_DIR", ROOT / "artifacts" / "ui-critique-2"))
out_dir.mkdir(parents=True, exist_ok=True)

tabs = ["harbour", "heard", "sky", "recordings", "station"]
viewports = [
    ("desktop", {"width": 1440, "height": 1000}),
    ("phone", {"width": 390, "height": 844}),
]


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, vp in viewports:
            page = browser.new_page(viewport=vp)
            if name == "phone":
                page.set_viewport_size(vp)
            page.goto(base, wait_until="networkidle", timeout=120_000)
            page.wait_for_selector(".harbour-svg", timeout=60_000)
            for tab in tabs:
                if name == "phone":
                    page.locator(f'.tab-btn[data-tab-target="{tab}"]').click(timeout=10_000)
                else:
                    page.locator(f"#panel-{tab}").scroll_into_view_if_needed()
                page.wait_for_timeout(400)
                page.screenshot(path=str(out_dir / f"{name}-tab-{tab}.png"))
            if name == "phone":
                page.locator('.tab-btn[data-tab-target="harbour"]').click(timeout=10_000)
            else:
                page.locator("#panel-harbour").scroll_into_view_if_needed()
            card = page.locator(".live-ship-card").first
            if card.count():
                card.click()
                page.wait_for_timeout(600)
                page.screenshot(path=str(out_dir / f"{name}-ship-sheet.png"))
                page.screenshot(path=str(out_dir / f"{name}-follow.png"))
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
            page.close()
        browser.close()
    print("Screenshots written to", out_dir)


if __name__ == "__main__":
    main()
