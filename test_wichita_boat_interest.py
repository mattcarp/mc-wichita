"""Boats of interest: lookup, persistence, debounced heard alerts."""

import json
import os
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"
LIVE_AIS = FIXTURES / "live_ais"
SEAWOLF_MMSI = 256760000

api_maritime_aviation_stub = types.ModuleType("api_maritime_aviation")
api_maritime_aviation_stub.add_maritime_aviation_routes = lambda app: app
sys.modules.setdefault("api_maritime_aviation", api_maritime_aviation_stub)


def _ship(mmsi: int, last_signal_s: float, **extra):
    return {
        "mmsi": mmsi,
        "display_name": "SEAWOLF X",
        "shipname": "SEAWOLF X",
        "callsign": "9HA5965",
        "lat": 35.89,
        "lon": 14.51,
        "speed_kn": 4.2,
        "speed_known": True,
        "last_signal_s": last_signal_s,
        "last_heard_utc": datetime.now(timezone.utc).isoformat(),
        "freshness": "now" if last_signal_s < 120 else "recent",
        "shiptype_category": "pleasure",
        "is_base_station": False,
        **extra,
    }


@pytest.fixture
def interest_env(tmp_path, monkeypatch):
    interests = tmp_path / "interests.json"
    events = tmp_path / "events"
    events.mkdir()
    monkeypatch.setenv("WICHITA_INTERESTS_FILE", str(interests))
    monkeypatch.setenv("WICHITA_EVENTS_DIR", str(events))
    monkeypatch.setenv("WICHITA_CAPTURES_DIRS", str(FIXTURES))
    monkeypatch.setenv("WICHITA_AIS_FIXTURE_DIR", str(LIVE_AIS))
    import wichita_interest as wi

    wi._engine = None  # noqa: SLF001
    import wichita_live_events as wle

    wle._engine = None  # noqa: SLF001
    return interests


def test_seawolf_seed_and_lookup(interest_env, monkeypatch):
    import wichita_interest as wi

    boats = wi.list_boats()
    assert any(int(b["mmsi"]) == SEAWOLF_MMSI for b in boats)
    cands = wi.lookup_boat_candidates("256760000", [])
    assert cands and cands[0]["mmsi"] == SEAWOLF_MMSI


def test_heard_alert_fires_once_per_arrival(interest_env, monkeypatch):
    import wichita_interest as wi
    from wichita_live_events import LiveEventEngine

    events = []

    def capture(kind, sentence, **fields):
        events.append((kind, sentence, fields))

    engine = LiveEventEngine()
    engine._patterns = type("X", (), {"ingest": lambda *a, **k: None})()  # noqa: SLF001

    interest = wi.get_boat_interest_engine(capture)
    ships_out = [_ship(SEAWOLF_MMSI, 30.0)]

    # Warm start: already in reception — no alert
    interest.ingest_ships(ships_out)
    assert not events

    # Leave reception (stale)
    interest.ingest_ships([])
    interest._in_reception[SEAWOLF_MMSI] = False  # noqa: SLF001
    interest._armed[SEAWOLF_MMSI] = True  # noqa: SLF001

    # Arrival edge
    interest.ingest_ships(ships_out)
    assert len(events) == 1
    assert events[0][0] == "boat_of_interest_heard"
    assert "Seawolf" in events[0][1] or "SEAWOLF" in events[0][1]
    assert events[0][2]["mmsi"] == SEAWOLF_MMSI

    # Still moored / heard — no second alert
    interest.ingest_ships(ships_out)
    assert len(events) == 1


def test_seawolf_mmsi_256760000_single_alert(interest_env):
    import wichita_interest as wi

    events = []

    def capture(kind, sentence, **fields):
        events.append((kind, sentence, fields))

    interest = wi.BoatInterestEngine(capture)
    ship = _ship(SEAWOLF_MMSI, 60.0)
    interest.ingest_ships([ship])
    interest._in_reception[SEAWOLF_MMSI] = False  # noqa: SLF001
    interest._armed[SEAWOLF_MMSI] = True  # noqa: SLF001
    interest.ingest_ships([ship])
    assert len(events) == 1
    assert events[0][2]["mmsi"] == SEAWOLF_MMSI
    interest.ingest_ships([ship])
    assert len(events) == 1


def test_replayed_position_report_triggers_single_interest_alert(interest_env, monkeypatch):
    """Decode a position report and feed the resulting MMSI through the interest engine once."""
    from ais_decoder import decode_nmea_lines
    import wichita_interest as wi

    nmea = "!AIVDM,1,1,,A,15M67N0000G?Uf6E`FepT@3n08Td,0*73"
    decoded = decode_nmea_lines([nmea])
    if not decoded:
        pytest.skip("pyais unavailable in this environment")
    mmsi = int(decoded[0]["mmsi"])
    wi.add_boat(mmsi=mmsi, label="Replay target")
    events = []

    def capture(kind, sentence, **fields):
        events.append((kind, sentence, fields))

    interest = wi.get_boat_interest_engine(capture)
    ship = _ship(mmsi, 45.0, display_name="Replay target")
    interest.ingest_ships([ship])
    interest._in_reception[mmsi] = False  # noqa: SLF001
    interest._armed[mmsi] = True  # noqa: SLF001
    interest.ingest_ships([ship])
    assert len(events) == 1
    assert events[0][0] == "boat_of_interest_heard"
    interest.ingest_ships([ship])
    assert len(events) == 1


def test_interest_api_add_remove(interest_env):
    import api_server
    from fastapi.testclient import TestClient

    client = TestClient(api_server.app)
    listed = client.get("/api/interests/boats").json()
    assert listed["boats"]
    new_id = listed["boats"][0]["id"]
    dup = client.post("/api/interests/boats", json={"mmsi": SEAWOLF_MMSI})
    assert dup.status_code == 409
    assert client.delete(f"/api/interests/boats/{new_id}").status_code == 200
    assert client.delete(f"/api/interests/boats/{new_id}").status_code == 404
