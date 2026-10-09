"""Read-only proxy helpers for AIS-catcher live feed (no control plane)."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from zoneinfo import ZoneInfo

from wichita_ais_copy import count_freshness, enrich_ship_copy, harbour_summary, freshness_bucket, movement_counts
from wichita_provenance import SOURCE_OUR_ANTENNA, provenance_fields
from wichita_captures import VALLETTA_AIS_BASE_MMSIS, mmsi_label

MALTA_TZ = ZoneInfo("Europe/Malta")
RECEIVER_LAT = 35.898666
RECEIVER_LON = 14.5145

logger = logging.getLogger(__name__)

AIS_TIMEOUT_SEC = float(os.environ.get("WICHITA_AIS_TIMEOUT_SEC", "2.5"))

_FIXTURE_MAP = {
    "/api/ships.json": "api_ships.json",
    "/api/stat.json": "api_stat.json",
    "/api/allpath.geojson": "api_allpath.geojson",
}

_SHIPTYPE_WORDS: Dict[int, str] = {
    0: "not available",
    30: "fishing",
    31: "towing",
    32: "towing (large)",
    33: "dredging",
    34: "diving",
    35: "military",
    36: "sailing",
    37: "pleasure craft",
    50: "pilot",
    51: "search and rescue",
    52: "tug",
    53: "port tender",
    54: "anti-pollution",
    55: "law enforcement",
    58: "medical transport",
    59: "non-combatant",
    60: "passenger",
    65: "passenger",
    70: "cargo",
    71: "cargo (hazard A)",
    72: "cargo (hazard B)",
    73: "cargo (hazard C)",
    74: "cargo (hazard D)",
    80: "tanker",
    90: "other",
    40: "high-speed craft",
    41: "high-speed craft",
}


def ais_catcher_base_url() -> str:
    return os.environ.get("WICHITA_AIS_URL", "http://127.0.0.1:8100").rstrip("/")


def ais_fixture_dir() -> Optional[Path]:
    raw = os.environ.get("WICHITA_AIS_FIXTURE_DIR", "").strip()
    if not raw:
        return None
    p = Path(raw).expanduser().resolve()
    return p if p.is_dir() else None


def _read_fixture(rel_path: str) -> Any:
    root = ais_fixture_dir()
    if root is None:
        raise FileNotFoundError("fixture dir not set")
    path = root / rel_path
    if not path.is_file():
        raise FileNotFoundError(rel_path)
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_ais_json(api_path: str, query: str = "") -> Tuple[Optional[Any], Optional[str]]:
    """Return (payload, error_message). error_message set when receiver offline."""
    fixture = ais_fixture_dir()
    if fixture is not None:
        rel = _FIXTURE_MAP.get(api_path.split("?")[0])
        if api_path.startswith("/api/ship.json") or api_path.startswith("/api/vessel"):
            mmsi = ""
            if "mmsi=" in api_path:
                mmsi = api_path.split("mmsi=", 1)[1].split("&", 1)[0]
            fname = f"api_ship_{mmsi}.json" if mmsi else None
            if fname and (fixture / fname).is_file():
                return _read_fixture(fname), None
            fname = f"api_vessel_{mmsi}.json"
            if mmsi and (fixture / fname).is_file():
                return _read_fixture(fname), None
            return None, "ship not in fixtures"
        if rel:
            try:
                return _read_fixture(rel), None
            except OSError as exc:
                return None, str(exc)
        return None, f"no fixture for {api_path}"

    url = f"{ais_catcher_base_url()}{api_path}"
    if query and "?" not in api_path:
        url = f"{url}?{query}" if query else url
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=AIS_TIMEOUT_SEC) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body), None
    except urllib.error.URLError as exc:
        logger.warning("AIS-catcher unreachable at %s: %s", url, exc)
        return None, "receiver offline"
    except json.JSONDecodeError as exc:
        logger.warning("AIS-catcher bad JSON from %s: %s", url, exc)
        return None, "receiver returned invalid JSON"
    except TimeoutError:
        return None, "receiver offline"


def shiptype_label(code: Any) -> str:
    try:
        c = int(code)
    except (TypeError, ValueError):
        return "unknown type"
    if c in _SHIPTYPE_WORDS:
        return _SHIPTYPE_WORDS[c]
    tens = (c // 10) * 10
    if tens in _SHIPTYPE_WORDS:
        return _SHIPTYPE_WORDS[tens]
    return f"type {c}"


def format_eta(raw: Dict[str, Any]) -> Optional[str]:
    m, d, h, mi = raw.get("eta_month"), raw.get("eta_day"), raw.get("eta_hour"), raw.get("eta_minute")
    if m is None or d is None:
        return None
    try:
        return f"{int(d):02d}/{int(m):02d} {int(h or 0):02d}:{int(mi or 0):02d} UTC"
    except (TypeError, ValueError):
        return None


def format_eta_malta(raw: Dict[str, Any], now: Optional[datetime] = None) -> Tuple[Optional[str], bool]:
    """Return (display string in Malta time, is_stale)."""
    m, d, h, mi = raw.get("eta_month"), raw.get("eta_day"), raw.get("eta_hour"), raw.get("eta_minute")
    if m is None or d is None:
        return None, False
    now = now or datetime.now(timezone.utc)
    try:
        eta_utc = datetime(
            year=now.year,
            month=int(m),
            day=int(d),
            hour=int(h or 0),
            minute=int(mi or 0),
            tzinfo=timezone.utc,
        )
        local = eta_utc.astimezone(MALTA_TZ)
        label = local.strftime("%d %b %H:%M")
        if eta_utc < now.astimezone(timezone.utc):
            return f"{local.strftime('%d %b %H:%M')} (out of date)", True
        return label, False
    except (TypeError, ValueError):
        return None, False


def stable_sort_key(ship: Dict[str, Any]) -> Tuple[int, str, int]:
    moving = 0 if (ship.get("speed_kn") or 0) >= 0.5 else 1
    name = (ship.get("display_name") or "").upper()
    return (moving, name, int(ship.get("mmsi") or 0))


def receiver_health(stat: Optional[Dict[str, Any]], online: bool) -> Dict[str, Any]:
    if not stat:
        return {"available": online, "online": online}
    run_s = stat.get("run_time")
    try:
        run_s = int(run_s) if run_s is not None else None
    except (TypeError, ValueError):
        run_s = None
    return {
        "available": True,
        "online": online,
        "hardware": stat.get("hardware"),
        "build_version": stat.get("build_version"),
        "run_time_sec": run_s,
        "msg_rate": stat.get("msg_rate"),
        "memory_bytes": stat.get("memory"),
        "vessel_count": stat.get("vessel_count"),
        "sample_rate": stat.get("sample_rate"),
        "product": stat.get("product"),
        "device_label": stat.get("device_label"),
        "tcp_clients": stat.get("tcp_clients"),
    }


def normalize_ship(raw: Dict[str, Any], now: Optional[datetime] = None) -> Dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    mmsi = int(raw.get("mmsi") or 0)
    name = (raw.get("shipname") or "").strip()
    callsign = (raw.get("callsign") or "").strip()
    country = (raw.get("country") or "").strip().upper() or None
    dest = (raw.get("destination") or "").strip()
    last_sig = raw.get("last_signal")
    try:
        last_sig_s = float(last_sig) if last_sig is not None else None
    except (TypeError, ValueError):
        last_sig_s = None
    label = mmsi_label(mmsi) if mmsi in VALLETTA_AIS_BASE_MMSIS else None
    display_name = label or (name if name else f"Unnamed, MMSI {mmsi:09d}")
    speed = raw.get("speed")
    cog = raw.get("cog")
    heading = raw.get("heading")
    eta_malta, eta_stale = format_eta_malta(raw, now)
    ship = {
        "mmsi": mmsi,
        "mmsi_display": f"{mmsi:09d}",
        "shipname": name or None,
        "display_name": display_name,
        "callsign": callsign or None,
        "country": country,
        "shiptype_code": raw.get("shiptype"),
        "shiptype_label": shiptype_label(raw.get("shiptype")),
        "destination": dest or None,
        "eta": format_eta(raw),
        "eta_malta": eta_malta,
        "eta_malta_stale": eta_stale,
        "imo": raw.get("imo"),
        "lat": raw.get("lat"),
        "lon": raw.get("lon"),
        "speed_kn": speed,
        "cog_deg": cog,
        "heading_deg": heading,
        "level_db": raw.get("level"),
        "message_count": raw.get("count"),
        "last_signal_s": last_sig_s,
        "last_heard_utc": datetime.fromtimestamp(
            now.timestamp() - last_sig_s, tz=timezone.utc
        ).isoformat()
        if last_sig_s is not None
        else None,
        "is_base_station": mmsi in VALLETTA_AIS_BASE_MMSIS,
        "nav_status": raw.get("status"),
        "freshness": freshness_bucket(last_sig_s),
    }
    ship.update(provenance_fields(SOURCE_OUR_ANTENNA, last_sig_s))
    return enrich_ship_copy(ship, raw)


def live_status_payload(stat: Optional[Dict[str, Any]], ships: List[Dict[str, Any]], online: bool, err: Optional[str]) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    ships_norm = [normalize_ship(s, now) for s in ships]
    vessels = [s for s in ships_norm if not s.get("is_base_station")]
    last_hour = sum(1 for s in vessels if (s.get("last_signal_s") or 99999) < 3600)
    min_last = min((s["last_signal_s"] for s in ships_norm if s.get("last_signal_s") is not None), default=None)
    last_msg_utc = (now.timestamp() - min_last) if min_last is not None else None
    mpm = None
    if stat:
        lm = stat.get("last_minute") or {}
        if lm.get("count") is not None:
            mpm = float(lm["count"])
        elif stat.get("msg_rate") is not None:
            try:
                mpm = float(stat["msg_rate"]) * 60.0
            except (TypeError, ValueError):
                mpm = None
    return {
        "source": "live",
        "online": online,
        "receiver_offline": not online,
        "error": err,
        "messages_per_min": mpm,
        "ships_in_last_hour": last_hour,
        "ship_count": len(vessels),
        "vessel_count": len(vessels),
        "base_station_count": len(ships_norm) - len(vessels),
        "last_message_utc": datetime.fromtimestamp(last_msg_utc, tz=timezone.utc).isoformat()
        if last_msg_utc
        else None,
    }


def live_dashboard_bundle() -> Dict[str, Any]:
    ships_raw, err_ships = fetch_ais_json("/api/ships.json")
    stat_raw, err_stat = fetch_ais_json("/api/stat.json")
    paths_raw, err_paths = fetch_ais_json("/api/allpath.geojson")
    online = ships_raw is not None
    err = err_ships or (None if stat_raw else err_stat)
    ships = (ships_raw or {}).get("ships") or []
    status = live_status_payload(stat_raw, ships, online, err)
    paths = paths_raw if isinstance(paths_raw, dict) else {"type": "FeatureCollection", "features": []}
    now = datetime.now(timezone.utc)
    normalized = [normalize_ship(s, now) for s in ships]
    vessels = [s for s in normalized if not s.get("is_base_station")]
    bases = [s for s in normalized if s.get("is_base_station")]
    vessels.sort(key=stable_sort_key)
    fresh = count_freshness(vessels)
    move = movement_counts(vessels)
    voice_busy = os.environ.get("WICHITA_VOICE_LIVE", "0").strip() not in ("1", "true", "yes")
    return {
        **status,
        "ships": vessels,
        "base_stations": bases,
        "freshness_counts": fresh,
        "movement_counts": move,
        "summary": harbour_summary(vessels, online, voice_busy),
        "receiver": {
            "lat": RECEIVER_LAT,
            "lon": RECEIVER_LON,
            "label": "Valletta balcony (approx.)",
        },
        "receiver_health": receiver_health(stat_raw, online),
        "paths": paths,
        "paths_error": err_paths,
    }


def live_ship_detail(mmsi: int) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    payload, err = fetch_ais_json(f"/api/ship.json?mmsi={mmsi}")
    if payload is None:
        return None, err or "not found"
    now = datetime.now(timezone.utc)
    return normalize_ship(payload, now), None
