"""Registry of narrowly scoped, deterministic short-link resolvers.

Implement `resolve(url)` on a plugin class and register it in PLUGINS.
Never guess from arbitrary advertising links or decode unknown query parameters.
"""
from typing import Protocol
from urllib.parse import parse_qs, urlsplit

from .security import UnsafeURL, normalize_url


class LinkResolverPlugin(Protocol):
    name: str

    def resolve(self, url: str) -> str | None: ...


class KnownOutboundRedirects:
    """Recognize well-known outbound URL parameter wrappers, without HTTP requests."""
    name = "known-outbound-query"

    # Each host/path/parameter triplet must be explicitly reviewed.
    RULES = (
        ("www.google.com", "/url", "q"),
        ("www.google.com", "/url", "url"),
        ("google.com", "/url", "q"),
        ("google.com", "/url", "url"),
        ("l.facebook.com", "/l.php", "u"),
        ("lm.facebook.com", "/l.php", "u"),
        ("out.reddit.com", "/", "url"),
        ("www.youtube.com", "/redirect", "q"),
        ("youtube.com", "/redirect", "q"),
    )

    def resolve(self, url: str) -> str | None:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        for rule_host, rule_path, name in self.RULES:
            if host == rule_host and parts.path == rule_path:
                values = parse_qs(parts.query, keep_blank_values=False).get(name, [])
                if len(values) != 1:
                    return None
                try:
                    candidate = normalize_url(values[0])
                except UnsafeURL:
                    return None
                if candidate == url:
                    return None
                return candidate
        return None


PLUGINS: tuple[LinkResolverPlugin, ...] = (KnownOutboundRedirects(),)


def apply_plugins(url: str) -> tuple[str, str] | None:
    for plugin in PLUGINS:
        candidate = plugin.resolve(url)
        if candidate is not None:
            return candidate, plugin.name
    return None
