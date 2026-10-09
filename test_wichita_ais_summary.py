"""Summary counts and type breakdown share one source of truth."""

import os
import sys
import types
from pathlib import Path

from fastapi.testclient import TestClient

FIXTURES = Path(__file__).resolve().parent / "fixtures"
LIVE_AIS = FIXTURES / "live_ais"

api_maritime_aviation_stub = types.ModuleType("api_maritime_aviation")
api_maritime_aviation_stub.add_maritime_aviation_routes = lambda app: app
sys.modules.setdefault("api_maritime_aviation", api_maritime_aviation_stub)

os.environ.setdefault("WICHITA_CAPTURES_DIRS", str(FIXTURES))
os.environ["WICHITA_AIS_FIXTURE_DIR"] = str(LIVE_AIS)

from wichita_ais_copy import freshness_bucket


def test_type_breakdown_matches_now_count_and_cards():
    import api_server

    client = TestClient(api_server.app)
    res = client.get("/api/live-ais/snapshot")
    assert res.status_code == 200
    body = res.json()
    now_count = body["freshness_counts"]["now"]
    breakdown = body.get("type_breakdown") or {}
    assert sum(breakdown.values()) == now_count
    cards_now = [s for s in body["ships"] if freshness_bucket(s.get("last_signal_s")) == "now"]
    assert len(cards_now) == now_count
    for s in cards_now:
        label = s.get("shiptype_label") or "vessels"
        assert breakdown.get(label, 0) >= 1
