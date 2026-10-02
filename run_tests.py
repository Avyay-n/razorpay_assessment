"""
Standalone Test Runner for Groww Reverse-Engineered Market Data API.

Can be run directly via:
    python run_tests.py

Runs comprehensive functional, validation, and performance tests against the API.
"""

import sys
import time
from typing import Callable, Any, List, Tuple
from fastapi.testclient import TestClient

from app.main import app
from app.utils.cache import cache

# Ensure UTF-8 output on Windows consoles if supported
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Terminal color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


class StandaloneTestRunner:
    """Executes test cases and displays a formatted summary report."""

    def __init__(self):
        self.client = TestClient(app)
        self.results: List[Tuple[str, str, float, str]] = []  # (name, status, duration_ms, details)

    def record(self, test_name: str, passed: bool, duration_ms: float, details: str = ""):
        status_str = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
        self.results.append((test_name, status_str, duration_ms, details))
        status_icon = "[+]" if passed else "[-]"
        color = GREEN if passed else RED
        print(f"  {color}{status_icon}{RESET} {test_name:<48} [{duration_ms:>6.2f}ms] {color}{status_str}{RESET}")
        if not passed and details:
            print(f"      {RED}Error: {details}{RESET}")

    def run_test(self, name: str, test_func: Callable[[], Any]):
        t0 = time.perf_counter()
        try:
            test_func()
            t1 = time.perf_counter()
            self.record(name, True, (t1 - t0) * 1000)
        except Exception as exc:
            t1 = time.perf_counter()
            self.record(name, False, (t1 - t0) * 1000, str(exc))

    def execute_all(self) -> bool:
        print(f"\n{BOLD}{CYAN}{'=' * 75}{RESET}")
        print(f"{BOLD}{CYAN}   GROWW MARKET DATA API - AUTOMATED TEST SUITE EXECUTION{RESET}")
        print(f"{BOLD}{CYAN}{'=' * 75}{RESET}\n")

        cache.clear()

        # 1. Health & System
        print(f"{BOLD}1. Health & Diagnostics Endpoints:{RESET}")
        def test_health():
            res = self.client.get("/health")
            assert res.status_code == 200, f"Expected 200, got {res.status_code}"
            data = res.json()
            assert data["status"] == "ok"
            assert "cache" in data
        self.run_test("GET /health -> Health check & cache stats", test_health)

        def test_timing_header():
            res = self.client.get("/health")
            assert "x-process-time-ms" in res.headers
        self.run_test("Middleware -> Verifying X-Process-Time-Ms header", test_timing_header)

        # 2. Universal Search
        print(f"\n{BOLD}2. Universal Search Endpoints:{RESET}")
        def test_search_stocks():
            res = self.client.get("/api/v1/search?q=Tata&size=5")
            assert res.status_code == 200, f"Status: {res.status_code}"
            d = res.json()
            assert d["total_results"] > 0
            assert len(d["results"]) <= 5
            assert any("Tata" in item["title"] or "TATA" in item["title"].upper() for item in d["results"])
        self.run_test("GET /api/v1/search?q=Tata -> Stock search", test_search_stocks)

        def test_search_mf():
            res = self.client.get("/api/v1/search?q=Parag%20Parikh&size=3")
            assert res.status_code == 200
            d = res.json()
            assert d["total_results"] > 0
            assert any(item["entity_type"] == "Scheme" for item in d["results"])
        self.run_test("GET /api/v1/search?q=Parag Parikh -> Mutual Fund search", test_mf := test_search_mf)

        def test_search_empty_validation():
            res = self.client.get("/api/v1/search?q=")
            assert res.status_code == 422
        self.run_test("GET /api/v1/search?q= -> Validation error 422", test_search_empty_validation)

        # 3. Live Quotes
        print(f"\n{BOLD}3. Real-Time Market Quotes:{RESET}")
        def test_quote_equity():
            res = self.client.get("/api/v1/quotes/RELIANCE")
            assert res.status_code == 200
            d = res.json()
            assert d["symbol"] == "RELIANCE"
            assert d["ltp"] > 0
            assert d["currency"] == "INR"
        self.run_test("GET /api/v1/quotes/RELIANCE -> Live equity quote", test_quote_equity)

        def test_quote_index():
            res = self.client.get("/api/v1/quotes/NIFTY")
            assert res.status_code == 200
            d = res.json()
            assert d["symbol"] == "NIFTY"
            assert d["ltp"] > 0
        self.run_test("GET /api/v1/quotes/NIFTY -> Live benchmark index quote", test_quote_index)

        def test_quote_not_found():
            res = self.client.get("/api/v1/quotes/INVALIDTICKERXYZ99")
            assert res.status_code in (404, 502)
        self.run_test("GET /api/v1/quotes/INVALID -> 404/502 handling", test_quote_not_found)

        # 4. Company Profile & Fundamentals
        print(f"\n{BOLD}4. Company Fundamentals & Profile:{RESET}")
        def test_company_profile():
            res = self.client.get("/api/v1/company/tata-motors-ltd")
            assert res.status_code == 200
            d = res.json()
            assert d["search_id"] == "tata-motors-ltd"
            assert len(d["fundamentals"]) >= 3
            names = [f["name"] for f in d["fundamentals"]]
            assert "Market Cap" in names
        self.run_test("GET /api/v1/company/tata-motors-ltd -> Profile & P/E", test_company_profile)

        def test_company_not_found():
            res = self.client.get("/api/v1/company/non-existent-company-slug-xyz")
            assert res.status_code == 404
        self.run_test("GET /api/v1/company/invalid-slug -> 404 handling", test_company_not_found)

        # 5. Candlestick Charts (OHLCV)
        print(f"\n{BOLD}5. Historical Candlestick Chart (OHLCV):{RESET}")
        def test_chart_candlesticks():
            res = self.client.get("/api/v1/chart/RELIANCE?interval=60&days=7")
            assert res.status_code == 200
            d = res.json()
            assert d["symbol"] == "RELIANCE"
            assert d["candle_count"] > 0
            c = d["candles"][0]
            assert all(k in c for k in ("open", "high", "low", "close", "volume", "datetime_iso"))
        self.run_test("GET /api/v1/chart/RELIANCE -> 60m OHLCV bars", test_chart_candlesticks)

        def test_chart_invalid_days():
            res = self.client.get("/api/v1/chart/RELIANCE?days=500")
            assert res.status_code == 422
        self.run_test("GET /api/v1/chart/RELIANCE?days=500 -> 422 Range limit", test_chart_invalid_days)

        # 6. Caching Layer Performance
        print(f"\n{BOLD}6. In-Memory Caching & Latency Check:{RESET}")
        # Initial call to populate cache
        self.client.get("/api/v1/quotes/INFY")
        def test_cache_speedup():
            # Second call should hit in-memory cache in sub-millisecond time
            t0 = time.perf_counter()
            res = self.client.get("/api/v1/quotes/INFY")
            t1 = time.perf_counter()
            elapsed_ms = (t1 - t0) * 1000
            assert res.status_code == 200
            assert elapsed_ms < 50, f"Expected cache hit < 50ms, got {elapsed_ms:.2f}ms"
        self.run_test("Cache Acceleration -> Second request latency < 50ms", test_cache_speedup)

        # Print summary
        total_tests = len(self.results)
        passed_tests = sum(1 for _, status, _, _ in self.results if "PASS" in status)
        failed_tests = total_tests - passed_tests

        print(f"\n{BOLD}{CYAN}{'=' * 75}{RESET}")
        print(f"{BOLD}TEST RESULTS SUMMARY:{RESET}")
        print(f"  Total Cases Executed : {total_tests}")
        print(f"  Passed Cases         : {GREEN}{passed_tests}{RESET}")
        print(f"  Failed Cases         : {RED if failed_tests > 0 else GREEN}{failed_tests}{RESET}")
        print(f"  Pass Rate            : {GREEN if failed_tests == 0 else RED}{passed_tests / total_tests * 100:.1f}%{RESET}")
        print(f"{BOLD}{CYAN}{'=' * 75}{RESET}\n")

        return failed_tests == 0


if __name__ == "__main__":
    runner = StandaloneTestRunner()
    success = runner.execute_all()
    sys.exit(0 if success else 1)
