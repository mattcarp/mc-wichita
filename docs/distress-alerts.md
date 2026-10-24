# Marine distress alerts (DSC Ch 70 + COSPAS-SARSAT 406 MHz)

Wichita is **receive-only**. This path decodes maritime GMDSS DSC on VHF channel 70 and first-generation 406 MHz beacons (EPIRB / PLB / ELT). It never transmits.

## Frequencies

| Service | Centre frequency | Modulation | Data rate |
| --- | --- | --- | --- |
| DSC (Ch 70) | **156.525 MHz** | FM (16K0G2B) with 1200 baud FSK (1300 / 2100 Hz) | ITU-R M.493 |
| COSPAS-SARSAT | **406.0–406.1 MHz** (Malta scan list: 406.028 MHz) | FM-discriminator audio carrying biphase-L PSK | 400 bit/s, ~520 ms burst / ~50 s period |

## Architecture

```
Antenna → SDR (HackRF and/or SDRplay) → IQ capture (cs8 / sdriq / cs16)
       → wichita_iq (read + NFM audio)
       → dsc_decoder/ (VHF DSC, UNLICENSE / tomastnc)  OR  wichita_sarsat406 (406, Apache-2.0 port from HTCommander)
       → wichita_distress (timeline + alert_store)
       → Dashboard live timeline + alert review queue
```

Distress and urgency/safety DSC, plus non-test 406 beacons, append:

- Live events (`marine_distress_*`, `marine_urgency_dsc`, `marine_safety_dsc`) with **top timeline priority** (with silent/loitering and boats of interest below).
- Critical alerts in `alert_store` (same review flow as voice stress).

DSC messages that include a **self MMSI** attempt an AIS lookup via `wichita_ais_live.live_ship_detail` so the dashboard can link to a known vessel.

## Ch 70 vs existing AIS capture (SDRplay)

**AIS-catcher on the RSPdx-R2 is locked to 161.975 / 162.025 MHz.** It cannot decode Ch 70 without abandoning AIS.

**Recommendation (one receiver path):**

1. **Keep AIS-catcher on the SDRplay** for continuous AIS (map, Boats of Interest, silent/loiter).
2. **Add a dedicated Ch 70 receiver on the HackRF One** — centre 156.525 MHz, ≥ 2 MS/s IQ, write raw cs8 with `hackrf_transfer` (no trimming). Run `wichita_distress` offline replay in a launchd loop or a small supervisor that decodes rolling captures.
3. **406 MHz on the same HackRF** is possible by time-slicing captures (406.028 MHz, 2 MS/s, ~1 s every minute) because beacon bursts are short and sparse; for production, prefer a **second scheduled capture** so Ch 70 is not missed during EPIRB windows.

Do **not** retune the SDRplay away from AIS unless AIS is moved to another machine.

## Offline replay (stored IQ)

API (also used from the Mini for validation):

```bash
# DSC from WAV or IQ
curl -s -X POST http://127.0.0.1:8000/api/distress/decode/dsc \
  -H 'Content-Type: application/json' \
  -d '{"path":"/path/to/routine_call.wav"}'

# 406 from WAV or IQ (set sample_rate_hz for raw HackRF cs8 without header)
curl -s -X POST http://127.0.0.1:8000/api/distress/decode/epirb \
  -H 'Content-Type: application/json' \
  -d '{"path":"/path/to/capture.iq","sample_rate_hz":2000000}'
```

Python:

```bash
python3 -c "from wichita_distress import replay_capture; print(replay_capture('fixtures/distress/routine_call.wav'))"
```

Supported IQ: **HackRF cs8**, **SDRangel .sdriq** (32-byte header), **SDRplay interleaved cs16** (sample rate required in env or API body).

## Verified on real recordings

| Decoder | Fixture | Result |
| --- | --- | --- |
| DSC | `fixtures/distress/routine_call.wav` (SDRangel #1707) | **Verified** — individual call, MMSI 233333334 / 201444555 |
| DSC | `fixtures/distress/selective_individual_call_2….sdriq` (SDRangel #1707) | **Not verified** — IQ present (~2.6 s burst) but FSK decode does not yet pass; tracked in `fixtures/distress/SOURCES.md` |
| 406 MHz | `fixtures/distress/sarsat_selftest_beacon.wav` (HTCommander) | **Verified** — hex `1C72091A2B3FDFF`, country 227, position 42.954° N, 1.364° E |

No synthetic on-air data is injected in production. Tests cite sources in `fixtures/distress/SOURCES.md`.

## Third-party code and licenses

| Component | Origin | License | Use |
| --- | --- | --- | --- |
| `dsc_decoder/` | [tomastnc/vhf-dsc-decoder](https://github.com/tomastnc/vhf-dsc-decoder) | **The Unlicense** | VHF DSC demod + ITU-R M.493 parse |
| `wichita_sarsat406.py` | Algorithm port from [HTCommander](https://github.com/ylianst/HTCommander) `sarsat_1g_*` (Apache-2.0) | Apache-2.0 (attribution in module docstring) | 406 demod + BCH/frame parse |
| SDRangel `demoddsc` | GPL-3 | **Not copied** — behaviour reference only |
| PortaPack Mayhem `epirb_rx` | GPL | **Not copied** — behaviour reference only |

## Enable on the Mac Mini (after review — not deployed by agents)

1. **HackRF Ch 70 capture** (example, receive-only):

   ```bash
   infisical run --env=dev -- hackrf_transfer -r /var/wichita/captures/ch70_$(date -u +%Y%m%dT%H%M%SZ).iq \
     -f 156525000 -s 2000000 -l 32 -g 40 -a 1 -n 8000000
   ```

2. **Decode loop** (cron or launchd calling API):

   ```bash
   infisical run --env=dev -- python3 -c "
   from wichita_distress import decode_dsc_file, ingest_dsc_messages
   ingest_dsc_messages(decode_dsc_file('/var/wichita/captures/latest_ch70.iq'), source='mini-hackrf')
   "
   ```

3. **406 MHz** — schedule separate `hackrf_transfer` at `-f 406028000` (or use `scan_config.py` EPIRB entry) and `decode_epirb_file` + `ingest_epirb_frames`.

4. **API** — ensure `api_server.py` is running (port 8000); dashboard picks up timeline events from `WICHITA_EVENTS_DIR`.

5. **Environment**

   - `WICHITA_EVENTS_DIR` — live timeline JSONL (default `~/wichita/live/events`)
   - `WICHITA_IQ_SAMPLE_RATE=2000000` when decoding raw HackRF cs8 without metadata
   - Optional future: `WICHITA_DISTRESS_LIVE=1` when a supervised live ingest job is added on the Mini

6. **Do not** enable transmit paths, bias-tee keys, or retune the SDRplay AIS receiver without an explicit ops change.

## Dashboard

Distress DSC and 406 events use the **red `timeline-distress`** styling in the live harbour timeline, sorted above routine quiet/loiter events. Pending alerts appear in the existing alert review panel with `signal_type` `distress` / `marine_dsc` / `sarsat_406`.
