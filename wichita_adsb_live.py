"""Aircraft for the Sky tab: one readsb-shaped model, two inputs, one layer.

Inputs (receive-only, no SDR control):
  * adsb.lol community feed, polled by ONE server-side background thread every
    15 s (browsers never call adsb.lol), cached, with exponential backoff.
  * local readsb aircraft.json from our own RTL-SDR (WICHITA_ADSB_URL). Config
    stub until the Mini's 1090 MHz receiver is live; off unless the env var is set.

Both go through normalize_aircraft() and are merged by ICAO hex in
merge_aircraft(): one aircraft, one marker, one row.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from wichita_feed_urls import validated_feed_url
from wichita_provenance import SOURCE_OUR_ANTENNA, SOURCE_PUBLIC_FEED, provenance_fields
from wichita_receiver_health import feed_health_payload
from untrusted_text import (
    MAX_LEN_AIRCRAFT_ID,
    MAX_LEN_REGISTRATION,
    MAX_LEN_TYPE_DESC,
    sanitize_untrusted_text,
)

logger = logging.getLogger(__name__)

ADSB_TIMEOUT_SEC = float(os.environ.get("WICHITA_ADSB_TIMEOUT_SEC", "2.5"))
EMERGENCY_SQUAWKS = {
    "7500": "Squawking 7500: hijack code, not confirmed by us",
    "7600": "Squawking 7600: radio failure, not confirmed by us",
    "7700": "Squawking 7700: general emergency, not confirmed by us",
}


SRC_LOCAL = "local antenna"
SRC_ADSBLOL = "adsb.lol"
SRC_BOTH = "local + adsb.lol"
ADSBLOL_URL = os.environ.get("WICHITA_ADSBLOL_URL", "https://api.adsb.lol/v2/lat/35.9/lon/14.5/dist/250")
ADSBLOL_INTERVAL_SEC = 15.0
ADSBLOL_MAX_BACKOFF_SEC = 300.0
ADSBLOL_STALE_SEC = 90.0
USER_AGENT = "Wichita/1.0 (wichitawire.com; non-commercial Malta rescue-listening alpha; 1 server, 15 s poll)"
FEED_LABEL = "Aircraft: adsb.lol, community feed"


def local_adsb_enabled() -> bool:
    return bool(os.environ.get("WICHITA_ADSB_URL", "").strip()) or adsb_fixture_path() is not None


def adsb_base_url() -> str:
    raw = os.environ.get("WICHITA_ADSB_URL", "http://127.0.0.1:8080/data/aircraft.json")
    return validated_feed_url(raw, "WICHITA_ADSB_URL", "http://127.0.0.1:8080/data/aircraft.json").rstrip("/")


def adsb_fixture_path() -> Optional[Path]:
    """Only when WICHITA_ADSB_FIXTURE_DIR is set (tests/dev replay, not production UI)."""
    raw = os.environ.get("WICHITA_ADSB_FIXTURE_DIR", "").strip()
    if not raw:
        return None
    p = Path(raw).expanduser().resolve()
    if p.is_file():
        return p
    if p.is_dir():
        candidate = p / "aircraft.json"
        return candidate if candidate.is_file() else None
    return None


def fetch_aircraft_json() -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    fixture = adsb_fixture_path()
    if fixture is not None and fixture.is_file():
        try:
            return json.loads(fixture.read_text(encoding="utf-8")), None
        except OSError as exc:
            return None, str(exc)

    url = adsb_base_url()
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=ADSB_TIMEOUT_SEC) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body), None
    except urllib.error.URLError as exc:
        logger.warning("readsb unreachable at %s: %s", url, exc)
        return None, "Receiver not connected"
    except json.JSONDecodeError:
        return None, "Receiver returned invalid JSON"
    except ValueError as exc:
        return None, str(exc)
    except TimeoutError:
        return None, "Receiver not connected"


def _squawk_note(squawk: Optional[str]) -> Optional[str]:
    if not squawk:
        return None
    s = str(squawk).strip().zfill(4)
    return EMERGENCY_SQUAWKS.get(s)


def is_emergency(p: Dict[str, Any]) -> bool:
    sq = str(p.get("squawk") or "").strip().zfill(4)
    em = str(p.get("emergency") or "none").strip().lower()
    return sq in EMERGENCY_SQUAWKS or em not in ("", "none")


def normalize_aircraft(
    raw: Dict[str, Any], now: Optional[datetime] = None, source: str = SRC_LOCAL
) -> Optional[Dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    lat, lon = raw.get("lat"), raw.get("lon")
    if lat is None or lon is None:
        return None
    seen = raw.get("seen_pos")
    if seen is None:
        seen = raw.get("seen")
    try:
        seen_s = float(seen) if seen is not None else None
    except (TypeError, ValueError):
        seen_s = None
    flight = sanitize_untrusted_text(raw.get("flight"), MAX_LEN_AIRCRAFT_ID)
    callsign = flight or None
    hex_id = (raw.get("hex") or "").strip().lower()
    if not hex_id:
        return None
    alt = raw.get("alt_baro")
    if alt is None:
        alt = raw.get("alt_geom")
    if alt == "ground":
        alt = 0
    squawk = raw.get("squawk")
    if squawk is not None:
        squawk = str(squawk).strip()
    gs = raw.get("gs")
    track = raw.get("track")
    if track is None:
        track = raw.get("heading")
    prov = provenance_fields(SOURCE_OUR_ANTENNA if source == SRC_LOCAL else SOURCE_PUBLIC_FEED, seen_s)
    emergency = (raw.get("emergency") or "none")
    emergency = str(emergency).strip().lower() or "none"
    out = {
        "id": hex_id,
        "hex": hex_id,
        "callsign": callsign,
        "display_name": callsign or hex_id.upper(),
        "lat": float(lat),
        "lon": float(lon),
        "altitude_ft": alt,
        "speed_kts": gs,
        "heading_deg": track,
        "squawk": squawk,
        "squawk_note": _squawk_note(squawk),
        "emergency": emergency,
        "registration": sanitize_untrusted_text(raw.get("r"), MAX_LEN_REGISTRATION) or None,
        "type": sanitize_untrusted_text(raw.get("t"), MAX_LEN_AIRCRAFT_ID) or None,
        "type_desc": sanitize_untrusted_text(raw.get("desc"), MAX_LEN_TYPE_DESC) or None,
        "source": source,
        "sources": [source],
        "last_signal_s": seen_s,
        "last_heard_utc": datetime.fromtimestamp(now.timestamp() - seen_s, tz=timezone.utc).isoformat()
        if seen_s is not None
        else None,
        **prov,
    }
    if emergency != "none" and not out["squawk_note"]:
        out["squawk_note"] = f"Emergency flag: {emergency}, not confirmed by us"
    out["is_emergency"] = is_emergency(out)
    return out


def merge_aircraft(local: List[Dict[str, Any]], remote: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Dedupe by ICAO hex. Prefer local antenna when its position is at least as fresh."""
    by_hex: Dict[str, Dict[str, Any]] = {}
    for p in remote:
        by_hex[p["hex"]] = p
    for p in local:
        other = by_hex.get(p["hex"])
        if other is None:
            by_hex[p["hex"]] = p
            continue
        la = p.get("last_signal_s")
        ra = other.get("last_signal_s")
        local_fresher = ra is None or (la is not None and la <= ra)
        win, lose = (p, other) if local_fresher else (other, p)
        merged = dict(win)
        for k in ("registration", "type", "type_desc", "callsign"):
            if not merged.get(k) and lose.get(k):
                merged[k] = lose[k]
        merged["display_name"] = merged.get("callsign") or merged["hex"].upper()
        merged["emergency"] = win["emergency"] if win["emergency"] != "none" else lose["emergency"]
        merged["squawk_note"] = win.get("squawk_note") or lose.get("squawk_note")
        merged["is_emergency"] = bool(win.get("is_emergency") or lose.get("is_emergency"))
        merged["source"] = SRC_BOTH
        merged["sources"] = [SRC_LOCAL, SRC_ADSBLOL]
        merged["position_source"] = win["source"]
        by_hex[p["hex"]] = merged
    return sort_aircraft(list(by_hex.values()))


def sort_aircraft(planes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Emergencies pinned to the top, then fresh before stale, then by name."""
    return sorted(
        planes,
        key=lambda p: (
            not p.get("is_emergency"),
            p.get("freshness") != "now",
            (p.get("callsign") or p.get("hex") or "").upper(),
        ),
    )


class AdsbLolPoller:
    """The only caller of adsb.lol. Background thread, cache, backoff."""

    def __init__(self, url: str = ADSBLOL_URL, interval: float = ADSBLOL_INTERVAL_SEC):
        self.url = url
        self.interval = interval
        self._lock = threading.Lock()
        self._payload: Optional[Dict[str, Any]] = None
        self._fetched_at: Optional[float] = None
        self._error: Optional[str] = None
        self._failures = 0
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def poll_once(self) -> None:
        req = urllib.request.Request(self.url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            if not isinstance(data, dict) or not isinstance(data.get("ac"), list):
                raise ValueError("unexpected adsb.lol payload")
            with self._lock:
                self._payload, self._fetched_at, self._error, self._failures = data, time.time(), None, 0
        except Exception as exc:  # network, JSON, HTTP 429/5xx
            logger.warning("adsb.lol poll failed: %s", exc)
            with self._lock:
                self._failures += 1
                self._error = "adsb.lol unreachable"

    def next_delay(self) -> float:
        if self._failures == 0:
            return self.interval
        return min(ADSBLOL_MAX_BACKOFF_SEC, self.interval * (2 ** min(self._failures, 5)))

    def _run(self) -> None:
        while not self._stop.is_set():
            self.poll_once()
            self._stop.wait(self.next_delay())

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="adsblol-poller", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def snapshot(self) -> Tuple[Optional[Dict[str, Any]], Optional[float], Optional[str]]:
        with self._lock:
            return self._payload, self._fetched_at, self._error


_POLLER: Optional[AdsbLolPoller] = None


def get_poller() -> AdsbLolPoller:
    global _POLLER
    if _POLLER is None:
        _POLLER = AdsbLolPoller()
    return _POLLER


def adsblol_enabled() -> bool:
    return os.environ.get("WICHITA_ADSBLOL", "1").strip() not in ("0", "false", "off")


def live_adsb_snapshot() -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    # Local antenna (stub until the Mini's readsb is live)
    local: List[Dict[str, Any]] = []
    local_on = False
    local_err: Optional[str] = "Local antenna not configured"
    if local_adsb_enabled():
        payload, local_err = fetch_aircraft_json()
        local_on = payload is not None and local_err is None
        for row in (payload or {}).get("aircraft") or []:
            if isinstance(row, dict):
                n = normalize_aircraft(row, now, SRC_LOCAL)
                if n:
                    local.append(n)
    # adsb.lol cache (filled by the background poller only)
    remote: List[Dict[str, Any]] = []
    feed_on = False
    feed_err: Optional[str] = None
    fetched_utc = None
    if adsblol_enabled():
        payload, fetched_at, feed_err = get_poller().snapshot()
        age = (time.time() - fetched_at) if fetched_at else None
        feed_on = payload is not None and age is not None and age < ADSBLOL_STALE_SEC
        if payload is None and not feed_err:
            feed_err = "Waiting for first adsb.lol poll"
        if fetched_at:
            fetched_utc = datetime.fromtimestamp(fetched_at, tz=timezone.utc).isoformat()
        extra_age = age or 0.0
        for row in (payload or {}).get("ac") or []:
            if isinstance(row, dict):
                r = dict(row)
                for k in ("seen", "seen_pos"):
                    if r.get(k) is not None:
                        try:
                            r[k] = float(r[k]) + extra_age
                        except (TypeError, ValueError):
                            pass
                n = normalize_aircraft(r, now, SRC_ADSBLOL)
                if n:
                    remote.append(n)
        if not feed_on and payload is not None and not feed_err:
            feed_err = "adsb.lol data is stale"
    planes = merge_aircraft(local, remote)
    online = local_on or feed_on
    youngest = min((p.get("last_signal_s") for p in planes if p.get("last_signal_s") is not None), default=None)
    health = feed_health_payload(
        receiver="readsb" if local_on else "adsb.lol",
        band="ADS-B 1090 MHz",
        online=online,
        error=None if online else (feed_err or local_err),
        youngest_signal_s=youngest,
        entity_count=len(planes),
    )
    try:
        from wichita_adsb_tracks import get_track_store

        get_track_store().record_snapshot(planes, now.isoformat())
    except Exception:
        pass
    labels = []
    if local_on:
        labels.append("Aircraft: local antenna")
    if adsblol_enabled():
        labels.append(FEED_LABEL)
    return {
        "online": online,
        "receiver_connected": online,
        "feed_paused": not online,
        "local_antenna_connected": local_on,
        "adsblol_online": feed_on,
        "adsblol_fetched_utc": fetched_utc,
        "error": None if online else (feed_err or local_err),
        "receiver_health": health,
        "source_label": " · ".join(labels) or "No aircraft source",
        "data_source": SOURCE_OUR_ANTENNA if local_on and not feed_on else SOURCE_PUBLIC_FEED,
        "aircraft": planes,
        "aircraft_count": len(planes),
        "emergency_count": sum(1 for p in planes if p.get("is_emergency")),
        "server_time_utc": now.isoformat(),
        "coverage": health.get("coverage"),
        "coverage_label": health.get("coverage_label"),
    }
