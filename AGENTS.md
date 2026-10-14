# AGENTS.md — mc-wichita

Project context for AI coding agents (Claude Code, Cursor, Codex, Symphony workers).
This is the cross-tool standard file ([agents.md](https://agents.md/)). `CLAUDE.md` symlinks here.

## What this project is

**Wichita — RF Forensics Platform with Speech-to-Speech Emotional Intelligence.** Monitors maritime and aviation frequencies in Malta to:
1. Detect threats through voice stress and behavioral analysis.
2. Save lives by identifying both explicit and implicit distress signals (e.g. "I'm fine" said while crying).

Multilingual environment (Maltese / English / Italian / Arabic). Runs against live SDR hardware (RTL-SDR, RSPdx, SDR++). Continuous capture from rooftop antenna, voice-stress scoring on captured audio, threat detection over keywords and behavioral cues.

Read [`WICHITA_PRD.md`](WICHITA_PRD.md) and [`MISSION.md`](MISSION.md) for the canonical product context. The other `WICHITA_*.md` docs are decision records and progress reports — useful background, not active specs.

## Stack

- **Python** primary — capture pipelines (`adsb_decoder_live.py`, `ais_decoder_live.py`), API server (`api_server.py`), stress scoring, transcription evaluation (LAVASR ablation).
- **HTML / JS** for dashboards (`dashboard/`, `wichita-websdr/`).
- **Shell** for setup and capture orchestration.
- **SDR hardware:** RTL-SDR, RSPdx; **SDR++.app** present for desktop-side inspection.
- **STT / S2S:** OpenAI Realtime + Whisper variants explored; LAVASR evaluation work.
- **Frequencies of interest:** AIS (maritime, 161.975 / 162.025 MHz), ADS-B (aviation, 1090 MHz), Maritime VHF channels (CH09 / CH16), FM broadcast as control signal.

## Hard rules (non-negotiable)

1. **All secrets through Infisical.** API keys (OpenAI, ElevenLabs), hardware credentials — via `infisical run --env=dev -- python3 …`. Never plaintext.
2. **No production deploy without `[symphony:deploy-ok]` marker per-issue.** Production for this project means: a release running on the rooftop SDR pipeline, a published demo, a system handed to a partner. Don't do that without explicit per-issue authorization.
3. **No mocks for hardware-affecting tests.** Use real audio captures (the repo has `audio_samples/` and `rf_captures/`), real SDR fixtures, or skip honestly. The whole point of the platform is real-world signal — mocked tests give false confidence.
4. **Don't push to `main` from agent runs.** Symphony branches stay local unless an issue carries `auto-push`.
5. **Don't introduce new dependencies without surfacing the choice.**
6. **Never commit changes unless the user explicitly asks.** No Co-Authored-By trailers; commits are authored by Matt Carpenter.
7. **Multilingual content stays multilingual.** Don't drop language support in passing edits. Maltese is small-language; if a tool only handles English, mark that limitation explicitly rather than silently filtering.
8. **Privacy and ethics posture.** This platform listens to live radio. Captures of live transmissions sit in `rf_captures/`. Respect data minimisation; don't expand capture scope or retention without an issue that explicitly authorises it. Don't push real captures to public surfaces.

## Dashboard feature freeze (from 2026-10-13)

The dashboard is ahead of the product. The hero says Wichita listens for how people sound, but the voice and ASR panels are still placeholders. Until that changes, the dashboard (`dashboard/`, `wichita-websdr/`, `tests/visual/`) is frozen.

**Allowed during the freeze:**
- Bug fixes: something broken, wrong or crashing.
- Data correctness: a feed showing stale, false or misleading values.
- Security, privacy and accessibility fixes.
- UI that a listening feature needs in order to ship. Build it in the same change as the feature.

**Not allowed:** restyles, copy rewrites, new panels, layout tweaks, new visual baselines for cosmetic changes, and map or ship-card polish. Put those ideas in `docs/notes/dashboard-backlog.md` instead.

**The freeze lifts** when the live dashboard shows one real received transmission end to end:
1. captured from the receiver chain,
2. transcribed, with the language marked,
3. scored for voice stress,
4. shown in the UI with its provenance.

Synthetic audio, `fake_audio_backup/` and mocked scores do not count. Record the lift in this section with the date and the commit.

**Approved exception (2026-10-14): ground voice.** Mattie approved the receive-only ground-voice feature (Heard tab, "Ground voice") during the freeze. Code: `wichita_ground_voice.py`, `wichita_ground_voice_routes.py`, `dashboard/ground_voice.js`. It ships gated: no audio flows until `WICHITA_GROUND_VOICE_CLEARED=true` is set after the MCA/IDPC opinions (item 2 below), and only for the Malta allowlist. The freeze otherwise stays on.

**Next listening work, in order:**
1. ADS-B from our own receiver: 1090 MHz antenna, readsb and the OpenSky feeder on the Mini. This gives the map real data, but the freeze stays on.
2. Get the legal opinions for ground voice. See `docs/notes/opensky.md`, to-do list. No ground-voice capture before they arrive (hard rule 8).
3. Pick a Maltese-capable ASR for the transcript slot. The leading candidate is mc-vuci's Maltese Whisper: 19.37% WER on FLEURS mt, against 21.90% for Parakeet. Surface the choice in an issue before wiring it in. English, Italian and Arabic must keep working.

## Commands

```bash
infisical run --env=dev -- python3 api_server.py            # start API server
infisical run --env=dev -- python3 ais_decoder_live.py      # AIS decoder
infisical run --env=dev -- python3 adsb_decoder_live.py     # ADS-B decoder
python3 -m pytest <module>/                                  # tests for a module
```

For symphony harness work specifically (TS, lives in `symphony/`):

```bash
cd symphony && npm install && npx tsc --noEmit
```

## Layout (key directories — there are many supporting files)

```
api_server.py                      Main API server
adsb_decoder_live.py               Aviation ADS-B live decoder
ais_decoder_live.py                Maritime AIS live decoder
ais_live_pipeline.py               AIS capture → decode pipeline
audio_samples/                     Real audio captures (test fixtures)
rf_captures/                       Real RF captures
config/                            Configuration files
dashboard/                         Web dashboard
wichita-websdr/                    Web SDR client
ablation_output/                   LAVASR ablation results
lavasr_eval_output/                LAVASR evaluation runs
fake_audio_backup/                 Synthetic test data (label clearly)
SDR++.app/                         macOS SDR++ application
WICHITA_PRD.md                     Canonical product spec
MISSION.md                         Mission statement
ARCHITECTURE.md                    System architecture
WICHITA_*.md                       Decision + progress records (background, not specs)
archive/docs/                      Archived status/handoff/todo reports (historical, not specs)
symphony/                          Linear→Claude harness (port 4753)
openspec/                          OpenSpec proposals + locked specs
```

## Conventions

- Python is the default language for capture, decoder, and pipeline code.
- Use `python3` explicitly; do not assume `python` is on PATH.
- Tests live alongside the module (`test_<module>.py`), not in a separate `tests/` tree.
- Log through `logging` with structured fields; capture-pipeline runs produce timestamped output to disk.
- Frequencies are constants at module top; do not magic-number them inside loops.
- The README currently has placeholder content (junk paste from elsewhere). The real entry point is `WICHITA_PRD.md` until the README is rewritten.

## Symphony / agent runs (this is important if you're invoked from Symphony)

Inside a fresh clone at `~/symphony_workspaces/<ISSUE-ID>/` on workshop, on branch `symphony/<ISSUE-ID>`. Read this file + `WICHITA_PRD.md` + `MISSION.md` + the relevant module's source before making changes.

Capture-pipeline-affecting changes need explicit acknowledgement of impact in the commit body — which decoder is affected, whether existing fixtures still pass, whether the antenna setup needs to be re-validated. Don't silently change capture parameters.

For Python changes: run `python3 -m pytest <module>/` if tests exist for the touched module. New modules need real tests against `audio_samples/` or `rf_captures/` fixtures (no mocks).

For TypeScript inside `symphony/`: `cd symphony && npx tsc --noEmit`.

## What NOT to do

- Don't push captures or audio samples that contain identifiable third-party voices to public surfaces.
- Don't disable language support to simplify a model integration.
- Don't expand capture scope or retention without an explicit issue.
- Don't write tests against mocks for hardware-touching code.
- Don't introduce a new SDR backend or transcription model without surfacing the choice in the issue.
- Don't use emojis in code or commits. WICHITA_PRD.md has emojis (it's a record); don't propagate them into new code.

## Cursor Cloud specific instructions

- The API listens on port 8000. Start it with `python3 api_server.py`. The README documents port 3000.
- Pytest collection fails on scripts that exit or open WAV files at import. Run:

```bash
python3 -m pytest --ignore=test_audio_pipeline.py --ignore=before_after_test.py --ignore=test_api_directly.py --ignore=test_consistency.py --ignore=test_determinism.py --ignore=test_formats.py --ignore=test_maltese.py --ignore=test_maritime.py
```

`test_audio_pipeline.py` calls `sys.exit` when `audio_preprocessor` is missing. The other ignored scripts open WAV captures at import time.

- Symphony: `npm ci --prefix symphony`, then `npx tsc --noEmit` from `symphony/`.
- Live AIS and ADS-B decoders are separate processes. The API stays up when they are absent.
