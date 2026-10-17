"""Conservative, extensible URL resolvers. No CAPTCHA/anti-bot circumvention."""
import html
import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import aiohttp

from .security import PublicResolver, UnsafeURL, normalize_url
from .plugins import apply_plugins


@dataclass(frozen=True)
class Resolution:
    url: str
    method: str
    note: str
    needs_manual: bool = False


# Hosting providers are normally handled better by JDownloader's plugins.
PASSTHROUGH_HOSTS = frozenset({
    "mega.nz", "mediafire.com", "drive.google.com", "dropbox.com", "pixeldrain.com",
    "1fichier.com", "gofile.io", "rapidgator.net", "terabox.com", "youtube.com",
    "youtu.be", "github.com", "gitlab.com", "archive.org", "wetransfer.com",
})


def passthrough(host: str) -> bool:
    return any(host == root or host.endswith("." + root) for root in PASSTHROUGH_HOSTS)


def target_from_html(page: str, base: str) -> str | None:
    """Recognize only deterministic navigation, never random advertisement anchors."""
    patterns = (
        r'<meta\s+[^>]*http-equiv\s*=\s*["\']?refresh["\']?[^>]*content\s*=\s*["\'][^"\']*?url\s*=\s*([^"\'>;]+)',
        r'<meta\s+[^>]*content\s*=\s*["\'][^"\']*?url\s*=\s*([^"\'>;]+)["\'][^>]*http-equiv\s*=\s*["\']?refresh',
        r'(?:window\.|document\.)?location(?:\.href)?\s*=\s*["\'](https?://[^"\']+)["\']',
        r'(?:window\.|document\.)?location\.replace\(\s*["\'](https?://[^"\']+)["\']\s*\)',
    )
    for pattern in patterns:
        match = re.search(pattern, page, re.IGNORECASE)
        if match:
            candidate = html.unescape(match.group(1).strip()).strip("'\" ")
            try:
                return normalize_url(urljoin(base, candidate))
            except UnsafeURL:
                continue
    return None


class RedirectResolver:
    """Plugin interface: subclasses can implement handle(url) in future releases."""

    def __init__(self, timeout: int = 12, max_hops: int = 8) -> None:
        self.timeout = timeout
        self.max_hops = max_hops

    async def resolve(self, original: str) -> Resolution:
        current = normalize_url(original)
        known = apply_plugins(current)
        if known:
            return Resolution(known[0], known[1], "Known outbound redirect extracted")
        if passthrough((urlsplit(current).hostname or "").lower()):
            return Resolution(current, "hoster", "Delegated to JDownloader's host plugin")
        visited: set[str] = set()
        timeout = aiohttp.ClientTimeout(total=self.timeout, connect=min(self.timeout, 8))
        connector = aiohttp.TCPConnector(resolver=PublicResolver(), use_dns_cache=False,
                                         force_close=True, limit=2)
        async with aiohttp.ClientSession(timeout=timeout, connector=connector,
                                         trust_env=False, headers={"User-Agent": "JFStackDownloader/0.1"}) as session:
            for hop in range(self.max_hops):
                if current in visited:
                    return Resolution(current, "cycle", "Redirect loop detected", needs_manual=True)
                visited.add(current)
                known = apply_plugins(current)
                if known:
                    current = known[0]
                    continue
                try:
                    # Each redirect is validated *before* the next network request.
                    normalized = normalize_url(current)
                    async with session.get(normalized, allow_redirects=False) as response:
                        if 300 <= response.status < 400 and response.headers.get("Location"):
                            current = normalize_url(urljoin(normalized, response.headers["Location"]))
                            continue
                        if response.status in {401, 403, 429, 503}:
                            return Resolution(current, "blocked", f"Site requires interaction (HTTP {response.status})", True)
                        if response.status >= 400:
                            return Resolution(current, "http", f"HTTP {response.status}; original/last URL retained", True)
                        media_type = response.headers.get("Content-Type", "").lower()
                        if "text/html" not in media_type:
                            return Resolution(current, "direct", "Direct or non-HTML resource")
                        raw = await response.content.read(65537)
                        if len(raw) > 65536:
                            return Resolution(current, "html", "HTML exceeded inspection limit; delegated to JDownloader")
                        page = raw.decode(response.charset or "utf-8", errors="replace")
                        candidate = target_from_html(page, str(response.url))
                        if candidate and candidate != current:
                            current = candidate
                            continue
                        if re.search(r'captcha|verify you are human|cloudflare challenge', page, re.I):
                            return Resolution(current, "manual", "CAPTCHA or verification may require manual action", True)
                        return Resolution(current, "html", "No deterministic redirect; JDownloader will inspect the link")
                except (aiohttp.ClientError, TimeoutError, UnicodeError, LookupError) as exc:
                    # Keep messages generic (no URL/token leakage into history).
                    return Resolution(current, "network", f"Cannot inspect target ({type(exc).__name__})", True)
        return Resolution(current, "limit", "Maximum redirect count reached", True)
