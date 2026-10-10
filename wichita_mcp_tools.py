"""Read-only MCP tool payloads (ships, planes, events)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

import wichita_adsb_live as wad
import wichita_ais_live as wal
from wichita_live_events import get_engine


def ships_now() -> Dict[str, Any]:
    bundle = wal.live_dashboard_bundle()
    return {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "receiver": bundle.get("receiver_health"),
        "ships": bundle.get("ships") or [],
        "caveat": "Observed AIS from our antenna — not official traffic data",
    }


def planes_now() -> Dict[str, Any]:
    snap = wad.live_adsb_snapshot()
    return {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "receiver": snap.get("receiver_health"),
        "aircraft": snap.get("aircraft") or [],
        "caveat": snap.get("data_caveat"),
    }


def events_since(hours: int = 2, limit: int = 50) -> Dict[str, Any]:
    engine = get_engine()
    page = engine.events_page(hours=hours, limit=limit, before=None)
    return {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "hours": hours,
        "events": page.get("events") or [],
        "caveat": "Heard-timeline from live AIS polling — human review required",
    }


TOOL_HANDLERS = {
    "ships_now": lambda args: ships_now(),
    "planes_now": lambda args: planes_now(),
    "events_since": lambda args: events_since(
        int(args.get("hours", 2)),
        int(args.get("limit", 50)),
    ),
}

TOOL_SCHEMAS = [
    {
        "name": "ships_now",
        "description": "Current AIS vessels heard by our antenna (read-only).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "planes_now",
        "description": "Current ADS-B aircraft heard by our antenna (read-only).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "events_since",
        "description": "Heard-timeline events from the last N hours.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "hours": {"type": "integer", "minimum": 1, "maximum": 48},
                "limit": {"type": "integer", "minimum": 1, "maximum": 200},
            },
        },
    },
]
