"""
Business logic and transformation service layer.
"""

from datetime import datetime, timezone
from typing import Optional, List
import logging

from app.client import (
    groww_client,
    ResourceNotFoundError,
    UpstreamRateLimitError,
    UpstreamServiceUnavailableError,
)
from app.models import (
    SearchResponse,
    SearchResultItem,
    LiveQuote,
    CompanyProfile,
    CompanyFundamentalItem,
    ChartResponse,
    CandleStick,
)
from app.utils.cache import cache

logger = logging.getLogger("groww_api.services")


class MarketDataService:
    """Service orchestrating caching and normalization of Groww data."""

    def __init__(self, client=groww_client, cache_instance=cache):
        self.client = client
        self.cache = cache_instance

    async def search(
        self, query: str, entity_type: Optional[str] = None, page: int = 0, size: int = 10
    ) -> SearchResponse:
        """Search across Indian financial instruments with caching."""
        clean_q = query.strip()
        cache_key = f"search:{clean_q.lower()}:{entity_type or 'all'}:{page}:{size}"

        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        raw = await self.client.search(clean_q, entity_type=entity_type, page=page, size=size)
        items = raw.get("content", [])

        normalized_items: List[SearchResultItem] = []
        for it in items:
            title = it.get("title") or it.get("company_short_name") or it.get("search_id") or "Unknown"
            search_id = it.get("search_id") or it.get("id") or ""
            entity = it.get("entity_type") or it.get("sub_entity_type") or "Stocks"

            normalized_items.append(
                SearchResultItem(
                    id=it.get("id") or search_id,
                    title=title,
                    entity_type=entity,
                    nse_scrip_code=it.get("nse_scrip_code"),
                    bse_scrip_code=it.get("bse_scrip_code"),
                    isin=it.get("isin"),
                    search_id=search_id,
                )
            )

        response = SearchResponse(
            query=clean_q,
            entity_type_filter=entity_type,
            total_results=len(normalized_items),
            results=normalized_items,
        )

        # Cache search queries for 60 seconds
        self.cache.set(cache_key, response, ttl=60)
        return response

    async def get_live_quote(self, symbol: str, exchange: str = "NSE") -> LiveQuote:
        """Get normalized real-time quote for an equity or index."""
        clean_symbol = symbol.strip().upper()
        cache_key = f"quote:{exchange}:{clean_symbol}"

        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        raw = await self.client.get_live_quote(clean_symbol, exchange=exchange)

        # Build normalized quote model
        quote = LiveQuote(
            symbol=raw.get("symbol") or clean_symbol,
            ltp=float(raw.get("ltp", 0.0)),
            day_change=float(raw.get("dayChange", 0.0)),
            day_change_percentage=float(raw.get("dayChangePerc", 0.0)),
            open=raw.get("open"),
            high=raw.get("high"),
            low=raw.get("low"),
            previous_close=raw.get("close"),
            volume=raw.get("volume"),
            year_high=raw.get("yearHighPrice"),
            year_low=raw.get("yearLowPrice"),
            timestamp_ms=raw.get("tsInMillis"),
            currency="INR",
        )

        # Cache live quotes for 15 seconds to smooth spike loads while keeping freshness
        self.cache.set(cache_key, quote, ttl=15)
        return quote

    async def get_company_profile(self, search_id: str) -> CompanyProfile:
        """Get detailed company profile and financial metrics."""
        clean_slug = search_id.strip().lower()
        cache_key = f"company:{clean_slug}"

        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        raw = await self.client.get_company_profile(clean_slug)
        header = raw.get("header") or {}
        details = raw.get("details") or {}
        raw_fundamentals = raw.get("fundamentals") or []
        price_data = raw.get("priceData") or {}

        fundamentals_list: List[CompanyFundamentalItem] = []
        for f in raw_fundamentals:
            if isinstance(f, dict) and f.get("name") and f.get("value") is not None:
                fundamentals_list.append(
                    CompanyFundamentalItem(
                        name=f.get("name"),
                        short_name=f.get("shortName"),
                        value=str(f.get("value")),
                    )
                )

        nse_prices = price_data.get("nse") or {}
        bse_prices = price_data.get("bse") or {}
        year_high = nse_prices.get("yearHighPrice") or bse_prices.get("yearHighPrice")
        year_low = nse_prices.get("yearLowPrice") or bse_prices.get("yearLowPrice")

        profile = CompanyProfile(
            search_id=header.get("searchId") or clean_slug,
            display_name=header.get("displayName") or "Unknown",
            short_name=header.get("shortName"),
            isin=header.get("isin"),
            groww_company_id=header.get("growwCompanyId"),
            industry_name=header.get("industryName"),
            about=details.get("aboutCompany"),
            ceo=details.get("companyCeoName"),
            managing_director=details.get("managingDirector"),
            founded_year=details.get("foundedYear"),
            parent_company=details.get("parentCompany"),
            fundamentals=fundamentals_list,
            year_high_price=year_high,
            year_low_price=year_low,
        )

        # Company profile fundamentals are static intraday; cache for 300s (5 mins)
        self.cache.set(cache_key, profile, ttl=300)
        return profile

    async def get_chart_data(
        self, symbol: str, interval_in_minutes: int = 60, days: int = 7
    ) -> ChartResponse:
        """Get OHLC historical candlesticks."""
        clean_symbol = symbol.strip().upper()
        cache_key = f"chart:{clean_symbol}:{interval_in_minutes}:{days}"

        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        raw = await self.client.get_chart_data(
            clean_symbol, interval_in_minutes=interval_in_minutes, days=days
        )
        raw_candles = raw.get("candles") or []

        parsed_candles: List[CandleStick] = []
        for c in raw_candles:
            if isinstance(c, list) and len(c) >= 6:
                ts = int(c[0])
                iso_dt = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
                parsed_candles.append(
                    CandleStick(
                        timestamp=ts,
                        datetime_iso=iso_dt,
                        open=float(c[1]),
                        high=float(c[2]),
                        low=float(c[3]),
                        close=float(c[4]),
                        volume=int(c[5]),
                    )
                )

        start_time_iso = parsed_candles[0].datetime_iso if parsed_candles else ""
        end_time_iso = parsed_candles[-1].datetime_iso if parsed_candles else ""

        response = ChartResponse(
            symbol=clean_symbol,
            interval_in_minutes=interval_in_minutes,
            candle_count=len(parsed_candles),
            start_time_iso=start_time_iso,
            end_time_iso=end_time_iso,
            candles=parsed_candles,
        )

        # Cache chart data for 60 seconds
        self.cache.set(cache_key, response, ttl=60)
        return response


# Singleton service
market_service = MarketDataService()
