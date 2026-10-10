# Improvements informed by God's Eye View

Date: 2026-09-09
Status: work-in-progress checkpoint accepted for commit on 2026-09-20; real pipeline/feed integration remains outstanding.

## Implementation checklist

- [x] Inspect upstream patterns and verify local gaps.
- [x] Add read-only evidence, question and delivery-health routes.
- [x] Finish independent feed states and remove automatic sample substitution.
- [x] Finish selectable evidence, audio, multilingual transcript and provenance views.
- [x] Connect source-health indicators and evidence questions.
- [x] Finish map context with explicit unknown location and observation timing.
- [x] Run unit/API tests and browser checks at 375/768/1440 widths.
- [x] Complete visual and security review; resolve findings.
- [ ] Matt's manual smoke test.
- [ ] Connect genuine capture/decoder progress telemetry before claiming quiet-versus-stalled diagnosis.
- [ ] Connect verified timestamped vessel observations before implementing candidate vessel associations.

Matt authorised a local checkpoint commit on 2026-09-20. No deployment or upstream communication is included.

### Recovery verification, 2026-09-13

The temporary environment and demo processes from September 10 no longer existed. Recreated the isolated Python environment with the existing API/test dependencies and restarted the local API. No application-code fixes were needed.

- Re-ran all 7 JavaScript policy tests, 17 Python/API tests and 16 Playwright scenarios successfully, without skips.
- Checked the normal live screen separately: no console or page errors, six basemap tiles loaded. Responsive screenshots were refreshed at 375/768/1440px.
- `git diff --check` passed. Existing dependency deprecation warnings remain.
- Fetched GitHub main explicitly: local `main` and remote main both resolve to `8a530eb65226b7259863b4f10e26a6942d1fa9d2`, 0 ahead / 0 behind. The missing `remote.origin.fetch` configuration had left `origin/main` stale; only the remote-tracking reference was refreshed. No pull, stash, reset, commit or rename changes were made.
- Local API: `http://127.0.0.1:3000`. Select Historical samples for the labelled demonstration. The separate UI fixture server on port 3001 was stopped after testing.

Restart the demo while this temporary environment exists:

```sh
/tmp/wichita-evidence-venv/bin/python3 -m uvicorn api_server:app --host 127.0.0.1 --port 3000
```

If temporary files are cleared again, the same isolated setup can be recreated using the installed `uv` tool:

```sh
uv venv /tmp/wichita-evidence-venv
uv pip install --python /tmp/wichita-evidence-venv/bin/python3 fastapi uvicorn python-multipart numpy httpx pytest
```

These setup commands install existing dependencies for local verification, not a locked production environment. No credentials are needed for this read-only local dashboard check. The next operational step remains identifying the real capture/decoder service and its timestamped AIS output; this checkout still lacks that telemetry and `rf_captures/`. Matt's smoke test remains pending.

### Local verification, 2026-09-10

- 7 JavaScript policy tests passed.
- 17 Python evidence/API tests passed, including serving an existing local audio file. No tests skipped. Existing dependency deprecation warnings remain.
- 16 Playwright browser scenarios passed: empty live data, explicit samples, return to live, Unicode and escaped transcript markup, zero measurements, event coordinates/unlocated state, actual local audio playback, evidence questions, focus across refresh, partial outage, offline recovery and paused-data aging.
- Screenshots inspected at 375, 768 and 1440px. Repeated screenshots checked for unexpected visual changes, allowing tiny anti-aliasing noise. There is no previously approved visual baseline; this is layout review and visual stability verification, not a claim of comparison to an approved old design.
- Final ordinary browsing produced no console or JavaScript errors. Basemap tiles loaded successfully. Visible text weights were all 400 or below.
- Independent Fiona-style review verified focus, freshness and timestamp fixes and reviewed all three screen sizes.
- Semgrep ran 227 applicable security/secrets rules on the four changed application code files. One pre-existing warning remains in `api_server.py`'s `_post_json` dynamic urllib helper; inspected callers use configured webhook URLs. No new-code finding was reported. This does not certify the rest of the application.
- The local API was tested on 127.0.0.1:3000. The separate :3001 browser fixture runner uses the real API and in-memory UI records only, bypasses alert creation/dispatch, and performs no RF operations. Fixture text is explicitly not a transcript of its audio reference.
- Authentication checks are not applicable: this dashboard has no login flow. No auth bypass was introduced.

At Matt’s request on September 19, the UI includes an animated synthetic spectrum and waterfall above the evidence workspace. The preview is explicitly labelled, has a pause control, respects reduced motion, and does not create evidence or affect hardware. Browser verification passed 18 scenarios, including animation and pause, with no JavaScript page errors; reduced-motion startup was also checked. It retains the mission, event review and explicit historical sample access. Leaflet 1.9.4, already used by `dashboard_map.html`, is vendored locally with its license; no new application library is introduced. The unavailable central design-system checkout could not supply a CSS import; the UI uses local `--mac-*` tokens, the documented MAC blue-400 accent, solid backgrounds, light typography and semantic border colors.

### What is not established

This checkout has no `rf_captures/` directory and its existing `/ais/vessels` implementation uses `get_sample_vessels()`. The API's capture and alert stores are process-local. No decoder heartbeat, real AIS stream or synchronized RF/AIS fixture was available. The health endpoint therefore reports delivery evidence separately from unknown pipeline state, and the map plots only explicitly recorded event coordinates. It makes no vessel association. These are honest capability limits, not completed hardware acceptance tests.

### Reproduce the checks

```sh
node --test dashboard/test_evidence_model.mjs
python3 -m pytest test_evidence_context.py test_evidence_api.py -q
python3 -m uvicorn api_server:app --host 127.0.0.1 --port 3000
# In a separate terminal, explicitly start the isolated UI fixture runner:
python3 dashboard/browser_test_server.py
# Use an existing Playwright install, with pngjs available beside it:
PLAYWRIGHT_MODULE=/absolute/path/to/node_modules/playwright node dashboard/test_browser.mjs
```

The verification run used an isolated `/tmp/wichita-evidence-venv` with the API's existing Python requirements plus test/scanning tools, because the default Python lacked FastAPI. It used the desktop's bundled Playwright install. No project dependency file was changed.


## Objective

Learn from God's Eye View and adapt useful engineering and interaction patterns to improve Wichita. Integration with its application and upstream contributions are optional later outcomes. Preserve Wichita's RF capture, multilingual analysis, and distress-review mission.

Reviewed upstream commit: `759652207fd1279ece97f0f19af566feb9a82146`.
Reviewed local sources: `WICHITA_PRD.md`, `MISSION.md`, `ARCHITECTURE.md`, `dashboard/index.html`, `api_server.py`, `ai_analysis_pipeline.py`, and `ais_decoder.py`.
This is a source inspection. Neither system was run for this assessment. Existing local changes were left intact. Other projects have not been inspected; cross-project applicability below is a proposal.

## Ranked improvements

| Priority | Adaptation | Verified Wichita gap | Relative effort |
| --- | --- | --- | --- |
| 1 | Explicit data origin, availability, and freshness | Dashboard substitutes embedded entries for empty successful API responses; one failed request replaces all panels with fallback data. | Small to medium |
| 2 | Evidence attached to each selected event | Alert API includes ID, audio URL, language, confidence, source and metadata; dashboard normalization discards these fields. | Medium |
| 3 | Separate service health from useful data delivery | Dashboard records refresh time as its update time, including offline refreshes. It does not establish when each source last delivered an observation. | Medium; backend coverage needs further inspection |
| 4 | Ground operator queries in selected evidence | A structured selection/context pattern could support questions about a specific event and its evidence. No working equivalent was established in the reviewed dashboard. | Medium to large |
| 5 | Geographic and temporal context | A map could associate events with candidate tracks while preserving uncertainty. Synchronized local RF/AIS fixtures have not been established. | Large; dependent on evidence availability |

### 1. Make the dashboard's data states accurate

Upstream lesson: distinguish live observations, estimates, missing configuration and unavailable feeds. The AIS watchdog judges freshness by valid data arrival, with separate reporting and reconnect thresholds.

Local evidence:

- `dashboard/index.html`, `refresh()`: successful empty captures or alerts are replaced with `fallbackDetections` or `fallbackIntel`, while the source label says live API.
- The same method uses `Promise.all`; one endpoint failure switches every panel to embedded entries.
- `normalizeCapture()` substitutes -35 dBFS, 0.2 voice score and 0.5 voice ratio for absent or falsy measurements. Valid zero values also take these defaults.
- Offline refresh updates `lastUpdatedAt` to the current clock time, which is distinct from the time of the displayed observations.

Proposed behavior:

- Empty successful responses display an empty state.
- Missing measurements display unavailable; valid zero remains zero.
- Each panel handles its own failures and retains its last successful result with a stale label and age.
- Show last successful fetch separately from observation time. A successful fetch of old observations does not make those observations current.
- Embedded material appears only through explicit sample/replay selection and carries its origin and original time. Audit its provenance before calling it real capture evidence; some referenced filenames begin with `SIM_`.
- Do not change capture parameters, retention, scoring or alert dispatch in this slice.

Acceptance: empty response, absent measurement, valid zero, partial endpoint outage, complete outage, recovery and explicit replay all produce distinct accurate states. Browser checks must cover console errors, keyboard use and 375/768/1440 widths, followed by Matt's smoke test. Hardware behavior is outside this slice; no simulated hardware test should be presented as real reception validation.

### 2. Keep the evidence accessible

Upstream lesson: its context store retains metadata for a selected entity, shared by interface and voice actions.

Preserve Wichita alert IDs, source, original transcript, language, confidence, metadata and audio references through normalization. Selecting an alert should expose those fields and local audio playback where available. Keep model interpretation separate from transcript text. Label the current acoustic stress score as experimental, with method/version and supporting features where available; a numeric score is not a validated probability of distress.

Acceptance: an actual existing local alert retains its identity and available evidence from API through display. Missing audio and unknown language remain explicit. Maltese, English, Italian and Arabic content survives unchanged. Establish safe audio access before introducing a new playback route.

### 3. Monitor delivery, with source-specific rules

Upstream lesson: `aisWatchdog.js` separates data freshness from socket connectivity; `aisStreamAdapter.js` distinguishes transport, authentication and rate-limit failures. `retryableLoad.js` avoids caching a rejected load forever and applies bounded retries.

Adapt the principle in Python where Wichita needs it. First inventory existing backend health reporting to avoid duplicating it. Keep last sample, last decoded message and last alert separate: a quiet radio channel or absence of alerts is not proof of a broken receiver. Determine freshness thresholds from the source's expected behavior; do not copy AISStream's timings into RF capture.

Acceptance: distinguish a connected but stalled capture pipeline, healthy quiet channel, decode failure and analysis failure using real fixtures or real service behavior. Credential and quota errors must stay visible and must not trigger aggressive retries.

### 4. Add grounded operator questions after evidence selection

Use the selected event's structured record to answer questions such as what triggered this alert or what evidence is missing. Deterministic filtering and retrieval should supply facts to the model. Tool results must explicitly report success/failure; UI changes must finish before the assistant confirms them. Treat transcript content as evidence, never as instructions to the operator assistant.

Start with event inspection. Radio tuning, outbound alerts and other consequential actions are outside the proposed scope.

### 5. Evaluate maps only after the evidence model works

Start with the existing map capability before adding Cesium or replacing the dashboard. A geographically unknown RF event must remain unlocated. Nearby vessels are candidate associations, not identified speakers. Correlation must use observation timestamps and source positions, not animation coordinates or arrival time alone.

God's Eye View's motion model is useful for display ideas, but smoothing must never alter the underlying evidence. Evaluate new dependencies separately if a concrete operator task requires 3D.

## Recommended first implementation

Implement priority 1 as a bounded dashboard change after scope review. Preserve the existing uncommitted dashboard work. Use the project's required UI review and browser validation workflow; no commit, deployment or external communication is part of this proposal.

Then implement priority 2. These two improvements make Wichita more trustworthy and useful without coupling it to another application. Reassess priorities 3-5 after testing them with the operator.

## Applicability to other projects

Candidate reusable patterns are source/freshness presentation, selected-record evidence, classified failures and tools that confirm completed actions. Apply them only after inspecting the receiving project. Do not create a shared library until at least two implementations demonstrate the same need.

## Upstream sources

- [Contribution and layer contracts](https://github.com/bilawalsidhu/gods-eye-view/blob/759652207fd1279ece97f0f19af566feb9a82146/CONTRIBUTING.md)
- [AIS freshness state machine](https://github.com/bilawalsidhu/gods-eye-view/blob/759652207fd1279ece97f0f19af566feb9a82146/src/data/aisWatchdog.js)
- [Classified AIS failures](https://github.com/bilawalsidhu/gods-eye-view/blob/759652207fd1279ece97f0f19af566feb9a82146/src/data/aisStreamAdapter.js)
- [Retryable loading](https://github.com/bilawalsidhu/gods-eye-view/blob/759652207fd1279ece97f0f19af566feb9a82146/src/data/retryableLoad.js)
- [Entity context](https://github.com/bilawalsidhu/gods-eye-view/blob/759652207fd1279ece97f0f19af566feb9a82146/src/data/contextStore.js)
- [Voice action implementation](https://github.com/bilawalsidhu/gods-eye-view/blob/759652207fd1279ece97f0f19af566feb9a82146/src/voice/gevActions.js)
- [Display motion model](https://github.com/bilawalsidhu/gods-eye-view/blob/759652207fd1279ece97f0f19af566feb9a82146/src/data/motionModel.js)

If copying code later, preserve required upstream attribution and review the relevant code and data terms. This assessment copies no upstream implementation.

## September 19 instrument console design recovery

Matt rejected the evidence-first visual hierarchy. Reworked the opening view around the RF spectrum, multicolour waterfall, selectable preview frequencies, generated audio envelope and adjacent Malta map. Restored mission prominence, multilingual scope and a signal-to-evidence workflow strip. Synthetic visuals remain separate from evidence and hardware. Fiona source review found no blocking defect; its pause-control accessibility suggestion was applied. Browser coverage includes channel selection, shared pause, responsive layouts at 375/521/768/1440, and evidence regression scenarios. Operator visual acceptance remains pending.

## Session close, 2026-09-20

Matt reviewed the revised console, called it better, and requested a commit before changing projects. This is a work-in-progress checkpoint, not operational acceptance. Latest UI validation: 19 browser scenarios and responsive screenshots at 375/521/768/1440 with no JavaScript page errors. At close, 17 Python/API tests and 7 JavaScript evidence tests passed again. Existing Python dependency deprecation warnings remain.

Resume with real capture provenance and progress telemetry, followed by a verified timestamped vessel feed. Keep preview signals explicitly synthetic. Full operator smoke testing and live-hardware validation remain open. Generated screenshots and unrelated bytecode deletions are excluded from the checkpoint.

Pre-commit Semgrep security/secrets scan ran 234 applicable rules across the four application files with zero findings. Vendored Leaflet CSS/license whitespace was normalised without changing content or attribution.
