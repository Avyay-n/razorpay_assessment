"""
Asynchronous HTTP client for Groww's internal endpoints with connection pooling and retries.
"""

import asyncio
import logging
import time
from typing import Any, Dict, Optional
import httpx

from app.config import (
    GROWW_BASE_URL,
    USER_AGENT,
    REQUEST_TIMEOUT_SECONDS,
    MAX_RETRIES,
    RETRY_BACKOFF_FACTOR,
)

logger = logging.getLogger("groww_api.client")


class UpstreamException(Exception):
    """Base exception for upstream network / service errors."""
    pass


class ResourceNotFoundError(UpstreamException):
    """Raised when an entity, ticker, or symbol is not found on upstream."""
    pass


class UpstreamRateLimitError(UpstreamException):
    """Raised when upstream throttles or blocks requests with 429."""
    pass


class UpstreamServiceUnavailableError(UpstreamException):
    """Raised when upstream returns 5xx or network fails after retries."""
    pass


class GrowwClient:
    """Async client interfacing with Groww web endpoints."""

    def __init__(self):
        self._headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://groww.in/",
            "Origin": "https://groww.in",
        }
        self._limits = httpx.Limits(max_keepalive_connections=20, max_connections=50)
        self._timeout = httpx.Timeout(REQUEST_TIMEOUT_SECONDS)
        self._client: Optional[httpx.AsyncClient] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def get_client(self) -> httpx.AsyncClient:
        """Lazy-initialize and return the httpx AsyncClient for the current event loop."""
        current_loop = asyncio.get_running_loop()
        if (
            self._client is None
            or self._client.is_closed
            or self._loop != current_loop
        ):
            self._client = httpx.AsyncClient(
                headers=self._headers,
                limits=self._limits,
                timeout=self._timeout,
                follow_redirects=True,
            )
            self._loop = current_loop
        return self._client

    async def close(self):
        """Close the underlying client connection pool."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _request_with_retry(
        self, method: str, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute HTTP request with exponential backoff retry on transient errors."""
        client = await self.get_client()
        last_error = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = await client.request(method, url, params=params)

                if response.status_code == 200:
                    data = response.json()
                    # Some Groww endpoints return empty JSON or null if not found
                    if not data:
                        raise ResourceNotFoundError(f"Upstream returned empty body for {url}")
                    return data

                if response.status_code == 404:
                    raise ResourceNotFoundError(f"Requested resource was not found upstream (404): {url}")

                if response.status_code == 429:
                    logger.warning(f"Upstream rate limit hit on attempt {attempt}: {url}")
                    if attempt == MAX_RETRIES:
                        raise UpstreamRateLimitError("Upstream rate limit (429) exceeded.")

                if response.status_code in (500, 502, 503, 504):
                    logger.warning(
                        f"Upstream returned HTTP {response.status_code} on attempt {attempt}/{MAX_RETRIES}: {url}"
                    )
                    if attempt == MAX_RETRIES:
                        raise UpstreamServiceUnavailableError(
                            f"Upstream server error HTTP {response.status_code} for {url}"
                        )

            except (httpx.RequestError, httpx.TimeoutException) as exc:
                last_error = exc
                logger.warning(f"Network error on attempt {attempt}/{MAX_RETRIES} for {url}: {exc}")
                if attempt == MAX_RETRIES:
                    raise UpstreamServiceUnavailableError(f"Network connection failed: {exc}") from exc

            # Sleep before next retry
            sleep_time = RETRY_BACKOFF_FACTOR * (2 ** (attempt - 1))
            await asyncio.sleep(sleep_time)

        raise UpstreamServiceUnavailableError(f"Failed to fetch {url} after {MAX_RETRIES} attempts. Error: {last_error}")

    async def search(
        self, query: str, entity_type: Optional[str] = None, page: int = 0, size: int = 10
    ) -> Dict[str, Any]:
        """Search instruments (stocks, mutual funds, indices)."""
        url = f"{GROWW_BASE_URL}/search/v1/entity"
        params = {
            "app": "false",
            "business": "all",
            "entity_type": entity_type or "",
            "from": page * size,
            "page": page,
            "q": query,
            "size": min(size, 25),
        }
        return await self._request_with_retry("GET", url, params=params)

    async def get_live_quote(self, symbol: str, exchange: str = "NSE") -> Dict[str, Any]:
        """Fetch latest live market price for symbol."""
        clean_symbol = symbol.strip().upper()
        url = f"{GROWW_BASE_URL}/stocks_data/v1/tr_live_prices/exchange/{exchange}/segment/CASH/{clean_symbol}/latest"
        return await self._request_with_retry("GET", url)

    async def get_company_profile(self, search_id: str) -> Dict[str, Any]:
        """Fetch company fundamentals and profile by search slug."""
        clean_slug = search_id.strip().lower()
        url = f"{GROWW_BASE_URL}/stocks_data/v1/company/search_id/{clean_slug}"
        data = await self._request_with_retry("GET", url)
        if not data.get("header"):
            raise ResourceNotFoundError(f"Company profile not found for slug: {clean_slug}")
        return data

    async def get_chart_data(
        self, symbol: str, interval_in_minutes: int = 60, days: int = 7
    ) -> Dict[str, Any]:
        """Fetch historical candlestick chart data."""
        clean_symbol = symbol.strip().upper()
        now_ms = int(time.time() * 1000)
        start_ms = now_ms - (days * 24 * 3600 * 1000)

        url = f"{GROWW_BASE_URL}/charting_service/v2/chart/exchange/NSE/segment/CASH/{clean_symbol}"
        params = {
            "intervalInMinutes": interval_in_minutes,
            "candleType": "FULL",
            "endTimeInMillis": now_ms,
            "startTimeInMillis": start_ms,
        }
        return await self._request_with_retry("GET", url, params=params)


# Singleton client
groww_client = GrowwClient()
