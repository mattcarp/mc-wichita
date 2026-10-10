"""Guard upstream receiver URLs (AIS / ADSB) to private addresses only."""

from __future__ import annotations

import ipaddress
import os
import socket
import urllib.parse
from typing import Optional, Tuple


def _allow_public_upstream() -> bool:
    return os.environ.get("WICHITA_ALLOW_PUBLIC_UPSTREAM", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def is_private_host(host: str) -> bool:
    host = (host or "").strip().lower()
    if not host:
        return False
    if host in ("localhost", "127.0.0.1", "::1"):
        return True
    if host.endswith(".ts.net"):
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


def assert_private_upstream(url: str) -> Tuple[bool, Optional[str]]:
    if _allow_public_upstream():
        return True, None
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False, f"unsupported scheme for upstream {parsed.scheme}"
    host = parsed.hostname
    if host is None:
        return False, "upstream URL missing host"
    if is_private_host(host):
        return True, None
    return False, f"upstream host {host} is not on the private allow-list"
