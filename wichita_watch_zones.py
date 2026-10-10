"""User-drawn harbour watch zones (point-in-polygon, persisted JSON)."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def zones_path() -> Path:
    raw = os.environ.get("WICHITA_WATCH_ZONES_FILE", "~/wichita/watch-zones.json").strip()
    p = Path(raw).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load() -> List[Dict[str, Any]]:
    path = zones_path()
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def _save(zones: List[Dict[str, Any]]) -> None:
    zones_path().write_text(json.dumps(zones, indent=2), encoding="utf-8")


def list_zones() -> List[Dict[str, Any]]:
    return _load()


def upsert_zone(name: str, polygon: List[List[float]], zone_id: Optional[str] = None) -> Dict[str, Any]:
    if len(polygon) < 3:
        raise ValueError("polygon needs at least 3 points")
    zones = _load()
    zid = zone_id or str(uuid.uuid4())
    rec = {"id": zid, "name": name.strip() or "Watch zone", "polygon": polygon}
    replaced = False
    for i, z in enumerate(zones):
        if z.get("id") == zid:
            zones[i] = rec
            replaced = True
            break
    if not replaced:
        zones.append(rec)
    _save(zones)
    return rec


def delete_zone(zone_id: str) -> bool:
    zones = _load()
    new = [z for z in zones if z.get("id") != zone_id]
    if len(new) == len(zones):
        return False
    _save(new)
    return True


def point_in_polygon(lat: float, lon: float, polygon: List[List[float]]) -> bool:
    """Ray casting; polygon as [[lat, lon], ...]."""
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        lat_i, lon_i = polygon[i][0], polygon[i][1]
        lat_j, lon_j = polygon[j][0], polygon[j][1]
        if ((lon_i > lon) != (lon_j > lon)) and (
            lat < (lat_j - lat_i) * (lon - lon_i) / (lon_j - lon_i + 1e-15) + lat_i
        ):
            inside = not inside
        j = i
    return inside


def zones_for_point(lat: float, lon: float) -> List[Dict[str, Any]]:
    hits = []
    for z in _load():
        poly = z.get("polygon") or []
        if poly and point_in_polygon(lat, lon, poly):
            hits.append(z)
    return hits


def check_vessel_zones(
    mmsi: int,
    lat: Optional[float],
    lon: Optional[float],
    inside_cache: Dict[int, List[str]],
) -> List[Tuple[str, str]]:
    """Return list of (zone_id, zone_name) for newly entered zones."""
    if lat is None or lon is None:
        return []
    current = {z["id"] for z in zones_for_point(lat, lon)}
    prev = set(inside_cache.get(mmsi, []))
    entered = current - prev
    inside_cache[mmsi] = list(current)
    names = {z["id"]: z.get("name", "Watch zone") for z in _load()}
    return [(zid, names.get(zid, "Watch zone")) for zid in entered]
