import os
import sys
import types
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).resolve().parent / "fixtures"

api_maritime_aviation_stub = types.ModuleType("api_maritime_aviation")
api_maritime_aviation_stub.add_maritime_aviation_routes = lambda app: app
sys.modules.setdefault("api_maritime_aviation", api_maritime_aviation_stub)

import wichita_captures as wc


@pytest.fixture(autouse=True)
def captures_env(monkeypatch):
    monkeypatch.setenv("WICHITA_CAPTURES_DIRS", str(FIXTURES))


def test_scan_finds_fixture_folders():
    refs = wc.scan_captures()
    ids = {r.capture_id for r in refs}
    assert "20261009T001016Z" in ids
    assert "20261009T002803Z" in ids


def test_capture_summary_provenance():
    ref = wc.resolve_capture("20261009T001016Z")
    assert ref is not None
    summary = wc.capture_summary(ref)
    assert summary["provenance_status"] == "genuine"
    assert "Indoor" in (summary["location"] or "")
    assert summary["ais_message_count"] >= 1


def test_ais_labels_valletta_base():
    ref = wc.resolve_capture("20261009T002803Z")
    assert ref is not None
    analysis = wc._read_json(ref.path / "analysis_report.json") or {}
    messages = wc.decode_ais_from_nmea(ref.path, analysis)
    assert messages
    labeled = [m for m in messages if m.get("label") == "Valletta AIS base station"]
    assert labeled


def test_wideband_psd_downsampled():
    ref = wc.resolve_capture("20261009T001016Z")
    psd = wc.load_wideband_psd(ref.path, max_points=100)
    assert psd["available"] is True
    assert len(psd["freq_mhz"]) <= 100
    assert len(psd["freq_mhz"]) == len(psd["psd_db_per_hz"])


def test_airband_scan_payload():
    ref = wc.resolve_capture("20261009T002803Z")
    air = wc.airband_payload(ref.path)
    assert air["available"] is True
    assert len(air["channels"]) > 10
    spur_tags = [c for c in air["channels"] if c.get("tag") == "known local spur"]
    assert spur_tags


def test_capture_feed_api_dashboard():
    import api_server

    client = TestClient(api_server.app)
    res = client.get("/api/capture-feed/dashboard")
    assert res.status_code == 200
    body = res.json()
    assert body["available"] is True
    assert body["primary_capture_id"] == "20261009T002803Z"
    assert body["primary"]["ais"]


def test_health_no_hackrf_field():
    import api_server

    client = TestClient(api_server.app)
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert "hackrf_status" not in data
    assert data["captures_on_disk"] >= 2


def test_timeline_groups_routine_ais():
    ref = wc.resolve_capture("20261009T002803Z")
    assert ref is not None
    detail = wc.capture_detail(ref)
    timeline = detail["timeline"]
    per_burst = [e for e in timeline if e.get("kind") == "ais"]
    summaries = [e for e in timeline if e.get("kind") == "ais_summary"]
    assert len(per_burst) == 0
    assert len(summaries) >= 1
    assert "Valletta AIS base station" in summaries[0]["title"]
    assert summaries[0].get("grouped") is True


def test_psd_trims_low_edge():
    ref = wc.resolve_capture("20261009T001016Z")
    psd = wc.load_wideband_psd(ref.path, max_points=500)
    assert psd["freq_mhz"][0] >= wc.MARINE_PSD_MIN_MHZ - 0.001
    assert psd.get("trim_note")


def test_antenna_power_rejected():
    import api_server

    client = TestClient(api_server.app)
    res = client.post(
        "/capture/signal",
        json={
            "frequency": 156800000,
            "sample_rate": 2000000,
            "duration": 0.1,
            "gain": 20,
            "amp_enable": False,
            "antenna_power": True,
        },
    )
    assert res.status_code == 403
