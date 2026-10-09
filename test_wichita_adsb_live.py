import os
from pathlib import Path

import wichita_adsb_live as wad

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "live_adsb"


def test_adsb_fixture_snapshot(monkeypatch):
    monkeypatch.setenv("WICHITA_ADSB_FIXTURE_DIR", str(FIXTURE))
    snap = wad.live_adsb_snapshot()
    assert snap["receiver_connected"] is True
    assert snap["aircraft_count"] == 2
    assert snap["data_source"] == "our_antenna"
    emergency = [p for p in snap["aircraft"] if p.get("squawk") == "7700"]
    assert len(emergency) == 1
    assert "7700" in (emergency[0].get("squawk_note") or "")


def test_adsb_offline_without_fixture(monkeypatch):
    monkeypatch.delenv("WICHITA_ADSB_FIXTURE_DIR", raising=False)
    monkeypatch.setenv("WICHITA_ADSB_URL", "http://127.0.0.1:9/aircraft.json")
    snap = wad.live_adsb_snapshot()
    assert snap["receiver_connected"] is False
    assert snap["error"]
