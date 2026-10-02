# Groww Reverse-Engineered Market Data API Wrapper

A production-grade, asynchronous REST API wrapper reverse-engineered over **Groww's** public web catalog endpoints. Built with **FastAPI**, **Pydantic (v2)**, and **httpx**, this service provides standardized, typed access to Indian equities, indices, mutual funds, company fundamentals, and historical OHLC candlestick chart data.

> **Assessment Submission — Option 1: Reverse-Engineer an API**  
> Complies strictly with the constraint: *Uses publicly accessible information only; does not bypass access controls or include private data.*

---

## Architecture Overview

```
Client Requests
      │
      ▼
┌────────────────────────────────────────────────────────┐
│ FastAPI Application (`app/main.py`)                    │
│   ├── Request Timing Middleware (X-Process-Time-Ms)    │
│   ├── Exception Handlers (404, 422, 429, 502)          │
│   └── OpenAPI / Swagger UI at `/docs`                  │
└─────────────────────────┬──────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────┐
│ Market Data Service Layer (`app/services.py`)          │
│   ├── Pydantic Normalization & Data Validation         │
│   └── In-Memory TTL Cache (`app/utils/cache.py`)       │
│         └── Sub-millisecond latency for repeated hits  │
└─────────────────────────┬──────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────┐
│ Resilient Upstream Client (`app/client.py`)            │
│   ├── Connection Pooling (`httpx.AsyncClient`)         │
│   ├── Exponential Backoff Retries on 5xx / Timeouts    │
│   └── Standard Browser Client Emulation                │
└─────────────────────────┬──────────────────────────────┘
                          │ (HTTPS)
                          ▼
             Groww Public Web Endpoints
```

---

## Features

- **Universal Catalog Search**: Autocomplete search across all Indian stocks, mutual funds, and benchmark indices.
- **Real-Time Live Quotes**: Last Traded Price (LTP), percentage and absolute day change, volume, open/high/low/previous close, and 52-week extremes.
- **Company Fundamentals & Profile**: Market capitalization, P/E ratio, P/B ratio, ROE, EPS, industry sector, executive leadership, and business summaries.
- **Historical Candlestick Charts (OHLCV)**: Time-series candlestick data with configurable intervals (e.g., 5, 15, 60, 1440 minutes) and historical ranges.
- **In-Memory TTL Caching**: High-performance thread-safe caching to minimize upstream calls and prevent rate limits.
- **Fault-Tolerant Network Layer**: Async HTTP client with connection pooling and exponential backoff retry.
- **Self-Contained Automated Testing**: Standalone test runner (`run_tests.py`) plus standard `pytest` suite.

---

## Project Structure

```
razorpay_assessment/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, routing, middleware & error handlers
│   ├── config.py            # Environment settings and defaults
│   ├── client.py            # Asynchronous Groww client with retry & pooling
│   ├── models.py            # Pydantic v2 schemas for requests & responses
│   ├── services.py          # Data normalization and cache orchestration
│   └── utils/
│       ├── __init__.py
│       └── cache.py         # Thread-safe in-memory TTL cache
├── tests/
│   ├── __init__.py
│   └── test_api.py          # Pytest unit and integration test suite
├── run_tests.py             # Standalone executable test runner with colored terminal report
├── requirements.txt         # Python package dependencies
├── LIMITATIONS_AND_LONG_TERM_FIX.md  # Detailed note on limitations and enterprise fix
└── README.md                # Setup, documentation, and endpoint guide
```

---

## Setup & Running Locally

### Prerequisites
- Python 3.10+ (Tested on Python 3.12)
- `pip` package manager

### 1. Clone & Set Up Virtual Environment

```bash
# Clone the repository
git clone <repository-url>
cd razorpay_assessment

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Start the API Server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The service will be live at: `http://localhost:8000`

### 3. Interactive API Documentation

Once the server is running, explore and test the endpoints interactively via Swagger UI:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## Running the Automated Test Suite

### Option A: Standalone Test Runner (Recommended)
Runs without external test dependencies and generates a formatted status summary:

```bash
python run_tests.py
```

Sample output:
```
===========================================================================
   GROWW MARKET DATA API - AUTOMATED TEST SUITE EXECUTION
===========================================================================

1. Health & Diagnostics Endpoints:
  [+] GET /health -> Health check & cache stats        [ 13.65ms] PASS
  [+] Middleware -> Verifying X-Process-Time-Ms header [  4.99ms] PASS

2. Universal Search Endpoints:
  [+] GET /api/v1/search?q=Tata -> Stock search        [585.12ms] PASS
  [+] GET /api/v1/search?q=Parag Parikh -> Mutual Fund search [542.06ms] PASS
  [+] GET /api/v1/search?q= -> Validation error 422    [  3.83ms] PASS

3. Real-Time Market Quotes:
  [+] GET /api/v1/quotes/RELIANCE -> Live equity quote [487.16ms] PASS
  [+] GET /api/v1/quotes/NIFTY -> Live benchmark index quote [557.03ms] PASS
  [+] GET /api/v1/quotes/INVALID -> 404/502 handling   [609.90ms] PASS

4. Company Fundamentals & Profile:
  [+] GET /api/v1/company/tata-motors-ltd -> Profile & P/E [714.28ms] PASS
  [+] GET /api/v1/company/invalid-slug -> 404 handling [623.26ms] PASS

5. Historical Candlestick Chart (OHLCV):
  [+] GET /api/v1/chart/RELIANCE -> 60m OHLCV bars     [642.01ms] PASS
  [+] GET /api/v1/chart/RELIANCE?days=500 -> 422 Range limit [  4.37ms] PASS

6. In-Memory Caching & Latency Check:
  [+] Cache Acceleration -> Second request latency < 50ms [  4.23ms] PASS

===========================================================================
TEST RESULTS SUMMARY:
  Total Cases Executed : 13
  Passed Cases         : 13
  Failed Cases         : 0
  Pass Rate            : 100.0%
===========================================================================
```

### Option B: Pytest Test Suite
```bash
pytest tests/ -v
```

---

## API Endpoint Reference

### 1. Health & Diagnostics
`GET /health`

**Sample Response:**
```json
{
  "status": "ok",
  "service": "Groww Market Data API",
  "version": "1.0.0",
  "timestamp": "2026-10-02T17:15:00.000Z",
  "cache": {
    "size": 4,
    "max_entries": 500,
    "hits": 12,
    "misses": 4,
    "default_ttl_seconds": 30
  }
}
```

---

### 2. Universal Instrument Search
`GET /api/v1/search?q={query}&entity_type={Stocks|Scheme}&page=0&size=10`

**Curl Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/search?q=Tata&size=2"
```

**Sample Response:**
```json
{
  "query": "Tata",
  "entity_type_filter": null,
  "total_results": 2,
  "results": [
    {
      "id": "tata-motors-ltd",
      "title": "Tata Motors Passenger",
      "entity_type": "Stocks",
      "nse_scrip_code": "TMPV",
      "bse_scrip_code": "500570",
      "isin": "INE155A01022",
      "search_id": "tata-motors-ltd"
    },
    {
      "id": "tata-consultancy-services-ltd",
      "title": "Tata Consultancy Services",
      "entity_type": "Stocks",
      "nse_scrip_code": "TCS",
      "bse_scrip_code": "532540",
      "isin": "INE467B01029",
      "search_id": "tata-consultancy-services-ltd"
    }
  ]
}
```

---

### 3. Real-Time Market Quote
`GET /api/v1/quotes/{symbol}?exchange=NSE`

**Curl Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/quotes/RELIANCE"
```

**Sample Response:**
```json
{
  "symbol": "RELIANCE",
  "ltp": 1167.7,
  "day_change": 12.45,
  "day_change_percentage": 1.08,
  "open": 1155.0,
  "high": 1172.0,
  "low": 1152.3,
  "previous_close": 1155.25,
  "volume": 6842103,
  "year_high": 1608.8,
  "year_low": 1115.55,
  "timestamp_ms": 1790961000000,
  "currency": "INR"
}
```

---

### 4. Company Profile & Fundamentals
`GET /api/v1/company/{search_id}`

**Curl Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/company/tata-motors-ltd"
```

**Sample Response:**
```json
{
  "search_id": "tata-motors-ltd",
  "display_name": "Tata Motors Passenger Vehicles",
  "short_name": "Tata Motors Passenger",
  "isin": "INE155A01022",
  "industry_name": "Auto Manufacturers",
  "fundamentals": [
    {
      "name": "Market Cap",
      "short_name": "Mkt Cap",
      "value": "₹1,03,124Cr"
    },
    {
      "name": "ROE",
      "short_name": "ROE",
      "value": "5.47%"
    },
    {
      "name": "P/E Ratio(TTM)",
      "short_name": "P/E Ratio(TTM)",
      "value": "1.30"
    }
  ],
  "year_high_price": 447.79,
  "year_low_price": 272.2
}
```

---

### 5. Historical Candlestick Chart (OHLCV)
`GET /api/v1/chart/{symbol}?interval=60&days=7`

**Curl Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/chart/RELIANCE?interval=60&days=7"
```

**Sample Response:**
```json
{
  "symbol": "RELIANCE",
  "interval_in_minutes": 60,
  "candle_count": 28,
  "start_time_iso": "2026-09-25T03:45:00+00:00",
  "end_time_iso": "2026-10-02T10:00:00+00:00",
  "candles": [
    {
      "timestamp": 1790356500,
      "datetime_iso": "2026-09-25T03:45:00+00:00",
      "open": 1160.0,
      "high": 1168.5,
      "low": 1158.0,
      "close": 1165.2,
      "volume": 412580
    }
  ]
}
```

---

## Assumptions & Boundaries

1. **Public Domain Information Only**: Operates strictly on open, publicly accessible catalog endpoints without accessing private user portfolios, orders, or credentials.
2. **Standard Exchange Tickers**: Stock quotes assume standard NSE/BSE ticker symbols (e.g., `RELIANCE`, `INFY`, `TMPV`, `NIFTY`).
3. **Company Slug Format**: Company profiles utilize Groww's public slug structure (e.g., `tata-motors-ltd`, `reliance-industries-ltd`), which can be discovered dynamically using the search endpoint.
4. **Market Hours & Pricing**: Price data reflects the last traded session when markets are closed (weekends or outside 9:15 AM – 3:30 PM IST).

---

## Limitations & Recommended Long-Term Fix

For the complete architectural critique detailing schema drift, rate limiting, and enterprise migration strategies (SEBI-licensed broker APIs, Redis caching tier, Kafka pub/sub streaming), refer to:

👉 **[LIMITATIONS_AND_LONG_TERM_FIX.md](LIMITATIONS_AND_LONG_TERM_FIX.md)**
