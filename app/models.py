"""
Pydantic data models for request and response serialization.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ---------------------------------------------------------
# Search Models
# ---------------------------------------------------------

class SearchResultItem(BaseModel):
    id: str = Field(..., description="Unique entity identifier or slug on Groww")
    title: str = Field(..., description="Display title of the stock, mutual fund, or index")
    entity_type: str = Field(..., description="Entity category: 'Stocks', 'Scheme' (Mutual Fund), etc.")
    nse_scrip_code: Optional[str] = Field(None, description="National Stock Exchange scrip code / ticker")
    bse_scrip_code: Optional[str] = Field(None, description="Bombay Stock Exchange scrip code")
    isin: Optional[str] = Field(None, description="International Securities Identification Number")
    search_id: str = Field(..., description="Search lookup slug used for company details")


class SearchResponse(BaseModel):
    query: str = Field(..., description="Search query executed")
    entity_type_filter: Optional[str] = Field(None, description="Entity type filter applied")
    total_results: int = Field(..., description="Number of results returned")
    results: List[SearchResultItem] = Field(default_factory=list, description="List of matched entities")


# ---------------------------------------------------------
# Live Quote Models
# ---------------------------------------------------------

class LiveQuote(BaseModel):
    symbol: str = Field(..., description="NSE Trading symbol (e.g., RELIANCE, INFY, NIFTY)")
    ltp: float = Field(..., description="Last Traded Price in INR")
    day_change: float = Field(..., description="Absolute price change for the trading day in INR")
    day_change_percentage: float = Field(..., description="Percentage price change for the trading day")
    open: Optional[float] = Field(None, description="Day opening price")
    high: Optional[float] = Field(None, description="Day high price")
    low: Optional[float] = Field(None, description="Day low price")
    previous_close: Optional[float] = Field(None, description="Previous day closing price")
    volume: Optional[int] = Field(None, description="Total traded volume")
    year_high: Optional[float] = Field(None, description="52-week high price")
    year_low: Optional[float] = Field(None, description="52-week low price")
    timestamp_ms: Optional[int] = Field(None, description="Epoch timestamp in milliseconds")
    currency: str = Field("INR", description="Trading currency")


# ---------------------------------------------------------
# Company Profile & Fundamentals Models
# ---------------------------------------------------------

class CompanyFundamentalItem(BaseModel):
    name: str = Field(..., description="Name of fundamental metric (e.g. Market Cap, P/E Ratio, ROE)")
    short_name: Optional[str] = Field(None, description="Abbreviated metric name (e.g. Mkt Cap, P/E)")
    value: str = Field(..., description="Formatted metric value (e.g. ₹1,03,124Cr, 15.2, 18.5%)")


class CompanyProfile(BaseModel):
    search_id: str = Field(..., description="Company slug identifier")
    display_name: str = Field(..., description="Full legal / trading company name")
    short_name: Optional[str] = Field(None, description="Short company name")
    isin: Optional[str] = Field(None, description="ISIN number")
    groww_company_id: Optional[str] = Field(None, description="Groww internal company ID")
    industry_name: Optional[str] = Field(None, description="Industry sector classification")
    about: Optional[str] = Field(None, description="Company overview and business summary")
    ceo: Optional[str] = Field(None, description="Chief Executive Officer name")
    managing_director: Optional[str] = Field(None, description="Managing Director name")
    founded_year: Optional[int] = Field(None, description="Year company was founded")
    parent_company: Optional[str] = Field(None, description="Parent conglomerate or holding group")
    fundamentals: List[CompanyFundamentalItem] = Field(
        default_factory=list, description="Key financial metrics (Market Cap, P/E, ROE, EPS, etc.)"
    )
    year_high_price: Optional[float] = Field(None, description="52-week high price")
    year_low_price: Optional[float] = Field(None, description="52-week low price")


# ---------------------------------------------------------
# Historical Candlestick Chart Models
# ---------------------------------------------------------

class CandleStick(BaseModel):
    timestamp: int = Field(..., description="Epoch timestamp in seconds")
    datetime_iso: str = Field(..., description="Human-readable ISO 8601 datetime (UTC)")
    open: float = Field(..., description="Candle opening price")
    high: float = Field(..., description="Candle highest price")
    low: float = Field(..., description="Candle lowest price")
    close: float = Field(..., description="Candle closing price")
    volume: int = Field(..., description="Volume traded during the candle interval")


class ChartResponse(BaseModel):
    symbol: str = Field(..., description="NSE Trading symbol")
    interval_in_minutes: int = Field(..., description="Candlestick resolution in minutes")
    candle_count: int = Field(..., description="Total number of candlesticks returned")
    start_time_iso: str = Field(..., description="Start of historical window in ISO 8601")
    end_time_iso: str = Field(..., description="End of historical window in ISO 8601")
    candles: List[CandleStick] = Field(default_factory=list, description="Chronological series of OHLCV bars")


# ---------------------------------------------------------
# System / Diagnostics Models
# ---------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = Field(..., description="Health status (e.g. 'ok')")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    timestamp: str = Field(..., description="Current ISO 8601 timestamp")
    cache: Dict[str, Any] = Field(default_factory=dict, description="In-memory cache metrics")


class ErrorResponse(BaseModel):
    error: str = Field(..., description="Error category or summary")
    detail: Optional[str] = Field(None, description="Detailed explanation of the failure")
    status_code: int = Field(..., description="HTTP status code")
