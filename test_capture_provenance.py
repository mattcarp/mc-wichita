import json
import struct
import wave
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from capture_provenance import (
    MARITIME_CH16_MHZ,
    ProvenanceImportError,
    ProvenanceStatus,
    attach_sidecar_retro,
    import_capture,
    read_sidecar,
    sha256_file,
    sidecar_path_for,
    validate_sidecar_against_audio,
    write_sidecar,
)


def _write_labelled_synthetic_wav(path: Path, sample_rate: int = 48000) -> None:
    """Clearly synthetic PCM for provenance tests (not real RF, not genuine)."""
    frames = 2400
    samples = [int(500 * ((i % 17) - 8)) for i in range(frames)]
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(struct.pack(f"<{len(samples)}h", *samples))


def test_write_and_read_sidecar_verifies_hash(tmp_path: Path) -> None:
    wav = tmp_path / "SYNTHETIC_test_capture.wav"
    _write_labelled_synthetic_wav(wav)

    observed = datetime(2025, 9, 12, 19, 46, 56, tzinfo=timezone.utc)
    sidecar = write_sidecar(
        wav,
        frequency_hz=int(MARITIME_CH16_MHZ * 1_000_000),
        provenance_status=ProvenanceStatus.SYNTHETIC,
        observation_time=observed,
    )

    assert sidecar == sidecar_path_for(wav)
    document = json.loads(sidecar.read_text(encoding="utf-8"))
    assert document["global"]["wichita:provenance_status"] == "synthetic"
    assert document["global"]["wichita:audio_sha256"] == sha256_file(wav)

    read_back = read_sidecar(wav)
    assert read_back.document is not None
    errors, _warnings = validate_sidecar_against_audio(wav, read_back.document)
    assert errors == []


def test_import_without_sidecar_is_unverified_not_genuine(tmp_path: Path) -> None:
    wav = tmp_path / "SYNTHETIC_no_sidecar.wav"
    _write_labelled_synthetic_wav(wav)

    result = import_capture(wav)
    assert result.metadata["provenance_status"] == "unverified"
    assert "sidecar" in result.metadata["provenance_missing_fields"]
    assert "not-established-genuine" in result.tags


def test_import_rejects_hash_mismatch(tmp_path: Path) -> None:
    wav = tmp_path / "SYNTHETIC_hash_mismatch.wav"
    _write_labelled_synthetic_wav(wav)
    write_sidecar(
        wav,
        frequency_hz=int(MARITIME_CH16_MHZ * 1_000_000),
        provenance_status=ProvenanceStatus.SYNTHETIC,
        observation_time=datetime(2025, 9, 12, 19, 46, 56, tzinfo=timezone.utc),
    )

    with wav.open("r+b") as handle:
        handle.seek(100)
        handle.write(b"\x00")

    with pytest.raises(ProvenanceImportError, match="audio_sha256_mismatch"):
        import_capture(wav)


def test_import_with_valid_sidecar_sets_observed_at(tmp_path: Path) -> None:
    wav = tmp_path / "SYNTHETIC_with_sidecar.wav"
    _write_labelled_synthetic_wav(wav)
    write_sidecar(
        wav,
        frequency_hz=int(MARITIME_CH16_MHZ * 1_000_000),
        provenance_status=ProvenanceStatus.UNVERIFIED,
        observation_time=datetime(2025, 9, 12, 19, 46, 56, tzinfo=timezone.utc),
    )

    result = import_capture(wav)
    assert result.metadata["observed_at"] is not None
    assert result.metadata["provenance_status"] == "unverified"


def test_attach_retro_defaults_to_unknown_observation_time(tmp_path: Path) -> None:
    name = "REAL_RTL_CAPTURE_Maritime_CH16_156.8MHz_20250912_194656.wav"
    wav = tmp_path / name
    _write_labelled_synthetic_wav(wav)

    attach_sidecar_retro(wav, provenance_status=ProvenanceStatus.UNVERIFIED)
    document = json.loads(sidecar_path_for(wav).read_text(encoding="utf-8"))
    assert document["captures"] == []
    assert document["global"]["wichita:provenance_status"] == "unverified"


def test_api_import_endpoint_does_not_dispatch(tmp_path: Path, monkeypatch) -> None:
    import sys
    import types

    api_maritime_aviation_stub = types.ModuleType("api_maritime_aviation")
    api_maritime_aviation_stub.add_maritime_aviation_routes = lambda app: app
    sys.modules["api_maritime_aviation"] = api_maritime_aviation_stub

    from fastapi.testclient import TestClient

    import api_server

    wav = tmp_path / "SYNTHETIC_api_import.wav"
    _write_labelled_synthetic_wav(wav)
    write_sidecar(
        wav,
        frequency_hz=int(MARITIME_CH16_MHZ * 1_000_000),
        provenance_status=ProvenanceStatus.SYNTHETIC,
        observation_time=datetime(2025, 9, 12, 19, 46, 56, tzinfo=timezone.utc),
    )

    dispatch_calls = []
    monkeypatch.setattr(
        api_server,
        "_dispatch_alert_to_mission_control",
        lambda alert: dispatch_calls.append(alert.id),
    )
    monkeypatch.setattr(api_server, "send_stress_alert", lambda *args, **kwargs: True)
    monkeypatch.setattr(api_server, "send_discord_alert", lambda *args, **kwargs: True)

    client = TestClient(api_server.app)
    response = client.post("/imports/provenance-capture", params={"audio_path": str(wav)})

    assert response.status_code == 200
    body = response.json()
    assert body["metadata"]["provenance_status"] == "synthetic"
    assert dispatch_calls == []

    evidence = client.get(f"/alerts/{body['id']}/evidence")
    assert evidence.status_code == 200
    assert evidence.json()["age_seconds"] is not None
