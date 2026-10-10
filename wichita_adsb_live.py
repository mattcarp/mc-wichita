"""Read-only proxy for local readsb / dump1090 aircraft.json (no SDR control)."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from wichita_provenance import SOURCE_OUR_ANTENNA, provenance_fields
from wichita_receiver_health import classify_receiver_state, feed_age_from_unix, receiver_health_block
from wichita_upstream import assert_private_upstream
from wichita_adsb_history import get_adsb_history

logger = logging.getLogger(__name__)

ADSB_TIMEOUT_SEC = float(os.environ.get("WICHITA_ADSB_TIMEOUT_SEC", "2.5"))
EMERGENCY_SQUAWKS = {
    "7500": "Squawking 7500: hijack code, not confirmed by us",
    "7600": "Squawking 7600: radio failure, not confirmed by us",
    "7700": "Squawking 7700: general emergency, not confirmed by us",
}


def adsb_base_url() -> str:
    return os.environ.get("WICHITA_ADSB_URL", "http://127.0.0.1:8080/data/aircraft.json").rstrip("/")


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
    ok, why = assert_private_upstream(url)
    if not ok:
        return None, why or "upstream blocked"
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
    except TimeoutError:
        return None, "Receiver not connected"


def _squawk_note(squawk: Optional[str]) -> Optional[str]:
    if not squawk:
        return None
    s = str(squawk).strip().zfill(4)
    return EMERGENCY_SQUAWKS.get(s)


def normalize_aircraft(raw: Dict[str, Any], now: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
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
    flight = (raw.get("flight") or "").strip()
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
    prov = provenance_fields(SOURCE_OUR_ANTENNA, seen_s)
    return {
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
        "last_signal_s": seen_s,
        "last_heard_utc": datetime.fromtimestamp(now.timestamp() - seen_s, tz=timezone.utc).isoformat()
        if seen_s is not None
        else None,
        **prov,
    }


def readsb_receiver_health(
    payload: Optional[Dict[str, Any]],
    err: Optional[str],
    planes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    if err == "Receiver not connected":
        reachable = False
        payload_valid = False
        feed_age = None
    elif err == "Receiver returned invalid JSON":
        reachable = True
        payload_valid = False
        feed_age = None
    else:
        reachable = True
        payload_valid = True
        feed_age = feed_age_from_unix((payload or {}).get("now"))
        if feed_age is None and planes:
            ages = [p.get("last_signal_s") for p in planes if p.get("last_signal_s") is not None]
            feed_age = min(ages) if ages else None
    min_seen = min(
        (p.get("last_signal_s") for p in planes if p.get("last_signal_s") is not None),
        default=None,
    )
    state = classify_receiver_state(
        reachable=reachable,
        payload_valid=payload_valid,
        feed_age_sec=feed_age,
        contact_count=len(planes),
    )
    return receiver_health_block(
        service="readsb",
        band="ADS-B 1090 MHz",
        source=SOURCE_OUR_ANTENNA,
        state=state,
        feed_age_sec=feed_age,
        contact_count=len(planes),
        last_signal_s=min_seen,
        extra={"error": err, "messages": (payload or {}).get("messages")},
    )


def live_adsb_snapshot() -> Dict[str, Any]:
    payload, err = fetch_aircraft_json()
    online = payload is not None and err is None
    now = datetime.now(timezone.utc)
    aircraft_raw = (payload or {}).get("aircraft") or []
    planes: List[Dict[str, Any]] = []
    for row in aircraft_raw:
        if not isinstance(row, dict):
            continue
        norm = normalize_aircraft(row, now)
        if norm:
            planes.append(norm)
    planes.sort(key=lambda p: (p.get("freshness") != "live", (p.get("callsign") or p.get("hex") or "").upper()))
    health = readsb_receiver_health(payload, err, planes)
    try:
        get_adsb_history().record_snapshot(planes, (payload or {}).get("now"))
    except OSError as exc:
        logger.warning("adsb history write failed: %s", exc)
    return {
        "online": health.get("online", online),
        "receiver_connected": health.get("reachable", online),
        "receiver_health": health,
        "error": err,
        "source_label": "Heard by our antenna",
        "data_source": SOURCE_OUR_ANTENNA,
        "data_caveat": "Observed from our antenna — not official flight data or ground truth",
        "aircraft": planes,
        "aircraft_count": len(planes),
        "server_time_utc": now.isoformat(),
    }
