#!/usr/bin/env python3
"""Stdio MCP server (read-only). Run behind Tailscale; no SDR control."""

from __future__ import annotations

import json
import sys
from typing import Any, Dict

from wichita_mcp_tools import TOOL_HANDLERS, TOOL_SCHEMAS

PROTOCOL_VERSION = "2024-11-05"


def _send(msg: Dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def _handle(msg: Dict[str, Any]) -> None:
    method = msg.get("method")
    req_id = msg.get("id")
    if method == "initialize":
        _send(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "wichita-readonly", "version": "1.0.0"},
                },
            }
        )
        return
    if method == "tools/list":
        _send({"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOL_SCHEMAS}})
        return
    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        handler = TOOL_HANDLERS.get(name)
        if not handler:
            _send(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": "unknown tool"},
                }
            )
            return
        payload = handler(args)
        _send(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
                    "isError": False,
                },
            }
        )
        return
    if req_id is not None:
        _send(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"unsupported method {method}"},
            }
        )


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        _handle(msg)


if __name__ == "__main__":
    main()
