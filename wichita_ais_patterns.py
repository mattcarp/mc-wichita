"""Conservative AIS pattern observations (plain English, not accusations)."""

from __future__ import annotations

import math
import os
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

# Malta harbour bounding box (same as live events; loitering ignored inside berths).
HARBOUR_LAT = (35.875, 35.925)
HARBOUR_LON = (14.48, 14.55)

# Approximate berth boxes where slow movement is normal.
_BERTH_BOXES: List[Tuple[float, float, float, float]] = [
    (35.82, 35.86, 14.52, 14.56),  # Marsaxlokk / Freeport
    (35.88, 35.91, 14.50, 14.53),  # Grand Harbour
]

LOITER_SPEED_KN = float(os.environ.get("WICHITA_AIS_LOITER_SPEED_KN", "1.5"))
LOITER_RADIUS_M = float(os.environ.get("WICHITA_AIS_LOITER_RADIUS_M", "400"))
LOITER_MINUTES = float(os.environ.get("WICHITA_AIS_LOITER_MINUTES", "45"))
UNUSUAL_SPEED_KN = float(os.environ.get("WICHITA_AIS_UNUSUAL_SPEED_KN", "28"))
UNUSUAL_HSC_SPEED_KN = float(os.environ.get("WICHITA_AIS_UNUSUAL_HSC_SPEED_KN", "42"))

OBSERVATION_PREFIX = "Observation (not verified): "


def _in_box(lat: float, lon: float, box: Tuple[float, float, float, float]) -> bool:
    lat0, lat1, lon0, lon1 = box
    return lat0 <= lat <= lat1 and lon0 <= lon <= lon1


def in_harbour(lat: Optional[float], lon: Optional[float]) -> bool:
    if lat is None or lon is None:
        return False
    return HARBOUR_LAT[0] <= lat <= HARBOUR_LAT[1] and HARBOUR_LON[0] <= lon <= HARBOUR_LON[1]


def in_berth(lat: Optional[float], lon: Optional[float]) -> bool:
    if lat is None or lon is None:
        return False
    return any(_in_box(lat, lon, b) for b in _BERTH_BOXES)


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


EventFn = Callable[..., Any]


class AisPatternObserver:
    def __init__(self, emit: EventFn) -> None:
        self._emit = emit
        self._inside: Dict[int, bool] = {}
        self._loiter_anchor: Dict[int, Tuple[float, float, float]] = {}
        self._loiter_logged: Set[int] = set()
        self._speed_logged: Set[int] = set()

    def ingest(self, ships: List[Dict[str, Any]], poll_sec: float) -> None:
        for s in ships:
            if s.get("is_base_station"):
                continue
            mmsi = int(s["mmsi"])
            lat, lon = s.get("lat"), s.get("lon")
            name = s.get("display_name") or f"MMSI {mmsi:09d}"
            spd = s.get("speed_kn")
            try:
                spd_f = float(spd) if spd is not None else 0.0
            except (TypeError, ValueError):
                spd_f = 0.0
            cat = s.get("shiptype_category") or "other"

            inside = in_harbour(lat, lon)
            was = self._inside.get(mmsi)
            if was is None:
                self._inside[mmsi] = inside
            elif was != inside:
                self._inside[mmsi] = inside
                if inside:
                    self._emit(
                        "pattern_arrival",
                        f"{OBSERVATION_PREFIX}{name} appears to have entered the harbour area.",
                        mmsi=mmsi,
                        display_name=name,
                    )
                else:
                    self._emit(
                        "pattern_departure",
                        f"{OBSERVATION_PREFIX}{name} appears to have left the harbour area.",
                        mmsi=mmsi,
                        display_name=name,
                    )

            limit = UNUSUAL_HSC_SPEED_KN if cat == "hsc" else UNUSUAL_SPEED_KN
            if spd_f >= limit and mmsi not in self._speed_logged:
                self._speed_logged.add(mmsi)
                self._emit(
                    "pattern_unusual_speed",
                    f"{OBSERVATION_PREFIX}{name} is reporting {spd_f:.1f} kn — unusually high for our snapshot.",
                    mmsi=mmsi,
                    display_name=name,
                    speed_kn=spd_f,
                )

            if lat is None or lon is None or in_berth(lat, lon):
                self._loiter_anchor.pop(mmsi, None)
                continue
            if spd_f > LOITER_SPEED_KN:
                self._loiter_anchor.pop(mmsi, None)
                continue
            anchor = self._loiter_anchor.get(mmsi)
            if anchor is None:
                self._loiter_anchor[mmsi] = (float(lat), float(lon), poll_sec)
                continue
            alat, alon, accum = anchor
            dist = _haversine_m(alat, alon, float(lat), float(lon))
            accum += poll_sec
            if dist > LOITER_RADIUS_M:
                self._loiter_anchor[mmsi] = (float(lat), float(lon), poll_sec)
                continue
            self._loiter_anchor[mmsi] = (alat, alon, accum)
            if accum >= LOITER_MINUTES * 60 and mmsi not in self._loiter_logged:
                self._loiter_logged.add(mmsi)
                self._emit(
                    "pattern_loiter",
                    f"{OBSERVATION_PREFIX}{name} has been moving slowly within a small area "
                    f"(about {int(LOITER_RADIUS_M)} m) for {int(LOITER_MINUTES)}+ minutes.",
                    mmsi=mmsi,
                    display_name=name,
                )
