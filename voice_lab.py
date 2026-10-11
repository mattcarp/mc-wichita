"""Voice Lab analysis: test microphone only, never wired to /alerts."""

from __future__ import annotations

import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Optional

SOURCE_TAG = "test-mic"


def mic_capture_enabled() -> bool:
    return os.getenv("WICHITA_VOICE_LAB_MIC", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def capture_mic_clip(
    duration_sec: float = 3.0,
    sample_rate: int = 16000,
) -> Path:
    """
    Record a short clip from the default input device (optional ReSpeaker / XVF3800).

    Requires optional dependency: sounddevice (not installed by default).
    """
    try:
        import sounddevice as sd
        import soundfile as sf
    except ImportError as exc:
        raise RuntimeError(
            "WICHITA_VOICE_LAB_MIC is set but sounddevice/soundfile are not installed"
        ) from exc

    device = os.getenv("WICHITA_VOICE_LAB_MIC_DEVICE")
    device_arg: Optional[int] = None
    if device and device.strip().isdigit():
        device_arg = int(device.strip())

    frames = int(max(0.5, duration_sec) * sample_rate)
    recording = sd.rec(
        frames,
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
        device=device_arg,
    )
    sd.wait()
    fd, tmp_path = tempfile.mkstemp(suffix=".wav", prefix="wichita-voice-lab-")
    os.close(fd)
    out = Path(tmp_path)
    sf.write(str(out), recording, sample_rate)
    return out


def analyze_voice_lab_clip(audio_path: Path, frequency_mhz: Optional[float] = None) -> Dict[str, Any]:
    """
    Return stress score (kenneth stress_scorer) plus implicit distress features.
    Does not create alerts or call external services.
    """
    from stress_scorer import score_stress as kenneth_score_stress
    from implicit_distress_detector import analyze_audio as implicit_analyze

    freq = frequency_mhz
    stress = kenneth_score_stress(str(audio_path), freq)
    stress_pct = float(stress.stress_score)
    implicit = implicit_analyze(
        str(audio_path),
        channel_id="VOICE_LAB",
        stress_score=stress_pct / 100.0,
    )

    return {
        "source": SOURCE_TAG,
        "not_evidence": True,
        "not_radio": True,
        "file": audio_path.name,
        "stress": asdict(stress),
        "implicit_distress": implicit,
        "banner": "TEST MICROPHONE - not radio, not evidence",
    }
