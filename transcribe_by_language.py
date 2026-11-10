"""
Transcribe a speech segment with the right model for its language.

Voice path task 4 (openspec/changes/voice-path). No hardware.

Routing, decided by measurement (see test_transcribe_by_language.py and the commit):
1. Language ID with the general model (Whisper large-v3-turbo, multilingual).
2. Maltese ("mt") goes to the mc-vuci Maltese fine-tune
   (carlosdanielhernandezmena/whisper-large-maltese-8k-steps-64h-ct2, MASRI); everything else
   is transcribed by the general model in the detected language.
3. Nothing is dropped. A low language probability or a low average log-probability marks the
   transcript unsure; the caller records it, tagged, via voice_record.

Model paths come from env so the server and the Air can differ:
  WICHITA_ASR_GENERAL  default: HF id mobiuslabsgmbh/faster-whisper-large-v3-turbo
  WICHITA_ASR_MALTESE  default: ~/Documents/projects/mc-vuci/asr/model
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, asdict
from functools import lru_cache
from pathlib import Path
from typing import Optional

GENERAL_DEFAULT = "mobiuslabsgmbh/faster-whisper-large-v3-turbo"
MALTESE_DEFAULT = str(Path("~/Documents/projects/mc-vuci/asr/model").expanduser())
LANG_UNSURE_BELOW = 0.6
LOGPROB_UNSURE_BELOW = -1.0  # mean avg_logprob over segments


@dataclass
class Transcript:
    text: str
    language: str
    language_probability: float
    model: str
    avg_logprob: Optional[float]
    unsure: bool
    unsure_reasons: list

    def confidence(self) -> float:
        """0..1: language probability times exp(mean log-probability)."""
        lp = math.exp(self.avg_logprob) if self.avg_logprob is not None else 0.0
        return round(self.language_probability * lp, 3)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["confidence"] = self.confidence()
        return d


def general_model_path() -> str:
    return os.environ.get("WICHITA_ASR_GENERAL", GENERAL_DEFAULT)


def maltese_model_path() -> str:
    return os.environ.get("WICHITA_ASR_MALTESE", MALTESE_DEFAULT)


@lru_cache(maxsize=2)
def _model(path: str):
    from faster_whisper import WhisperModel

    return WhisperModel(path, device="cpu", compute_type="int8")


def detect_language(wav: str) -> tuple:
    """(language, probability) from the general multilingual model."""
    model = _model(general_model_path())
    lang, prob, _all = model.detect_language(_load(wav))
    return lang, float(prob)


def _load(wav: str):
    """16 kHz mono float32. soundfile + scipy, not faster_whisper.decode_audio (PyAV API drift)."""
    from math import gcd

    import numpy as np
    import soundfile as sf
    from scipy.signal import resample_poly

    x, sr = sf.read(wav, always_2d=False)
    if x.ndim > 1:
        x = x.mean(axis=1)
    if sr != 16000:
        g = gcd(16000, int(sr))
        x = resample_poly(x, 16000 // g, int(sr) // g)
    return np.asarray(x, dtype=np.float32)


def _run(model_path: str, wav: str, language: str):
    model = _model(model_path)
    segments, info = model.transcribe(_load(wav), language=language, beam_size=5,
                                      vad_filter=False, condition_on_previous_text=False)
    segs = list(segments)
    text = " ".join(s.text.strip() for s in segs).strip()
    lp = sum(s.avg_logprob for s in segs) / len(segs) if segs else None
    return text, lp


def transcribe(wav: str, language: Optional[str] = None) -> Transcript:
    """Transcribe one segment. Pass language to skip detection (e.g. a channel known to be Maltese)."""
    if language is None:
        language, prob = detect_language(wav)
    else:
        prob = 1.0
    path = maltese_model_path() if language == "mt" else general_model_path()
    text, lp = _run(path, wav, language)

    reasons = []
    if prob < LANG_UNSURE_BELOW:
        reasons.append(f"language_probability {prob:.2f} < {LANG_UNSURE_BELOW}")
    if lp is None:
        reasons.append("no segments decoded")
    elif lp < LOGPROB_UNSURE_BELOW:
        reasons.append(f"avg_logprob {lp:.2f} < {LOGPROB_UNSURE_BELOW}")
    if not text:
        reasons.append("empty transcript")
    return Transcript(text=text, language=language, language_probability=round(prob, 3),
                      model="maltese" if language == "mt" else "general",
                      avg_logprob=round(lp, 3) if lp is not None else None,
                      unsure=bool(reasons), unsure_reasons=reasons)


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser(description="Transcribe WAV segments by language.")
    ap.add_argument("wav", nargs="+")
    ap.add_argument("--language")
    a = ap.parse_args()
    for w in a.wav:
        print(json.dumps({"file": w, **transcribe(w, a.language).as_dict()}, ensure_ascii=False))
