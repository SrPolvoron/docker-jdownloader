import hmac
import ipaddress
import socket
from urllib.parse import urlsplit

from aiohttp.abc import AbstractResolver


class UnsafeURL(ValueError):
    pass


def normalize_url(url: str) -> str:
    url = url.strip()
    if not url or len(url) > 4096 or any(ord(ch) < 32 or ord(ch) == 127 for ch in url):
        raise UnsafeURL("Invalid URL length or control characters")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as exc:
        raise UnsafeURL("Invalid URL or port") from exc
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        raise UnsafeURL("Only HTTP/HTTPS URLs are supported")
    if parts.username is not None or parts.password is not None:
        raise UnsafeURL("Embedded URL credentials are not supported")
    if port not in (None, 80, 443):
        raise UnsafeURL("Non-standard ports are not allowed")
    if parts.hostname.endswith("."):
        raise UnsafeURL("Trailing-dot hostnames are not allowed")
    if not hmac.compare_digest(parts.scheme, parts.scheme.lower()):
        raise UnsafeURL("Uppercase URL schemes are not supported")
    return url


def ensure_public_ip(address: str) -> None:
    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError as exc:
        raise UnsafeURL("Invalid resolved IP address") from exc
    if not ip.is_global:
        raise UnsafeURL("Target resolves to a non-public IP address")


async def resolve_public(host: str, port: int) -> list[dict]:
    try:
        # getaddrinfo is asynchronous via asyncio's threadpool.
        import asyncio
        responses = await asyncio.get_running_loop().getaddrinfo(
            host, port, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP
        )
    except OSError as exc:
        raise UnsafeURL("DNS lookup failed") from exc
    if not responses:
        raise UnsafeURL("DNS returned no addresses")
    result = []
    for family, _type, proto, _canon, sockaddr in responses:
        address = sockaddr[0]
        ensure_public_ip(address)
        result.append({"hostname": host, "host": address, "port": port,
                       "family": family, "proto": proto, "flags": 0})
    return result


class PublicResolver(AbstractResolver):
    async def resolve(self, host: str, port: int = 0, family: int = socket.AF_INET) -> list[dict]:
        del family
        return await resolve_public(host, port)

    async def close(self) -> None:
        pass


async def validate_destination(url: str) -> str:
    normalized = normalize_url(url)
    parsed = urlsplit(normalized)
    await resolve_public(parsed.hostname or "", parsed.port or (443 if parsed.scheme == "https" else 80))
    return normalized
