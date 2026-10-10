"""Malta wind and sea state via Open-Meteo (keyless, CC-BY attribution)."""

from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

MALTA_LAT = 35.8987
MALTA_LON = 14.5145
OPEN_METEO_ATTR = "Weather data by Open-Meteo.com (CC BY 4.0)"
CACHE_MIN_SEC = int(os.environ.get("WICHITA_WEATHER_CACHE_MIN", "30")) * 60
CACHE_MAX_SEC = int(os.environ.get("WICHITA_WEATHER_CACHE_MAX", "60")) * 60


def _cache_path() -> Path:
    raw = os.environ.get("WICHITA_WEATHER_CACHE", "~/wichita/cache/malta_weather.json").strip()
    p = Path(raw).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _fetch_open_meteo() -> Dict[str, Any]:
    params = urllib.parse.urlencode(
        {
            "latitude": MALTA_LAT,
            "longitude": MALTA_LON,
            "current": "wind_speed_10m,wind_direction_10m,wind_gusts_10m",
            "hourly": "wave_height,wave_direction,wind_speed_10m,wind_gusts_10m",
            "timezone": "Europe/Malta",
            "forecast_days": 2,
        }
    )
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "wichita/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _compass(deg: Optional[float]) -> str:
    if deg is None:
        return ""
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = int(round(float(deg) / 45)) % 8
    return dirs[idx]


def _plain_context(payload: Dict[str, Any]) -> str:
    cur = payload.get("current") or {}
    w_kmh = cur.get("wind_speed_10m")
    gust = cur.get("wind_gusts_10m")
    wdir = cur.get("wind_direction_10m")
    hourly = payload.get("hourly") or {}
    wave = None
    if hourly.get("wave_height"):
        wave = hourly["wave_height"][0]
    parts = []
    if w_kmh is not None:
        w_kn = float(w_kmh) * 0.539957
        parts.append(f"Wind about {w_kn:.0f} kn {_compass(wdir)}")
    if gust is not None and w_kmh is not None and float(gust) > float(w_kmh) + 5:
        parts.append(f"gusts to {float(gust) * 0.539957:.0f} kn")
    if wave is not None:
        parts.append(f"seas around {float(wave):.1f} m")
    if not parts:
        return "Weather unavailable right now."
    return ", ".join(parts) + "."


def _flags(payload: Dict[str, Any]) -> Dict[str, Any]:
    cur = payload.get("current") or {}
    gust = cur.get("wind_gusts_10m") or cur.get("wind_speed_10m")
    gale = False
    medicane_watch = False
    if gust is not None:
        gust_kn = float(gust) * 0.539957
        gale = gust_kn >= 34
        medicane_watch = gust_kn >= 45
    return {"gale": gale, "medican_watch": medicane_watch}


def malta_weather_bundle(force: bool = False) -> Dict[str, Any]:
    path = _cache_path()
    now = datetime.now(timezone.utc)
    if path.is_file() and not force:
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            fetched = datetime.fromisoformat(cached["fetched_utc"].replace("Z", "+00:00"))
            age = (now - fetched).total_seconds()
            if age < CACHE_MAX_SEC:
                cached["cache_age_sec"] = int(age)
                return cached
        except (OSError, json.JSONDecodeError, KeyError, ValueError):
            pass
    try:
        raw = _fetch_open_meteo()
        bundle = {
            "fetched_utc": now.isoformat(),
            "attribution": OPEN_METEO_ATTR,
            "location": {"lat": MALTA_LAT, "lon": MALTA_LON, "label": "Valletta"},
            "current": raw.get("current"),
            "hourly": {
                "time": (raw.get("hourly") or {}).get("time", [])[:6],
                "wave_height": (raw.get("hourly") or {}).get("wave_height", [])[:6],
                "wind_speed_10m": (raw.get("hourly") or {}).get("wind_speed_10m", [])[:6],
            },
            "plain_english": _plain_context(raw),
            "flags": _flags(raw),
            "source": "open-meteo",
        }
        path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
        bundle["cache_age_sec"] = 0
        return bundle
    except Exception as exc:
        logger.warning("Open-Meteo fetch failed: %s", exc)
        return {
            "fetched_utc": now.isoformat(),
            "error": str(exc),
            "attribution": OPEN_METEO_ATTR,
            "plain_english": "Could not refresh Malta weather.",
            "flags": {"gale": False, "medican_watch": False},
        }
