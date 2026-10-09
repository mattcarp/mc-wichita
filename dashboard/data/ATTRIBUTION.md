# Map data attribution

## `malta_coastline.geojson`

Land polygons from [osmdata.openstreetmap.de](https://osmdata.openstreetmap.de/data/land-polygons.html) `land-polygons-split-4326`, clipped to a Malta bounding box. **ODbL** — © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright).

## `malta_water.geojson`

Water and dock polygons (`water`, `dock`, `basin`, etc.) from the same Geofabrik extract, used to paint harbours (Grand Harbour, Marsamxett, creeks) as sea on top of the land fill. Same licence.

Regenerate both files (requires network once):

```bash
python3 scripts/build_malta_map_data.py
```

## Verification points (should appear over sea, not land fill)

| Place | lat | lon |
|-------|-----|-----|
| Fort St Elmo | 35.9019 | 14.5194 |
| Valletta waterfront | 35.8930 | 14.5180 |
| Sliema ferries | 35.9100 | 14.5040 |

Place labels on the map are approximate orientation aids only.

## God's Eye View (MIT) — motion interpolation

Smooth position display between real receiver reports (`dashboard/map_motion.js`) adapts the “one poll behind + interpolate” pattern from [God's Eye View](https://github.com/bilawalsidhu/gods-eye-view) (MIT). Copyright (c) Bilawal Sidhu and contributors; see `LICENSE` in that repository.

## CelesTrak TLE data

Satellite pass times use NORAD GP elements from [CelesTrak](https://celestrak.org/). Positions are **computed, not observed**.

## Python `sgp4` package

Satellite propagation uses the [`sgp4`](https://pypi.org/project/sgp4/) library (MIT). Listed in `requirements-gods-eye.txt`.
