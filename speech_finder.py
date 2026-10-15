"""
Speech finder: voice segments in a demodulated radio clip; silence, hiss and carrier out.

Voice path task 3 (openspec/changes/voice-path). No hardware.

Uses the Silero voice-activity model bundled with faster-whisper (the same package the
transcription stage needs), on 16 kHz mono. Measured 2026-10-15 against real speech
mixed with a real open-squelch hiss capture from our receiver:

    speech over hiss    Silero found     energy+flatness gate (first attempt)
    20 dB               26.3 s of 25.8   18.7 s of 20.5
     8 dB               26.1 s           5.0 s
     0 dB               25.7 s           not tested (already failing at 8 dB)
    hiss only (x3)      0 segments       0 segments

so the hand-built gate was dropped. Each segment also carries its level over the
clip's noise floor, so weak and strong calls can be told apart downstream.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from math import gcd
from pathlib import Path
from typing import List

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

VAD_SR = 16000
THRESHOLD = 0.5
MIN_SPEECH_MS = 250
MIN_SILENCE_MS = 300
FLOOR_PERCENTILE = 20
FRAME_SEC = 0.03


@dataclass
class Segment:
    start_s: float
    end_s: float
    snr_db: float

    @property
    def dur_s(self) -> float:
        return round(self.end_s - self.start_s, 3)


def _to_vad_rate(x: np.ndarray, sr: int) -> np.ndarray:
    if x.ndim > 1:
        x = x.mean(axis=1)
    x = x.astype(np.float64) - float(np.mean(x))
    if sr != VAD_SR:
        g = gcd(VAD_SR, sr)
        x = resample_poly(x, VAD_SR // g, sr // g)
    return x.astype(np.float32)


def _level_db(x: np.ndarray, sr: int) -> np.ndarray:
    n = int(FRAME_SEC * sr)
    count = len(x) // n
    fr = x[: count * n].reshape(count, n).astype(np.float64)
    return 10 * np.log10((fr ** 2).mean(axis=1) + 1e-12)


def find_speech(x: np.ndarray, sr: int) -> List[Segment]:
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    audio = _to_vad_rate(np.asarray(x), int(sr))
    if len(audio) < VAD_SR // 4 or not np.any(audio):
        return []
    opts = VadOptions(threshold=THRESHOLD, min_speech_duration_ms=MIN_SPEECH_MS,
                      min_silence_duration_ms=MIN_SILENCE_MS)
    stamps = get_speech_timestamps(audio, opts)
    level = _level_db(audio, VAD_SR)
    floor = float(np.percentile(level, FLOOR_PERCENTILE))
    out: List[Segment] = []
    for t in stamps:
        a, b = int(t["start"] / VAD_SR / FRAME_SEC), max(int(t["end"] / VAD_SR / FRAME_SEC), 1)
        seg_level = float(np.median(level[a:b])) if b > a else floor
        out.append(Segment(round(t["start"] / VAD_SR, 3), round(t["end"] / VAD_SR, 3),
                           round(seg_level - floor, 1)))
    return out


def find_speech_in_file(path: Path) -> List[Segment]:
    x, sr = sf.read(str(path), always_2d=False)
    return find_speech(np.asarray(x), int(sr))


def main() -> None:
    ap = argparse.ArgumentParser(description="Find speech segments in demodulated radio WAVs.")
    ap.add_argument("wav", type=Path, nargs="+")
    a = ap.parse_args()
    for p in a.wav:
        segs = find_speech_in_file(p)
        print(json.dumps({"file": str(p), "segments": [dict(asdict(s), dur_s=s.dur_s) for s in segs]}))


if __name__ == "__main__":
    main()
