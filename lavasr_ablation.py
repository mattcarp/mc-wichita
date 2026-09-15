#!/usr/bin/env python3
"""LavaSR v2 Ablation Test — mc-kenneth issue #28"""

import sys, os, time, json, datetime
import numpy as np
import torch
import librosa
import soundfile as sf
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

AUDIO_DIR = Path("audio_samples")
OUTPUT_DIR = Path("ablation_output")
OUTPUT_DIR.mkdir(exist_ok=True)
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
LAVASR_INPUT_SR = 16000
TARGET_SR = 48000

print(f"LavaSR v2 Ablation Test — mc-kenneth #28")
print(f"Device: {DEVICE} | {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
print()

print("Loading LavaSR model...")
t0 = time.time()
try:
    from LavaSR.model import LavaEnhance
    model = LavaEnhance(device=DEVICE)
    print(f"LavaSR loaded in {time.time()-t0:.1f}s")
    LAVASR_AVAILABLE = True
except Exception as e:
    print(f"LavaSR FAILED: {e}")
    LAVASR_AVAILABLE = False

# Whisper from system packages
print("Loading Whisper...")
WHISPER_AVAILABLE = False
try:
    sys.path.insert(0, '/usr/local/lib/python3.12/dist-packages')
    import whisper as whisper_pkg
    whisper_model = whisper_pkg.load_model("tiny")
    print("Whisper tiny loaded")
    WHISPER_AVAILABLE = True
except Exception as e:
    print(f"Whisper unavailable: {e}")
print()

def compute_lsd(a: np.ndarray, b: np.ndarray) -> float:
    n = min(len(a), len(b))
    a, b = a[:n].astype(np.float32), b[:n].astype(np.float32)
    sa = np.abs(np.fft.rfft(a, n=1024)) + 1e-10
    sb = np.abs(np.fft.rfft(b, n=1024)) + 1e-10
    return float(np.sqrt(np.mean((np.log10(sa) - np.log10(sb))**2)))

def transcribe(audio_np: np.ndarray, sr: int) -> str:
    if not WHISPER_AVAILABLE or audio_np is None:
        return ""
    try:
        sf.write("/tmp/_abl_tmp.wav", audio_np, sr)
        r = whisper_model.transcribe("/tmp/_abl_tmp.wav", fp16=False)
        return r.get("text","").strip()[:200]
    except Exception as e:
        return f"[error: {e}]"

audio_files = sorted(list(AUDIO_DIR.glob("*.mp3")) + list(AUDIO_DIR.glob("*.wav")))
print(f"Found {len(audio_files)} files:")
for f in audio_files:
    print(f"  {f.name}")
print()

results = []

for af in audio_files:
    print(f"→ {af.name}")
    try:
        wav16, _ = librosa.load(str(af), sr=LAVASR_INPUT_SR, mono=True)
        duration = len(wav16) / LAVASR_INPUT_SR
        print(f"  {duration:.1f}s")

        before_np = librosa.resample(wav16, orig_sr=LAVASR_INPUT_SR, target_sr=TARGET_SR).astype(np.float32)
        sf.write(str(OUTPUT_DIR / f"{af.stem}_before.wav"), before_np, TARGET_SR)

        lavasr_ran = False
        after_np = None

        if LAVASR_AVAILABLE:
            try:
                wav_t = torch.from_numpy(wav16).unsqueeze(0)  # [1, samples] — required by denoiser
                t1 = time.time()
                enhanced = model.enhance(wav_t, enhance=True, denoise=True, batch=False)
                elapsed = time.time() - t1
                after_np = enhanced.cpu().numpy().astype(np.float32) if isinstance(enhanced, torch.Tensor) else np.array(enhanced, dtype=np.float32)
                sf.write(str(OUTPUT_DIR / f"{af.stem}_after.wav"), after_np, TARGET_SR)
                lavasr_ran = True
                print(f"  LavaSR: {elapsed:.1f}s ({duration/elapsed:.1f}x realtime)")
            except Exception as e:
                import traceback; traceback.print_exc()
                print(f"  LavaSR failed: {e}")

        lsd = compute_lsd(before_np, after_np) if after_np is not None else None
        if lsd is not None:
            print(f"  LSD: {lsd:.4f}")

        tb = transcribe(before_np, TARGET_SR)
        ta = transcribe(after_np, TARGET_SR) if after_np is not None else ""
        print(f"  Whisper before: {tb[:100] or '(silent/no speech)'}")
        if lavasr_ran:
            print(f"  Whisper after:  {ta[:100] or '(silent/no speech)'}")

        results.append({
            "file": af.name, "duration_s": round(duration,2),
            "lavasr_ran": lavasr_ran,
            "lsd_naive_vs_enhanced": round(lsd,4) if lsd is not None else None,
            "transcript_before": tb, "transcript_after": ta,
            "words_before": len(tb.split()), "words_after": len(ta.split()),
        })
    except Exception as e:
        import traceback; traceback.print_exc()
        results.append({"file": af.name, "error": str(e), "lavasr_ran": False})
    print()

ran = [r for r in results if r.get("lavasr_ran")]
print("=" * 55)
print(f"SUMMARY — {len(ran)}/{len(results)} ran LavaSR")

verdict = "INCONCLUSIVE"
recommendation = "Insufficient data"

if ran:
    lsd_vals = [r["lsd_naive_vs_enhanced"] for r in ran if r.get("lsd_naive_vs_enhanced") is not None]
    avg_lsd = np.mean(lsd_vals) if lsd_vals else None
    avg_wb = np.mean([r.get("words_before",0) for r in ran])
    avg_wa = np.mean([r.get("words_after",0) for r in ran])
    if avg_lsd: print(f"Avg LSD:            {avg_lsd:.4f}")
    print(f"Avg words before:   {avg_wb:.1f}")
    print(f"Avg words after:    {avg_wa:.1f}")

    if WHISPER_AVAILABLE and avg_wb > 0:
        if avg_wa > avg_wb * 1.1:
            verdict = "POSITIVE"
            recommendation = "Integrate: SDR -> LavaSR enhance -> Silero VAD -> Whisper"
        elif avg_wa < avg_wb * 0.9:
            verdict = "NEGATIVE"
            recommendation = "Skip LavaSR — transcription degrades"
        else:
            verdict = "NEUTRAL"
            recommendation = "LavaSR minimal transcription impact on these samples; monitor with low-quality SDR captures"
    elif avg_lsd and avg_lsd > 0.05:
        verdict = "SIGNAL_CHANGED"
        recommendation = "LavaSR modifies spectrum significantly — needs Whisper comparison on real SDR captures (not post-processed MP3s)"

print(f"\nVERDICT: {verdict}")
print(f"RECOMMENDATION: {recommendation}\n")

md = f"""# LavaSR v2 Ablation Results

Generated: {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}  
Device: {DEVICE} | LavaSR 0.0.2

## Verdict: {verdict}

**Recommendation:** {recommendation}

## Results

| File | Duration | LavaSR | LSD | Words before | Words after |
|------|:---:|:---:|:---:|:---:|:---:|
"""
for r in results:
    lsd_s = f"{r['lsd_naive_vs_enhanced']:.4f}" if r.get("lsd_naive_vs_enhanced") is not None else "N/A"
    md += f"| {r['file']} | {r.get('duration_s','?')}s | {'✅' if r.get('lavasr_ran') else '❌'} | {lsd_s} | {r.get('words_before','?')} | {r.get('words_after','?')} |\n"

md += "\n## Transcription Samples (Whisper tiny)\n\n"
for r in ran[:4]:
    md += f"**{r['file']}**\n- Before: {r.get('transcript_before') or '(silent)'}\n- After:  {r.get('transcript_after') or '(silent)'}\n\n"

md += """## Methodology

- Audio source: Kenneth/audio_samples (real radio MP3s — post-processed ElevenLabs denoise tests)
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
"""

with open("ablation_results.md","w") as f: f.write(md)
with open("ablation_results.json","w") as f:
    json.dump({"generated": datetime.datetime.now(datetime.timezone.utc).isoformat(), "verdict": verdict,
               "recommendation": recommendation, "results": results}, f, indent=2)
print("Written: ablation_results.md + ablation_results.json")
