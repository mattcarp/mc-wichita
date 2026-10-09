# Map data attribution

## `malta_coastline.geojson`

Land outline from **OpenStreetMap** administrative boundary (relation `365307`, national), extracted from the [Geofabrik Malta](https://download.geofabrik.de/europe/malta.html) shapefile package. Simplified with Ramer–Douglas–Peucker (~10 m tolerance). **ODbL** — © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright).

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
