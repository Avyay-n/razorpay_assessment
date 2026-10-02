"""
Comprehensive test suite for the Groww Reverse-Engineered Market Data API.
Run via: pytest tests/ -v
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.utils.cache import cache

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_cache_before_each():
    """Ensure tests run with clean cache state."""
    cache.clear()


class TestHealthEndpoint:
    """Tests for service health and diagnostics."""

    def test_health_check_returns_ok(self):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "cache" in data
        assert "timestamp" in data


class TestSearchEndpoint:
    """Tests for universal search across stocks and mutual funds."""

    def test_search_valid_keyword(self):
        response = client.get("/api/v1/search?q=Tata&size=5")
        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "Tata"
        assert data["total_results"] > 0
        assert len(data["results"]) <= 5

        first_item = data["results"][0]
        assert "id" in first_item
        assert "title" in first_item
        assert "entity_type" in first_item
        assert "search_id" in first_item

    def test_search_filter_stocks(self):
        response = client.get("/api/v1/search?q=HDFC&entity_type=Stocks&size=5")
        assert response.status_code == 200
        data = response.json()
        assert data["total_results"] > 0
        for item in data["results"]:
            assert item["entity_type"] == "Stocks"

    def test_search_empty_query_fails_validation(self):
        response = client.get("/api/v1/search?q=")
        assert response.status_code == 422  # FastAPI validation error


class TestLiveQuoteEndpoint:
    """Tests for live quote endpoints."""

    def test_get_live_quote_equity(self):
        response = client.get("/api/v1/quotes/RELIANCE")
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "RELIANCE"
        assert isinstance(data["ltp"], (int, float))
        assert data["ltp"] > 0
        assert isinstance(data["day_change"], (int, float))
        assert isinstance(data["day_change_percentage"], (int, float))
        assert data["currency"] == "INR"

    def test_get_live_quote_index(self):
        response = client.get("/api/v1/quotes/NIFTY")
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "NIFTY"
        assert data["ltp"] > 0

    def test_get_live_quote_not_found(self):
        response = client.get("/api/v1/quotes/INVALID_TICKER_XYZ_999")
        assert response.status_code in (404, 502)
        data = response.json()
        assert "error" in data


class TestCompanyProfileEndpoint:
    """Tests for company fundamentals and profile retrieval."""

    def test_get_company_profile_success(self):
        response = client.get("/api/v1/company/tata-motors-ltd")
        assert response.status_code == 200
        data = response.json()
        assert data["search_id"] == "tata-motors-ltd"
        assert "display_name" in data
        assert len(data["fundamentals"]) > 0

        # Verify key fundamental metric structure
        first_metric = data["fundamentals"][0]
        assert "name" in first_metric
        assert "value" in first_metric

    def test_get_company_profile_not_found(self):
        response = client.get("/api/v1/company/non-existent-company-slug-xyz")
        assert response.status_code == 404
        data = response.json()
        assert data["status_code"] == 404
        assert "Resource Not Found" in data["error"]


class TestChartEndpoint:
    """Tests for historical candlestick OHLC chart data."""

    def test_get_chart_candlesticks_success(self):
        response = client.get("/api/v1/chart/RELIANCE?interval=60&days=5")
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "RELIANCE"
        assert data["interval_in_minutes"] == 60
        assert data["candle_count"] > 0
        assert len(data["candles"]) > 0

        candle = data["candles"][0]
        assert "timestamp" in candle
        assert "datetime_iso" in candle
        assert "open" in candle
        assert "high" in candle
        assert "low" in candle
        assert "close" in candle
        assert "volume" in candle

    def test_get_chart_invalid_days_range(self):
        response = client.get("/api/v1/chart/RELIANCE?days=1000")
        assert response.status_code == 422  # Exceeds max 90 days


class TestCacheAndMiddleware:
    """Tests for internal caching and custom headers."""

    def test_process_time_header_exists(self):
        response = client.get("/health")
        assert "x-process-time-ms" in response.headers

    def test_cache_clear_endpoint(self):
        # Populate cache
        client.get("/api/v1/quotes/RELIANCE")
        assert cache.stats()["size"] > 0

        # Clear cache
        response = client.post("/api/v1/cache/clear")
        assert response.status_code == 200
        assert cache.stats()["size"] == 0
