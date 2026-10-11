import os
import sys
import types
import wave
from pathlib import Path

import numpy as np

api_maritime_aviation_stub = types.ModuleType("api_maritime_aviation")
api_maritime_aviation_stub.add_maritime_aviation_routes = lambda app: app
sys.modules["api_maritime_aviation"] = api_maritime_aviation_stub

from fastapi.testclient import TestClient

import api_server

client = TestClient(api_server.app)

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "20261009T001230Z_voice"


def _write_wav(path: Path, seconds: float = 1.0, sr: int = 16000) -> None:
    t = np.arange(int(sr * seconds)) / sr
    samples = (0.2 * np.sin(2 * np.pi * 180 * t)).astype(np.float32)
    pcm = (np.clip(samples, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())


def test_voice_lab_status_banner() -> None:
    payload = client.get("/voice-lab/status").json()
    assert payload["feeds_alerts"] is False
    assert "TEST MICROPHONE" in payload["banner"]
    assert payload["source_tag"] == "test-mic"


def test_voice_lab_analyze_upload_does_not_create_alerts(tmp_path) -> None:
    wav = tmp_path / "lab_clip.wav"
    _write_wav(wav)

    before = len(client.get("/alerts").json())
    with wav.open("rb") as fh:
        response = client.post(
            "/voice-lab/analyze",
            files={"file": ("lab_clip.wav", fh, "audio/wav")},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "test-mic"
    assert body["not_evidence"] is True
    assert "stress" in body
    assert "implicit_distress" in body
    assert len(client.get("/alerts").json()) == before


def test_fixture_voice_manifest_present() -> None:
    manifest = FIXTURE_ROOT / "manifest.json"
    assert manifest.is_file()
    import json

    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data.get("provenance_status") == "genuine"
    assert "CH16_156p800MHz_nfm_16k.wav" in data.get("files", {})


def test_voice_lab_fixture_wav_when_present(tmp_path) -> None:
    """Use real fixture WAV when checked out; otherwise skip honestly."""
    candidate = FIXTURE_ROOT / "CH16_156p800MHz_nfm_16k.wav"
    if not candidate.is_file():
        return

    with candidate.open("rb") as fh:
        response = client.post(
            "/voice-lab/analyze",
            files={"file": (candidate.name, fh, "audio/wav")},
        )
    assert response.status_code == 200
    body = response.json()
    assert 0 <= body["stress"]["stress_score"] <= 100
