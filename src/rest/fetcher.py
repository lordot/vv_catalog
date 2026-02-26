import asyncio

import aiohttp
from aiohttp import ClientOSError, ClientConnectorError, ClientSSLError, ClientResponseError
from aiohttp_socks import ProxyConnector

from src.config import settings
from src.logger import logger


class CatalogFetcher:
    """Async HTTP client for scraping VkusVill catalog pages.

    Single-threaded, infinite retry on 502 with exponential backoff.
    """

    def __init__(self):
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> "CatalogFetcher":
        connector = ProxyConnector.from_url(settings.bot_proxy) if settings.bot_proxy else None
        self._session = aiohttp.ClientSession(connector=connector)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()

    _RETRYABLE_STATUSES = {502, 503, 504}

    async def fetch_page(self, url: str) -> str:
        """Fetch a page with infinite retry and exponential backoff on 502."""
        attempt = 0
        while True:
            delay = min(
                settings.retry_base_delay * (2 ** attempt),
                settings.retry_max_delay,
            )
            try:
                async with self._session.get(url) as resp:
                    if resp.status == 200:
                        return await resp.text()
                    if resp.status in self._RETRYABLE_STATUSES:
                        logger.warning(
                            f"GET {url} returned {resp.status}, "
                            f"retrying in {delay:.0f}s (attempt {attempt + 1})"
                        )
                        await asyncio.sleep(delay)
                        attempt += 1
                        continue
                    logger.error(f"GET {url} failed with {resp.status}")
                    return ""
            except (ClientOSError, ClientConnectorError, ClientResponseError,
                    ClientSSLError, asyncio.TimeoutError) as e:
                logger.error(
                    f"Attempt {attempt + 1} failed for {url}: {e}, "
                    f"retrying in {delay:.0f}s"
                )
                await asyncio.sleep(delay)
                attempt += 1

    async def fetch_page_bytes(self, url: str) -> bytes:
        """Fetch page as bytes (for product detail parsing). Infinite retry."""
        attempt = 0
        while True:
            delay = min(
                settings.retry_base_delay * (2 ** attempt),
                settings.retry_max_delay,
            )
            try:
                async with self._session.get(url) as resp:
                    if resp.status == 200:
                        return await resp.read()
                    if resp.status in self._RETRYABLE_STATUSES:
                        logger.warning(
                            f"GET {url} returned {resp.status}, "
                            f"retrying in {delay:.0f}s (attempt {attempt + 1})"
                        )
                        await asyncio.sleep(delay)
                        attempt += 1
                        continue
                    logger.error(f"GET {url} failed with {resp.status}")
                    return b""
            except (ClientOSError, ClientConnectorError, ClientResponseError,
                    ClientSSLError, asyncio.TimeoutError) as e:
                logger.error(
                    f"Attempt {attempt + 1} failed for {url}: {e}, "
                    f"retrying in {delay:.0f}s"
                )
                await asyncio.sleep(delay)
                attempt += 1
