# Aircraft of interest (“Flight of Fancy”)

Wichita’s **things-of-interest** model covers boats (`/api/interests/boats`) and aircraft (`/api/interests/flights`). Watch lists and conditional rules live in `WICHITA_INTERESTS_FILE` (default `~/wichita/interests.json`), seeded from `config/interests_seed.json` on first run.

Station reference for range rules: **Valletta rooftop** at `35.898666°N, 14.5145°E` (50 Archbishop St) — same coordinates as the AIS receiver in `wichita_ais_live.py`.

## Watch list

Users add aircraft by **ICAO hex**, **call sign**, or **registration**. Lookup searches the current ADS-B snapshot (local readsb and/or cached adsb.lol merge). Saved entries persist server-side.

Watched aircraft are:

- Pinned at the top of the Sky · planes list
- Highlighted on the harbour map (orange marker + ring)
- Announced on the live timeline as `aircraft_of_interest_seen` when they enter the feed (debounced like boats)

## Conditional rules (defaults)

Rules are stored under `aircraft_rules` in the interests file. If missing, these defaults apply:

| ID | Kind | Behaviour |
|----|------|-----------|
| `close-low-default` | `close_low` | Range **≤ 10 nmi** from station **and** altitude **≤ 3,000 ft**. Optional filters: `hex`, `callsign`, `registration`. `exclude_lmml_traffic: true` skips matches within **5 nmi** of LMML (35.8575°N, 14.4775°E) to reduce routine airport traffic. |
| `emergency-squawk` | `emergency_squawk` | Squawk **7500 / 7600 / 7700** or non-`none` emergency flag (same semantics as `wichita_adsb_live.EMERGENCY_SQUAWKS`). |
| `loiter-near-station` | `loiter` | Within **25 nmi**, below **8,000 ft**, speed **45–280 kt**, staying within **~1.8 km** of a track anchor for **≥ 12 minutes** (same pattern as AIS loiter detection). |

Rule hits set `interest_alert` on the aircraft row, show an **alert badge** in the UI, and emit timeline events:

- `aircraft_rule_alert` — proximity / squawk rules
- `aircraft_loiter` — loiter rule

Alerts are **receive-only** observations; copy uses “not confirmed by us” for squawks where applicable.

## JSON API (Matt’s World View / automation)

All endpoints require the same Clerk session as the dashboard unless `WICHITA_AUTH_REQUIRED=false` (dev/tests).

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/interests` | Summary: `boats`, `flights`, `aircraft_rules`, `station`. |
| `GET` | `/api/interests/flights` | Watch list + `aircraft_rules`. |
| `POST` | `/api/interests/flights/lookup` | Body `{ "query": "4caabc" }` → `{ "candidates": [...] }`. |
| `POST` | `/api/interests/flights` | Body `{ "hex"?, "callsign"?, "registration"?, "label"?, "note"? }` → saved entry. |
| `DELETE` | `/api/interests/flights/{flight_id}` | Remove watch-list entry. |
| `GET` | `/api/interests/aircraft/rules` | `{ "rules": [...] }`. |
| `PUT` | `/api/interests/aircraft/rules` | Body `{ "rules": [...] }` replaces stored rules. |
| `GET` | `/api/sky/adsb/snapshot` | Live ADS-B plus enrichment: `range_nm`, `interest_aircraft`, `interest_alert`, `aircraft_rules`. |

Boats endpoints remain at `/api/interests/boats` (unchanged).

## Implementation notes

- Python: `wichita_aircraft_interest.py` (rules + engine), integrated in `wichita_live_events` poll loop and `wichita_gods_eye_routes` snapshot.
- Dashboard: `dashboard/aircraft_of_interest.js`, shared helpers in `dashboard/things_of_interest.js`.
- Raw ADS-B text from decoders is not normalised beyond existing `normalize_aircraft()` behaviour.
