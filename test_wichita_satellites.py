import os
from pathlib import Path

import wichita_satellites as ws

FIXTURE_TLE = Path(__file__).resolve().parent / "fixtures" / "celestrak_tle_cache.json"


def test_satellite_overview_with_fixture_cache(monkeypatch):
    monkeypatch.setenv("WICHITA_TLE_CACHE", str(FIXTURE_TLE))
    monkeypatch.setenv("WICHITA_TLE_SKIP_FETCH", "1")
    out = ws.satellite_overview()
    assert out["data_source"] == "computed"
    assert out["source_label"] == "Computed, not observed"
    assert "TLE" in (out.get("freshness_label") or "")
    assert len(out["satellites"]) >= 1
    iss = out["satellites"][0]
    assert iss["ground_track"]
    assert "next_passes" in iss
