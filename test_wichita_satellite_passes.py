"""Pass predictions vs reference values (same TLE snapshot as Mini)."""

import json
from datetime import datetime, timezone
from pathlib import Path

from sgp4.api import Satrec

import wichita_satellites as ws

FIXTURE_TLE = Path(__file__).resolve().parent / "fixtures" / "celestrak_tle_cache.json"
# Reference window: ~16:00 Malta on 9 Oct 2026 (search from 14:00 UTC).
SEARCH_START = datetime(2026, 10, 9, 14, 0, 0, tzinfo=timezone.utc)


def _sat(norad: int) -> Satrec:
    cache = json.loads(FIXTURE_TLE.read_text(encoding="utf-8"))
    lines = cache["satellites"][str(norad)]["tle"]
    return Satrec.twoline2rv(lines[1], lines[2])


def _first_pass(norad: int):
    sat = _sat(norad)
    passes = ws.next_passes(sat, "", norad, SEARCH_START, hours=12)
    return passes[0] if passes else None


def test_iss_pass_malta():
    p = _first_pass(25544)
    assert p is not None
    assert p["max_time_malta"] == "09 Oct 16:06"
    assert 50 <= p["max_elevation_deg"] <= 55


def test_noaa15_pass_not_false_noon():
    p = _first_pass(25338)
    assert p is not None
    assert p["max_time_malta"] == "09 Oct 18:22"
    assert 20 <= p["max_elevation_deg"] <= 25
    assert "16:47" not in p["max_time_malta"]


def test_noaa18_evening_pass():
    p = _first_pass(28654)
    assert p is not None
    assert p["max_time_malta"] == "09 Oct 22:30"
    assert 26 <= p["max_elevation_deg"] <= 31


def test_meteor_m2_3_high_pass():
    p = _first_pass(57189)
    assert p is not None
    assert p["max_time_malta"] == "09 Oct 23:08"
    assert 77 <= p["max_elevation_deg"] <= 83


def test_tle_provenance_fresh():
    cache = json.loads(FIXTURE_TLE.read_text(encoding="utf-8"))
    from datetime import timedelta

    now = datetime.fromisoformat(cache["fetched_at_utc"].replace("Z", "+00:00")) + timedelta(
        seconds=30
    )
    prov = ws._satellite_provenance(cache["fetched_at_utc"], now)
    assert prov["freshness_label"] == "TLE just updated"
