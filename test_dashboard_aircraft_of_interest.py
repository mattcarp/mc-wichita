"""Playwright: aircraft-of-interest add flow, pinning, and alert badge."""

import os
import sys
import types
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright

FIXTURES = Path(__file__).resolve().parent / "fixtures"
LIVE_AIS = FIXTURES / "live_ais"
LIVE_ADSB = FIXTURES / "live_adsb"

api_maritime_aviation_stub = types.ModuleType("api_maritime_aviation")
api_maritime_aviation_stub.add_maritime_aviation_routes = lambda app: app
sys.modules.setdefault("api_maritime_aviation", api_maritime_aviation_stub)


@pytest.fixture(scope="module")
def dashboard_server(tmp_path_factory):
    root = tmp_path_factory.mktemp("air-interest")
    interests = root / "interests.json"
    os.environ["WICHITA_INTERESTS_FILE"] = str(interests)
    os.environ["WICHITA_CAPTURES_DIRS"] = str(FIXTURES)
    os.environ["WICHITA_AIS_FIXTURE_DIR"] = str(LIVE_AIS)
    os.environ["WICHITA_ADSB_FIXTURE_DIR"] = str(LIVE_ADSB)
    os.environ["WICHITA_ADSBLOL"] = "0"
    os.environ["WICHITA_AUTH_REQUIRED"] = "false"
    import uvicorn

    import api_server

    config = uvicorn.Config(api_server.app, host="127.0.0.1", port=8768, log_level="warning")
    server = uvicorn.Server(config)
    import threading

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    yield "http://127.0.0.1:8768/"
    server.should_exit = True


def test_aircraft_interest_add_pin_alert_badge(dashboard_server, tmp_path):
    base = dashboard_server
    shot_dir = tmp_path / "playwright"
    shot_dir.mkdir()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.add_init_script("globalThis.__WICHITA_SKIP_AUTH_GATE_AUTOMAIN__ = true;")
        page.route("**/alerts?*", lambda route: route.fulfill(status=200, content_type="application/json", body="[]"))
        page.goto(base, wait_until="networkidle", timeout=120_000)
        page.evaluate(
            """async () => {
              const shell = document.getElementById('appShell');
              if (shell) shell.hidden = false;
              document.body.classList.remove('auth-pending');
              const gate = document.getElementById('authGate');
              if (gate) gate.hidden = true;
              await import('/dashboard/dashboard.js?v=20261016-loading');
            }"""
        )
        page.wait_for_selector("#appShell:not([hidden])", timeout=30_000)
        page.click('.tab-btn[data-tab-target="sky"]')
        page.wait_for_selector("#panel-sky", state="visible", timeout=15_000)
        page.wait_for_selector('[data-test-id="aircraft-source-label"]', timeout=60_000)
        page.wait_for_selector('[data-test-id="air-interest-alert-4d20a2"]', timeout=30_000)
        badge = page.locator('[data-test-id="air-interest-alert-4d20a2"]')
        assert badge.is_visible()
        page.screenshot(path=str(shot_dir / "aircraft-interest-alert-badge.png"), full_page=False)
        page.locator('[data-test-id="air-interest-add"]').click()
        page.wait_for_selector("#airInterestDialog[open]")
        page.fill("#airInterestQuery", "4caabc")
        page.wait_for_selector('[data-test-id^="air-interest-candidate-"]', timeout=15_000)
        page.locator('[data-test-id^="air-interest-candidate-"]').first.click()
        page.wait_for_selector('[data-test-id="air-interest-save"]', state="visible")
        page.locator('[data-test-id="air-interest-save"]').click()
        page.wait_for_selector('[data-test-id="aircraft-of-interest-roster"]', timeout=15_000)
        page.screenshot(path=str(shot_dir / "aircraft-interest-pinned-roster.png"), full_page=False)
        roster = page.locator('[data-test-id="aircraft-of-interest-roster"]')
        assert "aircraft of interest" in roster.inner_text().lower()
        heard = page.locator('[data-test-id="air-interest-heard-4caabc"]')
        assert heard.count() >= 1
        browser.close()
