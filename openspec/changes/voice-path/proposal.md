# Voice path

Status: proposed, 2026-10-14. Alpha, one user (Matt), receive only.

## Why

Wichita's purpose is human voices over radio: a pilot, a skipper, someone on the ground on a
distress frequency. Today the pieces exist but do not form one path. About 20 modules cover
capture, demodulation, transcription, stress, distress and alerts, with several overlapping
"voice hunters". Alerts live only in process memory, and the Qwen3 transcription integration
is simulated. Nothing yet carries one real transmission from the antenna to a reviewable record.

Split Wichita into two paths:

- **Voice path (this change):** analogue voice channels. Find speech, keep the clip, write down
  what was said and in which language, score how the speaker sounds, put one evidence record in
  the review queue.
- **Data path (later, separate):** AIS, ADS-B, DSC, ACARS, NAVTEX. Decoders, positions, tracks.
  The voice path may look up the data path (which vessel was near CH16 at that minute) but never
  depends on it.

## Scenario it enables

A skipper calls on Marine CH16 in Maltese, sounding exhausted and confused, without saying
"mayday". Wichita keeps the clip, transcribes it in Maltese, scores the voice as stressed, flags
the transcript for implicit distress, and shows Matt one record with the audio, frequency,
UTC time, transcript, language, scores and why it was flagged. Matt listens and decides.

## Stages

1. **Tune and demodulate.** AM for airband (118-137, 121.5, 123.1, 225-400 MHz), narrow FM for
   marine VHF, amateur, PMR446 and CB. Frequencies from `scan_config.py`. SSB for HF is a later
   task.
2. **Find speech.** Squelch plus voice activity detection, so silence and carrier noise never
   become records.
3. **Keep the clip.** WAV plus a SigMF-shaped provenance sidecar (`capture_provenance.py`):
   frequency, mode, receiver, UTC start and end, signal level.
4. **Transcribe.** Language identification, then the best model per language. Maltese goes to
   the Maltese Whisper fine-tune already used by mc-vuci; English, Italian and Arabic to
   Whisper large-v3. A transcript that the model is unsure of is marked unsure, never dropped.
5. **Score the voice.** Acoustic stress (`stress_scorer.py`), implicit distress from the
   transcript (`implicit_distress_detector.py`), keywords (`keyword_threat_detection.py`).
6. **One evidence record.** Persisted to disk (not memory), UTC timestamps (fixes F2 and F3 from
   the 2026-09-14 review), surfaced in the existing review queue with playable audio.

## Decisions for Matt

- D1. **Consolidate, don't add.** One `voice_path.py` that calls the existing modules stage by
  stage. The duplicate hunters stay untouched until the path works, then retire.
- D2. **Maltese transcription** uses the mc-vuci Maltese Whisper (trained on MASRI,
  non-commercial; fine for a one-user alpha).
- D3. **Text distress check with Jev** as an optional extra judge on the transcript (fast, about
  0.3 s). Jev reads text only, so it adds to, never replaces, the acoustic stress score.
- D4. **Runs where the receiver is.** Develop and test here from files; run live on the machine
  with the SDR attached.

## Affected pipelines

New path only. AIS and ADS-B decoders untouched. `rtl_sdr_real_capture.py` and
`rspdx_capture_pipeline.py` are called, not changed, until a demodulation fix is needed. Existing
tests must keep passing.

## Languages

Maltese, English, Italian, Arabic. No language is filtered out; an unknown language is recorded
as unknown with the audio kept.

## Non-goals

- The data path (decoders, maps, vessel association).
- Alert dispatch to anyone but Matt. No outbound SMS, Telegram or emergency services.
- Speech-to-speech agents and the S2S architecture in ARCHITECTURE.md.
- Cellular, TETRA or any encrypted service.
- Legal review. Before any beta, the MCA is asked about every band.
