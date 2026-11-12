"""Track presence: LIVE / STALE / SIGNAL LOST, path gap splitting, optional dead reckoning.

Thresholds are informed by ITU-R M.1371 nominal Class A/B reporting (SO/CS) and
typical 1090 ES ADS-B position rates. All values are configurable via environment.
"""

from __future__ import annotations

import math
import os
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

from wichita_receiver_health import STATE_LIVE, STATE_STALE, STATE_UNREACHABLE, STATE_INVALID

STATUS_LIVE = "live"
STATUS_STALE = "stale"
STATUS_SIGNAL_LOST = "signal_lost"

_STATUS_LABELS = {
    STATUS_LIVE: "Live",
    STATUS_STALE: "Stale",
    STATUS_SIGNAL_LOST: "Signal lost",
}

TrackKind = Literal["ais", "adsb"]
AisClass = Literal["class_a", "class_b", "unknown"]

# Class A: 10 s (fast), 36 s (mid), 180 s (slow/anchor) SO — use tiered outer bounds.
AIS_CLASS_A_LIVE_SEC = float(os.environ.get("WICHITA_AIS_A_LIVE_SEC", "45"))
AIS_CLASS_A_STALE_SEC = float(os.environ.get("WICHITA_AIS_A_STALE_SEC", "210"))
AIS_CLASS_A_LOST_SEC = float(os.environ.get("WICHITA_AIS_A_LOST_SEC", "600"))

# Class B: 30 s (moving ≥2 kn), 180 s (slow) — margins for VHF/data link jitter.
AIS_CLASS_B_LIVE_SEC = float(os.environ.get("WICHITA_AIS_B_LIVE_SEC", "90"))
AIS_CLASS_B_STALE_SEC = float(os.environ.get("WICHITA_AIS_B_STALE_SEC", "270"))
AIS_CLASS_B_LOST_SEC = float(os.environ.get("WICHITA_AIS_B_LOST_SEC", "900"))

AIS_UNKNOWN_LIVE_SEC = float(os.environ.get("WICHITA_AIS_UNK_LIVE_SEC", "90"))
AIS_UNKNOWN_STALE_SEC = float(os.environ.get("WICHITA_AIS_UNK_STALE_SEC", "270"))
AIS_UNKNOWN_LOST_SEC = float(os.environ.get("WICHITA_AIS_UNK_LOST_SEC", "900"))

# ADS-B: often 1–2 s airborne; allow several missed reports before "lost".
ADSB_LIVE_SEC = float(os.environ.get("WICHITA_ADSB_LIVE_SEC", "15"))
ADSB_STALE_SEC = float(os.environ.get("WICHITA_ADSB_STALE_SEC", "45"))
ADSB_SIGNAL_LOST_SEC = float(os.environ.get("WICHITA_ADSB_LOST_SEC", "120"))

AIS_PATH_GAP_SEC = float(os.environ.get("WICHITA_AIS_PATH_GAP_SEC", "300"))
ADSB_PATH_GAP_SEC = float(os.environ.get("WICHITA_ADSB_PATH_GAP_SEC", "60"))

PROJECTED_MAX_SEC = float(os.environ.get("WICHITA_PROJECTED_MAX_SEC", "60"))


def thresholds_summary() -> Dict[str, Any]:
    return {
        "ais_class_a": {"live_s": AIS_CLASS_A_LIVE_SEC, "stale_s": AIS_CLASS_A_STALE_SEC, "lost_s": AIS_CLASS_A_LOST_SEC},
        "ais_class_b": {"live_s": AIS_CLASS_B_LIVE_SEC, "stale_s": AIS_CLASS_B_STALE_SEC, "lost_s": AIS_CLASS_B_LOST_SEC},
        "ais_unknown": {"live_s": AIS_UNKNOWN_LIVE_SEC, "stale_s": AIS_UNKNOWN_STALE_SEC, "lost_s": AIS_UNKNOWN_LOST_SEC},
        "adsb": {"live_s": ADSB_LIVE_SEC, "stale_s": ADSB_STALE_SEC, "lost_s": ADSB_SIGNAL_LOST_SEC},
        "path_gap_ais_s": AIS_PATH_GAP_SEC,
        "path_gap_adsb_s": ADSB_PATH_GAP_SEC,
        "projected_max_s": PROJECTED_MAX_SEC,
    }


def ais_ship_class(raw: Optional[Dict[str, Any]], ship: Optional[Dict[str, Any]] = None) -> AisClass:
    sc = None
    if raw is not None:
        sc = raw.get("shipclass")
    if sc is None and ship is not None:
        sc = ship.get("shipclass")
    try:
        sc_i = int(sc) if sc is not None else None
    except (TypeError, ValueError):
        sc_i = None
    if sc_i == 1:
        return "class_a"
    if sc_i == 0:
        return "class_b"
    return "unknown"


def _ais_thresholds(ais_class: AisClass) -> Tuple[float, float, float]:
    if ais_class == "class_a":
        return AIS_CLASS_A_LIVE_SEC, AIS_CLASS_A_STALE_SEC, AIS_CLASS_A_LOST_SEC
    if ais_class == "class_b":
        return AIS_CLASS_B_LIVE_SEC, AIS_CLASS_B_STALE_SEC, AIS_CLASS_B_LOST_SEC
    return AIS_UNKNOWN_LIVE_SEC, AIS_UNKNOWN_STALE_SEC, AIS_UNKNOWN_LOST_SEC


def classify_age(last_signal_s: Optional[float], live: float, stale: float, lost: float) -> str:
    if last_signal_s is None:
        return STATUS_SIGNAL_LOST
    try:
        age = float(last_signal_s)
    except (TypeError, ValueError):
        return STATUS_SIGNAL_LOST
    if age <= live:
        return STATUS_LIVE
    if age <= stale:
        return STATUS_STALE
    if age <= lost:
        return STATUS_SIGNAL_LOST
    return STATUS_SIGNAL_LOST


def feed_stalled(*, online: bool, receiver_health: Optional[Dict[str, Any]]) -> bool:
    if not online:
        return True
    state = (receiver_health or {}).get("state")
    return state in (STATE_STALE, STATE_UNREACHABLE, STATE_INVALID)


def apply_track_signal_fields(
    entity: Dict[str, Any],
    *,
    kind: TrackKind,
    ais_class: AisClass = "unknown",
    feed_stalled: bool = False,
) -> Dict[str, Any]:
    if kind == "ais":
        live, stale, lost = _ais_thresholds(ais_class)
    else:
        live, stale, lost = ADSB_LIVE_SEC, ADSB_STALE_SEC, ADSB_SIGNAL_LOST_SEC

    age = entity.get("last_signal_s")
    if feed_stalled:
        status = STATUS_STALE
        reason = "feed_stall"
        sudden = False
    else:
        status = classify_age(age, live, stale, lost)
        reason = "entity_silent" if status == STATUS_SIGNAL_LOST else None
        try:
            sudden = float(age or 0) > lost
        except (TypeError, ValueError):
            sudden = status == STATUS_SIGNAL_LOST

    entity["track_signal_status"] = status
    entity["track_signal_label"] = _STATUS_LABELS[status]
    entity["track_signal_reason"] = reason
    entity["track_signal_feed_stall"] = feed_stalled
    entity["sudden_silence_cue"] = sudden
    entity["last_fix_lat"] = entity.get("lat")
    entity["last_fix_lon"] = entity.get("lon")
    entity["last_fix_utc"] = entity.get("last_heard_utc")
    entity["track_signal_thresholds"] = {
        "live_s": live,
        "stale_s": stale,
        "lost_s": lost,
        "kind": kind,
        "ais_class": ais_class if kind == "ais" else None,
    }

    proj = projected_position(
        entity.get("lat"),
        entity.get("lon"),
        entity.get("speed_kn") if kind == "ais" else entity.get("speed_kts"),
        entity.get("cog_deg") if kind == "ais" else entity.get("heading_deg"),
        age,
    )
    if proj:
        entity["projected_position"] = proj
    else:
        entity.pop("projected_position", None)
    return entity


def projected_position(
    lat: Any,
    lon: Any,
    speed: Any,
    course_deg: Any,
    last_signal_s: Optional[float],
    *,
    max_sec: float = PROJECTED_MAX_SEC,
) -> Optional[Dict[str, Any]]:
    if lat is None or lon is None or last_signal_s is None:
        return None
    try:
        age = max(0.0, float(last_signal_s))
        spd = float(speed) if speed is not None else 0.0
        cog = float(course_deg) if course_deg is not None else None
        lat_f, lon_f = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if age <= 0 or spd < 0.3 or cog is None or age > max_sec:
        return None
    ex = _extrapolate(lat_f, lon_f, spd, cog, age)
    return {
        "lat": ex[0],
        "lon": ex[1],
        "projected": True,
        "projected_label": "Projected (dead reckoning, not a new fix)",
        "projected_age_s": round(age, 1),
        "projected_max_s": max_sec,
    }


def _extrapolate(lat: float, lon: float, speed_kn: float, cog_deg: float, dt_sec: float) -> Tuple[float, float]:
    km = (speed_kn * 1.852 * dt_sec) / 3600.0
    brng = math.radians(cog_deg)
    d_lat = (km / 111.32) * math.cos(brng)
    d_lon = (km / (111.32 * math.cos(math.radians(lat)))) * math.sin(brng)
    return lat + d_lat, lon + d_lon


def path_gap_sec(kind: TrackKind) -> float:
    return AIS_PATH_GAP_SEC if kind == "ais" else ADSB_PATH_GAP_SEC


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def implied_speed_kn(
    lat1: float,
    lon1: float,
    t1: float,
    lat2: float,
    lon2: float,
    t2: float,
) -> Optional[float]:
    dt = abs(float(t2) - float(t1))
    if dt <= 0:
        return None
    dist_nm = _haversine_m(lat1, lon1, lat2, lon2) / 1852.0
    return dist_nm / (dt / 3600.0)


def split_coords_at_time_gaps(
    coords: Sequence[Sequence[float]],
    times: Sequence[float],
    gap_sec: float,
) -> List[List[List[float]]]:
    """Split a lon/lat track where consecutive sample age delta exceeds gap_sec."""
    if len(coords) < 2:
        return [list(coords)] if coords else []
    if len(times) != len(coords):
        return [list(coords)]
    segments: List[List[List[float]]] = []
    current: List[List[float]] = [list(coords[0])]
    for i in range(1, len(coords)):
        dt = abs(float(times[i]) - float(times[i - 1]))
        if dt > gap_sec and len(current) >= 1:
            segments.append(current)
            current = [list(coords[i])]
        else:
            current.append(list(coords[i]))
    if current:
        segments.append(current)
    return segments


def split_coords_at_speed_jumps(
    coords: Sequence[Sequence[float]],
    times: Sequence[float],
    *,
    max_speed_kn: float,
    min_dt_sec: float,
) -> List[List[List[float]]]:
    if len(coords) < 2 or len(times) != len(coords):
        return [list(coords)] if coords else []
    segments: List[List[List[float]]] = []
    current: List[List[float]] = [list(coords[0])]
    for i in range(1, len(coords)):
        lon1, lat1 = float(coords[i - 1][0]), float(coords[i - 1][1])
        lon2, lat2 = float(coords[i][0]), float(coords[i][1])
        dt = abs(float(times[i]) - float(times[i - 1]))
        spd = implied_speed_kn(lat1, lon1, float(times[i - 1]), lat2, lon2, float(times[i]))
        jump = spd is not None and dt >= min_dt_sec and spd > max_speed_kn
        if jump and len(current) >= 1:
            segments.append(current)
            current = [list(coords[i])]
        else:
            current.append(list(coords[i]))
    if current:
        segments.append(current)
    return segments


def _feature_times(props: Dict[str, Any], n: int) -> List[float]:
    starts = props.get("timestamps_start") or props.get("timestamps") or []
    ends = props.get("timestamps_end") or []
    out: List[float] = []
    for i in range(n):
        t = None
        if i < len(starts) and starts[i] is not None:
            t = starts[i]
        elif i < len(ends) and ends[i] is not None:
            t = ends[i]
        if t is None:
            t = float(i)
        try:
            out.append(float(t))
        except (TypeError, ValueError):
            out.append(float(i))
    return out


def process_paths_geojson(
    geojson: Optional[Dict[str, Any]],
    *,
    gap_sec: float,
    split_speed_jump: bool = False,
    max_speed_kn: float = 75.0,
    min_dt_sec: float = 30.0,
) -> Dict[str, Any]:
    if not geojson or geojson.get("type") != "FeatureCollection":
        return {"type": "FeatureCollection", "features": []}
    features_in = geojson.get("features") or []
    out_features: List[Dict[str, Any]] = []
    for feat in features_in:
        if feat.get("type") != "Feature":
            continue
        geom = feat.get("geometry") or {}
        coords = geom.get("coordinates") or []
        if len(coords) < 2:
            if len(coords) == 1:
                out_features.append(feat)
            continue
        props = dict(feat.get("properties") or {})
        mmsi = props.get("mmsi") or feat.get("id")
        times = _feature_times(props, len(coords))
        segments = split_coords_at_time_gaps(coords, times, gap_sec)
        if split_speed_jump:
            refined: List[List[List[float]]] = []
            for seg in segments:
                if len(seg) < 2:
                    refined.append(seg)
                    continue
                idx0 = coords.index(seg[0]) if seg[0] in coords else 0
                seg_times = times[idx0 : idx0 + len(seg)]
                if len(seg_times) != len(seg):
                    seg_times = [float(j) for j in range(len(seg))]
                refined.extend(
                    split_coords_at_speed_jumps(seg, seg_times, max_speed_kn=max_speed_kn, min_dt_sec=min_dt_sec)
                )
            segments = refined
        track_key = props.get("track_key") or (f"{mmsi}" if mmsi is not None else None)
        for seg_i, seg in enumerate(segments):
            if len(seg) < 2:
                continue
            seg_props = {**props, "track_segment": seg_i, "track_gap_split": len(segments) > 1}
            if track_key:
                seg_props["track_key"] = track_key if seg_i == 0 else f"{track_key}#{seg_i}"
            out_features.append(
                {
                    "type": "Feature",
                    "id": f"{mmsi}-{seg_i}" if mmsi is not None else None,
                    "geometry": {"type": "LineString", "coordinates": seg},
                    "properties": seg_props,
                }
            )
    return {"type": "FeatureCollection", "features": out_features}


def split_adsb_track_points(points: List[Dict[str, Any]], gap_sec: float) -> List[List[Dict[str, Any]]]:
    if len(points) < 2:
        return [points] if points else []
    segments: List[List[Dict[str, Any]]] = []
    current = [points[0]]
    prev_ts = _point_epoch(points[0])
    for pt in points[1:]:
        ts = _point_epoch(pt)
        if prev_ts is not None and ts is not None and abs(ts - prev_ts) > gap_sec:
            segments.append(current)
            current = [pt]
        else:
            current.append(pt)
        prev_ts = ts
    if current:
        segments.append(current)
    return segments


def _point_epoch(pt: Dict[str, Any]) -> Optional[float]:
    raw = pt.get("ts_utc")
    if raw is None:
        return None
    try:
        from datetime import datetime, timezone

        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None
