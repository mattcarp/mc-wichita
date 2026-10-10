"""Feed health states for readsb and AIS-catcher (live / stale / unreachable / invalid)."""

from __future__ import annotations

from typing import Any, Dict, Optional

FEED_STALE_SEC = float(__import__("os").environ.get("WICHITA_FEED_STALE_SEC", "10"))
HEARD_WINDOW_SEC = 60.0

STATE_LIVE = "live"
STATE_STALE = "stale"
STATE_UNREACHABLE = "unreachable"
STATE_INVALID = "invalid"

_STATE_LABELS = {
    STATE_LIVE: "Live",
    STATE_STALE: "Stale",
    STATE_UNREACHABLE: "Unreachable",
    STATE_INVALID: "Invalid",
}

_BAND_AIS = "AIS 161.975 / 162.025 MHz"
_BAND_ADSB = "ADS-B 1090 MHz"


def classify_fetch_error(err: Optional[str]) -> str:
    if not err:
        return STATE_UNREACHABLE
    low = err.lower()
    if "invalid" in low or "json" in low:
        return STATE_INVALID
    return STATE_UNREACHABLE


def feed_health_state(
    *,
    online: bool,
    error: Optional[str],
    youngest_signal_s: Optional[float],
) -> str:
    if not online:
        return classify_fetch_error(error)
    if youngest_signal_s is not None and youngest_signal_s > FEED_STALE_SEC:
        return STATE_STALE
    return STATE_LIVE


def feed_health_payload(
    *,
    receiver: str,
    band: str,
    online: bool,
    error: Optional[str],
    youngest_signal_s: Optional[float],
    entity_count: int,
) -> Dict[str, Any]:
    state = feed_health_state(
        online=online,
        error=error,
        youngest_signal_s=youngest_signal_s,
    )
    quiet = state == STATE_LIVE and entity_count == 0
    coverage = "quiet" if quiet else ("active" if entity_count else "idle")
    if state in (STATE_UNREACHABLE, STATE_INVALID):
        coverage = "outage"
    return {
        "receiver": receiver,
        "band": band,
        "state": state,
        "state_label": _STATE_LABELS[state],
        "error": error if state in (STATE_UNREACHABLE, STATE_INVALID) else None,
        "youngest_signal_s": youngest_signal_s,
        "entity_count": entity_count,
        "coverage": coverage,
        "coverage_label": "Quiet (receiver healthy)" if quiet else None,
        "quiet": quiet,
    }


def heard_last_60s_badge(
    *,
    ais_count: int,
    adsb_count: int,
    bands_active: Optional[list[str]] = None,
) -> Dict[str, Any]:
    bands = bands_active or []
    if ais_count and _BAND_AIS not in bands:
        bands.append(_BAND_AIS)
    if adsb_count and _BAND_ADSB not in bands:
        bands.append(_BAND_ADSB)
    total = ais_count + adsb_count
    return {
        "label": "Heard by my antenna, last 60 s",
        "count": total,
        "ais_count": ais_count,
        "adsb_count": adsb_count,
        "bands": bands,
        "active": total > 0,
        "source": "our_antenna",
    }


def count_heard_within(entities: list[Dict[str, Any]], window_sec: float = HEARD_WINDOW_SEC) -> int:
    n = 0
    for ent in entities:
        age = ent.get("last_signal_s")
        if age is None:
            continue
        try:
            if float(age) <= window_sec:
                n += 1
        except (TypeError, ValueError):
            continue
    return n
