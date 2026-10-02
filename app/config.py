"""
Configuration module for the Groww reverse-engineered API service.
"""

import os

# Application Settings
APP_NAME = "Groww Market Data API"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = (
    "A production-grade, reverse-engineered REST API wrapper over Groww's public market "
    "catalog endpoints. Provides real-time stock quotes, search across equities & mutual funds, "
    "company fundamentals, and historical OHLC candlestick chart data without requiring private credentials."
)

# Upstream Service Configuration
GROWW_BASE_URL = os.getenv("GROWW_BASE_URL", "https://groww.in/v1/api")
USER_AGENT = os.getenv(
    "GROWW_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Network & Resilience Parameters
REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "10.0"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.5"))

# Caching Configuration
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "30"))
CACHE_MAX_ENTRIES = int(os.getenv("CACHE_MAX_ENTRIES", "500"))
