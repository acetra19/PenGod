"""Block obviously unsafe probe targets (SSRF mitigation for MVP)."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

_BLOCKED_HOST_SUFFIXES = (".local", ".localhost", ".internal")
_BLOCKED_HOSTS = frozenset(
    {
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "::1",
        "metadata.google.internal",
        "metadata",
    }
)


def assert_public_http_url(url: str) -> None:
    """
    Allow only http(s) URLs whose hostname resolves to non-private addresses.
    Raises ValueError with an English message if blocked.
    """
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only http and https URLs are allowed.")
    host = parsed.hostname
    if not host:
        raise ValueError("URL must include a hostname.")

    h = host.lower()
    if h in _BLOCKED_HOSTS:
        raise ValueError("Hostname is not allowed for probing.")
    for suf in _BLOCKED_HOST_SUFFIXES:
        if h.endswith(suf):
            raise ValueError("Hostname suffix is not allowed for probing.")

    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"DNS resolution failed: {exc}") from exc

    for _fam, _type, _proto, _canon, sockaddr in infos:
        addr = sockaddr[0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ValueError("Resolved IP is not a public probe target.")
