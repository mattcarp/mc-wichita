import wichita_ais_identity as wai
from wichita_ais_identity import (
    AisMmsiIdentityTracker,
    get_mmsi_identity_tracker,
    invalid_mmsi_reasons,
)


def test_invalid_mmsi_patterns():
    assert invalid_mmsi_reasons(123456789)
    assert invalid_mmsi_reasons(111111111)
    assert invalid_mmsi_reasons("12345")


def test_impossible_speed_splits_track_key(monkeypatch):
    monkeypatch.setattr(wai, "persist_advisory_alert", lambda _r: None)
    tr = AisMmsiIdentityTracker()
    base = {
        "mmsi": 256003495,
        "lat": 35.9,
        "lon": 14.5,
        "display_name": "TEST",
        "is_base_station": False,
    }
    tr.ingest_vessel(dict(base), now_epoch=1000.0, persist_alerts=False)
    far = dict(base, lat=36.2, lon=15.2)
    out = tr.ingest_vessel(far, now_epoch=1060.0, persist_alerts=False)
    assert out["track_segment"] >= 1
    assert "#" in out["track_key"]
    advisories = tr.consume_advisories()
    assert any(a["kind"] == wai.ADVISORY_SPOOF for a in advisories)


def test_same_mmsi_slow_move_stays_one_track(monkeypatch):
    monkeypatch.setattr(wai, "persist_advisory_alert", lambda _r: None)
    tr = AisMmsiIdentityTracker()
    ship = {
        "mmsi": 256001241,
        "lat": 35.9,
        "lon": 14.5,
        "display_name": "SLOW",
        "is_base_station": False,
    }
    tr.ingest_vessel(dict(ship), now_epoch=2000.0, persist_alerts=False)
    nudged = dict(ship, lat=35.9005, lon=14.5005)
    out = tr.ingest_vessel(nudged, now_epoch=2030.0, persist_alerts=False)
    assert out["track_key"] == "256001241"
    assert not tr.consume_advisories()


def test_tracker_singleton():
    assert get_mmsi_identity_tracker() is get_mmsi_identity_tracker()
