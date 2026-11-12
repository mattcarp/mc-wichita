from wichita_live_events import LiveEventEngine


def test_ship_silent_skipped_when_feed_stalled(monkeypatch):
    events = []
    monkeypatch.setattr("wichita_live_events.append_event", lambda k, s, **f: events.append((k, s)))
    eng = LiveEventEngine()
    ship = {
        "mmsi": 256003495,
        "lat": 35.9,
        "lon": 14.5,
        "display_name": "TEST",
        "last_signal_s": 2000,
        "freshness": "earlier",
        "track_signal_status": "signal_lost",
        "is_base_station": False,
    }
    eng.ingest_snapshot({"online": True, "feed_stalled": True, "ships": [ship]})
    assert not any(k == "ship_silent" for k, _ in events)
