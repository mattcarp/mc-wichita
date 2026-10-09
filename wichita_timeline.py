"""Presentation layer for the live AIS event log (filter, group, paginate)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

EVENT_KIND_PRIORITY = {
    "receiver_down": 0,
    "receiver_up": 1,
    "ship_first_heard": 2,
    "ship_status_change": 3,
    "ship_silent": 4,
    "ship_silent_group": 4,
}

DEFAULT_HOURS = 2
DEFAULT_LIMIT = 20


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)


def _quiet_window_key(ts: datetime) -> str:
    """Bucket quiet events into ~15 min windows for merging."""
    slot = (ts.minute // 15) * 15
    return ts.strftime(f"%Y-%m-%dT%H:{slot:02d}")


def prepare_timeline_events(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter noise, merge routine quiet flaps, sort by importance then time."""
    quiet_buckets: Dict[str, List[Dict[str, Any]]] = {}
    keep: List[Dict[str, Any]] = []

    for ev in raw:
        kind = ev.get("kind") or ""
        if kind == "ship_silent":
            try:
                ts = _parse_ts(ev["ts_utc"])
            except (KeyError, ValueError):
                continue
            key = _quiet_window_key(ts)
            quiet_buckets.setdefault(key, []).append(ev)
            continue
        keep.append(ev)

    for key, group in quiet_buckets.items():
        group.sort(key=lambda e: e.get("ts_utc", ""), reverse=True)
        if len(group) == 1:
            keep.append(group[0])
            continue
        names = []
        for ev in group[:8]:
            name = (ev.get("display_name") or ev.get("sentence") or "").split(" has gone quiet")[0]
            if name and name not in names:
                names.append(name)
        extra = len(group) - len(names)
        if len(names) == 1:
            sentence = group[0].get("sentence") or f"{names[0]} has gone quiet."
        else:
            sentence = f"{len(group)} ships went quiet ({', '.join(names[:4])}"
            if extra > 0:
                sentence += f", +{extra} more"
            sentence += ")."
        keep.append(
            {
                "ts_utc": group[0]["ts_utc"],
                "kind": "ship_silent_group",
                "sentence": sentence,
                "group_count": len(group),
                "group_key": key,
            }
        )

    def sort_key(ev: Dict[str, Any]) -> Tuple[int, float]:
        kind = ev.get("kind") or ""
        pri = EVENT_KIND_PRIORITY.get(kind, 9)
        try:
            ts = _parse_ts(ev["ts_utc"]).timestamp()
        except (KeyError, ValueError):
            ts = 0.0
        return (pri, -ts)

    keep.sort(key=sort_key)
    return keep


def paginate_events(
    events: List[Dict[str, Any]],
    *,
    limit: int = DEFAULT_LIMIT,
    before: Optional[str] = None,
) -> Dict[str, Any]:
    if before:
        try:
            cut = _parse_ts(before)
            events = [e for e in events if _parse_ts(e["ts_utc"]) < cut]
        except (KeyError, ValueError):
            pass
    page = events[:limit]
    has_more = len(events) > limit
    next_before = page[-1]["ts_utc"] if has_more and page else None
    return {
        "events": page,
        "has_more": has_more,
        "next_before": next_before,
        "limit": limit,
    }
