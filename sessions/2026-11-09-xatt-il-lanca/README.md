# Session 2026-11-09 — Xatt il-Lanca, Marsamxett

One hour, late afternoon, on foot. Receive-only.
Spot: the Sally Port steps above the Sliema ferry landing, Xatt il-Lanca. Route down
Triq San Nikola past Sally Port Pizzeria (102), across the ferry crossing.

Why here: the ferry landing is the densest AIS on foot in Malta, and it puts real maritime
voices on CH16 within earshot. Two objectives, same as always: real received human voice for
the pipeline, real AIS traffic to test the decoder against.

## Kit
| Item | Why | Where |
|---|---|---|
| **Mag mount + telescopic whip** | Real antenna over water instead of a duck. Extend the whip to ~45 cm for 156–162 MHz, shorter for airband | Base in bag, whip upright |
| RTL-SDR on the mag mount | AIS decode. Low power, the workhorse | Left bag pocket |
| SDRplay RSPdx-R2, **ANT A** | Marine voice on CH16 / CH09. Best ears | Padded pouch, middle |
| PortaPack + HackRF | Hands-on spectrum sweep of the harbour, airband, ADS-B on its own screen, no laptop | Padded pouch, with SD card cleared |
| UV-K5, charged | Instant airband and 2 m in the hand | Belt clip |
| Wired earbuds | CH16 through the noise, privately | Top pocket |
| Power bank + **two** USB data cables (C and Micro) | RTL and SDRplay from the bank, laptop battery spared | Front pocket |
| **SMA–BNC pigtail + SMA adapters only** | Mag mount is BNC; the radios are SMA | Front pocket, not the whole bag |
| Flipper Zero | 433.92 sniff: gate fobs, TPMS, weather stations | Trouser pocket |
| Wio Tracker, orange case, charged — **one only** | Meshtastic RX 869.525, nodes and positions. Listen only | Trouser pocket, other side |
| Laptop + charger | Runs AIS and records; charged for the walk back | Bag |
| Notepad + pen | Faster than typing, and survives | Top pocket |
| Sit mat / jacket | The steps are stone and the hour is late | Bag |

Three radios, three jobs. The PortaPack means no antenna swapping and no laptop cable for the
HackRF — it stands alone. Take the whip, leave the whole adapter bag behind.

## On site, 60 minutes
**0–5** Cross at the ferry crossing. Up the steps two or three from the bottom. Mag mount base flat
on a railing or the stone, whip upright at ~45 cm, clear of the wall. Earbuds in, ringer off. Sit mat down.
**5–10** `./sea-watch.sh ais` in one Terminal. Open `http://127.0.0.1:8110`. Then SDR++
on the SDRplay, ANT A: 156.800 FM, squelch just over the noise, recorder on.
**10–30** Work the harbour. Every distinct vessel that appears on AIS: note the time, name,
type. Every voice on 16: note time, who, what. Do not stop to edit anything.
**30–40** PortaPack: spectrum sweep across 150–170, look at the AIS bursts and the ferry's traffic,
then 118–137 AM for approach and tower. Note what is there, not what it says.
**40–50** CH09 156.450, then CH12 156.600 on the SDRplay, still recording. UV-K5 to airband,
slow scan. Flipper on 433.92, Read RAW, ten metres of the shore road and back. Wio Tracker listening.
**50–60** Pack, note the totals, walk back up before the light goes.

## Rules for the hour
- Three radios, three jobs; never two apps on one receiver.
- Whip upright, base on metal or flat stone, never pressed sideways against a wall.
- The PortaPack runs hot and eats its battery: short sweeps, screen off between them.
- The AIS map is the spine; voice is the prize. Don't chase a burst and lose the map.
- Note timestamps as `HH:MM:SS` in the notes file, nothing else. Analysis happens at home.
- If a real distress call lands: note the time, keep the recorder running, let it finish
  before touching anything.

## Afterwards
`./keep.sh` from this folder: copies notes, NMEA and logs into this session, hashes the audio
but leaves it in `~/wichita-captures`, and prints the clips to review. Then the pipeline runs
over the selected clips and this README gets a results section.
