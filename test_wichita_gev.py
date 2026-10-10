import os
import sys
import types
from pathlib import Path

from fastapi.testclient import TestClient

FIXTURES = Path(__file__).resolve().parent / "fixtures"
LIVE_AIS = FIXTURES / "live_ais"
LIVE_ADSB = FIXTURES / "live_adsb"

api_maritime_aviation_stub = types.ModuleType("api_maritime_aviation")
api_maritime_aviation_stub.add_maritime_aviation_routes = lambda app: app
sys.modules.setdefault("api_maritime_aviation", api_maritime_aviation_stub)

os.environ.setdefault("WICHITA_CAPTURES_DIRS", str(FIXTURES))
os.environ["WICHITA_AIS_FIXTURE_DIR"] = str(LIVE_AIS)
os.environ["WICHITA_ADSB_FIXTURE_DIR"] = str(LIVE_ADSB)
os.environ["WICHITA_SECURITY_ENABLED"] = "0"


def test_gev_receivers_and_mcp():
    import api_server

    client = TestClient(api_server.app)
    res = client.get("/api/gev/receivers")
    assert res.status_code == 200
    body = res.json()
    assert body["ais"]["service"] == "ais-catcher"
    assert body["adsb"]["service"] == "readsb"

    tools = client.get("/mcp/tools")
    assert tools.status_code == 200
    names = {t["name"] for t in tools.json()["tools"]}
    assert names == {"ships_now", "planes_now", "events_since"}

    ships = client.post("/mcp/call", json={"name": "ships_now", "arguments": {}})
    assert ships.status_code == 200
    payload = ships.json()["content"][0]["text"]
    assert "ships" in payload
