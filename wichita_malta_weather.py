"""Malta wind and sea state from Open-Meteo (keyless, CC-BY)."""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Tuple

MALTA_LAT = 35.8987
MALTA_LON = 14.5145
OPEN_METEO = "https://api.open-meteo.com/v1/forecast"
ATTRIBUTION = "Weather data by Open-Meteo.com (CC BY 4.0)"


def _cache_path() -> str:
    return os.environ.get("WICHITA_WEATHER_CACHE", "/tmp/wichita-open-meteo.json")


def _cache_ttl_sec() -> float:
    raw = os.environ.get("WICHITA_WEATHER_CACHE_MIN", "45")
    try:
        return max(30.0, min(3600.0, float(raw) * 60.0))
    except ValueError:
        return 45 * 60.0


def _read_cache() -> Optional[Dict[str, Any]]:
    path = _cache_path()
    try:
        with open(path, encoding="utf-8") as fh:
            blob = json.load(fh)
    except OSError:
        return None
    if time.time() - float(blob.get("fetched_at", 0)) > _cache_ttl_sec():
        return None
    return blob.get("payload")


def _write_cache(payload: Dict[str, Any]) -> None:
    path = _cache_path()
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"fetched_at": time.time(), "payload": payload}, fh)
    except OSError:
        pass


def _plain_wind(kmh: Optional[float]) -> str:
    if kmh is None:
        return "Wind unknown"
    if kmh < 15:
        return f"Light breeze around {kmh:.0f} km/h"
    if kmh < 30:
        return f"Moderate wind near {kmh:.0f} km/h"
    if kmh < 50:
        return f"Fresh wind near {kmh:.0f} km/h — choppy harbour"
    return f"Strong wind near {kmh:.0f} km/h — small craft should exercise caution"


def _gale_flags(wind_kmh: Optional[float], gust_kmh: Optional[float]) -> Dict[str, bool]:
    w = wind_kmh or 0
    g = gust_kmh or 0
    gale = w >= 62 or g >= 75
    medicane_hint = w >= 75 and g >= 90
    return {"gale_warning": gale, "medicane_watch": medicane_hint}


def fetch_open_meteo() -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    params = urllib.parse.urlencode(
        {
            "latitude": MALTA_LAT,
            "longitude": MALTA_LON,
            "current": "wind_speed_10m,wind_gusts_10m,wind_direction_10m",
            "hourly": "wave_height,wind_speed_10m",
            "timezone": "Europe/Malta",
            "forecast_days": 2,
        }
    )
    url = f"{OPEN_METEO}?{params}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode("utf-8")), None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return None, str(exc)


def malta_weather_card() -> Dict[str, Any]:
    cached = _read_cache()
    if cached:
        return cached
    raw, err = fetch_open_meteo()
    if raw is None:
        return {"ok": False, "error": err, "attribution": ATTRIBUTION}
    cur = raw.get("current") or {}
    hourly = raw.get("hourly") or {}
    wind = cur.get("wind_speed_10m")
    gust = cur.get("wind_gusts_10m")
    wave = None
    if hourly.get("wave_height"):
        wave = hourly["wave_height"][0]
    flags = _gale_flags(wind, gust)
    sea = "Sea state unknown"
    if wave is not None:
        if wave < 0.5:
            sea = f"Calm seas — wave height about {wave:.1f} m"
        elif wave < 1.5:
            sea = f"Slight seas — waves about {wave:.1f} m"
        else:
            sea = f"Rougher seas — waves about {wave:.1f} m"
    payload = {
        "ok": True,
        "attribution": ATTRIBUTION,
        "wind_kmh": wind,
        "wind_gust_kmh": gust,
        "wind_direction_deg": cur.get("wind_direction_10m"),
        "wave_height_m": wave,
        "wind_plain": _plain_wind(wind),
        "sea_plain": sea,
        **flags,
    }
    _write_cache(payload)
    return payload
