"""Private-only upstream feed URL validation for readsb and AIS-catcher."""

from __future__ import annotations

import ipaddress
import os
import socket
from typing import Optional
from urllib.parse import urlparse

_ALLOW_PUBLIC = os.environ.get("WICHITA_ALLOW_PUBLIC_FEED_URLS", "").strip().lower() in (
    "1",
    "true",
    "yes",
)


def _hostname_allowed(host: str) -> bool:
    if not host:
        return False
    host = host.strip().lower().rstrip(".")
    if host in ("localhost", "127.0.0.1", "::1"):
        return True
    try:
        addr = ipaddress.ip_address(host)
        return addr.is_private or addr.is_loopback or addr.is_link_local
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except OSError:
        return False
    for info in infos:
        ip = info[4][0]
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if addr.is_private or addr.is_loopback or addr.is_link_local:
            return True
    return False


def assert_private_feed_url(url: str, *, env_name: str) -> str:
    if _ALLOW_PUBLIC:
        return url
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"{env_name} must use http(s), got {parsed.scheme or 'missing'}")
    if not _hostname_allowed(parsed.hostname or ""):
        raise ValueError(
            f"{env_name} host must be private/localhost (got {parsed.hostname!r}). "
            "Set WICHITA_ALLOW_PUBLIC_FEED_URLS=1 only for dev."
        )
    return url


def validated_feed_url(raw: str, env_name: str, default: str) -> str:
    url = (raw or default).strip()
    return assert_private_feed_url(url, env_name=env_name)
