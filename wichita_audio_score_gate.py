"""Skip sentiment/stress scoring when audio quality or receiver state makes scores unreliable."""

from __future__ import annotations

import os
import threading
import time
import wave
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np

RETUNE_GUARD_SEC = float(os.environ.get("WICHITA_RETUNE_GUARD_SEC", "1.5"))
CLIP_PEAK_RATIO = float(os.environ.get("WICHITA_CLIP_PEAK_RATIO", "0.98"))
CLIP_SAMPLE_FRACTION = float(os.environ.get("WICHITA_CLIP_SAMPLE_FRACTION", "0.005"))

_RETUNE_LOCK = threading.Lock()
_LAST_TUNE_MONO: Optional[float] = None


def register_retune(at_mono: Optional[float] = None) -> None:
    """Record that the receiver re-tuned (receive-only scheduler / driver hook)."""
    global _LAST_TUNE_MONO
    with _RETUNE_LOCK:
        _LAST_TUNE_MONO = at_mono if at_mono is not None else time.monotonic()


def clear_retune_state() -> None:
    """Test helper: clear last retune marker."""
    global _LAST_TUNE_MONO
    with _RETUNE_LOCK:
        _LAST_TUNE_MONO = None


def seconds_since_retune(now_mono: Optional[float] = None) -> Optional[float]:
    with _RETUNE_LOCK:
        if _LAST_TUNE_MONO is None:
            return None
        now = now_mono if now_mono is not None else time.monotonic()
        return max(0.0, now - _LAST_TUNE_MONO)


def _clipping_metrics(wav_path: str) -> Tuple[float, float]:
    """Return (peak_ratio, clipped_fraction) for 16-bit PCM WAV."""
    with wave.open(wav_path, "rb") as w:
        n = w.getnframes()
        if n == 0:
            return 0.0, 0.0
        raw = w.readframes(n)
    if len(raw) < 2:
        return 0.0, 0.0
    samples = np.frombuffer(raw, dtype=np.int16)
    if samples.size == 0:
        return 0.0, 0.0
    peak = float(np.max(np.abs(samples)))
    peak_ratio = peak / 32767.0
    clip_mask = np.abs(samples) >= 32767
    clipped_fraction = float(np.mean(clip_mask))
    return peak_ratio, clipped_fraction


def score_skip_reason(
    wav_path: str,
    *,
    segment_meta: Optional[Dict[str, Any]] = None,
    now_mono: Optional[float] = None,
) -> Optional[str]:
    """Return human reason if scoring should be skipped, else None."""
    meta = segment_meta or {}
    if meta.get("retune_in_progress") or meta.get("during_retune"):
        return "not scored: retune"
    if meta.get("clipping") or meta.get("is_clipping"):
        return "not scored: clipping"
    since = meta.get("seconds_since_retune")
    if since is None:
        since = seconds_since_retune(now_mono)
    if since is not None and since < RETUNE_GUARD_SEC:
        return "not scored: retune"
    try:
        peak_ratio, clipped_fraction = _clipping_metrics(wav_path)
    except (wave.Error, OSError, EOFError):
        return None
    if peak_ratio >= CLIP_PEAK_RATIO or clipped_fraction >= CLIP_SAMPLE_FRACTION:
        return "not scored: clipping"
    peak_dbfs = meta.get("peak_dbfs")
    if peak_dbfs is not None:
        try:
            if float(peak_dbfs) >= -0.5:
                return "not scored: clipping"
        except (TypeError, ValueError):
            pass
    return None


def gated_stress_result(
    wav_path: str,
    frequency_hz: Optional[float],
    scorer,
    *,
    segment_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run scorer unless skip reason applies; always returns an event-shaped dict."""
    reason = score_skip_reason(wav_path, segment_meta=segment_meta)
    if reason:
        return {
            "skipped": True,
            "skip_reason": reason,
            "stress_score": None,
            "score": None,
            "model": "stress_scorer (placeholder)",
        }
    res = scorer(wav_path, frequency_hz)
    score = int(getattr(res, "stress_score", getattr(res, "score", res if isinstance(res, (int, float)) else 0)))
    return {
        "skipped": False,
        "skip_reason": None,
        "stress_score": score,
        "score": score,
        "model": "stress_scorer (placeholder)",
        "raw": res,
    }


def thresholds_summary() -> Dict[str, Any]:
    return {
        "retune_guard_sec": RETUNE_GUARD_SEC,
        "clip_peak_ratio": CLIP_PEAK_RATIO,
        "clip_sample_fraction": CLIP_SAMPLE_FRACTION,
    }