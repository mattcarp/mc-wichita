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
os.environ["WICHITA_ADSB_FIXTURE_DIR"] = str(FIXTURES / "live_adsb")

import api_server


def test_feed_health_endpoint():
    client = TestClient(api_server.app)
    res = client.get("/api/feed-health")
    assert res.status_code == 200
    body = res.json()
    assert body["ais"]["state"] == "live"
    assert "heard_badge" in body


def test_security_headers():
    client = TestClient(api_server.app)
    res = client.get("/health")
    assert res.headers.get("x-content-type-options") == "nosniff"
    assert res.headers.get("content-security-policy")
