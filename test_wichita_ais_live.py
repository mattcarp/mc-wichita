import os
import sys
import types
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).resolve().parent / "fixtures"
LIVE_AIS = FIXTURES / "live_ais"

api_maritime_aviation_stub = types.ModuleType("api_maritime_aviation")
api_maritime_aviation_stub.add_maritime_aviation_routes = lambda app: app
sys.modules.setdefault("api_maritime_aviation", api_maritime_aviation_stub)

os.environ.setdefault("WICHITA_CAPTURES_DIRS", str(FIXTURES))
os.environ["WICHITA_AIS_FIXTURE_DIR"] = str(LIVE_AIS)

import wichita_ais_live as wal


def test_fixture_ships_load():
    payload, err = wal.fetch_ais_json("/api/ships.json")
    assert err is None
    assert payload["count"] >= 10
    ships = payload["ships"]
    assert any(s["mmsi"] == 2155001 for s in ships)


def test_normalize_valletta_base():
    raw = next(s for s in wal.fetch_ais_json("/api/ships.json")[0]["ships"] if s["mmsi"] == 2155001)
    norm = wal.normalize_ship(raw)
    assert norm["display_name"] == "Valletta AIS base station"
    assert norm["is_base_station"] is True


def test_live_snapshot_api():
    import api_server

    client = TestClient(api_server.app)
    res = client.get("/api/live-ais/snapshot")
    assert res.status_code == 200
    body = res.json()
    assert body["online"] is True
    assert body["source"] == "live"
    assert len(body["ships"]) >= 10
    assert body["paths"]["type"] == "FeatureCollection"
    names = {s["display_name"] for s in body["ships"]}
    assert "Valletta AIS base station" in names


def test_live_ship_detail_fixture():
    import api_server

    client = TestClient(api_server.app)
    res = client.get("/api/live-ais/ships/2155001")
    assert res.status_code == 200
    assert res.json()["mmsi"] == 2155001
