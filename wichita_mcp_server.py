#!/usr/bin/env python3
"""Read-only stdio MCP server: ships_now, planes_now, events_since."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Minimal MCP over stdio (JSON-RPC 2.0) — no extra runtime deps.


def _allowed_origin() -> bool:
    bind = os.environ.get("WICHITA_MCP_BIND", "127.0.0.1").strip()
    if bind in ("0.0.0.0", "::"):
        return False
    host = os.environ.get("WICHITA_MCP_ALLOWED_HOST", "127.0.0.1").strip().lower()
    return host in ("127.0.0.1", "localhost", "::1")


def _ships_now() -> Dict[str, Any]:
    import wichita_ais_live as wal

    bundle = wal.live_dashboard_bundle()
    return {"ships": bundle.get("ships") or [], "online": bundle.get("online"), "summary": bundle.get("summary")}


def _planes_now() -> Dict[str, Any]:
    import wichita_adsb_live as wad

    return wad.live_adsb_snapshot()


def _events_since(iso_ts: str, limit: int = 50) -> List[Dict[str, Any]]:
    from wichita_live_events import get_engine

    cutoff = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    out = []
    for ev in get_engine().read_events(hours=72):
        try:
            ts = datetime.fromisoformat(ev["ts_utc"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if ts >= cutoff:
            out.append(ev)
        if len(out) >= limit:
            break
    return out


TOOLS = [
    {
        "name": "ships_now",
        "description": "Current AIS vessels from our antenna (read-only).",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "planes_now",
        "description": "Current ADS-B aircraft from readsb (read-only).",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "events_since",
        "description": "Heard-timeline events since an ISO UTC timestamp.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "since_utc": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 200},
            },
            "required": ["since_utc"],
        },
    },
]


def _tool_result(name: str, arguments: Dict[str, Any]) -> Any:
    if name == "ships_now":
        return _ships_now()
    if name == "planes_now":
        return _planes_now()
    if name == "events_since":
        since = arguments.get("since_utc") or datetime.now(timezone.utc).isoformat()
        limit = int(arguments.get("limit") or 50)
        return {"events": _events_since(since, limit=limit)}
    raise ValueError(f"unknown tool {name}")


def _reply(msg_id: Any, result: Any) -> None:
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": result}) + "\n")
    sys.stdout.flush()


def _error(msg_id: Any, code: int, message: str) -> None:
    sys.stdout.write(
        json.dumps({"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}) + "\n"
    )
    sys.stdout.flush()


def handle(msg: Dict[str, Any]) -> None:
    msg_id = msg.get("id")
    method = msg.get("method")
    params = msg.get("params") or {}
    if method == "initialize":
        _reply(
            msg_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "wichita-readonly", "version": "1.0.0"},
            },
        )
        return
    if method == "notifications/initialized":
        return
    if method == "tools/list":
        _reply(msg_id, {"tools": TOOLS})
        return
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        try:
            payload = _tool_result(name, args)
            _reply(
                msg_id,
                {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]},
            )
        except Exception as exc:
            _error(msg_id, -32000, str(exc))
        return
    if msg_id is not None:
        _error(msg_id, -32601, f"Method not found: {method}")


def main() -> None:
    if not _allowed_origin():
        print("WICHITA_MCP_BIND must be loopback-only (127.0.0.1)", file=sys.stderr)
        sys.exit(1)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        handle(msg)


if __name__ == "__main__":
    main()
