"""Playwright: boats-of-interest add flow and pinned roster."""

import os
import sys
import types
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright

FIXTURES = Path(__file__).resolve().parent / "fixtures"
LIVE_AIS = FIXTURES / "live_ais"

api_maritime_aviation_stub = types.ModuleType("api_maritime_aviation")
api_maritime_aviation_stub.add_maritime_aviation_routes = lambda app: app
sys.modules.setdefault("api_maritime_aviation", api_maritime_aviation_stub)


@pytest.fixture(scope="module")
def dashboard_server(tmp_path_factory):
    root = tmp_path_factory.mktemp("interest")
    interests = root / "interests.json"
    os.environ["WICHITA_INTERESTS_FILE"] = str(interests)
    os.environ["WICHITA_CAPTURES_DIRS"] = str(FIXTURES)
    os.environ["WICHITA_AIS_FIXTURE_DIR"] = str(LIVE_AIS)
    os.environ["WICHITA_AUTH_REQUIRED"] = "false"
    import uvicorn

    import api_server

    config = uvicorn.Config(api_server.app, host="127.0.0.1", port=8767, log_level="warning")
    server = uvicorn.Server(config)
    import threading

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    yield "http://127.0.0.1:8767/"
    server.should_exit = True


def test_boat_interest_add_flow_screenshot(dashboard_server, tmp_path):
    base = dashboard_server
    shot_dir = tmp_path / "playwright"
    shot_dir.mkdir()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.add_init_script(
            """
            globalThis.__WICHITA_SKIP_AUTH_GATE_AUTOMAIN__ = true;
            """
        )
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
        page.click('.tab-btn[data-tab-target="harbour"]')
        page.wait_for_selector("#panel-harbour", state="visible", timeout=15_000)
        page.wait_for_selector("#boatInterestAdd", state="visible", timeout=30_000)
        page.wait_for_function(
            """async () => {
              const r = await fetch('/api/live-ais/snapshot');
              const d = await r.json();
              return (d.interest_vessels || []).length > 0;
            }""",
            timeout=60_000,
        )
        page.wait_for_function(
            """() => document.querySelector('[data-test-id="boats-of-interest-roster"]')""",
            timeout=60_000,
        )
        page.screenshot(path=str(shot_dir / "boat-interest-pinned-roster.png"), full_page=False)
        page.locator("#boatInterestAdd").click()
        page.wait_for_selector("#boatInterestDialog[open]")
        page.screenshot(path=str(shot_dir / "boat-interest-dialog.png"), full_page=False)
        page.fill("#boatInterestQuery", "256760000")
        page.wait_for_selector('[data-test-id^="interest-candidate-"]', timeout=15_000)
        page.locator('[data-test-id^="interest-candidate-"]').first.click()
        page.wait_for_selector('[data-test-id="boat-interest-save"]', state="visible")
        page.screenshot(path=str(shot_dir / "boat-interest-confirm.png"), full_page=False)
        page.locator("button[data-interest-cancel]").click()
        text = page.locator('[data-test-id="boats-of-interest-roster"]').inner_text()
        assert "boats of interest" in text.lower()
        assert page.locator('[data-test-id^="ship-card-"]').count() >= 1
        browser.close()
