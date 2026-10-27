# Receiver scheduler

Small, receive-only scheduler for time-sharing Wichita’s SDRs across monitoring jobs. Pattern is similar in spirit to multi-band “watchkeeper” setups: a few receivers, many duties, explicit priorities.

## What it does

- Declares **receivers** (tunable range and maximum capture bandwidth).
- Declares **jobs** (center frequency, bandwidth, dwell time, priority, continuous vs periodic).
- **Assigns** jobs to receivers that can legally tune the frequency and fit the bandwidth.
- **Packs** multiple jobs into one wideband tune when they fit inside the receiver’s instantaneous bandwidth; otherwise **time-slices** sequential tune groups.
- Gives **marine distress** (`marine-ch16`, `marine-ch70-dsc`) the highest priority; continuous distress work **pre-empts** lower-priority jobs on the same receiver in the planning API.
- Rejects **forbidden** bands at parse time (TETRA 380–400 MHz, DECT, cellular 698 MHz–6 GHz). This is separate from the ground-voice Malta allowlist: the scheduler is meant for AIS, ADS-B, marine, airband, ISM, and field tests.
- Exposes **pure logic** in `wichita_receiver_scheduler.py`; hardware implements `ReceiverDriver` (tune + receive dwell only — no transmit API).

## Config

1. Copy `config/receiver_scheduler.example.json` to `config/receiver_scheduler.json` (or set `WICHITA_RECEIVER_SCHEDULER_CONFIG`).
2. Enable the feature flag:

```bash
export WICHITA_RECEIVER_SCHEDULER_ENABLED=true
export WICHITA_RECEIVER_SCHEDULER_CONFIG=config/receiver_scheduler.json
```

3. Inspect the computed plan (no hardware touched):

```bash
curl -s http://127.0.0.1:8000/api/receiver-scheduler/plan | jq .
```

`GET /api/receiver-scheduler/health` is always available and reports whether the flag is on.

Default is **off**: existing AIS supervisor, readsb, and capture pipelines are unchanged.

## How this fits the repo today

| Duty | Today | Scheduler role |
|------|--------|----------------|
| AIS on RSPdx | `ops/live/wichita_ais_supervisor.py` | Job `ais` when you choose to migrate |
| ADS-B | readsb / `WICHITA_ADSB_URL` | Job `adsb-1090` |
| Marine CH16 stream | `rtl_airband` + ground voice | Job `marine-ch16` (metadata only until wired) |
| Wideband voice hunt | `scan_config.py` / hunters | Periodic airband / FM jobs |

The scheduler does **not** replace those processes yet; it produces an assignment plan and optional dry-run driver hooks for tests.

## Deliberately not done yet

- No automatic takeover of AIS-catcher, readsb, or `rtl_airband` processes.
- No long-running tune loop in `api_server` lifespan (plan is on-demand via HTTP only).
- No SoapySDR / `hackrf_transfer` driver in-tree — implement `ReceiverDriver` when ready.
- No coordination with satellite pass prediction (`wichita_satellite_passes.py`) for weather-SAT dwell.
- No persistence of `last_run` for periodic jobs across API restarts.
- Dashboard UI for the plan is out of scope while the dashboard freeze remains (bug-fix / listening-feature exception only).

## Tests

```bash
python3 -m pytest test_wichita_receiver_scheduler.py -q
```

Uses `FakeClock` and `FakeReceiverDriver` only — no mocks of RF hardware.
