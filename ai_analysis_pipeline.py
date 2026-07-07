#!/usr/bin/env python3
"""
Kenneth AI analysis pipeline for local audio files.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence
import wave

import numpy as np

from whisper_transcription import WhisperConfig, transcribe_audio_file
from alert_dispatcher import send_stress_alert
from keyword_threat_detection import detect_threats

HIGH_STRESS_THRESHOLD = 70

DEFAULT_FLAGGED_TERMS = (
    "mayday",
    "pan-pan",
    "pan pan",
    "sos",
    "distress",
    "emergency",
    "help",
    "man overboard",
    "fire",
    "collision",
    "taking on water",
    "weapon",
    "bomb",
    "hostage",
)


@dataclass
class StressFeatures:
    pitch_variance_hz2: float
    zero_crossing_rate: float
    speech_rate_per_sec: float
    rms_energy: float
    voiced_ratio: float


def _load_audio_mono(audio_file_path: str | Path) -> tuple[np.ndarray, int]:
    path = Path(audio_file_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Audio file not found: {path}")

    try:
        import soundfile as sf

        data, sample_rate = sf.read(str(path), always_2d=False)
        audio = np.asarray(data, dtype=np.float32)
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)
        return audio, int(sample_rate)
    except Exception:
        if path.suffix.lower() != ".wav":
            raise RuntimeError(
                f"Could not decode {path}. Install soundfile for non-WAV formats."
            )

    with wave.open(str(path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_rate = wav_file.getframerate()
        sample_width = wav_file.getsampwidth()
        frames = wav_file.readframes(wav_file.getnframes())

    if sample_width == 1:
        samples = np.frombuffer(frames, dtype=np.uint8).astype(np.float32)
        samples = (samples - 128.0) / 128.0
    elif sample_width == 2:
        samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    elif sample_width == 4:
        samples = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"Unsupported WAV sample width: {sample_width}")

    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    return samples, int(sample_rate)


def _frame_audio(audio: np.ndarray, frame_size: int, hop_size: int) -> np.ndarray:
    if audio.size < frame_size:
        return np.empty((0, frame_size), dtype=np.float32)
    frame_count = 1 + (audio.size - frame_size) // hop_size
    frames = np.empty((frame_count, frame_size), dtype=np.float32)
    for index in range(frame_count):
        start = index * hop_size
        frames[index] = audio[start : start + frame_size]
    return frames


def _estimate_pitch_hz(frame: np.ndarray, sample_rate: int) -> float:
    centered = frame - np.mean(frame)
    energy = float(np.sqrt(np.mean(centered * centered)))
    if energy < 0.01:
        return 0.0

    autocorr = np.correlate(centered, centered, mode="full")[len(centered) - 1 :]
    min_lag = max(1, int(sample_rate / 350.0))
    max_lag = min(len(autocorr) - 1, int(sample_rate / 80.0))
    if max_lag <= min_lag:
        return 0.0

    region = autocorr[min_lag : max_lag + 1]
    lag = int(np.argmax(region)) + min_lag
    if lag <= 0:
        return 0.0

    return float(sample_rate / lag)


def extract_stress_features(audio_file_path: str | Path) -> StressFeatures:
    audio, sample_rate = _load_audio_mono(audio_file_path)
    if audio.size == 0:
        return StressFeatures(0.0, 0.0, 0.0, 0.0, 0.0)

    frame_size = max(256, int(0.03 * sample_rate))
    hop_size = max(128, int(0.01 * sample_rate))
    frames = _frame_audio(audio, frame_size, hop_size)
    if frames.size == 0:
        rms = float(np.sqrt(np.mean(audio * audio)))
        return StressFeatures(0.0, 0.0, 0.0, rms, 0.0)

    frame_rms = np.sqrt(np.mean(frames * frames, axis=1))
    rms_energy = float(np.mean(frame_rms))

    voiced_mask = frame_rms > max(0.02, float(np.median(frame_rms) * 0.75))
    voiced_pitches: List[float] = []
    for frame, voiced in zip(frames, voiced_mask):
        if not voiced:
            continue
        pitch = _estimate_pitch_hz(frame, sample_rate)
        if 70.0 <= pitch <= 450.0:
            voiced_pitches.append(pitch)

    pitch_variance = float(np.var(voiced_pitches)) if len(voiced_pitches) > 1 else 0.0
    voiced_ratio = float(np.mean(voiced_mask)) if voiced_mask.size else 0.0
    zcr = float(np.mean(np.abs(np.diff(np.signbit(audio)).astype(np.float32))))

    try:
        import librosa

        # Prefer librosa for robust pitch + ZCR extraction.
        f0, _, _ = librosa.pyin(
            audio,
            fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C7"),
            sr=sample_rate,
            frame_length=frame_size,
            hop_length=hop_size,
        )
        voiced_f0 = f0[np.isfinite(f0)] if f0 is not None else np.array([])
        if voiced_f0.size > 1:
            pitch_variance = float(np.var(voiced_f0))

        zcr_matrix = librosa.feature.zero_crossing_rate(
            y=audio, frame_length=frame_size, hop_length=hop_size
        )
        if zcr_matrix.size:
            zcr = float(np.mean(zcr_matrix))
    except Exception:
        # Fallback to numpy/autocorrelation-derived features.
        pass

    # Approximate speech rate by counting voiced onsets per second.
    onsets = np.logical_and(voiced_mask[1:], np.logical_not(voiced_mask[:-1]))
    duration_sec = max(1e-6, float(audio.size / sample_rate))
    speech_rate = float(np.count_nonzero(onsets) / duration_sec)

    return StressFeatures(
        pitch_variance_hz2=pitch_variance,
        zero_crossing_rate=zcr,
        speech_rate_per_sec=speech_rate,
        rms_energy=rms_energy,
        voiced_ratio=voiced_ratio,
    )


def score_stress(audio_features: StressFeatures | Dict[str, float]) -> int:
    """
    Convert stress-related audio features into a 0-100 score.

    The second signal: what the channel carries below the words.
    Shannon (1948) says it can be recovered; the lineman heard it
    through the whine. This is where we listen.
    """
    if isinstance(audio_features, StressFeatures):
        features = audio_features
    else:
        features = StressFeatures(
            pitch_variance_hz2=float(audio_features.get("pitch_variance_hz2", 0.0)),
            zero_crossing_rate=float(audio_features.get("zero_crossing_rate", 0.0)),
            speech_rate_per_sec=float(audio_features.get("speech_rate_per_sec", 0.0)),
            rms_energy=float(audio_features.get("rms_energy", 0.0)),
            voiced_ratio=float(audio_features.get("voiced_ratio", 0.0)),
        )

    # Normalize pitch variance: typical stressed speech variance is 1–10 Hz²
    # (librosa pyin returns Hz values; variance of a 2-octave sweep ≈ 2–8 Hz²).
    # The previous normalizer (/1500) was calibrated for raw autocorrelation
    # estimates and made this component near-zero for librosa outputs.
    pitch_component = min(100.0, (features.pitch_variance_hz2 / 6.0) * 100.0)
    zcr_component = min(100.0, max(0.0, ((features.zero_crossing_rate - 0.03) / 0.17) * 100.0))
    speech_component = min(
        100.0, max(0.0, ((features.speech_rate_per_sec - 0.3) / 2.5) * 100.0)
    )
    energy_component = min(100.0, (features.rms_energy / 0.25) * 100.0)

    raw_score = (
        0.45 * pitch_component
        + 0.25 * zcr_component
        + 0.20 * speech_component
        + 0.10 * energy_component
    )
    bounded = int(round(min(100.0, max(0.0, raw_score))))
    return bounded


def compute_stress_score(audio_file_path: str | Path) -> int:
    features = extract_stress_features(audio_file_path)
    return score_stress(features)


def classify_threat_keywords(
    text: str,
    flagged_terms: Optional[Sequence[str]] = None,
) -> Dict[str, object]:
    haystack = (text or "").lower()
    terms = tuple(flagged_terms or DEFAULT_FLAGGED_TERMS)

    matches = [term for term in terms if term.lower() in haystack]
    unique_matches = sorted(set(matches))

    return {
        "is_flagged": bool(unique_matches),
        "matched_terms": unique_matches,
        "match_count": len(unique_matches),
    }


def analyze_transmission(
    transcription_dict: Dict[str, object],
    frequency_hz: float | None = None,
) -> Dict[str, object]:
    return detect_threats(transcription_dict, frequency_hz=frequency_hz)


def analyse_transmission(
    transcription_dict: Dict[str, object],
    frequency_hz: float | None = None,
) -> Dict[str, object]:
    # Compatibility alias for callers using British spelling.
    return analyze_transmission(transcription_dict, frequency_hz=frequency_hz)


def analyze_audio_file(
    audio_file_path: str | Path,
    whisper_config: Optional[WhisperConfig] = None,
    flagged_terms: Optional[Sequence[str]] = None,
) -> Dict[str, object]:
    path = Path(audio_file_path)
    transcript = transcribe_audio_file(path, whisper_config)
    transcript_text = str(transcript.get("text", "")).strip()
    stress_features = extract_stress_features(path)
    stress_score = score_stress(stress_features)
    keyword_result = classify_threat_keywords(transcript_text, flagged_terms)
    transmission_alert = analyze_transmission(transcript, frequency_hz=None)
    if stress_score > HIGH_STRESS_THRESHOLD:
        send_stress_alert(
            stress_score=stress_score,
            frequency=None,
            transcription=transcript_text,
            indicators=keyword_result.get("matched_terms", []),
        )

    return {
        "audio_file": str(path),
        "transcript": transcript,
        "stress_score": stress_score,
        "stress_features": {
            "pitch_variance_hz2": stress_features.pitch_variance_hz2,
            "zero_crossing_rate": stress_features.zero_crossing_rate,
            "speech_rate_per_sec": stress_features.speech_rate_per_sec,
            "rms_energy": stress_features.rms_energy,
            "voiced_ratio": stress_features.voiced_ratio,
        },
        "threat_classification": keyword_result,
        "alert": transmission_alert,
    }


def find_audio_files(directory: str | Path = "audio_samples") -> List[Path]:
    root = Path(directory)
    if not root.exists() or not root.is_dir():
        return []
    allowed_extensions = {".wav", ".mp3", ".m4a", ".flac", ".ogg"}
    files = [item for item in root.iterdir() if item.suffix.lower() in allowed_extensions]
    return sorted(files)


def analyze_audio_directory(
    directory: str | Path = "audio_samples",
    whisper_config: Optional[WhisperConfig] = None,
    flagged_terms: Optional[Sequence[str]] = None,
) -> List[Dict[str, object]]:
    results = []
    for audio_path in find_audio_files(directory):
        results.append(analyze_audio_file(audio_path, whisper_config, flagged_terms))
    return results


__all__ = [
    "DEFAULT_FLAGGED_TERMS",
    "StressFeatures",
    "analyze_audio_directory",
    "analyze_audio_file",
    "analyze_transmission",
    "analyse_transmission",
    "classify_threat_keywords",
    "compute_stress_score",
    "extract_stress_features",
    "find_audio_files",
    "score_stress",
]
