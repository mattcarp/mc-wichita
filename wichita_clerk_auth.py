"""Clerk session JWT verification for Wichita dashboard API routes."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import jwt
from jwt.algorithms import RSAAlgorithm
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

_DEFAULT_PUBLISHABLE = "pk_test_ZGFybGluZy1ib3hlci0xNTA0LmNsZXJrLmFjY291bnRzLmRldiQ="
_DEFAULT_FRONTEND_API = "https://darling-boxer-1504.clerk.accounts.dev"
_DEFAULT_JWKS = Path(__file__).resolve().parent / "config" / "clerk_jwks.json"
_DEFAULT_AUTHORIZED_PARTIES = (
    "https://wichitawire.com",
    "https://matts-mac-mini.tail6a2168.ts.net",
    "http://localhost:3000",
)

_PUBLIC_EXACT = frozenset({"/", "/health"})
_PUBLIC_PREFIXES = (
    "/dashboard/",
    "/docs",
    "/redoc",
    "/openapi.json",
)

_jwks_lock = threading.Lock()
_jwks_cache: Optional[Dict[str, Any]] = None
_jwks_cache_mtime: float = 0.0
_remote_jwks_fetched_at: float = 0.0
_REMOTE_REFRESH_SEC = 3600.0


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def auth_required() -> bool:
    return _env_bool("WICHITA_AUTH_REQUIRED", True)


def clerk_publishable_key() -> str:
    return os.environ.get("WICHITA_CLERK_PUBLISHABLE_KEY", _DEFAULT_PUBLISHABLE).strip()


def clerk_frontend_api() -> str:
    return os.environ.get("WICHITA_CLERK_FRONTEND_API", _DEFAULT_FRONTEND_API).rstrip("/")


def clerk_jwks_path() -> Path:
    raw = os.environ.get("WICHITA_CLERK_JWKS_PATH", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return _DEFAULT_JWKS


def authorized_parties() -> Set[str]:
    raw = os.environ.get("WICHITA_CLERK_AUTHORIZED_PARTIES", "").strip()
    if not raw:
        return set(_DEFAULT_AUTHORIZED_PARTIES)
    return {p.strip().rstrip("/") for p in raw.split(",") if p.strip()}


def allowed_emails() -> Optional[Set[str]]:
    raw = os.environ.get("WICHITA_ALLOWED_EMAILS", "").strip()
    if not raw:
        return None
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def is_public_path(path: str) -> bool:
    if path in _PUBLIC_EXACT:
        return True
    return any(path.startswith(prefix) for prefix in _PUBLIC_PREFIXES)


def _read_jwks_file() -> Dict[str, Any]:
    path = clerk_jwks_path()
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _fetch_remote_jwks() -> Optional[Dict[str, Any]]:
    url = f"{clerk_frontend_api()}/.well-known/jwks.json"
    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError, ValueError) as exc:
        logger.debug("Clerk JWKS refresh failed: %s", exc)
        return None


def get_jwks(force_remote: bool = False) -> Dict[str, Any]:
    global _jwks_cache, _jwks_cache_mtime, _remote_jwks_fetched_at
    path = clerk_jwks_path()
    mtime = path.stat().st_mtime if path.is_file() else 0.0
    with _jwks_lock:
        stale_file = _jwks_cache is None or mtime != _jwks_cache_mtime
        remote_due = time.monotonic() - _remote_jwks_fetched_at > _REMOTE_REFRESH_SEC
        if stale_file or force_remote or (remote_due and _jwks_cache is None):
            try:
                _jwks_cache = _read_jwks_file()
                _jwks_cache_mtime = mtime
            except OSError as exc:
                logger.warning("Could not read Clerk JWKS file: %s", exc)
                _jwks_cache = {"keys": []}
        if force_remote or remote_due:
            remote = _fetch_remote_jwks()
            _remote_jwks_fetched_at = time.monotonic()
            if remote and remote.get("keys"):
                _jwks_cache = remote
        return _jwks_cache or {"keys": []}


def _key_for_kid(kid: str, jwks: Dict[str, Any]) -> Optional[str]:
    for entry in jwks.get("keys") or []:
        if entry.get("kid") == kid:
            return RSAAlgorithm.from_jwk(json.dumps(entry))
    return None


def _email_from_claims(claims: Dict[str, Any]) -> Optional[str]:
    for key in ("email", "primary_email_address", "email_address"):
        val = claims.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip().lower()
    return None


def verify_clerk_token(token: str) -> Dict[str, Any]:
    """Validate a Clerk session JWT; raises jwt.PyJWTError on failure."""
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    if not kid:
        raise jwt.InvalidTokenError("missing kid")

    jwks = get_jwks()
    pem = _key_for_kid(kid, jwks)
    if pem is None:
        jwks = get_jwks(force_remote=True)
        pem = _key_for_kid(kid, jwks)
    if pem is None:
        raise jwt.InvalidTokenError("unknown signing key")

    issuer = clerk_frontend_api()
    parties = authorized_parties()
    claims = jwt.decode(
        token,
        pem,
        algorithms=["RS256"],
        issuer=issuer,
        options={"require": ["exp", "sub"]},
    )

    azp = claims.get("azp")
    if not azp or azp not in parties:
        raise jwt.InvalidTokenError("azp not authorized")

    allow = allowed_emails()
    if allow is not None:
        email = _email_from_claims(claims)
        if not email or email not in allow:
            raise jwt.InvalidTokenError("email not allowed")

    return claims


def token_from_request(request: Request) -> Optional[str]:
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    cookie = request.cookies.get("__session")
    if cookie:
        return cookie
    return None


def token_from_websocket(websocket) -> Optional[str]:
    auth = websocket.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    for part in (websocket.headers.get("cookie") or "").split(";"):
        piece = part.strip()
        if piece.startswith("__session="):
            return piece.split("=", 1)[1].strip() or None
    return None


def require_http_auth(request: Request) -> Optional[JSONResponse]:
    if not auth_required() or is_public_path(request.url.path):
        return None
    token = token_from_request(request)
    if not token:
        return JSONResponse({"detail": "Authentication required"}, status_code=401)
    try:
        verify_clerk_token(token)
    except jwt.PyJWTError:
        return JSONResponse({"detail": "Invalid or expired session"}, status_code=401)
    return None


async def require_websocket_auth(websocket) -> bool:
    if not auth_required():
        return True
    token = token_from_websocket(websocket)
    if not token:
        await websocket.close(code=4401)
        return False
    try:
        verify_clerk_token(token)
    except jwt.PyJWTError:
        await websocket.close(code=4401)
        return False
    return True


def clerk_public_config() -> Dict[str, str]:
    return {
        "publishableKey": clerk_publishable_key(),
        "frontendApi": clerk_frontend_api(),
    }


def clerk_csp_directives() -> str:
    api = clerk_frontend_api()
    turnstile = "https://challenges.cloudflare.com"
    protect_cdn = "https://cdn.protect.clerk.com"
    protect_hosts = "https://*.protect.clerk.com"
    protect_connect = "https://*.protect.clerk.com:*"
    return (
        "default-src 'self'; "
        f"script-src 'self' {api} {turnstile} {protect_cdn} {protect_hosts}; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https://img.clerk.com; "
        f"connect-src 'self' {api} https://api.clerk.com {protect_cdn} {protect_connect}; "
        f"frame-src 'self' {api} {turnstile} {protect_hosts}; "
        "font-src 'self'; "
        "worker-src 'self' blob:; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )


class ClerkAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        denied = require_http_auth(request)
        if denied is not None:
            return denied
        return await call_next(request)
