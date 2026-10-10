#!/usr/bin/env python3
"""
Kenneth Implicit Distress Detector — issue #19

Detects distress WITHOUT explicit words. 'I'm fine' said while hyperventilating
IS a distress signal.

Acoustic patterns:
  - Breathing / labored respiration (rhythmic bursts 0.15-0.9 Hz)
  - Background sounds: alarms (tonal), crying (pitch-variable)
  - Slurred speech (low centroid, low ZCR)
  - Signal weakening over transmissions

Behavioral patterns (multi-session):
  - Voice quality degradation across transmissions
  - Shrinking transmission durations
  - Repeated identical message (desperation loop via MFCC fingerprint)

Usage:
    python implicit_distress_detector.py --audio capture.wav
    python implicit_distress_detector.py --watch /path/to/captures/ --channel-id CH16
"""

import argparse, json, logging, os, sys, time
from collections import defaultdict, Counter, deque
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import scipy.signal as sig
import soundfile as sf

try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("implicit-distress")

ALERT_LEVELS = ["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"]

ALERT_THRESHOLDS = {
    "breathing_detected":          "MEDIUM",
    "background_alarm":            "HIGH",
    "background_crying":           "HIGH",
    "slurred_speech":              "MEDIUM",
    "voice_degrading":             "HIGH",
    "signal_weakening":            "LOW",
    "silence_increasing":          "LOW",
    "desperation_loop":            "HIGH",
    "alarm_plus_stressed_voice":   "CRITICAL",
    "weakening_plus_distress_kw":  "CRITICAL",
}

def max_alert(*levels):
    idx = max((ALERT_LEVELS.index(l) for l in levels if l in ALERT_LEVELS), default=0)
    return ALERT_LEVELS[idx]


@dataclass
class TransmissionRecord:
    timestamp: str
    channel_id: str
    duration_s: float
    spectral_centroid: float
    zero_crossing_rate: float
    energy_rms: float
    mfcc_hash: Optional[str]
    breathing_score: float
    slur_score: float
    alarm_score: float
    cry_score: float


class SessionTracker:
    MAX_HISTORY = 20
    def __init__(self):
        self._sessions: Dict[str, deque] = defaultdict(lambda: deque(maxlen=self.MAX_HISTORY))
    def record(self, channel_id, rec):
        self._sessions[channel_id].append(rec)
    def history(self, channel_id):
        return list(self._sessions[channel_id])
    def clear(self, channel_id):
        self._sessions[channel_id].clear()

_tracker = SessionTracker()


def load_audio(path: str, target_sr: int = 16000) -> Tuple[np.ndarray, int]:
    audio, sr = sf.read(path, dtype="float32", always_2d=False)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if sr != target_sr:
        num = int(len(audio) * target_sr / sr)
        audio = sig.resample(audio, num)
        sr = target_sr
    return audio, sr


def breathing_score(audio: np.ndarray, sr: int) -> float:
    """Detect labored breathing via rhythmic 100-800Hz bursts at 0.15-0.9 Hz."""
    sos = sig.butter(4, [100, 800], btype="band", fs=sr, output="sos")
    filtered = sig.sosfilt(sos, audio)
    envelope = np.abs(sig.hilbert(filtered))
    win = max(1, int(sr * 0.05))
    smooth = np.convolve(envelope, np.ones(win)/win, mode="same")
    if len(smooth) < sr * 2:
        return 0.0
    freqs = np.fft.rfftfreq(len(smooth), 1/sr)
    fft_mag = np.abs(np.fft.rfft(smooth))
    breath_mask = (freqs >= 0.15) & (freqs <= 0.9)
    rhythm_score = float(fft_mag[breath_mask].sum() / (fft_mag.sum() + 1e-10))
    band_rms = float(np.sqrt(np.mean(filtered**2)))
    overall_rms = float(np.sqrt(np.mean(audio**2))) + 1e-10
    band_ratio = min(1.0, band_rms / overall_rms * 3)
    return float(min(1.0, rhythm_score * 4 * band_ratio))


def slur_score(audio: np.ndarray, sr: int) -> float:
    """Slurred speech: low spectral centroid + low ZCR."""
    if len(audio) < sr * 0.5:
        return 0.0
    zcr_val = float(np.mean(np.diff(np.sign(audio)) != 0))
    if HAS_LIBROSA:
        centroid = float(np.mean(librosa.feature.spectral_centroid(y=audio, sr=sr)[0]))
    else:
        freqs = np.fft.rfftfreq(len(audio), 1/sr)
        mag = np.abs(np.fft.rfft(audio))
        centroid = float(np.sum(freqs * mag) / (np.sum(mag) + 1e-10))
    centroid_score = max(0.0, 1.0 - centroid / 2000.0)
    zcr_score = max(0.0, 1.0 - zcr_val / 0.08)
    return float(min(1.0, centroid_score * 0.6 + zcr_score * 0.4))


def background_alarm_score(audio: np.ndarray, sr: int) -> float:
    """Detect alarm tones: low spectral flatness (tonal) + repetitive beep pattern."""
    sos = sig.butter(4, [500, 4000], btype="band", fs=sr, output="sos")
    filtered = sig.sosfilt(sos, audio)
    if len(filtered) < 512:
        return 0.0
    _, psd = sig.welch(filtered, sr, nperseg=min(512, len(filtered)))
    psd = psd + 1e-20
    flatness = float(np.exp(np.mean(np.log(psd))) / np.mean(psd))
    tonal_score = max(0.0, 1.0 - flatness * 10)
    envelope = np.abs(sig.hilbert(filtered))
    env_freqs = np.fft.rfftfreq(len(envelope), 1/sr)
    env_fft = np.abs(np.fft.rfft(envelope))
    beep_mask = (env_freqs >= 0.5) & (env_freqs <= 4.0)
    beep_ratio = float(env_fft[beep_mask].sum() / (env_fft.sum() + 1e-10))
    return float(min(1.0, tonal_score * 0.5 + beep_ratio * 10 * 0.5))


def background_cry_score(audio: np.ndarray, sr: int) -> float:
    """Detect crying: irregular amplitude modulation + pitch variability."""
    sos = sig.butter(4, [200, 2000], btype="band", fs=sr, output="sos")
    filtered = sig.sosfilt(sos, audio)
    envelope = np.abs(sig.hilbert(filtered))
    if len(envelope) < 100:
        return 0.0
    env_cv = float(np.std(envelope) / (np.mean(envelope) + 1e-10))
    if HAS_LIBROSA:
        try:
            f0, voiced, _ = librosa.pyin(audio, fmin=librosa.note_to_hz("C2"), fmax=librosa.note_to_hz("C7"), sr=sr)
            if voiced is not None:
                voiced_f0 = f0[voiced == 1.0]
                if len(voiced_f0) > 10:
                    pitch_cv = float(np.std(voiced_f0) / (np.mean(voiced_f0) + 1e-10))
                    return float(min(1.0, (env_cv * 0.5 + pitch_cv * 0.5)))
        except Exception:
            pass
    return float(min(1.0, env_cv * 0.6))


def mfcc_fingerprint(audio: np.ndarray, sr: int) -> Optional[str]:
    """Rough MFCC fingerprint for loop detection."""
    if not HAS_LIBROSA or len(audio) < sr * 0.5:
        return None
    try:
        mfccs = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=13)
        mean_mfcc = np.mean(mfccs, axis=1)
        quantized = (np.clip(mean_mfcc, -40, 40) / 80 * 16).astype(int)
        return "".join(f"{v:x}" for v in quantized)
    except Exception:
        return None


def spectral_centroid_hz(audio: np.ndarray, sr: int) -> float:
    if HAS_LIBROSA:
        return float(np.mean(librosa.feature.spectral_centroid(y=audio, sr=sr)[0]))
    freqs = np.fft.rfftfreq(len(audio), 1/sr)
    mag = np.abs(np.fft.rfft(audio))
    return float(np.sum(freqs * mag) / (np.sum(mag) + 1e-10))


def analyze_behavioral(history: List[TransmissionRecord]) -> Dict:
    result = {"voice_degrading": False, "signal_weakening": False,
              "silence_increasing": False, "desperation_loop": False,
              "n_transmissions": len(history)}
    if len(history) < 3:
        return result
    x = np.arange(len(history))
    centroids = [r.spectral_centroid for r in history]
    slope = float(np.polyfit(x, centroids, 1)[0])
    result["voice_degrading"] = slope < -50  # dropping >50 Hz per tx
    rms_vals = [r.energy_rms for r in history]
    slope = float(np.polyfit(x, rms_vals, 1)[0])
    result["signal_weakening"] = slope < -0.005
    durations = [r.duration_s for r in history]
    slope = float(np.polyfit(x, durations, 1)[0])
    result["silence_increasing"] = slope < -0.5  # shrinking >0.5s/tx
    fingerprints = [r.mfcc_hash for r in history if r.mfcc_hash]
    if fingerprints:
        result["desperation_loop"] = any(v >= 3 for v in Counter(fingerprints).values())
    return result


def analyze_audio(path: str, channel_id: str = "UNKNOWN", stress_score: float = 0.0) -> Dict:
    try:
        audio, sr = load_audio(path)
    except Exception as e:
        return {"error": str(e), "alert_level": "NONE"}
    duration = len(audio) / sr
    if duration < 0.5:
        return {"alert_level": "NONE", "reason": "too_short", "duration_s": duration}

    b_score  = breathing_score(audio, sr)
    sl_score = slur_score(audio, sr)
    al_score = background_alarm_score(audio, sr)
    cr_score = background_cry_score(audio, sr)
    centroid = spectral_centroid_hz(audio, sr)
    z_score  = float(np.mean(np.diff(np.sign(audio)) != 0))
    rms      = float(np.sqrt(np.mean(audio**2)))
    fp       = mfcc_fingerprint(audio, sr)

    rec = TransmissionRecord(
        timestamp=datetime.utcnow().isoformat(), channel_id=channel_id,
        duration_s=duration, spectral_centroid=centroid, zero_crossing_rate=z_score,
        energy_rms=rms, mfcc_hash=fp, breathing_score=b_score,
        slur_score=sl_score, alarm_score=al_score, cry_score=cr_score,
    )
    _tracker.record(channel_id, rec)
    behavioral = analyze_behavioral(_tracker.history(channel_id))

    triggered = []
    if b_score  > 0.4: triggered.append("breathing_detected")
    if al_score > 0.5: triggered.append("background_alarm")
    if cr_score > 0.4: triggered.append("background_crying")
    if sl_score > 0.5: triggered.append("slurred_speech")
    if behavioral.get("voice_degrading"):    triggered.append("voice_degrading")
    if behavioral.get("signal_weakening"):   triggered.append("signal_weakening")
    if behavioral.get("silence_increasing"): triggered.append("silence_increasing")
    if behavioral.get("desperation_loop"):   triggered.append("desperation_loop")
    if "background_alarm" in triggered and stress_score > 0.6:
        triggered.append("alarm_plus_stressed_voice")
    if "signal_weakening" in triggered and stress_score > 0.7:
        triggered.append("weakening_plus_distress_kw")

    alert_levels = [ALERT_THRESHOLDS.get(t, "LOW") for t in triggered]
    alert_level  = max_alert(*alert_levels) if alert_levels else "NONE"

    result = {
        "file": os.path.basename(path), "channel_id": channel_id,
        "timestamp": rec.timestamp, "duration_s": round(duration, 2),
        "alert_level": alert_level, "triggers": triggered,
        "scores": {
            "breathing":          round(b_score, 3),
            "slurred_speech":     round(sl_score, 3),
            "background_alarm":   round(al_score, 3),
            "background_crying":  round(cr_score, 3),
            "spectral_centroid_hz": round(centroid, 1),
            "energy_rms":         round(rms, 4),
            "stress_score_in":    round(stress_score, 3),
        },
        "behavioral": behavioral,
        "session_transmissions": len(_tracker.history(channel_id)),
    }
    if alert_level != "NONE":
        logger.warning(f"⚠️  [{alert_level}] {channel_id} — {', '.join(triggered)}")
    return result


def watch_directory(watch_dir: str, channel_id: str, poll_interval: float = 2.0):
    watch_path = Path(watch_dir)
    seen = set(watch_path.glob("*.wav"))
    logger.info(f"Watching {watch_dir} for new WAV files (channel={channel_id})...")
    while True:
        time.sleep(poll_interval)
        current = set(watch_path.glob("*.wav"))
        for wav in sorted(current - seen):
            logger.info(f"New file: {wav.name}")
            print(json.dumps(analyze_audio(str(wav), channel_id=channel_id), indent=2))
        seen = current


def main():
    parser = argparse.ArgumentParser(description="Kenneth Implicit Distress Detector")
    parser.add_argument("--audio",        help="Path to WAV file")
    parser.add_argument("--watch",        help="Directory to watch for new WAV files")
    parser.add_argument("--channel-id",   default="UNKNOWN")
    parser.add_argument("--stress-score", type=float, default=0.0,
                        help="Stress score from kenneth_stress_monitor (0-1)")
    args = parser.parse_args()
    if args.watch:
        watch_directory(args.watch, args.channel_id)
    elif args.audio:
        print(json.dumps(analyze_audio(args.audio, args.channel_id, args.stress_score), indent=2))
    else:
        parser.print_help(); sys.exit(1)

if __name__ == "__main__":
    main()
