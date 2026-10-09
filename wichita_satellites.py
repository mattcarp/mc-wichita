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

from wichita_provenance import SOURCE_COMPUTED, provenance_fields

try:
    from sgp4.api import Satrec, jday
except ImportError:  # pragma: no cover
    Satrec = None  # type: ignore
    jday = None  # type: ignore

logger = logging.getLogger(__name__)

MALTA_TZ = ZoneInfo("Europe/Malta")
OBSERVER_LAT = 35.898666
OBSERVER_LON = 14.5145
CACHE_HOURS = 12
def _cache_path() -> Path:
    raw = os.environ.get("WICHITA_TLE_CACHE", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return Path(__file__).resolve().parent / "dashboard" / "data" / "celestrak_tle_cache.json"

# Curated NORAD catalog numbers (CelesTrak gp.php?CATNR=).
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


def _elevation_deg(sat: Satrec, when: datetime, lat: float, lon: float) -> float:
    jd, fr = jday(
        when.year,
        when.month,
        when.day,
        when.hour,
        when.minute,
        when.second + when.microsecond / 1e6,
    )
    e, r, v = sat.sgp4(jd, fr)
    if e != 0:
        return -90.0
    # ECI position km; simple topocentric conversion.
    x, y, z = r
    theta = math.radians(lon)
    phi = math.radians(lat)
    # Greenwich sidereal approx
    t = (jd + fr - 2451545.0) / 36525.0
    gmst = math.radians((280.46061837 + 360.98564736629 * (jd + fr - 2451545.0)) % 360)
    xg = x * math.cos(gmst) + y * math.sin(gmst)
    yg = -x * math.sin(gmst) + y * math.cos(gmst)
    zg = z
    xe = xg * math.sin(theta) - yg * math.cos(theta)
    ye = xg * math.cos(theta) + yg * math.sin(theta)
    ze = zg
    xn = xe
    yn = ye * math.cos(phi) - ze * math.sin(phi)
    zn = ye * math.sin(phi) + ze * math.cos(phi)
    az = math.atan2(yn, xn)
    elev = math.atan2(zn, math.hypot(xn, yn))
    return math.degrees(elev)


def _subpoint(sat: Satrec, when: datetime) -> Tuple[float, float]:
    jd, fr = jday(
        when.year,
        when.month,
        when.day,
        when.hour,
        when.minute,
        when.second + when.microsecond / 1e6,
    )
    e, r, _v = sat.sgp4(jd, fr)
    if e != 0:
        return 0.0, 0.0
    x, y, z = r
    lon = math.degrees(math.atan2(y, x)) % 360.0
    if lon > 180:
        lon -= 360
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
    step = timedelta(seconds=30)
    t = start
    end = start + timedelta(hours=hours)
    in_pass = False
    pass_start: Optional[datetime] = None
    max_el = -90.0
    max_t: Optional[datetime] = None
    while t < end:
        el = _elevation_deg(sat, t, OBSERVER_LAT, OBSERVER_LON)
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
    t = start
    for _ in range((minutes * 60) // step_sec + 1):
        lat, lon = _subpoint(sat, t)
        pts.append([round(lon, 4), round(lat, 4)])
        t += timedelta(seconds=step_sec)
    return pts


def satellite_overview(force_tle: bool = False) -> Dict[str, Any]:
    prov = provenance_fields(SOURCE_COMPUTED, None)
    if Satrec is None:
        return {
            **prov,
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
    now = datetime.now(timezone.utc)
    out_sats: List[Dict[str, Any]] = []
    for _name, norad in SATELLITES:
        entry = (cache.get("satellites") or {}).get(str(norad))
        if not entry:
            continue
        lines = entry["tle"]
        sat = Satrec.twoline2rv(lines[1], lines[2])
        passes = next_passes(sat, entry["name"], norad, now)
        track = ground_track(sat, now - timedelta(minutes=45), minutes=90)
        out_sats.append(
            {
                "name": entry["name"],
                "norad": norad,
                "next_passes": passes,
                "ground_track": track,
                **provenance_fields(SOURCE_COMPUTED, None),
            }
        )
    return {
        **prov,
        "observer": {"lat": OBSERVER_LAT, "lon": OBSERVER_LON, "label": "Valletta balcony (approx.)"},
        "tle_fetched_at_utc": cache.get("fetched_at_utc"),
        "tle_source": cache.get("source") or "CelesTrak",
        "satellites": out_sats,
    }
