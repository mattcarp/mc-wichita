# AGENTS.md — mc-kenneth

Project context for AI coding agents (Claude Code, Cursor, Codex, Symphony workers).
This is the cross-tool standard file ([agents.md](https://agents.md/)). `CLAUDE.md` symlinks here.

## What this project is

**Kenneth — RF Forensics Platform with Speech-to-Speech Emotional Intelligence.** Monitors maritime and aviation frequencies in Malta to:
1. Detect threats through voice stress and behavioral analysis.
2. Save lives by identifying both explicit and implicit distress signals (e.g. "I'm fine" said while crying).

Multilingual environment (Maltese / English / Italian / Arabic). Runs against live SDR hardware (RTL-SDR, RSPdx, SDR++). Continuous capture from rooftop antenna, voice-stress scoring on captured audio, threat detection over keywords and behavioral cues.

Read [`KENNETH_PRD.md`](KENNETH_PRD.md) and [`MISSION.md`](MISSION.md) for the canonical product context. The other `KENNETH_*.md` docs are decision records and progress reports — useful background, not active specs.

## Stack

- **Python** primary — capture pipelines (`adsb_decoder_live.py`, `ais_decoder_live.py`), API server (`api_server.py`), stress scoring, transcription evaluation (LAVASR ablation).
- **HTML / JS** for dashboards (`dashboard/`, `kenneth-websdr/`).
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
kenneth-websdr/                    Web SDR client
ablation_output/                   LAVASR ablation results
lavasr_eval_output/                LAVASR evaluation runs
fake_audio_backup/                 Synthetic test data (label clearly)
SDR++.app/                         macOS SDR++ application
KENNETH_PRD.md                     Canonical product spec
MISSION.md                         Mission statement
ARCHITECTURE.md                    System architecture
RF_FORENSICS_PIPELINE_COMPLETE.md  Pipeline status report
KENNETH_*.md                       Decision + progress records (background, not specs)
symphony/                          Linear→Claude harness (port 4753)
openspec/                          OpenSpec proposals + locked specs
```

## Conventions

- Python is the default language for capture, decoder, and pipeline code.
- Use `python3` explicitly; do not assume `python` is on PATH.
- Tests live alongside the module (`test_<module>.py`), not in a separate `tests/` tree.
- Log through `logging` with structured fields; capture-pipeline runs produce timestamped output to disk.
- Frequencies are constants at module top; do not magic-number them inside loops.
- The README currently has placeholder content (junk paste from elsewhere). The real entry point is `KENNETH_PRD.md` until the README is rewritten.

## Symphony / agent runs (this is important if you're invoked from Symphony)

Inside a fresh clone at `~/symphony_workspaces/<ISSUE-ID>/` on workshop, on branch `symphony/<ISSUE-ID>`. Read this file + `KENNETH_PRD.md` + `MISSION.md` + the relevant module's source before making changes.

Capture-pipeline-affecting changes need explicit acknowledgement of impact in the commit body — which decoder is affected, whether existing fixtures still pass, whether the antenna setup needs to be re-validated. Don't silently change capture parameters.

For Python changes: run `python3 -m pytest <module>/` if tests exist for the touched module. New modules need real tests against `audio_samples/` or `rf_captures/` fixtures (no mocks).

For TypeScript inside `symphony/`: `cd symphony && npx tsc --noEmit`.

## What NOT to do

- Don't push captures or audio samples that contain identifiable third-party voices to public surfaces.
- Don't disable language support to simplify a model integration.
- Don't expand capture scope or retention without an explicit issue.
- Don't write tests against mocks for hardware-touching code.
- Don't introduce a new SDR backend or transcription model without surfacing the choice in the issue.
- Don't use emojis in code or commits. KENNETH_PRD.md has emojis (it's a record); don't propagate them into new code.
