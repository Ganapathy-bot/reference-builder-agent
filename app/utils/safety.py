"""URL safety checks. Retrieved page text is data, never instructions."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeURL(ValueError):
    """The URL is not safe to fetch."""


_BLOCKED_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "metadata.internal",
}


def assert_public_host(host: str | None) -> None:
    if not host:
        raise UnsafeURL("URL host is missing.")
    cleaned = host.strip().strip("[]").rstrip(".").lower()
    if cleaned in _BLOCKED_HOSTS or cleaned.endswith(".local") or cleaned.endswith(".localhost"):
        raise UnsafeURL("That URL is not allowed.")
    try:
        literal = ipaddress.ip_address(cleaned)
        addresses = [literal]
    except ValueError:
        try:
            infos = socket.getaddrinfo(cleaned, None)
        except socket.gaierror as exc:
            raise UnsafeURL("Could not resolve that host.") from exc
        addresses = []
        for info in infos:
            try:
                addresses.append(ipaddress.ip_address(info[4][0]))
            except ValueError:
                continue
    if not addresses:
        raise UnsafeURL("Could not resolve that host.")
    for address in addresses:
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
        ):
            raise UnsafeURL("That URL is not allowed.")


def assert_safe_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeURL("Only http and https URLs can be fetched.")
    if parsed.username or parsed.password:
        raise UnsafeURL("URLs with credentials are not allowed.")
    assert_public_host(parsed.hostname)
    return parsed.geturl()
