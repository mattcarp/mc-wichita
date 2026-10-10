import os
from pathlib import Path

import wichita_watch_zones as wz


def test_point_in_polygon_and_persist(tmp_path, monkeypatch):
    zfile = tmp_path / "zones.json"
    monkeypatch.setenv("WICHITA_WATCH_ZONES_FILE", str(zfile))
    poly = [[35.88, 14.49], [35.88, 14.54], [35.92, 14.54], [35.92, 14.49]]
    rec = wz.upsert_zone("Test harbour", poly)
    assert rec["id"]
    assert wz.point_in_polygon(35.9, 14.51, poly)
    assert not wz.point_in_polygon(35.8, 14.4, poly)
    inside: dict = {}
    entered = wz.check_vessel_zones(123456789, 35.9, 14.51, inside)
    assert len(entered) == 1
    assert wz.check_vessel_zones(123456789, 35.9, 14.51, inside) == []
