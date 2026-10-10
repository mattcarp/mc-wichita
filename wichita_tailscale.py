"""Host allow-list, CSP, and nosniff for Tailscale-served Wichita API."""

from __future__ import annotations

import os
from typing import Callable, Iterable, List, Optional, Set

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

DEFAULT_HOSTS = (
    "localhost",
    "127.0.0.1",
    "[::1]",
    "testserver",
)


def _parse_allowlist(raw: str) -> Set[str]:
    hosts: Set[str] = set()
    for part in raw.split(","):
        h = part.strip().lower()
        if h:
            hosts.add(h)
    return hosts


def allowed_hosts_from_env() -> Set[str]:
    raw = os.environ.get("WICHITA_ALLOWED_HOSTS", "").strip()
    hosts = _parse_allowlist(raw) if raw else set()
    for h in DEFAULT_HOSTS:
        hosts.add(h)
    tailscale = os.environ.get("WICHITA_TAILSCALE_HOSTNAME", "").strip().lower()
    if tailscale:
        hosts.add(tailscale)
    return hosts


def security_enabled() -> bool:
    return os.environ.get("WICHITA_SECURITY_ENABLED", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def _host_allowed(host_header: Optional[str], allow: Set[str]) -> bool:
    if not host_header:
        return False
    host = host_header.split(":", 1)[0].strip().lower()
    if host in allow:
        return True
    for entry in allow:
        if entry.startswith(".") and host.endswith(entry):
            return True
    return False


def csp_header() -> str:
    return (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )


class TailscaleSecurityMiddleware(BaseHTTPMiddleware):
    """Reject requests whose Host is not on the Wichita allow-list."""

    def __init__(self, app, allow: Optional[Iterable[str]] = None) -> None:
        super().__init__(app)
        self._allow = set(allow) if allow is not None else allowed_hosts_from_env()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not security_enabled():
            response = await call_next(request)
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            return response

        path = request.url.path
        if path in ("/health", "/docs", "/redoc", "/openapi.json"):
            pass
        elif not _host_allowed(request.headers.get("host"), self._allow):
            return JSONResponse(
                status_code=403,
                content={"detail": "Host not allowed"},
                headers={
                    "X-Content-Type-Options": "nosniff",
                    "Content-Security-Policy": csp_header(),
                },
            )

        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Content-Security-Policy", csp_header())
        return response


def origin_allowed(origin: Optional[str], allow: Optional[Set[str]] = None) -> bool:
    if not origin:
        return False
    allow = allow or allowed_hosts_from_env()
    origin_l = origin.lower()
    for host in allow:
        if origin_l.endswith(f"//{host}") or origin_l.endswith(f"//{host}:"):
            return True
        if f"//{host}:" in origin_l:
            return True
    return False
