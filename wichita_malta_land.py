"""Point-in-land tests for bundled Malta coastline GeoJSON."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

DATA_DIR = Path(__file__).resolve().parent / "dashboard" / "data"
COASTLINE_PATH = DATA_DIR / "malta_coastline.geojson"


def _pip(lon: float, lat: float, ring: Sequence[Sequence[float]]) -> bool:
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-15) + xi
        ):
            inside = not inside
        j = i
    return inside


@lru_cache(maxsize=1)
def load_land_geojson() -> Dict[str, Any]:
    return json.loads(COASTLINE_PATH.read_text(encoding="utf-8"))


def point_on_land(lon: float, lat: float, geojson: Dict[str, Any] | None = None) -> bool:
    """True if (lon, lat) is inside a land polygon (outer ring, excluding holes)."""
    geojson = geojson or load_land_geojson()
    for feat in geojson.get("features") or []:
        geom = feat.get("geometry") or {}
        gtype = geom.get("type")
        coords = geom.get("coordinates") or []
        polys: List[List[List[List[float]]]] = []
        if gtype == "Polygon":
            polys = [coords]
        elif gtype == "MultiPolygon":
            polys = coords
        for poly in polys:
            if not poly:
                continue
            outer = poly[0]
            if not _pip(lon, lat, outer):
                continue
            in_hole = any(_pip(lon, lat, hole) for hole in poly[1:])
            if not in_hole:
                return True
    return False


# Reference points for regression tests (lon, lat, label)
SEA_POINTS: Tuple[Tuple[float, float, str], ...] = (
    (14.538, 35.920, "GOUTAMARU offshore"),
    (14.513, 35.939, "ORIENS NOVUS offshore"),
    (14.523, 35.893, "Grand Harbour water"),
    (14.508, 35.901, "Marsamxett water"),
)

LAND_POINTS: Tuple[Tuple[float, float, str], ...] = (
    (14.5103, 35.8961, "Valletta City Gate"),
    (14.4030, 35.8860, "Mdina"),
    (14.2394, 36.0443, "Victoria Gozo"),
)
