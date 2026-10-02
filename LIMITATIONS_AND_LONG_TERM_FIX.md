# Solution Limitations & Long-Term Architectural Recommendations

## 1. Executive Summary

This project reverse-engineers publicly accessible catalog and market endpoints from **Groww** (India's leading retail investment and wealth platform) to create a clean, standardized, typed REST API wrapper using FastAPI, Pydantic, and an asynchronous HTTP resilience layer.

While the solution successfully fulfills the requirements using strictly **publicly accessible information** (without bypassing access controls, authentication walls, or handling private user data), reverse-engineering internal web frontend APIs inherently possesses production trade-offs. 

This document details the critical limitations of this reverse-engineered approach and proposes a robust, enterprise-grade long-term architecture suitable for high-scale fintech systems like Razorpay.

---

## 2. Solution Limitations

### 2.1 Schema Drift and Undocumented Contract Changes
* **Risk**: Internal web APIs are designed exclusively for consumption by the provider's own single-page application (SPA) or mobile app. They are **not** versioned public contracts.
* **Impact**: Field names, response nesting, or underlying data structures may change overnight without deprecation notices or versioning (e.g., changing from `ltp` to `last_price`, or altering timestamp epoch formats from milliseconds to seconds).
* **Current Mitigation**: Pydantic models with optional/fallback parsing and robust normalization layers catch validation mismatches early, but an unannounced breaking change will cause endpoint failures.

### 2.2 Lack of Service Level Agreements (SLAs) & Reliability Guarantees
* **Risk**: Public-facing internal endpoints offer zero uptime guarantees or support channels to external callers.
* **Impact**: Unannounced maintenance windows, 502/503 errors during market open/close spikes (9:15 AM and 3:30 PM IST), or DNS-level changes can abruptly degrade availability.

### 2.3 IP Throttling, WAF, and Bot-Mitigation Challenges
* **Risk**: The current implementation utilizes realistic browser User-Agent headers, connection pooling, and in-memory TTL caching. However, upstream infrastructure frequently deploys Web Application Firewalls (Cloudflare, Akamai, AWS WAF, or Datadome).
* **Impact**: High concurrent request volume originating from a small pool of static IP addresses (e.g., AWS EC2 or GCP egress IPs) will trigger rate-limit throttling (HTTP 429) or bot challenge pages (JavaScript challenges or CAPTCHAs).

### 2.4 Polling Latency vs. Real-Time Tick Streaming (WebSockets)
* **Risk**: Market data in high-frequency trading or active portfolio tracking changes on a sub-second basis.
* **Impact**: The reverse-engineered REST endpoints require client polling (`GET /quotes/{symbol}`). Polling introduces artificial latency (100ms–1000ms), adds unnecessary bandwidth overhead, and risks triggering upstream rate limits when scaling to thousands of concurrent users.

### 2.5 Regulatory and Compliance Constraints (SEBI Guidelines)
* **Risk**: In India, the Securities and Exchange Board of India (SEBI) and stock exchanges (NSE/BSE) maintain strict regulatory frameworks concerning the redistribution and dissemination of real-time market data.
* **Impact**: Operating a commercial service on scraped or reverse-engineered market data without formal exchange licensing or broker agreements poses legal and regulatory liabilities.

---

## 3. Recommended Long-Term Architecture

To transition this proof-of-concept into a production-grade, highly available, and compliant market data infrastructure, the following architectural upgrades are recommended:

```
                                  +------------------------------------+
                                  |    Direct SEBI Broker / Feeds      |
                                  | (Kite Connect / Angel / NSE DotEx) |
                                  +-----------------+------------------+
                                                    |
                                                    v
                                  +-----------------+------------------+
                                  |   High-Speed Tick Ingestion Engine |
                                  |  (Go / Rust / Python Asyncio WS)   |
                                  +-----------------+------------------+
                                                    |
                         +--------------------------+--------------------------+
                         |                                                     |
                         v                                                     v
          +--------------+-------------+                         +-------------+--------------+
          |   Redis In-Memory Cluster  |                         |   Kafka / Redis Streams    |
          |  (LTP Quotes, 5-15s TTL)   |                         |  (Real-Time Quote Pub/Sub) |
          +--------------+-------------+                         +-------------+--------------+
                         |                                                     |
                         v                                                     v
          +--------------+-------------+                         +-------------+--------------+
          | FastAPI Application Server |                         |  WebSocket Fan-Out Gateway |
          |   (REST Queries & Search)  |                         |  (Sub-Second Client Push)  |
          +--------------+-------------+                         +-------------+--------------+
                         ^                                                     ^
                         |                                                     |
                         +--------------------------+--------------------------+
                                                    |
                                    +---------------+---------------+
                                    |       API Gateway (Kong)      |
                                    | (Rate Limiting, Auth, Routing)|
                                    +---------------+---------------+
                                                    |
                                            Downstream Clients
```

### 3.1 Migration to Official, SEBI-Compliant Market Data Providers
* **Solution**: Replace unofficial web scraping endpoints with official, licensed developer APIs:
  - **Authorized Broker APIs**: Zerodha Kite Connect, Angel One SmartAPI, or Upstox Developer Platform (providing official REST & WebSocket tick feeds).
  - **Direct Exchange Market Data**: Direct subscriptions to NSE/BSE DotEx feeds for enterprise-tier level-1 (L1) and level-2 (L2) market depth.
* **Benefit**: Guaranteed 99.9% uptime SLAs, structured schema versioning, legal compliance, and sub-100ms tick latency.

### 3.2 Multi-Tier Distributed Caching (Redis Cluster)
* **Tier 1 — Live Quotes**: Store current LTP and bid/ask in Redis key-value pairs with short TTLs (5–15 seconds during market hours, 24 hours off-market). Repeat queries for hot tickers (e.g., `RELIANCE`, `INFY`) will never touch upstream providers.
* **Tier 2 — Company Fundamentals**: Cache company profile, balance sheet, and financial ratios in Redis or Postgres with a 24-hour TTL, as corporate fundamentals only update quarterly.
* **Tier 3 — Time-Series Candlestick Storage**: Persist OHLC historical bars into a time-series database (e.g., **TimescaleDB** or **ClickHouse**), incrementally updating only the latest incomplete candle.

### 3.3 Event-Driven WebSocket Streaming & Fan-Out Gateway
* **Solution**: Maintain a single persistent upstream WebSocket connection to the exchange feed. Broadcast incoming price ticks into an event bus (e.g., **Kafka** or **Redis Streams**).
* **Benefit**: A WebSocket fan-out gateway can serve 100,000+ connected end-user clients simultaneously with zero added load on the upstream provider.

### 3.4 Resiliency & Circuit Breaker Pattern
* **Circuit Breaker**: Implement circuit breakers (e.g., via `pybreaker` or Envoy Gateway) configured with:
  - Failure threshold: 5 consecutive 5xx errors or timeouts within a 30-second sliding window.
  - Recovery state: Half-open after 60 seconds, routing 10% of traffic to verify upstream health.
  - Fallback mechanism: Return the last known cached quote with a `"stale": true` flag and header rather than failing downstream requests.

### 3.5 Automated Schema Drift Detection & Contract Testing
* **Synthetic Probes**: Deploy background canary jobs running every 15 minutes that execute end-to-end contract assertions (using Pydantic validation and Great Expectations).
* **Alerting**: Trigger PagerDuty/Slack alerts immediately upon any unexpected schema deviations before user-facing requests encounter degradation.
