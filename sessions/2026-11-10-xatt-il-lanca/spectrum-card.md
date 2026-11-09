# Spectrum card — what is out there from the Sally Port steps

R&D posture: this is a survey of what a receiver can pull out of the air, not a product spec.
Reception is free in Malta; nothing here transmits. No encrypted service is broken into.

## Three verbs, and only the third counts
**Hear** — demodulate to audio. **Decode** — turn modulation into data. **Information** — a name,
a position, a value, a timestamp. Bursts you cannot decode are only noise with a shape; do not
mistake them for findings.

## A. Decodable now, with tools already on the machine
| Freq | What it is | Tool | Information yield |
|---|---|---|---|
| 161.975 / 162.025 | AIS 1 and 2. Every ferry, pilot boat, tug, yacht, barge, aid to navigation | `sea-watch.sh ais` | MMSI, name, type, position, course, speed |
| 156.525 (CH70) | DSC. Digital distress and routine alerting, no voice | `sea-watch.sh dsc` → `dsc_decoder` | MMSI, nature of distress, position, time |
| 156.800 (CH16) | Distress, safety, calling, FM voice | `sea-watch.sh voice` / SDR++ | Human voice, the hour's real evidence |
| 156.450, 156.600, 156.650, 156.700 | Marina, port operations, bridge-to-bridge | as above | Working traffic, pilot and ferry coordination |
| 1090 | ADS-B and Mode S | `sea-watch.sh adsb` | Callsign, altitude, position, squawk |
| 433.92 | ISM: car tyre sensors, gate and fob remotes, weather stations, alarms | `sea-watch.sh ism` (rtl_433) | Device model, ID, temperature, pressure, battery |
| 118–137 | Airband voice, AM. Tower, ground, approach, 121.5 guard | UV-K5 / PortaPack / SDR++ | Human voice, phraseology, aircraft types |
| 225–400 | Military UHF airband, AM. Luqa is joint civil–military | SDRplay, AM | Occasional military movement, sparse |

## B. Digitised, and NOT decodable with today's tools — name them, don't chase them
| Freq | What it is | Would need |
|---|---|---|
| 380–400 | TETRA, Maltese emergency services and much government traffic | `tetra-rx` or SDRangel |
| 150–174, 400–470 | DMR, dPMR, NXDN: hotel, security, port contractors | `dsd-fme` |
| 174–240 | DAB+ ensemble | `welle.io` or `rtl-dab` |
| 470–694 | DVB-T2 television | a DVB demod chain |
| 131.725 / 136.975 | ACARS and VDL Mode 2, aircraft data link | `acarsdec`, `dumpvdl2` |
| 153, 466 blocks | POCSAG paging, if still active locally | `multimon-ng` |
| 700–2600 | GSM, LTE, 5G | power and shape only, without srsRAN |
| 406.025 / 406.028 | COSPAS-SARSAT EPIRB bursts | `wichita_sarsat406.py`, and luck |

## C. Physically out of reach or not worth it on a whip
- 3 GHz and up: marine radar, 5 GHz Wi-Fi. Nothing in the bag reaches them usefully.
- 1575.42 GPS L1: a peak on the waterfall, no fix.
- 1030 MHz SSR uplink: needs timing we do not have.
- 137.1 / 137.9125 weather satellites: decodable with SatDump, but they want a circular
  antenna and a pass prediction, not a whip at 4 pm.
- 490 / 518 kHz NAVTEX and most HF: an earpiece whip without a ground plane is a poor antenna.

## D. What this changes in the hour
Nothing in the packing list; it changes where the radios point.
- 5–10 AIS on and CH16 recording. Both run continuously.
- 10–30 Vessel log. CH09 and CH12 in the last ten minutes of that block.
- 30–40 PortaPack sweep 150–170 then 118–137, reading bursts against section B so they are
  recognised rather than chased. One DSC pass on CH70 only if 16 goes quiet.
- 40–50 Flipper on 433.92 alongside `ism` on the RTL for ten minutes: RTL decodes, Flipper
  catches the raw of anything rtl_433 cannot name.
- 50–60 Pack. Do not start anything new.

## E. Cheap upgrades for a future run, in value order
1. `dsd-fme` — opens DMR, the busiest business band in a working harbour.
2. SatDump — weather satellite passes, high novelty, needs a better antenna.
3. `multimon-ng` — pagers.
4. `tetra-rx` — emergency services, hardest of the four to get working.
