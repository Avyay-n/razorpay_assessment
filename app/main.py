"""
FastAPI Application Entry Point.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import time
import logging

from fastapi import FastAPI, HTTPException, Query, Path, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import APP_NAME, APP_VERSION, APP_DESCRIPTION
from app.client import (
    groww_client,
    ResourceNotFoundError,
    UpstreamRateLimitError,
    UpstreamServiceUnavailableError,
)
from app.models import (
    HealthResponse,
    ErrorResponse,
    SearchResponse,
    LiveQuote,
    CompanyProfile,
    ChartResponse,
)
from app.services import market_service
from app.utils.cache import cache

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("groww_api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycle."""
    logger.info("Initializing Groww Market Data API service...")
    yield
    logger.info("Shutting down Groww Market Data API service and closing connection pool...")
    await groww_client.close()


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Process Timing Middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = (time.perf_counter() - start_time) * 1000
    response.headers["X-Process-Time-Ms"] = f"{process_time:.2f}"
    return response


# ---------------------------------------------------------
# Custom Exception Handlers
# ---------------------------------------------------------

@app.exception_handler(ResourceNotFoundError)
async def resource_not_found_handler(request: Request, exc: ResourceNotFoundError):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"error": "Resource Not Found", "detail": str(exc), "status_code": 404},
    )


@app.exception_handler(UpstreamRateLimitError)
async def upstream_rate_limit_handler(request: Request, exc: UpstreamRateLimitError):
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"error": "Upstream Rate Limit Exceeded", "detail": str(exc), "status_code": 429},
    )


@app.exception_handler(UpstreamServiceUnavailableError)
async def upstream_service_unavailable_handler(request: Request, exc: UpstreamServiceUnavailableError):
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"error": "Upstream Gateway Error", "detail": str(exc), "status_code": 502},
    )


# ---------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------

@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Diagnostics"],
    summary="Service Health Check",
    description="Returns current service status, active version, and in-memory cache statistics."
)
async def health_check():
    return HealthResponse(
        status="ok",
        service=APP_NAME,
        version=APP_VERSION,
        timestamp=datetime.now(timezone.utc).isoformat(),
        cache=cache.stats(),
    )


@app.get(
    "/api/v1/search",
    response_model=SearchResponse,
    responses={400: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
    tags=["Catalog Search"],
    summary="Search Indian Equities & Mutual Funds",
    description="Universal autocomplete search across NSE/BSE listed stocks, indices, and mutual fund schemes."
)
async def search_instruments(
    q: str = Query(..., min_length=1, max_length=100, description="Search keyword (e.g. 'Tata', 'Reliance', 'Parag Parikh')"),
    entity_type: str = Query(None, description="Filter by type: 'Stocks', 'Scheme' (Mutual Fund), or empty for all"),
    page: int = Query(0, ge=0, description="Page index (0-based)"),
    size: int = Query(10, ge=1, le=25, description="Number of results per page (max 25)")
):
    try:
        return await market_service.search(query=q, entity_type=entity_type, page=page, size=size)
    except Exception as exc:
        if isinstance(exc, (ResourceNotFoundError, UpstreamRateLimitError, UpstreamServiceUnavailableError)):
            raise exc
        logger.error(f"Unexpected error in search: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error executing search")


@app.get(
    "/api/v1/quotes/{symbol}",
    response_model=LiveQuote,
    responses={404: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
    tags=["Market Data"],
    summary="Get Real-Time Live Quote",
    description="Fetches live market price, day change, volume, 52-week high/low for an equity symbol or major index."
)
async def get_live_quote(
    symbol: str = Path(..., min_length=1, max_length=25, description="NSE Trading symbol (e.g. 'RELIANCE', 'TMPV', 'INFY', 'NIFTY')"),
    exchange: str = Query("NSE", description="Exchange: 'NSE' or 'BSE'")
):
    try:
        return await market_service.get_live_quote(symbol=symbol, exchange=exchange)
    except Exception as exc:
        if isinstance(exc, (ResourceNotFoundError, UpstreamRateLimitError, UpstreamServiceUnavailableError)):
            raise exc
        logger.error(f"Unexpected error in get_live_quote for {symbol}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error fetching quote for {symbol}")


@app.get(
    "/api/v1/company/{search_id}",
    response_model=CompanyProfile,
    responses={404: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
    tags=["Company Research"],
    summary="Get Company Fundamentals & Profile",
    description="Retrieves company profile, business description, executive leadership, and financial ratios (P/E, Market Cap, ROE, etc.)."
)
async def get_company_profile(
    search_id: str = Path(..., min_length=1, max_length=100, description="Company slug identifier (e.g. 'reliance-industries-ltd', 'tata-motors-ltd')")
):
    try:
        return await market_service.get_company_profile(search_id=search_id)
    except Exception as exc:
        if isinstance(exc, (ResourceNotFoundError, UpstreamRateLimitError, UpstreamServiceUnavailableError)):
            raise exc
        logger.error(f"Unexpected error in get_company_profile for {search_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error fetching profile for {search_id}")


@app.get(
    "/api/v1/chart/{symbol}",
    response_model=ChartResponse,
    responses={404: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
    tags=["Historical Charts"],
    summary="Get Historical Candlestick Chart (OHLCV)",
    description="Fetches historical candlestick chart data (Open, High, Low, Close, Volume) over a designated timeframe."
)
async def get_chart_data(
    symbol: str = Path(..., min_length=1, max_length=25, description="NSE Trading symbol (e.g. 'RELIANCE', 'INFY')"),
    interval: int = Query(60, description="Candle interval in minutes (e.g. 5, 15, 60, 1440)"),
    days: int = Query(7, ge=1, le=90, description="Historical range in days (1 to 90)")
):
    try:
        return await market_service.get_chart_data(symbol=symbol, interval_in_minutes=interval, days=days)
    except Exception as exc:
        if isinstance(exc, (ResourceNotFoundError, UpstreamRateLimitError, UpstreamServiceUnavailableError)):
            raise exc
        logger.error(f"Unexpected error in get_chart_data for {symbol}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error fetching chart for {symbol}")


@app.post(
    "/api/v1/cache/clear",
    tags=["Diagnostics"],
    summary="Clear Internal Cache",
    description="Administrative utility to invalidate all cached entries."
)
async def clear_cache():
    cache.clear()
    return {"message": "Cache successfully cleared", "stats": cache.stats()}
