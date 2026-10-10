import json
from pathlib import Path

import wichita_watch_zones as wwz


def test_point_in_polygon_square(tmp_path, monkeypatch):
    monkeypatch.setenv("WICHITA_WATCH_ZONES_FILE", str(tmp_path / "zones.json"))
    ring = [[14.5, 35.9], [14.52, 35.9], [14.52, 35.92], [14.5, 35.92], [14.5, 35.9]]
    assert wwz.point_in_polygon(35.91, 14.51, ring)
    assert not wwz.point_in_polygon(35.95, 14.51, ring)


def test_upsert_zone(tmp_path, monkeypatch):
    monkeypatch.setenv("WICHITA_WATCH_ZONES_FILE", str(tmp_path / "zones.json"))
    z = wwz.upsert_zone({"id": "marsamxett", "name": "Marsamxett", "polygon": [[14.49, 35.9], [14.5, 35.9], [14.5, 35.91]]})
    assert z["id"] == "marsamxett"
    assert len(wwz.list_zones()) == 1
