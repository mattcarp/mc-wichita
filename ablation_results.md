# LavaSR v2 Ablation Results

Generated: 2026-03-02 04:52:31 UTC  
Device: cpu | LavaSR 0.0.2

## Verdict: SIGNAL_CHANGED

**Recommendation:** LavaSR modifies spectrum significantly — needs Whisper comparison on real SDR captures (not post-processed MP3s)

## Results

| File | Duration | LavaSR | LSD | Words before | Words after |
|------|:---:|:---:|:---:|:---:|:---:|
| net_fm_after.mp3 | 5.04s | ✅ | 2.9645 | 0 | 0 |
| net_fm_after_PROPER.mp3 | 5.04s | ✅ | 2.9645 | 0 | 0 |
| one_radio_after.mp3 | 10.03s | ✅ | 2.8038 | 0 | 0 |
| one_radio_before.mp3 | 10.03s | ✅ | 1.8394 | 0 | 0 |
| radio_malta_after.mp3 | 5.04s | ✅ | 3.2112 | 0 | 0 |
| radio_malta_after_PROPER.mp3 | 5.04s | ✅ | 3.2112 | 0 | 0 |

## Transcription Samples (Whisper tiny)

**net_fm_after.mp3**
- Before: (silent)
- After:  (silent)

**net_fm_after_PROPER.mp3**
- Before: (silent)
- After:  (silent)

**one_radio_after.mp3**
- Before: (silent)
- After:  (silent)

**one_radio_before.mp3**
- Before: (silent)
- After:  (silent)

## Methodology

- Audio source: Wichita/audio_samples (real radio MP3s — post-processed ElevenLabs denoise tests)
- Before: librosa load at 16kHz → resample to 48kHz (naive baseline)
- After: same 16kHz input → LavaSR enhance (denoise=True, enhance=True) → 48kHz
- LSD: Log-Spectral Distance between naive and LavaSR output
- Whisper tiny word count as proxy for intelligibility
- Note: audio_samples are already processed (ElevenLabs denoised) — real ablation value
  will be higher on raw SDR captures; recommend re-test with raw .raw/.wav SDR files

## Next Steps

- Capture raw SDR audio (before any denoising) for a cleaner baseline comparison
- Test with Whisper base/small for better transcription accuracy
- If hardware arrives (TRAM 1410 antenna + adapter): capture live signals for real-world test
