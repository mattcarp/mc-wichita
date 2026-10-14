import os
from pathlib import Path

import wichita_adsb_live as wad

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "live_adsb"


def test_adsb_fixture_snapshot(monkeypatch):
    monkeypatch.setenv("WICHITA_ADSBLOL", "0")
    monkeypatch.setenv("WICHITA_ADSB_FIXTURE_DIR", str(FIXTURE))
    snap = wad.live_adsb_snapshot()
    assert snap["receiver_connected"] is True
    assert snap["aircraft_count"] == 2
    assert snap["data_source"] == "our_antenna"
    emergency = [p for p in snap["aircraft"] if p.get("squawk") == "7700"]
    assert len(emergency) == 1
    assert "7700" in (emergency[0].get("squawk_note") or "")


def test_adsb_offline_without_fixture(monkeypatch):
    monkeypatch.setenv("WICHITA_ADSBLOL", "0")
    monkeypatch.delenv("WICHITA_ADSB_FIXTURE_DIR", raising=False)
    monkeypatch.setenv("WICHITA_ADSB_URL", "http://127.0.0.1:9/aircraft.json")
    snap = wad.live_adsb_snapshot()
    assert snap["receiver_connected"] is False
    assert snap["error"]


# --- adsb.lol + merge -------------------------------------------------------

def _raw(hex_id, **kw):
    base = {"hex": hex_id, "flight": "ABC123 ", "lat": 35.9, "lon": 14.5, "alt_baro": 30000,
            "gs": 420, "track": 90, "squawk": "1000", "seen_pos": 3.0, "seen": 1.0,
            "r": "9H-AAA", "t": "A320", "emergency": "none"}
    base.update(kw)
    return base


def test_normalise_adsblol_fields():
    p = wad.normalize_aircraft(_raw("4D2001"), source=wad.SRC_ADSBLOL)
    assert p["hex"] == "4d2001" and p["callsign"] == "ABC123"
    assert p["registration"] == "9H-AAA" and p["type"] == "A320"
    assert p["source"] == "adsb.lol" and p["data_source"] == "public_feed"
    assert p["is_emergency"] is False
    assert wad.normalize_aircraft(_raw("x", lat=None)) is None
    assert wad.normalize_aircraft(_raw("4d2002", alt_baro="ground"))["altitude_ft"] == 0


def test_dedupe_one_row_prefers_fresher_local():
    local = [wad.normalize_aircraft(_raw("4d2001", seen_pos=1.0, lat=36.0, r=""), source=wad.SRC_LOCAL)]
    remote = [wad.normalize_aircraft(_raw("4d2001", seen_pos=9.0, lat=35.0), source=wad.SRC_ADSBLOL),
              wad.normalize_aircraft(_raw("4d2009"), source=wad.SRC_ADSBLOL)]
    merged = wad.merge_aircraft(local, remote)
    assert len(merged) == 2
    m = [p for p in merged if p["hex"] == "4d2001"][0]
    assert m["source"] == "local + adsb.lol" and m["lat"] == 36.0
    assert m["registration"] == "9H-AAA"  # filled from adsb.lol


def test_dedupe_uses_adsblol_position_when_fresher():
    local = [wad.normalize_aircraft(_raw("4d2001", seen_pos=30.0, lat=36.0), source=wad.SRC_LOCAL)]
    remote = [wad.normalize_aircraft(_raw("4d2001", seen_pos=2.0, lat=35.0), source=wad.SRC_ADSBLOL)]
    m = wad.merge_aircraft(local, remote)[0]
    assert m["lat"] == 35.0 and m["source"] == "local + adsb.lol" and m["position_source"] == "adsb.lol"


def test_emergency_sorting_pins_to_top():
    rows = [wad.normalize_aircraft(_raw("a1", flight="AAA1")),
            wad.normalize_aircraft(_raw("a2", flight="ZZZ1", squawk="7600")),
            wad.normalize_aircraft(_raw("a3", flight="MMM1", emergency="minfuel")),
            wad.normalize_aircraft(_raw("a4", flight="BBB1", squawk="7500"))]
    out = wad.sort_aircraft(rows)
    assert [p["hex"] for p in out[:3]] == ["a4", "a3", "a2"]
    assert all(p["is_emergency"] for p in out[:3]) and not out[3]["is_emergency"]
    assert "minfuel" in out[1]["squawk_note"]


def test_snapshot_from_poller_cache(monkeypatch):
    import time
    monkeypatch.delenv("WICHITA_ADSB_URL", raising=False)
    monkeypatch.delenv("WICHITA_ADSB_FIXTURE_DIR", raising=False)
    poller = wad.AdsbLolPoller()
    poller._payload = {"now": time.time(), "ac": [_raw("4d2001"), _raw("4d2002", squawk="7700")]}
    poller._fetched_at = time.time()
    monkeypatch.setattr(wad, "_POLLER", poller)
    snap = wad.live_adsb_snapshot()
    assert snap["receiver_connected"] and not snap["feed_paused"]
    assert snap["aircraft_count"] == 2 and snap["aircraft"][0]["squawk"] == "7700"
    assert "adsb.lol, community feed" in snap["source_label"]


def test_snapshot_feed_paused_on_error(monkeypatch):
    monkeypatch.delenv("WICHITA_ADSB_URL", raising=False)
    monkeypatch.delenv("WICHITA_ADSB_FIXTURE_DIR", raising=False)
    poller = wad.AdsbLolPoller(url="http://127.0.0.1:9/nope")
    poller.poll_once()
    assert poller.next_delay() > poller.interval
    monkeypatch.setattr(wad, "_POLLER", poller)
    snap = wad.live_adsb_snapshot()
    assert snap["feed_paused"] is True and snap["aircraft_count"] == 0
