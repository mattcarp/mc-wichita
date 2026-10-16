"""Incident replay: synced frames, retained voice clips, auth-gated playback."""

import json
import os
import struct
import sys
import types
import wave
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).resolve().parent / "fixtures"
LIVE_AIS = FIXTURES / "live_ais"

api_maritime_aviation_stub = types.ModuleType("api_maritime_aviation")
api_maritime_aviation_stub.add_maritime_aviation_routes = lambda app: app
sys.modules.setdefault("api_maritime_aviation", api_maritime_aviation_stub)


def _write_wav(path: Path, seconds: float = 0.25) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rate = 8000
    frames = int(rate * seconds)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack("<" + "h" * frames, *([0] * frames)))


def _write_event_log(root: Path, ts: datetime, sentence: str = "Test incident.") -> None:
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"events-{ts.strftime('%Y-%m-%d')}.jsonl"
    rec = {
        "ts_utc": ts.isoformat(),
        "kind": "ship_first_heard",
        "sentence": sentence,
        "lat": 35.9,
        "lon": 14.51,
        "display_name": "TESTSHIP",
    }
    path.write_text(json.dumps(rec) + "\n", encoding="utf-8")


def test_voice_clips_only_retained_flagged(tmp_path):
    import wichita_ground_voice as gv
    import wichita_incident_replay as wir

    base = tmp_path / "gv"
    wav = tmp_path / "seg.wav"
    _write_wav(wav)
    started = datetime.now(timezone.utc)
    gv.submit_segment("marine-ch16", str(wav), started.timestamp(), scorer=lambda p, f: 20, base=base)
    low = wir.voice_clips_in_window(started - timedelta(minutes=1), started + timedelta(minutes=1), base=base)
    assert low == []

    wav2 = tmp_path / "seg2.wav"
    _write_wav(wav2)
    ev = gv.submit_segment("marine-ch16", str(wav2), started.timestamp(), scorer=lambda p, f: 85, base=base)
    clips = wir.voice_clips_in_window(started - timedelta(minutes=1), started + timedelta(minutes=1), base=base)
    assert len(clips) == 1
    assert clips[0]["clip_id"] == ev["clip"]
    assert clips[0]["playback_url"].startswith("/api/incident-replay/clips/")


def test_replay_frame_ships_and_assist(tmp_path, monkeypatch):
    import wichita_ais_tracks as wat
    import wichita_incident_replay as wir

    monkeypatch.setenv("WICHITA_AIS_SNAPSHOTS_DIR", str(tmp_path / "ais"))
    monkeypatch.setenv("WICHITA_ADSB_TRACKS_DIR", str(tmp_path / "adsb"))
    events_dir = tmp_path / "events"
    monkeypatch.setenv("WICHITA_EVENTS_DIR", str(events_dir))

    anchor = datetime.now(timezone.utc).replace(microsecond=0)
    _write_event_log(events_dir, anchor)

    store = wat.AisSnapshotStore()
    store.record_ships(
        [
            {
                "mmsi": 232031859,
                "lat": 35.901,
                "lon": 14.515,
                "speed_kn": 5.0,
                "display_name": "NEARBY",
                "shiptype_category": "cargo",
                "is_base_station": False,
            }
        ],
        ts=anchor,
    )

    adsb_root = tmp_path / "adsb"
    adsb_root.mkdir(parents=True, exist_ok=True)
    hex_id = "abc123"
    row = {
        "ts_utc": anchor.isoformat(),
        "hex": hex_id,
        "lat": 35.905,
        "lon": 14.52,
        "altitude_ft": 1200,
        "callsign": "TEST1",
    }
    (adsb_root / f"{hex_id}.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")

    frame = wir.replay_frame(anchor.isoformat(), anchor.isoformat(), window_min=30)
    assert frame is not None
    assert len(frame["ships"]) == 1
    assert frame["ships"][0]["display_name"] == "NEARBY"
    assert len(frame["aircraft"]) == 1
    assert frame["nearest_assist"][0]["kind"] == "vessel"


def test_scene_includes_voice_clip_count(tmp_path, monkeypatch):
    import wichita_ground_voice as gv
    import wichita_incident_replay as wir

    events_dir = tmp_path / "events"
    monkeypatch.setenv("WICHITA_EVENTS_DIR", str(events_dir))
    base = tmp_path / "gv"
    monkeypatch.setenv("WICHITA_GROUND_VOICE_DIR", str(base))

    anchor = datetime.now(timezone.utc).replace(microsecond=0)
    _write_event_log(events_dir, anchor)
    wav = tmp_path / "a.wav"
    _write_wav(wav)
    gv.submit_segment("air-121-5", str(wav), anchor.timestamp(), scorer=lambda p, f: 90, base=base)

    scene = wir.scene_by_ts(anchor.isoformat())
    assert scene is not None
    assert scene["voice_clip_count"] == 1
    assert scene["voice_clips"][0]["channel_id"] == "air-121-5"


def test_clip_route_and_path_guard(tmp_path, monkeypatch):
    import wichita_ground_voice as gv
    from fastapi import FastAPI
    from wichita_platform_routes import router

    base = tmp_path / "gv"
    monkeypatch.setenv("WICHITA_GROUND_VOICE_DIR", str(base))
    wav = base / "clips" / "marine-ch16-1.wav"
    _write_wav(wav)
    assert gv.resolve_clip_path("../etc/passwd", base=base) is None

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    assert client.get("/api/incident-replay/clips/marine-ch16-1.wav").status_code == 409
    monkeypatch.setenv("WICHITA_GROUND_VOICE_CLEARED", "true")
    res = client.get("/api/incident-replay/clips/marine-ch16-1.wav")
    assert res.status_code == 200
    assert res.headers.get("content-type", "").startswith("audio/")


def test_adsb_snapshot_nearest(tmp_path, monkeypatch):
    import wichita_adsb_tracks as wat

    monkeypatch.setenv("WICHITA_ADSB_TRACKS_DIR", str(tmp_path))
    now = datetime.now(timezone.utc).replace(microsecond=0)
    store = wat.AdsbTrackStore()
    store.record_snapshot(
        [{"hex": "a1b2c3", "lat": 35.9, "lon": 14.5, "callsign": "WX1"}],
        now.isoformat(),
    )
    planes = store.snapshot_nearest(now.isoformat(), max_delta_s=30)
    assert len(planes) == 1
    assert planes[0]["callsign"] == "WX1"
