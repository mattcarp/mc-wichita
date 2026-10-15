"""speech_finder on real captures.

Negatives: the three 2025-09-12 RTL-SDR captures are open-squelch hiss (spectral
flatness ~1.0, energy flat to 0.4 dB), so they must yield no segments.
The speech-in-hiss measurement (real voice mixed with real receiver hiss, 0-20 dB) is
recorded in speech_finder's docstring; the voice take is personal and not committed.
Positive: real received voice clips placed in fixtures/voice/*.wav (with a .json
listing the expected speech spans). None exist yet; the test skips until the new
antenna produces one. No synthetic speech stands in for it.
"""

import json
from pathlib import Path

import numpy as np
import pytest

import speech_finder as sfd

ROOT = Path(__file__).parent
NOISE = sorted(ROOT.glob("REAL_RTL_CAPTURE_*.wav"))
VOICE = sorted((ROOT / "fixtures" / "voice").glob("*.wav"))


@pytest.mark.parametrize("wav", NOISE, ids=lambda p: p.name[17:40])
def test_real_noise_captures_yield_no_speech(wav):
    assert sfd.find_speech_in_file(wav) == []


def test_noise_fixtures_present():
    assert len(NOISE) == 3


def test_digital_silence_and_short_input():
    assert sfd.find_speech(np.zeros(48000), 48000) == []
    assert sfd.find_speech(np.zeros(100), 48000) == []


@pytest.mark.skipif(not VOICE, reason="no real received voice clip in fixtures/voice yet")
@pytest.mark.parametrize("wav", VOICE, ids=lambda p: p.name)
def test_real_voice_clip_found(wav):
    spans = json.loads(wav.with_suffix(".json").read_text())["speech_spans_s"]
    segs = sfd.find_speech_in_file(wav)
    assert segs, "no speech found in a clip with known speech"
    for lo, hi in spans:
        assert any(s.start_s <= hi and s.end_s >= lo for s in segs), (lo, hi, segs)
