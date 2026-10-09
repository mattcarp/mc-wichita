#!/usr/bin/env python3
"""Regenerate dashboard/data/malta_*.geojson (ODbL).

Land: osmdata.openstreetmap.de land-polygons-split-4326 clipped to Malta bbox
(not OSM admin relation 365307, which includes territorial sea).

Water: Geofabrik Malta extract (harbour inlets, docks).
"""

from __future__ import annotations

import json
import os
import sys
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

import shapefile

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "dashboard" / "data"

MALTA_BBOX = (14.18, 35.78, 14.58, 36.10)  # min_lon, min_lat, max_lon, max_lat

GEOFABRIK_ZIP_URL = "https://download.geofabrik.de/europe/malta-latest-free.shp.zip"
GEOFABRIK_ZIP_PATH = Path("/tmp/malta-latest-free.shp.zip")
GEOFABRIK_EXTRACT = Path("/tmp/malta_shp_build")

LAND_ZIP_URL = "https://osmdata.openstreetmap.de/download/land-polygons-split-4326.zip"
LAND_ZIP_PATH = Path(os.environ.get("MALTA_LAND_ZIP", "/tmp/land-split-full.zip"))
LAND_EXTRACT = Path(os.environ.get("MALTA_LAND_EXTRACT", "/tmp/land_osm"))
LAND_SHP = LAND_EXTRACT / "land-polygons-split-4326" / "land_polygons.shp"


def rdp(points: list, eps: float) -> list:
    def pdist(point, start, end):
        x0, y0 = point
        x1, y1 = start
        x2, y2 = end
        if (x1, y1) == (x2, y2):
            return ((x0 - x1) ** 2 + (y0 - y1) ** 2) ** 0.5
        num = abs((y2 - y1) * x0 - (x2 - x1) * y0 + x2 * y1 - y2 * x1)
        den = ((y2 - y1) ** 2 + (x2 - x1) ** 2) ** 0.5
        return num / den if den else 0.0

    if len(points) < 3:
        return points
    start, end = points[0], points[-1]
    idx, dmax = 0, 0.0
    for i in range(1, len(points) - 1):
        d = pdist(points[i], start, end)
        if d > dmax:
            idx, dmax = i, d
    if dmax > eps:
        return rdp(points[: idx + 1], eps)[:-1] + rdp(points[idx:], eps)
    return [start, end]


def _bbox_intersects(shape_bbox: tuple, bbox: tuple) -> bool:
    min_lon, min_lat, max_lon, max_lat = bbox
    x0, y0, x1, y1 = shape_bbox
    return not (x1 < min_lon or x0 > max_lon or y1 < min_lat or y0 > max_lat)


def ensure_land_shapefile() -> Path:
    if LAND_SHP.is_file():
        return LAND_SHP
    if not LAND_ZIP_PATH.is_file():
        print(f"Downloading land polygons (~886MB) to {LAND_ZIP_PATH}…", file=sys.stderr)
        urlretrieve(LAND_ZIP_URL, LAND_ZIP_PATH)
    LAND_EXTRACT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(LAND_ZIP_PATH) as zf:
        zf.extractall(LAND_EXTRACT)
    if not LAND_SHP.is_file():
        raise SystemExit(f"Expected shapefile at {LAND_SHP}")
    return LAND_SHP


def load_land_multipolygon(bbox: tuple = MALTA_BBOX) -> list:
    shp_path = ensure_land_shapefile()
    sf = shapefile.Reader(str(shp_path))
    rings: list = []
    for shp in sf.shapes():
        if not _bbox_intersects(shp.bbox, bbox):
            continue
        parts = list(shp.parts) + [len(shp.points)]
        for i in range(len(shp.parts)):
            pts = shp.points[parts[i] : parts[i + 1]]
            if len(pts) < 4:
                continue
            ring = [[round(p[0], 6), round(p[1], 6)] for p in pts]
            if ring[0] != ring[-1]:
                ring.append(ring[0])
            ring = rdp(ring, 0.00005)
            if len(ring) >= 4:
                rings.append([ring])
    return rings


def load_water_features(extract: Path) -> list:
    water = shapefile.Reader(str(extract / "gis_osm_water_a_free_1.shp"))
    water_feats = []
    for rec, shp in zip(water.records(), water.shapes()):
        if shp.shapeType != 5:
            continue
        fclass = rec[2]
        if fclass not in ("water", "dock", "riverbank", "basin", "canal", "pond"):
            continue
        parts = list(shp.parts) + [len(shp.points)]
        for i in range(len(shp.parts)):
            pts = shp.points[parts[i] : parts[i + 1]]
            if len(pts) < 4:
                continue
            ring = [[round(p[0], 6), round(p[1], 6)] for p in pts]
            if ring[0] != ring[-1]:
                ring.append(ring[0])
            lons = [p[0] for p in ring]
            lats = [p[1] for p in ring]
            if max(lons) - min(lons) < 0.00015 and max(lats) - min(lats) < 0.00015:
                continue
            ring = rdp(ring, 0.00008)
            if len(ring) >= 4:
                water_feats.append(
                    {
                        "type": "Feature",
                        "properties": {"fclass": fclass, "name": rec[3] or ""},
                        "geometry": {"type": "Polygon", "coordinates": [ring]},
                    }
                )
    return water_feats


def main() -> int:
    if not GEOFABRIK_ZIP_PATH.is_file():
        urlretrieve(GEOFABRIK_ZIP_URL, GEOFABRIK_ZIP_PATH)
    GEOFABRIK_EXTRACT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(GEOFABRIK_ZIP_PATH) as zf:
        zf.extractall(GEOFABRIK_EXTRACT)

    land_coords = load_land_multipolygon()
    water_feats = load_water_features(GEOFABRIK_EXTRACT)

    meta_land = {
        "source": "osmdata.openstreetmap.de land-polygons-split-4326 (WGS84), clipped to Malta bbox",
        "license": "ODbL https://www.openstreetmap.org/copyright",
        "bbox": list(MALTA_BBOX),
    }
    meta_water = {
        "source": "OpenStreetMap via Geofabrik Malta extract (water areas)",
        "license": "ODbL https://www.openstreetmap.org/copyright",
    }
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "malta_coastline.geojson").write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "metadata": meta_land,
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"name": "Malta islands (coastline land)"},
                        "geometry": {"type": "MultiPolygon", "coordinates": land_coords},
                    }
                ],
            },
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    (DATA / "malta_water.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "metadata": meta_water, "features": water_feats}, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"land polygons {len(land_coords)} water features {len(water_feats)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
