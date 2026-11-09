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
| RTL-SDR on its SMA whip | AIS decode. Low power, the workhorse | Left bag pocket, whip attached before leaving |
| SDRplay RSPdx-R2 | Marine voice on CH16 / CH09. Best ears | Padded pouch, middle of bag |
| UV-K5, charged | Airband AM and 2 m in the hand, no cables, no setup | Belt clip, outside the bag |
| Wired earbuds | CH16 through the noise, privately | Top pocket |
| Power bank + USB-C cable | RTL and SDRplay from the bank, laptop battery spared | Front pocket |
| Flipper Zero | 433.92 sniff: gate fobs, TPMS, weather stations | Trouser pocket |
| Wio Tracker L1 Pro, charged | Meshtastic RX 869.525, nodes and positions. Listen only | Trouser pocket, other side |
| Laptop + charger | Runs AIS and records; charger for the walk back | Bag, charged |
| Notepad + pen | Faster than typing, and survives | Top pocket |
| Sit mat / jacket | The steps are stone and the hour is late | Bag |

Left behind on purpose: **the HackRF.** Swapping antennas mid-hour costs more than it gives;
airband comes off the UV-K5 by hand instead.
Left on the Mini: nothing. The SDRplay comes off the rooftop, so rooftop AIS pauses.

## On site, 60 minutes
**0–5** Cross at the ferry crossing. Up the steps two or three from the bottom, antenna clear
of the wall, earbuds in, ringer off. Sit mat down.
**5–10** `./sea-watch.sh ais` in one Terminal. Open `http://127.0.0.1:8110`. Then SDR++
on the SDRplay: 156.800 FM, squelch just over the noise, recorder on.
**10–30** Work the harbour. Every distinct vessel that appears on AIS: note the time, name,
type. Every voice on 16: note time, who, what. Do not stop to edit anything.
**30–40** Swap the SDRplay to CH09 156.450, then CH12 156.600, still recording. UV-K5 to
airband, slow scan, listen for approach and tower.
**40–50** Pocket toys. Flipper on 433.92, Read RAW, walk ten metres along the shore road and
back. Wio Tracker listening; note any node, position, message.
**50–60** Pack, note the totals, walk back up before the light goes.

## Rules for the hour
- Two SDRs, two jobs, never two apps on one receiver.
- The AIS map is the spine; voice is the prize. Don't chase a burst and lose the map.
- Note timestamps as `HH:MM:SS` in the notes file, nothing else. Analysis happens at home.
- If a real distress call lands: note the time, keep the recorder running, let it finish
  before touching anything.

## Afterwards
`./keep.sh` from this folder: copies notes, NMEA and logs into this session, hashes the audio
but leaves it in `~/wichita-captures`, and prints the clips to review. Then the pipeline runs
over the selected clips and this README gets a results section.
