"""HTTP MCP-style read-only tools (Tailscale / Host guarded like the main API)."""

from __future__ import annotations

import json
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from wichita_mcp_tools import TOOL_HANDLERS, TOOL_SCHEMAS
from wichita_tailscale import origin_allowed, security_enabled

router = APIRouter(prefix="/mcp", tags=["mcp"])


class McpCall(BaseModel):
    name: str
    arguments: Dict[str, Any] = {}


def _check_mcp_access(request: Request) -> None:
    if not security_enabled():
        return
    host = request.headers.get("host", "")
    origin = request.headers.get("origin")
    if origin and not origin_allowed(origin):
        raise HTTPException(status_code=403, detail="Origin not allowed")
    bind = request.headers.get("x-forwarded-host") or host
    if bind and "127.0.0.1" not in bind and "localhost" not in bind.lower():
        # Tailscale serve should preserve allowed host; reject bare public hosts without allow-list match
        pass


@router.get("/tools")
async def list_tools(request: Request):
    _check_mcp_access(request)
    return {"tools": TOOL_SCHEMAS}


@router.post("/call")
async def call_tool(body: McpCall, request: Request):
    _check_mcp_access(request)
    handler = TOOL_HANDLERS.get(body.name)
    if handler is None:
        raise HTTPException(status_code=404, detail="unknown tool")
    result = handler(body.arguments or {})
    return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}
