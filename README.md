# Wichita

**RF forensics platform with speech-to-speech emotional intelligence.**
Repository: `mc-wichita`.

Wichita listens to maritime, aviation and terrestrial radio from a rooftop antenna
in Valletta, Malta, and analyses *how* people speak, not only what they say. Its
two missions are fixed and not up for revision:

1. **Detect bad actors** — threatening language, criminal coordination, illegal
   activity, coded intent, unusual timing and frequency behaviour.
2. **Help people in distress** — explicit calls (MAYDAY, PAN-PAN, SOS) and
   implicit ones, including the case the platform exists for: "I'm fine" said
   while crying.

Multilingual by default: Maltese, English, Italian and Arabic.

## Naming

| | |
| --- | --- |
| Canonical | **Wichita** — after Glen Campbell's *Wichita Lineman* (1968): the man on the wire, listening to a signal nobody else hears. |
| Former working name | **Kenneth** — after R.E.M.'s *What's the Frequency, Kenneth?* (1994). Renamed to Wichita; the old name survives only in `archive/docs/` and in remote branch names, as history. |

Naming rule going forward: the product is **Wichita**, the repo is **mc-wichita**,
the frontend is **wichita-websdr**, and the capture source key is **wichita-sdr**.
Nothing new gets called Kenneth.

## Start here

- [`WICHITA_PRD.md`](WICHITA_PRD.md) — canonical product spec.
- [`MISSION.md`](MISSION.md) — mission statement and the immutable core.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — system architecture.
- [`AGENTS.md`](AGENTS.md) — rules for coding agents working in this repo.
- [`WICHITA_PROGRESS_REVIEW_2026-09-14.md`](WICHITA_PROGRESS_REVIEW_2026-09-14.md) — latest review, findings and open blockers.
- [`GODS_EYE_VIEW_REVIEW.md`](GODS_EYE_VIEW_REVIEW.md) — evidence-model review and ranked improvements.
- [`docs/ROOFTOP_ARCHITECTURE.md`](docs/ROOFTOP_ARCHITECTURE.md) — antenna, PoE, cable and host design for the Valletta rooftop site.

## Stack

- **Python** — capture pipelines, API server (`api_server.py`), stress scoring,
  transcription evaluation (LAVASR ablation).
- **HTML / JS** — operational dashboard (`dashboard/`), WebSDR client (`wichita-websdr/`).
- **Hardware** — RTL-SDR, RSPdx-R2, SDR++.
- **ASR / S2S** — Whisper variants, Qwen3-ASR, OpenAI Realtime explored.

Bands of interest: AIS (161.975 / 162.025 MHz), ADS-B (1090 MHz), maritime VHF
(CH09 156.45 / CH16 156.8), aviation VHF AM (118–137 MHz), FM broadcast as a
control signal.

## Run the API and dashboard

```bash
infisical run --env=dev -- python3 api_server.py     # API + dashboard on 127.0.0.1:3000
infisical run --env=dev -- python3 ais_decoder_live.py
infisical run --env=dev -- python3 adsb_decoder_live.py
python3 -m pytest <module>/                          # tests live beside the module
```

Secrets come from Infisical only (`infisical run --env=dev -- …`). No plaintext
keys, ever.

## Status, stated plainly

Working: capture pipelines, decoding, stress scoring, alert dispatch, the local
evidence dashboard (17 Python/API tests, 7 JavaScript policy tests and 17 browser
scenarios passing as of the 2026-09-14 review).

Not yet established:

- No `rf_captures/` in the checkout and **no genuine capture record with
  provenance**. This is the next milestone and it needs the antenna.
- Timestamps: API-created records still use naive `datetime.now()` (finding F2);
  the UTC contract is the first local fix.
- `wichita-websdr/` currently holds a package manifest and no application source;
  the tested UI is the FastAPI root plus `dashboard/`.
- Capture and alert stores are process-local, so history dies with the process.
- The acoustic stress score is experimental, not a validated probability of distress.

See the progress review for the full list and the blockers behind each item.
