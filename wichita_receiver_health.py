"""Unified receiver health states for AIS-catcher and readsb (read-only feeds)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

STALE_AFTER_SEC = 10.0
AIS_SPEED_NOT_AVAILABLE_KN = 102.3
AIS_COURSE_NOT_AVAILABLE_DEG = 360.0

STATE_LIVE = "live"
STATE_STALE = "stale"
STATE_UNREACHABLE = "unreachable"
STATE_INVALID = "invalid"
STATE_QUIET = "quiet"


def ais_speed_is_unknown(speed: Any) -> bool:
    if speed is None:
        return True
    try:
        v = float(speed)
    except (TypeError, ValueError):
        return True
    return v >= AIS_SPEED_NOT_AVAILABLE_KN - 0.05


def ais_course_is_unknown(cog: Any) -> bool:
    if cog is None:
        return True
    try:
        v = float(cog)
    except (TypeError, ValueError):
        return True
    if v >= 510:
        return True
    return 359.9 <= v <= 360.1


def sanitize_ais_motion(
    speed: Any, cog: Any, heading: Any
) -> Dict[str, Any]:
    speed_unknown = ais_speed_is_unknown(speed)
    cog_unknown = ais_course_is_unknown(cog)
    if heading is None:
        heading_unknown = True
    else:
        try:
            hv = float(heading)
        except (TypeError, ValueError):
            heading_unknown = True
        else:
            heading_unknown = hv >= 510
    out: Dict[str, Any] = {
        "speed_kn": None if speed_unknown else float(speed),
        "cog_deg": None if cog_unknown else float(cog) % 360.0,
        "heading_deg": None if heading_unknown else float(heading) % 360.0,
        "speed_unknown": speed_unknown,
        "cog_unknown": cog_unknown,
        "heading_unknown": heading_unknown,
    }
    return out


def classify_receiver_state(
    *,
    reachable: bool,
    payload_valid: bool,
    feed_age_sec: Optional[float],
    contact_count: int,
) -> str:
    if not reachable:
        return STATE_UNREACHABLE
    if not payload_valid:
        return STATE_INVALID
    if feed_age_sec is not None and feed_age_sec > STALE_AFTER_SEC:
        return STATE_STALE
    if contact_count == 0:
        return STATE_QUIET
    return STATE_LIVE


def heard_badge(
    *,
    source: str,
    band: str,
    state: str,
    last_signal_s: Optional[float],
    window_sec: float = 60.0,
) -> Dict[str, Any]:
    heard_recent = last_signal_s is not None and last_signal_s <= window_sec
    label = "Heard by my antenna, last 60 s" if heard_recent else "Heard by my antenna"
    return {
        "label": label,
        "source": source,
        "band": band,
        "state": state,
        "heard_last_60s": heard_recent,
        "last_signal_s": last_signal_s,
    }


def receiver_health_block(
    *,
    service: str,
    band: str,
    source: str,
    state: str,
    feed_age_sec: Optional[float],
    contact_count: int,
    last_signal_s: Optional[float],
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    block: Dict[str, Any] = {
        "service": service,
        "band": band,
        "source": source,
        "state": state,
        "stale_after_sec": STALE_AFTER_SEC,
        "feed_age_sec": feed_age_sec,
        "contact_count": contact_count,
        "quiet": state == STATE_QUIET,
        "online": state in (STATE_LIVE, STATE_QUIET, STATE_STALE),
        "reachable": state != STATE_UNREACHABLE,
        "checked_at_utc": now.isoformat(),
        "badge": heard_badge(
            source=source,
            band=band,
            state=state,
            last_signal_s=last_signal_s,
        ),
    }
    if extra:
        block.update(extra)
    return block


def feed_age_from_unix(now_unix: Optional[float]) -> Optional[float]:
    if now_unix is None:
        return None
    try:
        age = datetime.now(timezone.utc).timestamp() - float(now_unix)
    except (TypeError, ValueError):
        return None
    if age < 0:
        return 0.0
    return age
