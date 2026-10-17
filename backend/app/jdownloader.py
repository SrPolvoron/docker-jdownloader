"""Private Click'n'Load bridge; link submission is not download confirmation."""
import aiohttp


class JDownloaderUnavailable(RuntimeError):
    pass


class CNLClient:
    def __init__(self, base: str):
        self.base = base.rstrip("/")

    async def is_ready(self) -> bool:
        try:
            timeout = aiohttp.ClientTimeout(total=3)
            async with aiohttp.ClientSession(timeout=timeout, trust_env=False) as session:
                async with session.get(self.base + "/flash/") as response:
                    return response.status == 200 and "jdownloader" in (await response.text())[:2000].lower()
        except (aiohttp.ClientError, TimeoutError):
            return False

    async def send(self, url: str) -> None:
        try:
            timeout = aiohttp.ClientTimeout(total=7)
            async with aiohttp.ClientSession(timeout=timeout, trust_env=False) as session:
                async with session.post(self.base + "/flash/add",
                                        data={"urls": url}) as response:
                    body = (await response.text())[:128].lower()
                    if response.status != 200 or body.strip() != "success":
                        raise JDownloaderUnavailable("Click'n'Load rejected the link")
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise JDownloaderUnavailable("Click'n'Load is unreachable. Check JDownloader settings") from exc
