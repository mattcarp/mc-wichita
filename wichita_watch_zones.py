"""Geofence watch zones — alert when a vessel enters a drawn area."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from wichita_live_events import append_event

Zone = Dict[str, Any]


def zones_path() -> Path:
    raw = os.environ.get("WICHITA_WATCH_ZONES_FILE", "~/wichita/watch_zones.json").strip()
    p = Path(raw).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load() -> List[Zone]:
    path = zones_path()
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _save(zones: List[Zone]) -> None:
    zones_path().write_text(json.dumps(zones, ensure_ascii=False, indent=2), encoding="utf-8")


def list_zones() -> List[Zone]:
    return _load()


def upsert_zone(zone: Zone) -> Zone:
    zones = _load()
    zid = zone.get("id")
    if not zid:
        raise ValueError("zone id required")
    replaced = False
    for i, z in enumerate(zones):
        if z.get("id") == zid:
            zones[i] = zone
            replaced = True
            break
    if not replaced:
        zones.append(zone)
    _save(zones)
    return zone


def delete_zone(zone_id: str) -> bool:
    zones = _load()
    new = [z for z in zones if z.get("id") != zone_id]
    if len(new) == len(zones):
        return False
    _save(new)
    return True


def point_in_polygon(lat: float, lon: float, ring: List[List[float]]) -> bool:
    """Ray casting; ring is [[lon, lat], ...]."""
    inside = False
    n = len(ring)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        intersect = ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-15) + xi
        )
        if intersect:
            inside = not inside
        j = i
    return inside


class WatchZoneEngine:
    def __init__(self) -> None:
        self._inside: Dict[Tuple[str, int], bool] = {}
        self._lock = threading.Lock()

    def ingest_ships(self, ships: List[Dict[str, Any]]) -> None:
        zones = _load()
        if not zones:
            return
        with self._lock:
            for zone in zones:
                zid = zone.get("id") or ""
                ring = zone.get("polygon") or []
                name = zone.get("name") or zid
                for ship in ships:
                    if ship.get("is_base_station"):
                        continue
                    mmsi = int(ship.get("mmsi") or 0)
                    lat, lon = ship.get("lat"), ship.get("lon")
                    if lat is None or lon is None:
                        continue
                    key = (zid, mmsi)
                    inside = point_in_polygon(float(lat), float(lon), ring)
                    was = self._inside.get(key, False)
                    self._inside[key] = inside
                    if inside and not was:
                        display = ship.get("display_name") or f"MMSI {mmsi:09d}"
                        append_event(
                            "watch_zone_enter",
                            f"{display} entered watch zone “{name}”.",
                            mmsi=mmsi,
                            zone_id=zid,
                            zone_name=name,
                            lat=lat,
                            lon=lon,
                        )


_engine: Optional[WatchZoneEngine] = None


def get_watch_engine() -> WatchZoneEngine:
    global _engine
    if _engine is None:
        _engine = WatchZoneEngine()
    return _engine
