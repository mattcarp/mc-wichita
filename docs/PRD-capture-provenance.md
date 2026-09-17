# PRD — capture provenance and the first traceable record

Status: proposed, not started. Owner: Matt. Needs a go before code.

## Problem

The stated next milestone is *one genuine RF record, traceable from source to
screen*. It is blocked, but not for the reason the 2026-09-14 review gives. There
is no `rf_captures/` and no live reception, true — but three recordings already
sit at the repo root:

```
REAL_RTL_CAPTURE_FM_Radio_Test_88.5MHz_20250912_194650.wav
REAL_RTL_CAPTURE_Maritime_CH09_156.45MHz_20250912_194702.wav
REAL_RTL_CAPTURE_Maritime_CH16_156.8MHz_20250912_194656.wav
```

What is known about them, verified on 2026-09-17:

- 48 kHz, mono, PCM_16, 5.00 s, 240000 samples.
- Non-silent: peaks at 0.700, RMS between -5.9 and -7.8 dBFS.
- Pairwise correlation between all three is ~0.000, so they are three distinct
  recordings, not one file copied.
- The identical 0.700 peak is explained by `rtl_sdr_real_capture.py`: lines 203
  and 234 normalise to 0.7, and line 269 captures 5 s. So the files are
  consistent with having come off real hardware.

What is *not* known: whether they came off the air at those frequencies, when, on
what receiver, and with what gain. The filename asserts it. A filename is not
provenance, and this repo also contains `fake_audio_backup/` with
`REAL_MARITIME_CH16_*` and `VOICE_CAPTURE_CH16_Emergency_*` files, so the
distinction between real and plausible has already been blurred once here.

Meanwhile the evidence layer cannot see any of them: there is no source record,
no observation time, no analysis method, and no import path. Every field the
evidence review asks for is missing because nothing writes them down.

## Goal

Every capture carries machine-readable provenance, and one record with real
provenance flows all the way from audio file to the operator's screen.

## Non-goals

- No live capture, no hardware, no antenna. This slice is file-based.
- No change to alert dispatch. Import stays separate from dispatch, permanently.
- No expansion of capture scope or retention.
- No new runtime dependencies.
- No claim that a capture is genuine until it is established as such.

## Design

### 1. Sidecar metadata, SigMF-shaped

One JSON file beside each capture, `<capture>.sigmf-meta`, following the SigMF
global-object idiom (spec v1.2.6) so the format is not invented here.

```json
{
  "global": {
    "core:datatype": "rf32_le",
    "core:sample_rate": 48000,
    "core:version": "1.0.0",
    "core:hw": "RTL-SDR Blog V3, gain 40 dB",
    "core:author": "Matt Carpenter",
    "wichita:source": "wichita-sdr",
    "wichita:frequency_hz": 156800000,
    "wichita:provenance_status": "unverified",
    "wichita:method": "rtl_fm demod, 48 kHz mono, normalised 0.7",
    "wichita:tool": "rtl_sdr_real_capture.py",
    "wichita:audio_sha256": "<hex>"
  },
  "captures": [
    { "core:sample_start": 0, "core:frequency": 156800000,
      "core:datetime": "2025-09-12T19:46:56+02:00" }
  ],
  "annotations": []
}
```

`core:datetime` is the **observation time**, timezone-aware, derived from the
filename stamp interpreted in `Europe/Malta`. `provenance_status` is one of
`genuine`, `synthetic`, `unverified` and is never inferred — it is recorded.

### 2. Hash the audio

`audio_sha256` ties the sidecar to the bytes. A sidecar that has drifted from its
audio is worse than no sidecar, and the hash makes that detectable.

### 3. Read-only importer, separate from dispatch

A single function plus a thin CLI: read capture + sidecar, validate, emit an
`AlertRecord`-shaped evidence record into the existing store via the existing
route shape — **without** calling any dispatch path. Malformed or missing
sidecars are rejected loudly, not defaulted.

Unknowns stay unknown. A capture with no sidecar imports as `unverified` with an
explicit missing-fields list, which is a legitimate and useful state.

### 4. One field the evidence model already supports

`metadata.observed_at` drives the "observation time with timezone" check in
`evidence_context.py`. Populating it is what changes the record from
"undated" to ageable — the contract F2 established.

## Acceptance

1. A sidecar exists for all three `REAL_RTL_CAPTURE_*` files, and its
   `provenance_status` reflects what was actually established, not what was hoped.
2. Each imported record shows, in the dashboard, its identity, the audio playable
   locally, an aware observation time distinct from its creation time, and an
   explicit list of what is still unknown.
3. `evidence_context` reports a real `age_seconds` for an imported record.
4. Importing invokes no dispatch: no Discord, Telegram, or webhook call.
5. Browser verification at 375/768/1440 with no console errors.
6. Tests are real: no mocks, real local audio, real API. New module gets tests
   beside it.
7. `python3 -m pytest` on the touched modules passes, plus the 7 Node policy
   tests.

## The honest open question

Are those three recordings genuine off-air captures? Establish it and record
*how* — or label them `synthetic` or `unverified` and stop pretending. Either
answer is acceptable. An unlabelled "REAL_" file in a forensics repo is not.

This is deliberately the first task, because the platform's entire value is that
its evidence means something. Proving the provenance path on a file whose status
is already in doubt is the cheapest possible rehearsal for the day real
transmissions arrive.
