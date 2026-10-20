"""Read-only proxy helpers for AIS-catcher live feed (no control plane)."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from zoneinfo import ZoneInfo

from wichita_ais_copy import (
    count_freshness,
    enrich_ship_copy,
    harbour_summary_bundle,
    freshness_bucket,
    movement_counts,
)
from wichita_ais_nav import normalize_ais_course, normalize_ais_heading, normalize_ais_speed
from wichita_feed_urls import validated_feed_url
from wichita_provenance import SOURCE_OUR_ANTENNA, provenance_fields
from wichita_receiver_health import feed_health_payload, heard_last_60s_badge, count_heard_within
from wichita_captures import VALLETTA_AIS_BASE_MMSIS, mmsi_label
from untrusted_text import (
    MAX_LEN_CALLSIGN,
    MAX_LEN_DESTINATION,
    MAX_LEN_SHIPNAME,
    sanitize_untrusted_text,
)
import wichita_mmsi

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
    raw = os.environ.get("WICHITA_AIS_URL", "http://127.0.0.1:8100")
    return validated_feed_url(raw, "WICHITA_AIS_URL", "http://127.0.0.1:8100").rstrip("/")


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
    except ValueError as exc:
        return None, str(exc)
    except TimeoutError:
        return None, "receiver offline"


def shiptype_label(code: Any) -> str:
    try:
        c = int(code)
    except (TypeError, ValueError):
        return "unknown type"
    if c in _SHIPTYPE_WORDS:
        label = _SHIPTYPE_WORDS[c]
        if label == "not available":
            return "Unknown type"
        return label
    tens = (c // 10) * 10
    if tens in _SHIPTYPE_WORDS:
        return _SHIPTYPE_WORDS[tens]
    return "Unknown type"


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
            return None, True
        if (eta_utc - now.astimezone(timezone.utc)).days > 30:
            return None, True
        return label, False
    except (TypeError, ValueError):
        return None, False


def stable_sort_key(ship: Dict[str, Any]) -> Tuple[int, str, int]:
    moving = 0 if (ship.get("speed_kn") or 0) >= 0.5 else 1
    name = (ship.get("display_name") or "").upper()
    return (moving, name, int(ship.get("mmsi") or 0))


def receiver_health(
    stat: Optional[Dict[str, Any]],
    online: bool,
    *,
    error: Optional[str] = None,
    ships: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    vessels = ships or []
    youngest = min((s.get("last_signal_s") for s in vessels if s.get("last_signal_s") is not None), default=None)
    feed = feed_health_payload(
        receiver="AIS-catcher",
        band="AIS 161.975 / 162.025 MHz",
        online=online,
        error=error,
        youngest_signal_s=youngest,
        entity_count=len(vessels),
    )
    if not stat:
        return {**feed, "available": online, "online": online}
    run_s = stat.get("run_time")
    try:
        run_s = int(run_s) if run_s is not None else None
    except (TypeError, ValueError):
        run_s = None
    return {
        **feed,
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
    name = sanitize_untrusted_text(raw.get("shipname"), MAX_LEN_SHIPNAME)
    callsign = sanitize_untrusted_text(raw.get("callsign"), MAX_LEN_CALLSIGN)
    country = (raw.get("country") or "").strip().upper() or None
    dest = sanitize_untrusted_text(raw.get("destination"), MAX_LEN_DESTINATION)
    last_sig = raw.get("last_signal")
    try:
        last_sig_s = float(last_sig) if last_sig is not None else None
    except (TypeError, ValueError):
        last_sig_s = None
    label = mmsi_label(mmsi) if mmsi in VALLETTA_AIS_BASE_MMSIS else None
    display_name = label or (name if name else f"Unnamed, MMSI {mmsi:09d}")
    speed, speed_known = normalize_ais_speed(raw.get("speed"))
    cog, cog_known = normalize_ais_course(raw.get("cog"))
    heading, heading_known = normalize_ais_heading(raw.get("heading"))
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
        "speed_known": speed_known,
        "cog_deg": cog,
        "cog_known": cog_known,
        "heading_deg": heading,
        "heading_known": heading_known,
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
    }
    tier = freshness_bucket(last_sig_s)
    ship["freshness"] = tier
    ship.update(provenance_fields(SOURCE_OUR_ANTENNA, last_sig_s))
    ship["freshness"] = tier
    ship["freshness_label"] = {"now": "Now", "recent": "Recent", "earlier": "Earlier"}.get(tier, "Earlier")
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


ROSTER_WINDOW_S = float(os.environ.get("WICHITA_ROSTER_WINDOW_S", "3600"))


def roster_file() -> Optional[Path]:
    raw = os.environ.get("WICHITA_AIS_ROSTER_FILE", "").strip()
    if not raw:
        snaps = os.environ.get("WICHITA_AIS_SNAPSHOTS_DIR", "").strip()
        if not snaps:
            return None
        raw = str(Path(snaps).expanduser().parent / "ais_roster.json")
    return Path(raw).expanduser()


def _load_roster(path: Optional[Path]) -> Dict[str, Any]:
    if path is None or not path.is_file():
        return {"ships": {}, "last_ok_epoch": None}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("ships"), dict):
            return data
    except (OSError, ValueError):
        logger.warning("AIS roster file unreadable: %s", path)
    return {"ships": {}, "last_ok_epoch": None}


def _save_roster(path: Optional[Path], roster: Dict[str, Any]) -> None:
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(roster), encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        logger.warning("AIS roster not saved: %s", exc)


def merge_roster(
    ships_raw: Optional[List[Dict[str, Any]]],
    online: bool,
    now_epoch: float,
    path: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], Optional[float]]:
    """Persist every real ship heard and return the roster (raw dicts, last_signal recomputed).

    Online: keep ships heard within ROSTER_WINDOW_S (AIS-catcher forgets ships sooner).
    Offline: keep the last known list unchanged so the page never goes blank.
    """
    path = path if path is not None else roster_file()
    roster = _load_roster(path)
    entries: Dict[str, Any] = roster.get("ships") or {}
    if online:
        for raw in ships_raw or []:
            try:
                mmsi = int(raw.get("mmsi") or 0)
                heard = now_epoch - float(raw.get("last_signal") or 0)
            except (TypeError, ValueError):
                continue
            if not mmsi:
                continue
            prev = entries.get(str(mmsi))
            if prev and float(prev.get("heard_epoch") or 0) > heard and not raw.get("lat"):
                continue
            entries[str(mmsi)] = {"raw": raw, "heard_epoch": heard}
        cutoff = now_epoch - ROSTER_WINDOW_S
        entries = {k: v for k, v in entries.items() if float(v.get("heard_epoch") or 0) >= cutoff}
        roster = {"ships": entries, "last_ok_epoch": now_epoch}
        _save_roster(path, roster)
    out = []
    for v in entries.values():
        raw = dict(v.get("raw") or {})
        raw["last_signal"] = max(0.0, now_epoch - float(v.get("heard_epoch") or now_epoch))
        out.append(raw)
    return out, roster.get("last_ok_epoch")


_POOL = None
_CACHE_LOCK = threading.Lock()
_CACHE: Dict[str, Any] = {"bundle": None, "at": 0.0}
_POLLER_STARTED = False
POLL_INTERVAL_S = float(os.environ.get("WICHITA_AIS_POLL_S", "4"))


def _fetch_three() -> Tuple[Tuple[Any, Any], Tuple[Any, Any], Tuple[Any, Any]]:
    """Fetch ships, stat and paths from AIS-catcher in parallel (worst case one timeout, not three)."""
    global _POOL
    if _POOL is None:
        _POOL = ThreadPoolExecutor(max_workers=3, thread_name_prefix="ais-fetch")
    futs = [_POOL.submit(fetch_ais_json, p) for p in ("/api/ships.json", "/api/stat.json", "/api/allpath.geojson")]
    return tuple(f.result() for f in futs)  # type: ignore[return-value]


def _poll_loop() -> None:
    while True:
        try:
            b = live_dashboard_bundle()
            with _CACHE_LOCK:
                _CACHE["bundle"], _CACHE["at"] = b, time.time()
        except Exception:  # noqa: BLE001 - keep the poller alive
            logger.exception("AIS background poll failed")
        time.sleep(POLL_INTERVAL_S)


def cached_dashboard_bundle() -> Dict[str, Any]:
    """Answer instantly from the background poller's latest bundle; compute once if none yet."""
    global _POLLER_STARTED
    if not _POLLER_STARTED:
        with _CACHE_LOCK:
            if not _POLLER_STARTED:
                _POLLER_STARTED = True
                threading.Thread(target=_poll_loop, name="ais-poller", daemon=True).start()
    with _CACHE_LOCK:
        b, at = _CACHE["bundle"], _CACHE["at"]
    if b is None:
        b = live_dashboard_bundle()
        with _CACHE_LOCK:
            _CACHE["bundle"], _CACHE["at"] = b, time.time()
        at = time.time()
    out = dict(b)
    out["cache_age_s"] = round(max(0.0, time.time() - at), 2)
    return out


def live_dashboard_bundle() -> Dict[str, Any]:
    (ships_raw, err_ships), (stat_raw, err_stat), (paths_raw, err_paths) = _fetch_three()
    online = ships_raw is not None
    err = err_ships or (None if stat_raw else err_stat)
    registry = wichita_mmsi.update_registry((ships_raw or {}).get("ships") or []) if online else wichita_mmsi.load_registry()
    ships, last_ok_epoch = merge_roster(
        (ships_raw or {}).get("ships") or [], online, datetime.now(timezone.utc).timestamp()
    )
    status = live_status_payload(stat_raw, ships, online, err)
    paths = paths_raw if isinstance(paths_raw, dict) else {"type": "FeatureCollection", "features": []}
    now = datetime.now(timezone.utc)
    normalized = [normalize_ship(s, now) for s in ships]
    vessels = [s for s in normalized if not s.get("is_base_station")]
    bases = [s for s in normalized if s.get("is_base_station")]
    vessels.sort(key=stable_sort_key)
    for v in vessels:
        v["mmsi_info"] = wichita_mmsi.lookup(v["mmsi"], registry, shiptype_label)
    voice_busy = os.environ.get("WICHITA_VOICE_LIVE", "0").strip() not in ("1", "true", "yes")
    summary_block = harbour_summary_bundle(vessels, online, voice_busy)
    rx_health = receiver_health(stat_raw, online, error=err, ships=vessels)
    return {
        **status,
        "ships": vessels,
        "base_stations": bases,
        "freshness_counts": summary_block["freshness_counts"],
        "movement_counts": summary_block["movement_counts"],
        "summary": summary_block["text"],
        "type_breakdown": summary_block["type_breakdown"],
        "nearby_now": summary_block["nearby_now"],
        "receiver": {
            "lat": RECEIVER_LAT,
            "lon": RECEIVER_LON,
            "label": "Valletta balcony (approx.)",
        },
        "receiver_health": rx_health,
        "heard_badge": heard_last_60s_badge(ais_count=count_heard_within(vessels), adsb_count=0),
        "coverage": rx_health.get("coverage"),
        "coverage_label": rx_health.get("coverage_label"),
        "paths": paths,
        "paths_error": err_paths,
        "roster_window_s": ROSTER_WINDOW_S,
        "feed_paused": not online,
        "feed_last_ok_utc": datetime.fromtimestamp(last_ok_epoch, tz=timezone.utc).isoformat()
        if last_ok_epoch
        else None,
    }


def live_ship_detail(mmsi: int) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    payload, err = fetch_ais_json(f"/api/ship.json?mmsi={mmsi}")
    if payload is None:
        return None, err or "not found"
    now = datetime.now(timezone.utc)
    return normalize_ship(payload, now), None
