import json
from pathlib import Path
from unittest.mock import patch

import pytest

import wichita_satellites as ws

FIXTURE_TLE = Path(__file__).resolve().parent / "fixtures" / "celestrak_tle_cache.json"


def _iss_tle_lines():
    cache = json.loads(FIXTURE_TLE.read_text(encoding="utf-8"))
    return cache["satellites"]["25544"]["tle"]


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


def test_parse_tle_rejects_missing_line1():
    name, _l1, l2 = _iss_tle_lines()
    body = "\n".join(["<html>error</html>", name, l2, "trailing noise"])
    with pytest.raises(ValueError):
        ws._parse_tle_response(body, 25544)


def test_parse_tle_rejects_missing_line2():
    name, l1, _l2 = _iss_tle_lines()
    body = "\n".join([name, l1, "not a tle line"])
    with pytest.raises(ValueError):
        ws._parse_tle_response(body, 25544)


def test_parse_tle_rejects_garbage_body():
    body = "Service Unavailable\nPlease try again later.\n404"
    with pytest.raises(ValueError):
        ws._parse_tle_response(body, 25544)


def test_parse_tle_accepts_valid_fixture_body():
    name, l1, l2 = _iss_tle_lines()
    body = "\n".join([name, l1, l2])
    tle = ws._parse_tle_response(body, 25544)
    assert tle == [name, l1, l2]


def test_satellite_overview_skips_bad_cache_entry(monkeypatch, tmp_path):
    cache = json.loads(FIXTURE_TLE.read_text(encoding="utf-8"))
    cache["satellites"]["25544"] = {
        "name": "ISS (ZARYA)",
        "norad": 25544,
        "tle": ["ISS", "not line 1", "not line 2 either"],
    }
    bad_cache = tmp_path / "bad_mixed.json"
    bad_cache.write_text(json.dumps(cache), encoding="utf-8")
    monkeypatch.setenv("WICHITA_TLE_CACHE", str(bad_cache))
    monkeypatch.setenv("WICHITA_TLE_SKIP_FETCH", "1")
    out = ws.satellite_overview()
    norads = {s["norad"] for s in out["satellites"]}
    assert 25544 not in norads
    assert 25338 in norads


def test_refresh_tle_cache_keeps_previous_tle_on_fetch_failure(monkeypatch, tmp_path):
    cache_path = tmp_path / "tle_cache.json"
    prior = json.loads(FIXTURE_TLE.read_text(encoding="utf-8"))
    prior["satellites"]["25544"]["tle_fetched_at_utc"] = prior["fetched_at_utc"]
    cache_path.write_text(json.dumps(prior), encoding="utf-8")
    monkeypatch.setenv("WICHITA_TLE_CACHE", str(cache_path))
    monkeypatch.delenv("WICHITA_TLE_SKIP_FETCH", raising=False)

    good_iss = prior["satellites"]["25544"]["tle"]
    good_noaa = prior["satellites"]["25338"]["tle"]

    def fake_fetch(norad: int):
        if norad == 25544:
            raise ValueError("simulated CelesTrak failure")
        if norad == 25338:
            return good_noaa
        entry = prior["satellites"].get(str(norad))
        if entry:
            return entry["tle"]
        raise ValueError(f"no fixture for {norad}")

    with patch.object(ws, "_fetch_tle_lines", side_effect=fake_fetch):
        refreshed = ws.refresh_tle_cache(force=True)

    assert "25544" in refreshed["satellites"]
    assert refreshed["satellites"]["25544"]["tle"] == good_iss
    assert refreshed["satellites"]["25338"]["tle"] == good_noaa
    saved = json.loads(cache_path.read_text(encoding="utf-8"))
    assert saved["satellites"]["25544"]["tle"] == good_iss
