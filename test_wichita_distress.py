"""Marine distress decoders — real public fixtures only."""

from __future__ import annotations

from pathlib import Path

import pytest

from wichita_distress import decode_dsc_file, decode_epirb_file, ingest_dsc_messages

FIX = Path(__file__).resolve().parent / "fixtures" / "distress"

# SDRangel GitHub issue #1707 — routine_call.zip
DSC_WAV = FIX / "routine_call.wav"
# Same issue — selective_individual_call_2 sdriq (IQ replay gap documented in SOURCES.md)
DSC_SDRIQ = FIX / "selective_individual_call_2.2023-06-03T19_21_59_833.sdriq"
# HTCommander src/test/sarsat_samples/sarsat_selftest_beacon.wav
SARSAT_WAV = FIX / "sarsat_selftest_beacon.wav"


def test_dsc_decode_routine_call_wav():
    msgs = decode_dsc_file(DSC_WAV)
    assert len(msgs) >= 1
    m = msgs[0]
    assert m.get("address_mmsi") == "233333334"
    assert m.get("self_id_mmsi") == "201444555"
    assert m.get("is_valid") is True


@pytest.mark.xfail(reason="sdriq IQ FM chain not verified on this fixture yet — see fixtures/distress/SOURCES.md")
def test_dsc_decode_sdriq_selective_call():
    msgs = decode_dsc_file(DSC_SDRIQ)
    assert len(msgs) >= 1


def test_sarsat_decode_selftest_wav():
    frames = decode_epirb_file(SARSAT_WAV)
    assert len(frames) == 1
    f = frames[0]
    assert f["hex_id"] == "1C72091A2B3FDFF"
    assert f["country_code"] == 227
    assert f["crc1_ok"] and f["crc2_ok"]
    assert abs(f["latitude"] - 42.954) < 0.01
    assert abs(f["longitude"] - 1.364) < 0.01


def test_dsc_distress_priority_maps_to_timeline_kind(monkeypatch):
    events = []

    def _fake_append(kind, sentence, **fields):
        rec = {"kind": kind, "sentence": sentence, **fields}
        events.append(rec)
        return rec

    monkeypatch.setattr("wichita_distress.append_event", _fake_append)
    monkeypatch.setattr("wichita_distress.alert_store.append_alert_record", lambda _r: None)

    routine = {"format_code": 120, "category": "Routine", "self_id_mmsi": "201444555"}
    assert ingest_dsc_messages([routine], source="test") == []
    distress = {
        "format_code": 112,
        "category": "Distress",
        "self_id_mmsi": "201444555",
        "distress_nature": "Fire, explosion",
        "is_valid": True,
        "confidence": 1.0,
    }
    raised = ingest_dsc_messages([distress], source="test")
    assert len(raised) == 1
    assert events[0]["kind"] == "marine_distress_dsc"
