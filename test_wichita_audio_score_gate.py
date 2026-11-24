"""Sentiment/stress gate: retune and clipping."""

import struct
import time
import wave
from pathlib import Path

import pytest

import wichita_audio_score_gate as gate


def _write_wav(path: Path, samples, *, peak: int = 2000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        frames = struct.pack(f"<{len(samples)}h", *samples)
        w.writeframes(frames)


def test_retune_guard_skips(monkeypatch, tmp_path):
    monkeypatch.setenv("WICHITA_RETUNE_GUARD_SEC", "2.0")
    gate.register_retune()
    wav = tmp_path / "a.wav"
    _write_wav(wav, [0] * 800)
    reason = gate.score_skip_reason(str(wav))
    assert reason == "not scored: retune"


def test_retune_meta_flag(tmp_path):
    wav = tmp_path / "b.wav"
    _write_wav(wav, [0] * 800)
    reason = gate.score_skip_reason(str(wav), segment_meta={"during_retune": True})
    assert reason == "not scored: retune"


def test_clipping_by_peak(tmp_path, monkeypatch):
    gate.clear_retune_state()
    monkeypatch.setenv("WICHITA_CLIP_PEAK_RATIO", "0.98")
    wav = tmp_path / "c.wav"
    _write_wav(wav, [32767] * 400 + [1000] * 400)
    reason = gate.score_skip_reason(str(wav))
    assert reason == "not scored: clipping"


def test_gated_stress_result_returns_skip(tmp_path):
    gate.clear_retune_state()
    wav = tmp_path / "d.wav"
    _write_wav(wav, [32767] * 800)

    def scorer(_p, _f):
        raise AssertionError("scorer should not run")

    out = gate.gated_stress_result(str(wav), 121_500_000, scorer)
    assert out["skipped"] is True
    assert out["skip_reason"] == "not scored: clipping"


def test_thresholds_summary_exposes_keys():
    summary = gate.thresholds_summary()
    assert set(summary) >= {"retune_guard_sec", "clip_peak_ratio", "clip_sample_fraction"}