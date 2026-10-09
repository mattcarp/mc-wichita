import os
import subprocess
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


def test_station_snapshot_from_capture_settings():
    ref = wc.resolve_capture("20261009T002803Z")
    snap = wc.station_snapshot_from_capture(ref)
    assert snap["device_serial"] == "2403090170"
    assert snap["bias_t"] == "false"
    assert snap["overflows"] == 0
    assert snap["noise_rms_dbfs"] == -39.26
    assert "002803Z" in snap["source_label"]


def test_timeline_events_expose_time_utc():
    ref = wc.resolve_capture("20261009T002803Z")
    detail = wc.capture_detail(ref)
    summaries = [e for e in detail["timeline"] if e.get("kind") == "ais_summary"]
    assert summaries
    assert "time_utc" in summaries[0]
    assert "time_malta" not in summaries[0]
    assert summaries[0]["time_utc"].endswith("+00:00") or summaries[0]["time_utc"].endswith("Z")


def test_timeline_uses_malta_in_ais_summary():
    ref = wc.resolve_capture("20261009T002803Z")
    detail = wc.capture_detail(ref)
    summaries = [e for e in detail["timeline"] if e.get("kind") == "ais_summary"]
    assert summaries
    assert "Malta" in summaries[0]["detail"]
    assert "UTC" not in summaries[0]["detail"]


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


def test_psd_plot_span_from_sigmf():
    ref = wc.resolve_capture("20261009T002803Z")
    psd = wc.load_wideband_psd(ref.path, max_points=500)
    assert psd["plot_min_mhz"] < 156.3
    assert psd["plot_max_mhz"] > 162.2
    assert psd["freq_mhz"][0] >= psd["plot_min_mhz"] - 0.001
    assert psd["draw_max_mhz"] < psd["plot_max_mhz"]
    assert psd["draw_min_mhz"] > psd["plot_min_mhz"] + 0.2
    assert "CH09 at band edge" in " ".join(psd.get("span_notes") or [])
    assert "CH70 at band edge" in " ".join(psd.get("span_notes") or [])
    assert max(psd["freq_mhz"]) >= psd["draw_max_mhz"] - 0.01
    assert min(psd["freq_mhz"]) <= psd["draw_min_mhz"] + 0.01
    assert "AIS2 near band edge" in " ".join(psd.get("span_notes") or [])
    assert "trace starts" in psd.get("span_caption", "")
    assert psd.get("span_caption")

    indoor = wc.resolve_capture("20261009T001016Z")
    psd_in = wc.load_wideband_psd(indoor.path, max_points=500)
    assert psd_in["iq_center_mhz"] == 159.4125
    assert psd_in["plot_min_mhz"] > 156.4


def test_spectrum_x_alignment_node():
    root = Path(__file__).resolve().parent
    subprocess.run(
        ["node", "--test", "dashboard/spectrum_x_alignment_test.mjs"],
        cwd=root,
        check=True,
    )


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
