#!/usr/bin/env python3
"""Regenerate dashboard/data/malta_*.geojson from Geofabrik Malta extract (ODbL)."""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

import shapefile

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "dashboard" / "data"
ZIP_URL = "https://download.geofabrik.de/europe/malta-latest-free.shp.zip"
ZIP_PATH = Path("/tmp/malta-latest-free.shp.zip")
EXTRACT = Path("/tmp/malta_shp_build")


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


def main() -> int:
    if not ZIP_PATH.is_file():
        urlretrieve(ZIP_URL, ZIP_PATH)
    EXTRACT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH) as zf:
        zf.extractall(EXTRACT)

    admin = shapefile.Reader(str(EXTRACT / "gis_osm_adminareas_a_free_1.shp"))
    land_coords = []
    for rec, shp in zip(admin.records(), admin.shapes()):
        if str(rec[0]) != "365307":
            continue
        ring = [[round(p[0], 6), round(p[1], 6)] for p in shp.points]
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        land_coords.append([rdp(ring, 0.0001)])

    water = shapefile.Reader(str(EXTRACT / "gis_osm_water_a_free_1.shp"))
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

    meta = {
        "source": "OpenStreetMap via Geofabrik Malta extract (relation 365307 land + water areas)",
        "license": "ODbL https://www.openstreetmap.org/copyright",
    }
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "malta_coastline.geojson").write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "metadata": meta,
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"name": "Malta, Gozo, Comino"},
                        "geometry": {"type": "MultiPolygon", "coordinates": land_coords},
                    }
                ],
            },
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    (DATA / "malta_water.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "metadata": meta, "features": water_feats}, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"land rings {len(land_coords)} water features {len(water_feats)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
