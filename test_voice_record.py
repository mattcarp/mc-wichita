"""voice_record against a real receiver capture (REAL_RTL_CAPTURE ch16, 2025-09-12).

The clip's provenance is unverified, so every record built from it says so.
"""

import shutil
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import alert_store
import voice_record as vr
from capture_provenance import ProvenanceStatus, read_sidecar

REAL_CH16 = Path(__file__).parent / "REAL_RTL_CAPTURE_Maritime_CH16_156.8MHz_20250912_194656.wav"
START = datetime(2025, 9, 12, 17, 46, 56, tzinfo=timezone.utc)


@pytest.fixture
def clip(tmp_path, monkeypatch):
    monkeypatch.setenv("WICHITA_ALERTS_DIR", str(tmp_path / "alerts"))
    dst = tmp_path / REAL_CH16.name
    shutil.copy(REAL_CH16, dst)
    return dst


def test_minimal_record_lists_every_unknown(clip):
    rec = vr.build_voice_record(clip, frequency_mhz=156.8, mode="nfm", observed_start=START)
    meta = rec["metadata"]
    assert rec["signal_type"] == "marine_vhf"
    assert meta["unknown_fields"] == list(vr.OPTIONAL_FIELDS)
    assert rec["transcript"] is None and meta["scores"] is None
    assert "not-established-genuine" in rec["tags"]
    assert meta["observed_end_source"] == "start_plus_clip_duration"
    assert abs(meta["clip_duration_sec"] - 5.0) < 0.1
    assert meta["observed_start_utc"].endswith("+00:00")


def test_sidecar_written_and_matches_clip(clip):
    vr.build_voice_record(clip, frequency_mhz=156.8, mode="nfm", observed_start=START,
                          hw="RTL-SDR Blog V4, gain 40 dB")
    side = read_sidecar(clip)
    assert not side.errors
    g = side.document["global"]
    assert g["wichita:frequency_hz"] == 156_800_000
    assert g["wichita:provenance_status"] == "unverified"
    assert g["core:hw"] == "RTL-SDR Blog V4, gain 40 dB"


def test_naive_time_refused(clip):
    with pytest.raises(vr.VoiceRecordError, match="timezone-aware"):
        vr.build_voice_record(clip, frequency_mhz=156.8, mode="nfm",
                              observed_start=START.replace(tzinfo=None))


def test_bad_mode_and_reversed_times_refused(clip):
    with pytest.raises(vr.VoiceRecordError):
        vr.build_voice_record(clip, frequency_mhz=156.8, mode="wfm", observed_start=START)
    with pytest.raises(vr.VoiceRecordError):
        vr.build_voice_record(clip, frequency_mhz=156.8, mode="nfm", observed_start=START,
                              observed_end=START - timedelta(seconds=1))


def test_unsure_transcript_kept_and_tagged(clip):
    rec = vr.build_voice_record(clip, frequency_mhz=156.8, mode="nfm", observed_start=START,
                                transcript="radio check", language="en",
                                transcript_confidence=0.31, scores={"stress": 0.2})
    assert rec["transcript"] == "radio check"
    assert "transcript:unsure" in rec["tags"]
    assert "transcript" not in rec["metadata"]["unknown_fields"]
    assert rec["confidence"] == 0.2


def test_signal_type_mapping():
    assert vr.signal_type_for(121.5) == "emergency"
    assert vr.signal_type_for(145.5) == "amateur"
    assert vr.signal_type_for(433.5) == "amateur"
    assert vr.signal_type_for(27.065) == "unknown"


def test_persisted_record_loads_into_review_queue(clip):
    rec = vr.build_voice_record(clip, frequency_mhz=156.8, mode="nfm", observed_start=START)
    vr.persist_voice_record(rec)
    rows = alert_store.load_alert_records()
    assert [r["id"] for r in rows] == [rec["id"]]

    stub = types.ModuleType("api_maritime_aviation")
    stub.add_maritime_aviation_routes = lambda app: app
    sys.modules.setdefault("api_maritime_aviation", stub)
    import api_server

    loaded = api_server.AlertRecord(**rows[0])
    assert loaded.review_status.value == "pending_review"
    assert loaded.signal_type.value == "marine_vhf"
    assert loaded.metadata["unknown_fields"] == list(vr.OPTIONAL_FIELDS)
