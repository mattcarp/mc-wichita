"""CelesTrak TLE fetch (12 h cache) and pass prediction over Valletta (SGP4)."""

from __future__ import annotations

import json
import logging
import math
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from zoneinfo import ZoneInfo

from wichita_provenance import SOURCE_COMPUTED, SOURCE_LABELS, provenance_fields

try:
    from sgp4.api import Satrec, jday
except ImportError:  # pragma: no cover
    Satrec = None  # type: ignore
    jday = None  # type: ignore

logger = logging.getLogger(__name__)

MALTA_TZ = ZoneInfo("Europe/Malta")
OBSERVER_LAT = 35.8989
OBSERVER_LON = 14.5146
OBSERVER_ALT_KM = 0.05  # ~50 m above WGS84 ellipsoid
CACHE_HOURS = 12

WGS84_A_KM = 6378.137
WGS84_F = 1.0 / 298.257223563


def _cache_path() -> Path:
    raw = os.environ.get("WICHITA_TLE_CACHE", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return Path(__file__).resolve().parent / "dashboard" / "data" / "celestrak_tle_cache.json"


SATELLITES: Tuple[Tuple[str, int], ...] = (
    ("ISS (ZARYA)", 25544),
    ("NOAA 15", 25338),
    ("NOAA 18", 28654),
    ("NOAA 19", 33591),
    ("METEOR-M2", 40069),
    ("METEOR-M2 2", 44387),
    ("METEOR-M2 3", 57189),
)


def _cache_max_age_sec() -> float:
    return float(os.environ.get("WICHITA_TLE_CACHE_HOURS", str(CACHE_HOURS))) * 3600.0


def _fetch_tle_lines(norad: int) -> List[str]:
    url = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={norad}&FORMAT=TLE"
    req = urllib.request.Request(url, headers={"User-Agent": "Wichita-dashboard/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        text = resp.read().decode("utf-8", errors="replace")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < 3:
        raise ValueError(f"TLE too short for {norad}")
    return lines[-3:]


def load_tle_cache() -> Dict[str, Any]:
    path = _cache_path()
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {"fetched_at_utc": None, "satellites": {}}


def save_tle_cache(data: Dict[str, Any]) -> None:
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def refresh_tle_cache(force: bool = False) -> Dict[str, Any]:
    if Satrec is None:
        raise RuntimeError("sgp4 package required for satellite propagation")
    skip = os.environ.get("WICHITA_TLE_SKIP_FETCH", "").strip().lower() in ("1", "true", "yes")
    cache = load_tle_cache()
    if skip and cache.get("satellites"):
        return cache
    fetched = cache.get("fetched_at_utc")
    age_ok = False
    if fetched and not force:
        try:
            t0 = datetime.fromisoformat(fetched.replace("Z", "+00:00"))
            age_ok = (datetime.now(timezone.utc) - t0).total_seconds() < _cache_max_age_sec()
        except ValueError:
            age_ok = False
    if age_ok and cache.get("satellites"):
        return cache

    sats: Dict[str, Any] = {}
    for name, norad in SATELLITES:
        try:
            lines = _fetch_tle_lines(norad)
            sats[str(norad)] = {"name": name, "norad": norad, "tle": lines}
        except (urllib.error.URLError, ValueError, TimeoutError) as exc:
            logger.warning("TLE fetch failed for %s: %s", norad, exc)
    cache = {
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "CelesTrak NORAD GP elements",
        "satellites": sats,
    }
    if sats:
        save_tle_cache(cache)
    return cache


def _gmst_rad(jd_ut: float) -> float:
    """Greenwich mean sidereal time (radians) at Julian date UT (Vallado)."""
    t = (jd_ut - 2451545.0) / 36525.0
    gmst_deg = (
        280.46061837
        + 360.98564736629 * (jd_ut - 2451545.0)
        + 0.000387933 * t * t
        - (t**3) / 38710000.0
    )
    return math.radians(gmst_deg % 360.0)


def _geodetic_to_ecef_km(lat_deg: float, lon_deg: float, alt_km: float) -> Tuple[float, float, float]:
    e2 = WGS84_F * (2.0 - WGS84_F)
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    sin_lat = math.sin(lat)
    cos_lat = math.cos(lat)
    n = WGS84_A_KM / math.sqrt(1.0 - e2 * sin_lat * sin_lat)
    x = (n + alt_km) * cos_lat * math.cos(lon)
    y = (n + alt_km) * cos_lat * math.sin(lon)
    z = (n * (1.0 - e2) + alt_km) * sin_lat
    return x, y, z


def _teme_to_ecef_km(r_teme: Tuple[float, float, float], gmst: float) -> Tuple[float, float, float]:
    x, y, z = r_teme
    c = math.cos(gmst)
    s = math.sin(gmst)
    return (c * x + s * y, -s * x + c * y, z)


def _ecef_to_enu(
    dx: float, dy: float, dz: float, lat_deg: float, lon_deg: float
) -> Tuple[float, float, float]:
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    sin_lat, cos_lat = math.sin(lat), math.cos(lat)
    sin_lon, cos_lon = math.sin(lon), math.cos(lon)
    east = -sin_lon * dx + cos_lon * dy
    north = -sin_lat * cos_lon * dx - sin_lat * sin_lon * dy + cos_lat * dz
    up = cos_lat * cos_lon * dx + cos_lat * sin_lon * dy + sin_lat * dz
    return east, north, up


def _elevation_deg(sat: Satrec, when: datetime, lat: float, lon: float, alt_km: float) -> float:
    when = when.astimezone(timezone.utc)
    jd, fr = jday(
        when.year,
        when.month,
        when.day,
        when.hour,
        when.minute,
        when.second + when.microsecond / 1e6,
    )
    err, r_teme, _v = sat.sgp4(jd, fr)
    if err != 0:
        return -90.0
    gmst = _gmst_rad(jd + fr)
    sx, sy, sz = _teme_to_ecef_km((r_teme[0], r_teme[1], r_teme[2]), gmst)
    ox, oy, oz = _geodetic_to_ecef_km(lat, lon, alt_km)
    east, north, up = _ecef_to_enu(sx - ox, sy - oy, sz - oz, lat, lon)
    return math.degrees(math.atan2(up, math.hypot(east, north)))


def _subpoint(sat: Satrec, when: datetime) -> Tuple[float, float]:
    when = when.astimezone(timezone.utc)
    jd, fr = jday(
        when.year,
        when.month,
        when.day,
        when.hour,
        when.minute,
        when.second + when.microsecond / 1e6,
    )
    err, r_teme, _v = sat.sgp4(jd, fr)
    if err != 0:
        return 0.0, 0.0
    gmst = _gmst_rad(jd + fr)
    x, y, z = _teme_to_ecef_km((r_teme[0], r_teme[1], r_teme[2]), gmst)
    lon = math.degrees(math.atan2(y, x))
    hyp = math.hypot(x, y)
    lat = math.degrees(math.atan2(z, hyp))
    return lat, lon


def next_passes(
    sat: Satrec,
    name: str,
    norad: int,
    start: datetime,
    hours: int = 36,
    min_elev: float = 10.0,
) -> List[Dict[str, Any]]:
    passes: List[Dict[str, Any]] = []
    step = timedelta(seconds=20)
    t = start.astimezone(timezone.utc)
    end = t + timedelta(hours=hours)
    in_pass = False
    pass_start: Optional[datetime] = None
    max_el = -90.0
    max_t: Optional[datetime] = None
    while t < end:
        el = _elevation_deg(sat, t, OBSERVER_LAT, OBSERVER_LON, OBSERVER_ALT_KM)
        if el >= min_elev:
            if not in_pass:
                in_pass = True
                pass_start = t
                max_el = el
                max_t = t
            elif el > max_el:
                max_el = el
                max_t = t
        elif in_pass:
            if pass_start and max_t:
                local = max_t.astimezone(MALTA_TZ)
                passes.append(
                    {
                        "aos_utc": pass_start.isoformat(),
                        "max_utc": max_t.isoformat(),
                        "max_elevation_deg": round(max_el, 1),
                        "max_time_malta": local.strftime("%d %b %H:%M"),
                    }
                )
            in_pass = False
            pass_start = None
            max_el = -90.0
            max_t = None
        t += step
    return passes[:3]


def ground_track(sat: Satrec, start: datetime, minutes: int = 90, step_sec: int = 120) -> List[List[float]]:
    pts: List[List[float]] = []
    t = start.astimezone(timezone.utc)
    for _ in range((minutes * 60) // step_sec + 1):
        lat, lon = _subpoint(sat, t)
        pts.append([round(lon, 4), round(lat, 4)])
        t += timedelta(seconds=step_sec)
    return pts


def _tle_age_label(fetched_at_utc: Optional[str], now: datetime) -> Tuple[Optional[float], str]:
    if not fetched_at_utc:
        return None, "TLE age unknown"
    try:
        t0 = datetime.fromisoformat(fetched_at_utc.replace("Z", "+00:00"))
    except ValueError:
        return None, "TLE age unknown"
    age_sec = max(0.0, (now.astimezone(timezone.utc) - t0).total_seconds())
    if age_sec < 120:
        return age_sec, "TLE just updated"
    if age_sec < 3600:
        return age_sec, f"TLE {int(age_sec // 60)} min old"
    if age_sec < _cache_max_age_sec():
        return age_sec, f"TLE {int(age_sec // 3600)} h old"
    return age_sec, f"TLE over {int(_cache_max_age_sec() // 3600)} h old"


def _satellite_provenance(fetched_at_utc: Optional[str], now: datetime) -> Dict[str, Any]:
    age_sec, tle_label = _tle_age_label(fetched_at_utc, now)
    base = provenance_fields(SOURCE_COMPUTED, age_sec)
    base["freshness_label"] = tle_label
    base["tle_age_s"] = age_sec
    return base


def satellite_overview(force_tle: bool = False) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    if Satrec is None:
        return {
            **_satellite_provenance(None, now),
            "error": "Satellite propagation unavailable (install sgp4)",
            "observer": {"lat": OBSERVER_LAT, "lon": OBSERVER_LON, "label": "Valletta balcony (approx.)"},
            "tle_fetched_at_utc": None,
            "satellites": [],
        }
    try:
        cache = refresh_tle_cache(force=force_tle)
    except Exception as exc:  # noqa: BLE001
        logger.warning("TLE refresh failed: %s", exc)
        cache = load_tle_cache()
    fetched_at = cache.get("fetched_at_utc")
    prov = _satellite_provenance(fetched_at, now)
    out_sats: List[Dict[str, Any]] = []
    for _name, norad in SATELLITES:
        entry = (cache.get("satellites") or {}).get(str(norad))
        if not entry:
            continue
        lines = entry["tle"]
        sat = Satrec.twoline2rv(lines[1], lines[2])
        passes = next_passes(sat, entry["name"], norad, now)
        track = ground_track(sat, now - timedelta(minutes=45), minutes=90)
        in_progress = False
        if passes:
            try:
                aos = datetime.fromisoformat(passes[0]["aos_utc"].replace("Z", "+00:00"))
                los_guess = datetime.fromisoformat(passes[0]["max_utc"].replace("Z", "+00:00")) + timedelta(
                    minutes=12
                )
                in_progress = aos <= now <= los_guess
            except (KeyError, ValueError):
                in_progress = False
        out_sats.append(
            {
                "name": entry["name"],
                "norad": norad,
                "next_passes": passes,
                "pass_in_progress": in_progress,
                "ground_track": track,
                **_satellite_provenance(fetched_at, now),
            }
        )

    def _pass_sort_key(sat: Dict[str, Any]) -> str:
        passes = sat.get("next_passes") or []
        if not passes:
            return "9999"
        return passes[0].get("max_utc") or passes[0].get("aos_utc") or "9999"

    out_sats.sort(key=_pass_sort_key)
    return {
        **prov,
        "source_label": SOURCE_LABELS[SOURCE_COMPUTED],
        "observer": {"lat": OBSERVER_LAT, "lon": OBSERVER_LON, "label": "Valletta balcony (approx.)"},
        "tle_fetched_at_utc": fetched_at,
        "tle_source": cache.get("source") or "CelesTrak",
        "satellites": out_sats,
    }
