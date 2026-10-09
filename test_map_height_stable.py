"""Playwright: map height stable over 10s at phone viewport (390x844)."""

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright


def test_harbour_map_height_stable():
    base = "http://127.0.0.1:8000/"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.goto(base, wait_until="networkidle", timeout=90_000)
        page.wait_for_selector(".harbour-svg", timeout=30_000)
        page.wait_for_timeout(2000)

        def heights():
            return page.evaluate(
                """() => {
              const svg = document.querySelector('.harbour-svg');
              const host = document.querySelector('#harbourMap');
              return {
                svg: svg ? Math.round(svg.getBoundingClientRect().height) : 0,
                host: host ? Math.round(host.getBoundingClientRect().height) : 0,
              };
            }"""
            )

        h0 = heights()
        assert h0["svg"] >= 100 and h0["host"] >= 100
        page.wait_for_timeout(10_000)
        h1 = heights()
        assert abs(h1["svg"] - h0["svg"]) <= 4
        assert abs(h1["host"] - h0["host"]) <= 4
        browser.close()
