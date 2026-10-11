import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import wichita_ais_tracks as wat


def test_snapshot_roundtrip_and_activity(tmp_path, monkeypatch):
    monkeypatch.setenv("WICHITA_AIS_SNAPSHOTS_DIR", str(tmp_path))
    monkeypatch.setenv("WICHITA_AIS_TRACK_HOURS", "48")
    store = wat.AisSnapshotStore()
    now = datetime.now(timezone.utc)
    ships = [
        {
            "mmsi": 232031859,
            "lat": 35.89,
            "lon": 14.51,
            "speed_kn": 10.0,
            "display_name": "TESTSHIP",
            "shiptype_category": "cargo",
            "is_base_station": False,
        }
    ]
    store.record_ships(ships, ts=now)
    meta = store.timeline_meta(hours=48)
    assert meta["snapshot_count"] == 1
    snap = store.snapshot_nearest(now.isoformat(), max_delta_s=5)
    assert snap is not None
    assert snap["ships"][0]["mmsi"] == 232031859
    buckets = store.activity_by_type(hours=24)
    assert len(buckets) == 24
    assert buckets[-1]["vessels_total"] >= 1
    assert buckets[-1]["by_type"].get("cargo", 0) >= 1


def test_trim_drops_old_rows(tmp_path, monkeypatch):
    monkeypatch.setenv("WICHITA_AIS_SNAPSHOTS_DIR", str(tmp_path))
    monkeypatch.setenv("WICHITA_AIS_TRACK_HOURS", "1")
    store = wat.AisSnapshotStore()
    old = datetime.now(timezone.utc) - timedelta(hours=3)
    store.record_ships(
        [{"mmsi": 1, "lat": 35.9, "lon": 14.5, "shiptype_category": "other", "is_base_station": False}],
        ts=old,
    )
    path = tmp_path / "snapshots.jsonl"
    assert path.is_file()
    store.record_ships(
        [{"mmsi": 2, "lat": 35.9, "lon": 14.5, "shiptype_category": "other", "is_base_station": False}],
    )
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["ships"][0]["mmsi"] == 2
