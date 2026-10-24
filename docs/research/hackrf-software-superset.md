# Wichita vs HackRF software: superset tracker

_Last updated 2026-10-24 (Europe/Malta). Author: Grok Bot, for Mattie._

Mattie's ask (via MC Mac Mini): survey the computer-side software for the HackRF, list every feature,
and make sure Wichita ends up a **superset** of all of them. This is the research record behind the
Page of the same name. Wichita stays **strictly receive-only**; anything that transmits or targets
cellular/TETRA/DECT is excluded on purpose (see the last section).

## Scope and method

- **Open-source tools**: features read from their source trees and docs (release tags checked live on
  2026-10-24).
- **Closed-source tools** (SDRconnect, SDR# ): features read from vendor docs, and for SDRconnect,
  static binary analysis with the REA reverse-engineering connector on a copy of Mattie's own install.
- **Verified vs assumed** is stated throughout. Nothing was run against live radio; no installs were
  made on the Mac Mini or the MacBook Air.

## Hardware baseline (verified)

- HackRF One (clone board), firmware **2026.01.3**, Homebrew `hackrf-tools` 2026.01.3 on the Mac Mini.
- SDRplay RSPdx-R2 (runs AIS-catcher).
- RTL-SDR Blog V4 (feeds rtl_airband ch16; currently unplugged per the sea-test thread).
- MacBook Air: `SDR++.app` and `SDRconnect.app` in /Applications, plus `hackrf_transfer`/`hackrf_sweep`.

## The tools surveyed (versions verified 2026-10-24)

| Tool | Latest | License | Role |
| --- | --- | --- | --- |
| hackrf-tools | 2026.01.3 | open (GPL) | CLI: sweep, transfer, info, biast, clock, cpld, debug, operacake |
| SDR++ | 1.0.4 / nightly | open (GPL) | Cross-platform live receiver; bundled on the Air |
| SDRconnect | 1.0.10 (SDRplay) | **closed** | SDRplay's receiver; installed on the Air; HackRF not a source |
| SDRangel | 7.27.2 | open (GPL) | Multi-demod Swiss-army receiver, huge decoder set |
| GQRX | 2.17.7 | open (GPL) | GNU Radio/Qt receiver |
| GNU Radio | 3.10.12 | open (GPL) | DSP flowgraph framework |
| Universal Radio Hacker (URH) | 2.10.0 (archived) | open (GPL) | Protocol RE, demod, decodings (also fuzz/TX — excluded) |
| CubicSDR | 0.2.7 | open (GPL) | SoapySDR receiver |
| SDR# (SDRSharp) | rev 1921 | **closed**, Windows-only | HackRF One only in nightly |
| inspectrum | 0.4.0 | open (GPL) | Offline capture viewer, symbol extraction |
| SatDump | 1.2.2 | open (GPL) | Satellite downlink decoder |
| QSpectrumAnalyzer | 2.2.0 | open (GPL) | GUI over hackrf_sweep |
| rtl_433 | 25.12 | open (GPL) | ISM-band device decoder (HackRF via SoapySDR) |
| dump1090 / readsb | rolling | open (GPL) | ADS-B 1090 decoders |
| AIS-catcher | 0.70 | open (MIT) | AIS decoder (in use on the SDRplay) |
| multimon-ng | 1.6.1 | open (GPL) | POCSAG/FLEX, AFSK1200 (APRS), EAS, DTMF, selcall audio decoder |
| dumpvdl2 / acarsdec | 2.7.0 / 3.7 | open | Aircraft datalink (VDL2 / ACARS) |
| sdrtrunk | 0.6.1 | open (GPL) | Trunked/analog voice scanner-recorder |
| Artemis | 4.2.0 | open (GPL) | Signal identification (sigidwiki database) |
| hackrf_sweep GUI (pavsa) | 2024.11.10 | open | Windows spectrum analyzer |
| PortaPack Mayhem | 2.4.0 | open (GPL) | On-device firmware (RX apps; TX apps excluded) |
| SigMF | 1.2.6 | spec | Recording metadata standard |

## hackrf-tools features (verified from v2026.01.3 source)

- `hackrf_sweep`: wideband FFT sweep, `-f min:max` MHz, `-w` FFT bin width 2445–5000000 Hz, LNA `-l`
  (0–40 dB/8), VGA `-g` (0–62 dB/2), amp `-a`, antenna power `-p`, one-shot `-1`, `-N` sweeps, binary
  `-B`, inverse FFT `-I`, FFTW wisdom `-W`/`-P`. **This is the band-coverage engine.**
- `hackrf_transfer`: RX to file (`-r`, cs8 I/Q), TX from file (`-t` — not used, receive-only), `-w`
  WAV header + auto-name.
- `hackrf_info`, `hackrf_biast`, `hackrf_clock`, `hackrf_operacake`, `hackrf_debug`,
  `hackrf_cpldjtag`, `hackrf_spiflash`: device info, bias-tee, clock, antenna switch, registers, flashing.

## SDR++ features (verified from the installed .app bundle on the Air)

Plugins present: sources — hackrf, rtl_sdr, rtl_tcp, sdrplay, airspy, airspyhf, bladerf, limesdr,
plutosdr, rfnm, fobos, hermes, rfspace, spyserver, **sdrpp_server** (remote), file. Processing —
`radio` (AM/NFM/WFM/USB/LSB/CW/DSB/RAW), `meteor_demodulator`, **`scanner`** (start/stop freq,
interval, level, linger-time), **`frequency_manager`** (bookmarks/bands), **`recorder`**,
`network_sink`/`network_source`, `rigctl_server`/`rigctl_client`, `discord_integration`. HackRF source
exposes LNA, VGA, amp, bias-tee, sample rate, serial select (verified in `hackrf_source.dylib`).

## SDRconnect features (vendor docs + REA static analysis)

Verified by REA on a copy of `/Applications/SDRconnect.app/Contents/MacOS/SDRconnect` (SHA-256
`4dc4ca11…befcb3e`, arm64 Mach-O): it is a **.NET NativeAOT** app built with Avalonia UI + ReactiveUI
+ SkiaSharp, with a `swig_bindings.dylib` wrapping the SDRplay API (`libcoreradio`). Internal modules
(from the embedded assembly names): `Recording`, `IqPlayback`, `Diversity`, `ScheduledEvents`,
`StoredFrequencies`, `Profiles`, `RdsView`, `AudioSpectrum`/`AuxSpectrum`/`MpxSpectrum`. The networking
layer uses `evpp` + `CppServer` TCP (`NetworkServer…`, default port 50000 for the remote IQ/audio
server) and exposes a `CoreRadioNetworkServer::SetWebSocketPort` (the port-5454 WebSocket API). Opus
codec and nlohmann-json are statically linked. Build string: Jenkins "SDRconnect Mac ARM64".

Feature list (vendor, cross-checked against the binary): multiple VRXs; remote server (full-IQ and
audio modes, LAN/WAN); RDS decoder; profiles; **timed recordings with recurrence** (new scheduler
engine); calibrated power meter + S-meter; **SNR measurement**; wide/narrow noise blankers; noise
reduction; band framing; **HDR mode (RSPdx)**; RSPduo diversity; headless server; IQ recording (64-bit
single file) + **IQ playback as a device**; MP3 audio recording; notch filters; configurable audio AGC;
PPM correction; IARU band buttons; tabulated frequency store; audio pre-roll; MPX view of WFM;
peak-hold with decay; **WebSocket API 1.0.3 on port 5454** (JSON `event_type`/`property`/`value`;
set/get properties, stream IQ to third-party decoders). HackRF is **not** a source for SDRconnect — it
is SDRplay-only — so its value to Wichita is the IQ server + WebSocket automation model, not direct
HackRF control.

## SDRangel features (verified from v7.27.2 plugin tree)

The widest decoder set of any tool here. Channel demods: **ADS-B, AIS, DSC, NAVTEX, DAB, FT8, M17,
Meshtastic, MeshCore, Inmarsat, VOR, ILS, RTTY, Packet, DSD (digital voice), Pager (POCSAG/FLEX),
Radiosonde, End-of-train**, plus AM/NFM/WFM/SSB/FreeDV/ChirpChat(LoRa). Features: **Map**, Satellite
Tracker, Sky Map, Star Tracker, APRS, Morse decoder, SID monitor, VOR localizer, heat map, frequency
scanner, **SigMF file sink/source**, remote TCP sink (networked receiver). HackRF is a first-class
source (`hackrfinput`).

## Other tools, in brief (verified)

- **URH**: easy demod with automatic modulation detection, customizable decodings (e.g. CC1101
  whitening), manual + automatic protocol field assignment. (Fuzzing/simulation/TX excluded.)
- **inspectrum**: offline spectrogram with zoom/pan, cursors to measure period and symbol rate, export
  of time slices / filtered / demodulated data. The right tool for reading a raw capture.
- **Artemis**: signal identification against the sigidwiki database — name an unknown emission from its
  waterfall shape and parameters.
- **multimon-ng**: POCSAG512/1200/2400, FLEX, AFSK1200 (APRS packets), EAS, DTMF, ZVEI/CCIR selcall, Morse, from demodulated audio. (No DSC or AIS.)
- **dumpvdl2 / acarsdec**: aircraft datalink messages (position, free text, ops) off VDL2 / ACARS.
- **sdrtrunk**: scan and record analog + trunked voice systems, call logging.
- **SatDump**: NOAA/Meteor/etc. downlink imagery and data.
- **PortaPack Mayhem 2.4.0** (on-device reference): RX apps — ADS-B RX, AIS RX, APRS RX, POCSAG
  (pager) RX, **EPIRB RX (406 MHz distress beacons)**, ACARS RX, AFSK/FLEX/RTTY/SSTV/WEFAX/NOAA-APT RX, Sonde, Weather station, TPMS RX, ERT (utility meters), Recon/Search/Looking-Glass
  (wideband sweep), Audio RX, Capture, Replay (of own captures), Freqman, Level/Analyzer. (All TX and
  jammer apps excluded.)

## What Wichita already has (verified from the repo)

- **AIS** (AIS-catcher on the SDRplay, live), **ADS-B** (adsb.lol feed + local readsb path), marine VHF
  **ch16** voice (rtl_airband → Icecast → dashboard), airband, FM, PMR446 allowlist.
- **Voice ASR** (Whisper / Qwen3) and the core: **acoustic stress score 0–100**, implicit distress
  detector, keyword/threat detection — multilingual (mt/en/it/ar).
- **Aircraft of Interest** and **Boats of Interest** (saved targets, proximity/loiter/squawk rules),
  **watch zones** (geofence), **incident/harbour replay**, satellite passes (TLE/SGP4),
  **receiver health**, **auto_tune** wideband scan, read-only **MCP server**, a **spectrum websocket**
  (SDRplay waterfall), alert dispatch (Telegram/Discord), **capture provenance** (SigMF-shaped sidecars
  + hashing + read-only import API).
- websdr is still a stub (package manifest only).

## Feature matrix — Wichita coverage

Legend: ✓ has it · ◑ partial · ✗ missing.

| Capability | Who has it | Wichita |
| --- | --- | --- |
| Wideband sweep / spectrum survey | hackrf_sweep, SDRangel, SDR++, QSpectrumAnalyzer, Mayhem Looking-Glass | ◑ (auto_tune + SDRplay spectrum_ws; no HackRF sweep panel) |
| Live waterfall UI an operator drives | SDR++, SDRconnect, GQRX, SDRangel, CubicSDR | ◑ (spectrum_ws read-only; no tuning/zoom) |
| Voice demods (AM/NFM/WFM/SSB/CW) | all receivers | ✓ (NFM/AM/FM in the capture path) |
| Activity scanner (stop on signal) | SDR++ scanner, SDRconnect, sdrtrunk | ◑ (voice_hunting_scanner exists, not live/integrated) |
| Frequency manager / bookmarks / bands | SDR++, SDRconnect, SDRangel, Mayhem Freqman | ✗ (scan lists in code, no managed store) |
| **DSC (marine distress + MMSI)** | SDRangel (demoddsc) | ✗ |
| NAVTEX | SDRangel | ✗ |
| **EPIRB / PLB 406 MHz beacon decode** | Mayhem (epirb_rx) | ✗ |
| ADS-B decode | dump1090/readsb, SDRangel, Mayhem | ✓ |
| AIS decode | AIS-catcher, SDRangel | ✓ |
| ACARS / VDL2 (aircraft datalink) | acarsdec, dumpvdl2, SDRangel | ✗ |
| Pager decode (POCSAG / FLEX) | multimon-ng, SDRangel, Mayhem | ✗ |
| APRS | SDRangel, Mayhem, multimon-ng (AFSK1200), direwolf | ✗ |
| Digital voice (DMR/M17 etc., monitor) | SDRangel, DSD-FME, sdrtrunk | ✗ |
| LoRa / Meshtastic decode | SDRangel (ChirpChat/Meshtastic) | ✗ (868/433 captured raw only) |
| RDS | SDRconnect, SDR++, SDRangel | ✗ |
| Signal identification (sigidwiki) | Artemis | ✗ |
| Offline capture analysis (symbol/cursor) | inspectrum, URH | ◑ (numpy analysis; no symbol tooling) |
| Protocol reverse-engineering | URH | ✗ |
| True SigMF recording | SDRangel (sigmffilesink/input), SigMF spec | ◑ (SigMF-shaped sidecars; spec conformance not checked) |
| IQ playback as a device / replay | SDRconnect, SDR++, SDRangel | ◑ (incident replay of decoded data, not IQ) |
| Remote IQ/audio server (share a receiver) | SDRconnect (50000/5454), SDR++ server, spyserver | ✗ (relevant for the Pi 5 second site) |
| Networked decoder feed (WebSocket/TCP IQ) | SDRconnect WebSocket API, SDRangel remote sink | ◑ (MCP + REST out; no IQ-in API) |
| SNR / calibrated power / S-meter | SDRconnect | ✗ |
| Noise blanker / noise reduction | SDRconnect | ✗ |
| HF / shortwave below 30 MHz | all, with the right antenna | ✗ (Mobile-Whip planned) |
| Coverage map (range per bearing) | (none directly; derivable) | ✗ |
| Recurring recording scheduler | SDRconnect | ◑ (launchd baseline job; no UI scheduler) |

## Ranked gap list (mission-first)

Ranked by how much each serves Wichita's two missions — **detect bad actors** and **help people in
distress** — not by how common the feature is.

1. **DSC decoder on Ch70 (156.525 MHz), plus 406 MHz EPIRB/PLB beacons.** DSC is the marine **digital distress** channel: a MAYDAY
   relay or distress alert carries the vessel's **MMSI**, position and nature of distress as data,
   before any voice. Decoding it (an SDRangel-style DSC demod — SDRangel is the only surveyed tool with
   one — on a dedicated RTL/HackRF channel) ties straight into Boats of Interest and the distress mission, and is arguably the single
   highest-value addition. The same block should take 406 MHz EPIRB/PLB bursts (Mayhem's `epirb_rx` is
   the reference decoder), the beacon a sinking vessel or a person in the water sets off. Build: port or wrap SDRangel's `demoddsc` (GPL) as a headless decoder: 156.525 → 1200 Bd FSK → DSC decoder → map MMSI to the AIS track → alert.
2. **Signal identification (Artemis / sigidwiki).** When the waterfall shows an emission nobody can
   name, a lookup against the sigidwiki catalogue tells the operator what it is. This is the "detect
   bad actors" counterpart to voice: it labels the non-voice signals in a sweep. Build: ship the
   sigidwiki database + a matcher that takes center freq, bandwidth and shape from a capture and returns
   candidate IDs in the evidence view.
3. **Live HackRF wideband spectrum + activity scanner.** hackrf_sweep already runs; what is missing is
   a dashboard panel that shows the sweep as a waterfall and a scanner that stops on activity and hands
   the segment to the voice pipeline. This turns the fixed channel list into real discovery and makes
   the roof/sea tests visible in Wichita rather than in raw files. Build: wrap `hackrf_sweep -B` into a
   websocket feed (like spectrum_ws), add a scanner that thresholds and triggers a capture.
4. **Aircraft/marine datalink + pager decode (ACARS/VDL2, POCSAG/FLEX, APRS).** These carry text and
   coordination that voice does not: aircraft ops messages, pager traffic, APRS positions. They widen
   "detect bad actors" to the data side and give context around the voice. Build: audio-tap the existing
   airband/VHF demods into multimon-ng (POCSAG/FLEX/APRS) / acarsdec / dumpvdl2, store decoded messages as evidence.
5. **True SigMF recording + IQ replay, and a remote IQ server.** Validate the capture provenance against the
   SigMF spec (today it is described as "SigMF-shaped"), add IQ playback so a stored capture can be re-run through any
   decoder, and stand up a small remote IQ/audio server (the SDRconnect model) so the planned Pi 5
   second receiver site can stream into Wichita over Tailscale. Build: adopt the `sigmf` Python
   package for read/write; add an IQ-playback source; expose an authenticated IQ-over-websocket feed.

## Excluded on purpose (receive-only)

Wichita never transmits and never intercepts protected traffic. The following features exist in some of
the tools above and are **deliberately left out**:

- All **transmit** paths: `hackrf_transfer -t`, SDRangel TX plugins, URH fuzzing/simulation, every
  Mayhem TX/Transmitter/Transceiver app, jammer, replay-attack and spoofing apps (GPS sim, keyfob,
  TPMS TX, OOK brute, etc.).
- **Replay as re-transmission** (Mayhem Replay used to key a transmitter) — Wichita's "replay" is
  evidence playback only.
- **Cellular, TETRA and DECT** interception — refused in code (ground-voice allowlist) and not added.
- Bias-tee/antenna-switch control is receive-side only; nothing keys a PA.

## REA: what it could and could not do (stated plainly)

- **Could**: open the SDRconnect Mach-O on the box and confirm its identity (arm64, SHA-256
  `4dc4ca11…`); the artifact-graph, .NET managed-static and plist providers were available. Combined
  with `strings`/`nm` on Mattie's own copied binaries, this established that SDRconnect is a .NET
  NativeAOT Avalonia app, its internal module/assembly names, the SWIG→SDRplay-API boundary, the
  evpp/CppServer TCP server on port 50000, and the `SetWebSocketPort` (5454) entry point.
- **Could not**: run the deep decompilers. Ghidra, Hopper, IDA and Kuna are **not configured** on the
  box (no `GHIDRA_INSTALL_DIR`, no Java, no Hopper launcher), so `binary_overview`, `search_strings`,
  `list_procedures` and pseudo-code all returned `provider_unavailable`. The macOS-native providers
  (`inspect_macho`, `inspect_plist`, code-signature) require macOS and are unavailable on the Linux box.
  `inspect_binary_layout` needs a pwntools Python that is not provisioned. Per the rules, no provider
  was installed to route around this.
- **Net**: the structural/static facts above are **verified**; full function-level decompilation of
  SDRconnect was **not performed**. It was not needed — SDRconnect's feature set is documented by the
  vendor, and HackRF is not even one of its sources, so its only relevance to Wichita (the IQ server +
  WebSocket automation model) is fully covered by the public WebSocket API doc.

## Verified vs assumed

- **Verified**: all version/release dates (GitHub API, 2026-10-24); hackrf-tools options (v2026.01.3
  source); SDR++ plugin set (installed bundle); SDRconnect identity and internals (REA + strings on
  Mattie's copy); SDRangel plugin set (v7.27.2 tree); Mayhem app list (v2.4.0 tree); Wichita's current
  features (repo source).
- **Assumed / from vendor docs**: SDRconnect's exact feature wording and the WebSocket property list
  (SDRplay docs, not re-derived from the binary); SDR# HackRF-in-nightly status (HackRF docs). Build
  effort estimates in the gap list are rough.
