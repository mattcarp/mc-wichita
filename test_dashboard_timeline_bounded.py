"""Playwright: Heard timeline stays bounded with a large on-disk event log."""

import json
import os
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright

FIXTURES = Path(__file__).resolve().parent / "fixtures"
LIVE_AIS = FIXTURES / "live_ais"

api_maritime_aviation_stub = types.ModuleType("api_maritime_aviation")
api_maritime_aviation_stub.add_maritime_aviation_routes = lambda app: app
sys.modules.setdefault("api_maritime_aviation", api_maritime_aviation_stub)


def _seed_events(dir_path: Path, count: int = 150) -> None:
    dir_path.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    path = dir_path / f"events-{now.strftime('%Y-%m-%d')}.jsonl"
    rows = []
    for i in range(count):
        ts = now - timedelta(minutes=i)
        rows.append(
            json.dumps(
                {
                    "ts_utc": ts.isoformat(),
                    "kind": "ship_silent",
                    "sentence": f"Vessel {i} has gone quiet (no AIS for 15 min).",
                    "display_name": f"V{i}",
                }
            )
        )
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


@pytest.fixture(scope="module")
def dashboard_server(tmp_path_factory):
    events_dir = tmp_path_factory.mktemp("events")
    _seed_events(events_dir, 150)
    os.environ["WICHITA_CAPTURES_DIRS"] = str(FIXTURES)
    os.environ["WICHITA_AIS_FIXTURE_DIR"] = str(LIVE_AIS)
    os.environ["WICHITA_EVENTS_DIR"] = str(events_dir)
    import uvicorn

    import api_server

    config = uvicorn.Config(api_server.app, host="127.0.0.1", port=8766, log_level="warning")
    server = uvicorn.Server(config)
    import threading

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    yield "http://127.0.0.1:8766/"
    server.should_exit = True


def test_timeline_shell_bounded(dashboard_server):
    base = dashboard_server
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(base, wait_until="networkidle", timeout=120_000)
        page.locator("#panel-heard").scroll_into_view_if_needed()
        page.wait_for_selector(".timeline-shell", timeout=30_000)
        metrics = page.evaluate(
            """() => {
              const shell = document.querySelector('.timeline-shell');
              const items = document.querySelectorAll('#timeline li');
              return {
                shellH: shell ? shell.getBoundingClientRect().height : 0,
                items: items.length,
                docH: document.documentElement.scrollHeight,
              };
            }"""
        )
        assert metrics["items"] <= 25
        assert metrics["shellH"] > 80
        assert metrics["shellH"] < 600
        assert metrics["docH"] < 5000
        browser.close()
