# Wichita progress review, 2026-09-14

The operator queue now includes non-stress alerts. The next milestone is one
genuine RF record, with traceable source, observation time, audio and analysis,
reviewable through the local evidence dashboard.

## GitHub parity

- Repository: `https://github.com/mattcarp/mc-wichita.git`, local branch `main`.
- Local HEAD, freshly fetched `origin/main`, and GitHub's advertised main all
  resolve to `8a530eb65226b7259863b4f10e26a6942d1fa9d2`: 0 ahead, 0 behind.
- Latest main commit: July 9, 2026, 21:03:17 +02:00.
- No commits since September 13, 2026, 00:00 +02:00 on any fetched branch.
- `remote.origin.fetch` is unset. A normal fetch fetched main only. An explicit
  all-heads refspec refreshed remote-tracking metadata without changing config,
  the index, or the checkout. It discovered two previously missing branch refs.
- The newer rename and evidence-dashboard work is staged/unstaged/untracked
  locally, not included in main parity.

| Remote branch | Advertised head |
| --- | --- |
| `main` | `8a530eb65226b7259863b4f10e26a6942d1fa9d2` |
| `archive/signal-ethics` | `be627670d4f5edecd3a53e0ebfceb2ddaa1f0376` |
| `feat/systemd-services` | `3f021d6c82e39c229f1fc769041d23abc2c4b46e` |
| `feat/waterfall` | `c486682e7c5b7e521c06ffed94412c563461eb08` |
| `workshop-kenneth-features-2026-05-08` | `3eb63d8bcd0562995755a1eb37554d4ea8e7da6f` |

## Complete changed-file inventory at entry

28 non-generated, non-vendor paths: 18 tracked and 10 untracked. Renames count
once at their destination. All changed hunks and all new application/test source
were inspected. Canonical PRD, mission, architecture and evidence review were
read for context. No `.taskmaster` directory was present.

| Path | Entry state | Review scope |
| --- | --- | --- |
| `AGENTS.md` | staged | Identity, canonical-doc and path rename |
| `ARCHITECTURE.md` | staged | Rename and architecture claims versus implementation |
| `DOCKER_INSTALLATION_GUIDE.md` | staged | Renamed container/config examples |
| `DOCUMENTATION.md` | staged | Renamed document/frontend references |
| `ELEVENLABS_INTEGRATION.md` | staged | Pipeline naming |
| `INSTALL.md` | staged | Renamed frontend instructions |
| `MAC_MINI_DEPLOYMENT.md` | staged | Renamed deployment references |
| `MISSION.md` | staged | Dual mission, provenance and rename |
| `WICHITA_PRD.md` | staged rename | Former `KENNETH_PRD.md`; requirements unchanged except naming |
| `ablation_results.md` | staged | Audio-source naming |
| `api_server.py` | unstaged | Evidence/question/health and allowlisted dashboard routes; callers/models |
| `dashboard/index.html` | staged and unstaged | Rename plus replacement evidence workspace |
| `dashboard_map.html` | staged | Title/heading rename; legacy surface |
| `symphony/WORKFLOW.md` | staged | Clone URL, worktree and canonical-doc references |
| `wichita-websdr/.gitignore` | staged rename | Identical content |
| `wichita-websdr/package.json` | staged rename | Identical scripts/dependencies; app source absent |
| `wichita_qwen3_integration.py` | staged rename | Output guide rename; simulation implementation |
| `wichita_qwen3_integration_guide.md` | staged rename | Title/integration naming; example status |
| `GODS_EYE_VIEW_REVIEW.md` | untracked | Implementation, acceptance and Sept 13 recovery record |
| `dashboard/browser_test_server.py` | untracked | In-memory presentation fixtures, no dispatch |
| `dashboard/dashboard.css` | untracked | Layout, tokens, responsive rules |
| `dashboard/dashboard.js` | untracked | Fetching, queue, evidence, audio, questions, map |
| `dashboard/evidence-model.mjs` | untracked | Normalization, freshness, retry, coordinates, audio policy |
| `dashboard/test_browser.mjs` | untracked | Real API/browser flows and visual stability |
| `dashboard/test_evidence_model.mjs` | untracked | Seven display-policy tests |
| `evidence_context.py` | untracked | Evidence, question and delivery-time semantics |
| `test_evidence_api.py` | untracked | Read-only API and existing audio tests |
| `test_evidence_context.py` | untracked | Unknowns, geography, timestamps and multilingual evidence |

Excluded: four tracked deleted `__pycache__/*.pyc` files, renamed WebSDR
`.next/trace`, three untracked Leaflet vendor/license files, and existing
`output/playwright` screenshots/scanner output. These were inventoried, not
treated as authored application changes. The review's isolated environment and
new screenshots are also generated outputs.

Additional integration context inspected: `api_maritime_aviation.py`,
`maritime_aviation_capture.py`, `ais_decoder.py`, `ai_analysis_pipeline.py`,
adjacent API tests, and remote `feat/systemd-services:SERVICES.md`.

## Findings

- F1, fixed: `dashboard/dashboard.js:5` fetched `/stress-alerts` for a queue
  labelled All events. `api_server.py:405` excludes noncritical alerts without
  stress terms. A warning about coordinated interference therefore disappeared
  despite the threat-detection mission and PRD all-alert timeline requirement.
  The queue now fetches the existing `/alerts?limit=40`; it remains a bounded
  recent-record queue, not a full archive.
- F2, open: `api_server.py:944` and `api_server.py:1386` create records with naive
  `datetime.now()`. `evidence_context.py:27` correctly rejects those timestamps
  for age calculations. Actual API-created records consequently lack a usable
  delivery age, while aware UI fixtures pass. New records need explicit UTC;
  historical timezone-less records must remain unknown. This is actionable
  locally and does not require live hardware to design the timestamp contract.
- F3, integration gap: `api_server.py:320` keeps alerts/captures only in process
  memory; `api_server.py:1085` always calls `get_sample_vessels()`. The actual
  route is `/maritime/ais`, despite the older review's `/ais/vessels` reference.
  This checkout has no `rf_captures/`. Audio fixtures exist, but their presence
  does not establish live reception or a synchronized RF/AIS observation.
- F4, documentation gap: `INSTALL.md:32` and `MAC_MINI_DEPLOYMENT.md:38` direct
  users to a WebSDR frontend whose directory contains only a package manifest,
  ignore file and generated trace, with no Next app/pages source. The locally
  tested UI is the FastAPI root plus `dashboard/`. Likewise,
  `wichita_qwen3_integration.py:84` explicitly simulates transcription; the
  renamed guide does not establish a working provider integration. Architecture
  S2S/accuracy/latency statements remain targets, not demonstrated capabilities.

The March 1 remote service record names `kenneth-dashboard.service`,
`kenneth-sentinel.service`, and `kenneth-hunter.service` on the former Workshop
NUC. This is historical discovery evidence only. No service host was contacted,
and no current receiver location or service state was inferred from it.

## Changes and verification

Authored changes are limited to `dashboard/dashboard.js`,
`dashboard/browser_test_server.py`, `dashboard/test_browser.mjs`, and this report.
All entry-stage changes and existing screenshots were preserved.

- Added a warning-level non-stress threat fixture, directly in process memory.
  No alert-creation route or outbound dispatch was invoked.
- Added browser coverage for that threat, its recorded trigger, and the
  Alerts/Captures/All events filters. Confirmed the stress-only endpoint excludes
  it. Before the endpoint change, the browser test failed waiting for this row.
- After the change: 17 browser scenarios, 17 Python evidence/API tests, and
  7 JavaScript policy tests passed, with no skips.
- Verified real existing local audio playback, four transcript languages,
  partial failure, offline recovery, stale/paused state and keyboard focus.
- Inspected threat screenshots at 375/768/1440: no horizontal overflow or
  overlapping text, and zero browser console/page errors. Existing sample
  visual-stability comparisons passed at all three widths. There is no approved
  baseline, so this does not claim design regression acceptance by Matt.
- Screenshots are under `output/playwright/alert-coverage-20260914/`; older
  screenshots were not overwritten.
- Unstaged `git diff --check` passed. The staged rename has pre-existing trailing
  spaces at `ELEVENLABS_INTEGRATION.md:52` and `WICHITA_PRD.md:312`, preserved.
- Seven existing dependency deprecation/configuration warnings were reported.
  An isolated `.venv-wichita-review` installed the existing test/API dependencies;
  no project dependency manifest was changed.
- No full hardware/dispatch suite, fresh Semgrep scan or independent Fiona run
  was performed. No new components, capture logic or dispatch behavior changed.
  Authentication tests are not applicable to this dashboard, which has no login.

## Next milestone and blockers

Deliver one traceable RF event into this review queue: original audio reference,
source identifier, timezone-aware observation and ingestion times, original
transcript/language when available, analysis method and recorded trigger.
Unavailable fields must stay explicitly unknown. Prove API-to-browser fidelity
and have Matt inspect the recording and evidence.

The first local implementation step is F2's timestamp contract, followed by a
read-only import from the identified capture producer or an existing genuine
record plus sidecar metadata. Keep imports separate from alert dispatch. The
producer's current host/output and a genuine record with provenance still need
to be identified; the historical Workshop service document is not sufficient.

Quiet-versus-stalled diagnosis additionally requires actual capture/decoder
progress telemetry and expected cadence. Vessel association requires synchronized
RF and real AIS observations. Neither is a reason to delay the timestamp fix or
the first evidence import. Matt's manual smoke test remains outstanding.

No commit, push, pull, reset, deployment, hardware change or outbound alert was
performed. This review is scoped only to Wichita.
