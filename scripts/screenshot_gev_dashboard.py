#!/usr/bin/env python3
"""Capture dashboard screenshots at desktop and mobile sizes."""

from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path("/opt/cursor/artifacts/screenshots")
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:8000/"


def shot(page, name, width, height):
    page.set_viewport_size({"width": width, "height": height})
    page.goto(BASE, wait_until="networkidle")
    page.wait_for_timeout(2500)
    path = OUT / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    print(path)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        shot(page, "gev-dashboard-1440x1000", 1440, 1000)
        shot(page, "gev-dashboard-390x844", 390, 844)
        page.goto("http://127.0.0.1:8000/dashboard/radar_wall.html", wait_until="networkidle")
        page.set_viewport_size({"width": 1440, "height": 1000})
        page.wait_for_timeout(2000)
        page.screenshot(path=str(OUT / "gev-radar-wall-1440x1000.png"), full_page=True)
        browser.close()


if __name__ == "__main__":
    main()
