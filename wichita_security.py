"""Tailscale-facing hardening: Host allow-list, CSP, nosniff."""

from __future__ import annotations

import os
from typing import Callable, Iterable, List, Optional, Set

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_DEFAULT_HOSTS = {
    "localhost",
    "127.0.0.1",
    "[::1]",
    "testserver",
    # The Mini as reached over the tailnet and the LAN.
    "matts-mac-mini",
    "matts-mac-mini.local",
    "matts-mac-mini.tail6a2168.ts.net",
    "100.114.183.100",
}


def _parse_hosts(raw: str) -> Set[str]:
    out: Set[str] = set(_DEFAULT_HOSTS)
    for part in raw.split(","):
        h = part.strip().lower()
        if not h:
            continue
        out.add(h)
        if ":" in h and not h.startswith("["):
            out.add(h.split(":", 1)[0])
    return out


def allowed_hosts() -> Set[str]:
    raw = os.environ.get("WICHITA_ALLOWED_HOSTS", "").strip()
    if not raw:
        return _DEFAULT_HOSTS
    return _parse_hosts(raw)


def security_headers() -> dict[str, str]:
    csp = os.environ.get(
        "WICHITA_CSP",
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; "
        "base-uri 'self'; form-action 'self'",
    )
    return {
        "Content-Security-Policy": csp,
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "same-origin",
        "X-Frame-Options": "DENY",
    }


def _host_ok(request: Request, allowed: Set[str]) -> bool:
    host = (request.headers.get("host") or "").split(",")[0].strip().lower()
    if not host:
        return True
    bare = host.split(":", 1)[0]
    return host in allowed or bare in allowed


class WichitaSecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, skip_paths: Optional[Iterable[str]] = None) -> None:
        super().__init__(app)
        self._allowed = allowed_hosts()
        self._skip = set(skip_paths or ("/health", "/docs", "/redoc", "/openapi.json"))

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path not in self._skip and not _host_ok(request, self._allowed):
            return Response("Host not allowed", status_code=403)
        response = await call_next(request)
        for k, v in security_headers().items():
            response.headers.setdefault(k, v)
        return response
