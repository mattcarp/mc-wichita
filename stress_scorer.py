"""
Kenneth Voice Stress Scorer
Analyzes audio to detect stress/panic/exhaustion from vocal features.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional
import json
import os

# Ensure numba/librosa can cache in writable locations in restricted environments.
os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache")
import librosa
import numpy as np


@dataclass
class StressResult:
    timestamp: str
    audio_path: str
    duration_s: float
    stress_score: int  # 0-100
    alert_level: str  # LOW / MEDIUM / HIGH / CRITICAL
    indicators: list[str]  # ["elevated_pitch", "high_speech_rate", ...]
    features: dict  # raw feature values for debugging


def _safe_mean(values: np.ndarray) -> float:
    if values.size == 0:
        return 0.0
    return float(np.mean(values))


def _safe_std(values: np.ndarray) -> float:
    if values.size == 0:
        return 0.0
    return float(np.std(values))


def _clamp(value: float, low: float, high: float) -> float:
    return float(max(low, min(value, high)))


def _alert_level(score: int) -> str:
    if score <= 30:
        return "LOW"
    if score <= 55:
        return "MEDIUM"
    if score <= 79:
        return "HIGH"
    return "CRITICAL"


def score_stress(audio_path: str, frequency: Optional[float] = None) -> StressResult:
    """Score voice stress from an audio file. Returns StressResult."""
    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        # mono=True ensures stereo/other channel layouts are mixed down consistently.
        y, sr = librosa.load(audio_path, sr=None, mono=True)
    except Exception as exc:
        raise ValueError(f"Failed to load audio file '{audio_path}': {exc}") from exc

    duration_s = float(librosa.get_duration(y=y, sr=sr)) if y.size else 0.0

    # Very short files are not reliable for pitch/rhythm features.
    if duration_s < 0.5 or y.size == 0:
        features = {
            "sample_rate": int(sr),
            "frequency": float(frequency) if frequency is not None else None,
            "f0_mean": 0.0,
            "f0_std": 0.0,
            "zcr_mean": 0.0,
            "spec_centroid_mean": 0.0,
            "jitter": 0.0,
            "silence_ratio": 1.0 if y.size else 0.0,
            "shimmer": 0.0,
            "components": {
                "f0_instability": 0.0,
                "zcr_component": 0.0,
                "centroid_component": 0.0,
                "jitter_component": 0.0,
                "silence_component": 0.0,
            },
        }
        return StressResult(
            timestamp=timestamp,
            audio_path=audio_path,
            duration_s=duration_s,
            stress_score=0,
            alert_level="LOW",
            indicators=[],
            features=features,
        )

    # Core features
    f0, voiced_flag, _ = librosa.pyin(y, fmin=50, fmax=500)
    voiced_f0 = f0[~np.isnan(f0)] if f0 is not None else np.array([], dtype=np.float32)
    f0_mean = _safe_mean(voiced_f0)
    f0_std = _safe_std(voiced_f0)

    zcr = librosa.feature.zero_crossing_rate(y)
    zcr_mean = _safe_mean(zcr)

    spec_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
    spec_centroid_mean = _safe_mean(spec_centroid)

    rms = librosa.feature.rms(y=y)
    rms_values = np.squeeze(rms)

    # Jitter: frame-to-frame F0 change spread on voiced frames.
    jitter = 0.0
    if voiced_f0.size > 1:
        jitter = _safe_std(np.diff(voiced_f0))

    # Silence ratio: fraction of RMS frames below threshold.
    silence_ratio = float(np.mean(rms_values < 0.01)) if rms_values.size else 0.0

    # Shimmer: variation of frame energy (RMS).
    shimmer = _safe_std(rms_values)

    # Components normalized into [0, 1]
    f0_instability = _clamp(f0_std / 80.0, 0.0, 1.0)
    zcr_component = _clamp(zcr_mean * 500.0, 0.0, 1.0)
    centroid_component = _clamp(spec_centroid_mean / 5000.0, 0.0, 1.0)
    jitter_component = _clamp(jitter / 30.0, 0.0, 1.0)
    silence_component = _clamp(silence_ratio, 0.0, 1.0)

    score = _clamp(
        f0_instability * 35.0
        + zcr_component * 25.0
        + centroid_component * 20.0
        + jitter_component * 10.0
        + silence_component * 10.0,
        0.0,
        100.0,
    )
    stress_score = int(round(score))

    indicators: list[str] = []
    if f0_mean > 220:
        indicators.append("elevated_pitch")
    if f0_std > 40:
        indicators.append("pitch_instability")
    if zcr_mean > 0.08:
        indicators.append("high_speech_rate")
    if spec_centroid_mean > 3000:
        indicators.append("spectral_shift")
    if jitter > 15:
        indicators.append("voice_jitter")
    if silence_ratio > 0.4:
        indicators.append("high_silence")
    if shimmer > 0.05:
        indicators.append("voice_shimmer")

    features = {
        "sample_rate": int(sr),
        "frequency": float(frequency) if frequency is not None else None,
        "f0_mean": f0_mean,
        "f0_std": f0_std,
        "zcr_mean": zcr_mean,
        "spec_centroid_mean": spec_centroid_mean,
        "jitter": jitter,
        "silence_ratio": silence_ratio,
        "shimmer": shimmer,
        "components": {
            "f0_instability": f0_instability,
            "zcr_component": zcr_component,
            "centroid_component": centroid_component,
            "jitter_component": jitter_component,
            "silence_component": silence_component,
        },
        "voiced_frames": int(voiced_f0.size),
        "total_samples": int(y.size),
    }

    return StressResult(
        timestamp=timestamp,
        audio_path=audio_path,
        duration_s=duration_s,
        stress_score=stress_score,
        alert_level=_alert_level(stress_score),
        indicators=indicators,
        features=features,
    )


if __name__ == "__main__":
    import sys

    result = score_stress(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else None)
    print(json.dumps(asdict(result), indent=2))
