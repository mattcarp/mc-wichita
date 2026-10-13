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
    assert body.get("summary")
    base_names = {s["display_name"] for s in body.get("base_stations") or []}
    assert "Valletta AIS base station" in base_names
    assert body["ships"][0].get("lead_sentence")


def test_live_ship_detail_fixture():
    import api_server

    client = TestClient(api_server.app)
    meta = client.get("/api/live-ais/history/meta")
    assert meta.status_code == 200
    res = client.get("/api/live-ais/ships/2155001")
    assert res.status_code == 200
    assert res.json()["mmsi"] == 2155001


def test_roster_keeps_last_list_when_feed_drops(tmp_path):
    import wichita_ais_live as wal

    path = tmp_path / "roster.json"
    ships = [{"mmsi": 248000662, "shipname": "KATALEYA", "last_signal": 30},
             {"mmsi": 215020000, "last_signal": 1200}]
    out, ok = wal.merge_roster(ships, True, 10_000.0, path)
    assert len(out) == 2 and ok == 10_000.0
    # AIS-catcher forgot one ship; roster keeps it inside the window
    out, _ = wal.merge_roster(ships[:1], True, 10_060.0, path)
    assert len(out) == 2
    # Feed down: last list kept, last-heard keeps ageing honestly
    out, ok = wal.merge_roster(None, False, 20_000.0, path)
    assert len(out) == 2 and ok == 10_060.0
    k = [s for s in out if s["mmsi"] == 248000662][0]
    assert abs(k["last_signal"] - (20_000.0 - 10_030.0)) < 1
    # Feed back: entries older than the window are pruned
    out, _ = wal.merge_roster([], True, 20_000.0, path)
    assert out == []
