# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-06-17

### Added

- **TFEX underlying-price service** (`get_underlying_price`, `TFEXUnderlyingPriceService`,
  `UnderlyingPrice`): fetches the underlying instrument price for a TFEX series via
  `GET /api/set/tfex/series/{symbol}/underlying-price`. For SET50 index options/futures the underlying
  is the **SET50 index spot** — exposes last/prior/high/low, change, total volume/value, and P/E + P/BV.
  Mirrors the existing TFEX service pattern (SessionManager/Incapsula bypass, NaN-rejecting hardened
  parsing, `get_*` convenience function + `*_raw` variant); 100% module test coverage. Adds the
  `verify_underlying_price.py` script and the `examples/tfex/03_underlying_price.ipynb` notebook.

## [0.2.1] - 2026-06-17

Robustness and concurrency hardening release. No public API changes — function
signatures, return types, Pydantic model fields, and `en`/`th` + symbol normalization
are all preserved. See `COMPREHENSIVE_AUDIT.md` for full details and benchmarks.

### Fixed

- **Silent financial-data corruption:** `NaN`/`Infinity` values from the SET/TFEX APIs were
  silently accepted into numeric model fields (prices, P/E, margins). They are now rejected at
  decode time with a clear error that includes the originating symbol and endpoint.
- Parse and validation failures now raise with **symbol + endpoint context** (and per-item
  index for lists) instead of a bare, context-free `ValidationError`/`JSONDecodeError`.
- Replaced unsafe `assert isinstance(data, dict)` in the TFEX trading-statistics and
  series-list raw paths — `assert` is stripped under `python -O` — with explicit, contextful
  errors.
- **Session warm-up stampede:** concurrent cold-start callers each fired their own warm-up
  round-trip (which can trip bot detection); warm-up is now serialized to run at most once.
- Offloaded blocking cache initialization (directory creation + opening the on-disk cache) off
  the asyncio event loop.

### Changed

- Centralized JSON decode + Pydantic validation across all SET/TFEX services into a shared
  internal helper (`settfex/utils/parsing.py`), removing ~111 lines of duplicated boilerplate.
- Hoisted static request headers in `AsyncDataFetcher.fetch()` to a module-level constant.
- Added regression tests for malformed/NaN/partial responses and TFEX coverage
  (test suite 116 → 149; coverage 49% → 61%).

## [0.2.0] - 2026-06-09

### Added

#### New SET Services

- **Chart Quotation Service** — Fetch intraday and historical price chart data with 9 period options (1D, 5D, 1M, 3M, 6M, 1Y, 3Y, 5Y, MAX). Returns OHLCV data points with timestamps, accumulated volume support, and trading intermission handling.
  - `get_chart_quotation(symbol, period="1D", accumulated=False)` convenience function
  - `ChartQuotationService` class for advanced usage
  - Endpoint: `/api/set/stock/{symbol}/chart-quotation`

- **Latest Historical Trading Service** — Fetch latest trading day summary with OHLCV, P/E ratio, P/BV ratio, dividend yield, market cap, and par value.
  - `get_latest_historical_trading(symbol)` convenience function
  - `LatestHistoricalTradingService` class for advanced usage
  - Endpoint: `/api/set/stock/{symbol}/latest-historical-trading`

#### Stock Class Integration
- Added `get_chart_quotation()` method to `Stock` class
- Added `get_latest_historical_trading()` method to `Stock` class

### Changed

#### CI/CD Infrastructure
- Added GitHub Actions CI workflow (`ci.yml`) — Ruff lint, format check, mypy, pytest with coverage
- Added GitHub Actions Release workflow (`release.yml`) — automated PyPI publishing via Trusted Publisher + GitHub Release creation with changelog extraction

## [0.1.0] - 2025-10-06

### 🎉 First Public Release

This is the initial public release of **settfex**, a Python library for fetching real-time and historical data from the Stock Exchange of Thailand (SET) and Thailand Futures Exchange (TFEX).

#### ✨ Features

##### SET (Stock Exchange of Thailand) Services

- **Stock List Service** - Fetch complete list of all stocks on SET/mai with filtering capabilities
- **Stock Highlight Data Service** - Get key metrics including market cap, P/E, P/B, dividend yield
- **Stock Profile Service** - Access listing details, IPO data, foreign ownership limits
- **Company Profile Service** - Comprehensive company info with ESG ratings, governance scores
- **Corporate Action Service** - Track dividends, shareholder meetings, and corporate events
- **Shareholder Service** - Monitor major shareholders and ownership distribution
- **NVDR Holder Service** - Track Non-Voting Depository Receipt holders
- **Board of Directors Service** - Access board composition and management structure
- **Trading Statistics Service** - Historical trading performance across multiple periods
- **Price Performance Service** - Compare stock performance vs sector and market
- **Financial Service** - Balance sheet, income statement, and cash flow data

##### TFEX (Thailand Futures Exchange) Services

- **TFEX Series List Service** - Complete list of futures and options series with filtering
- **TFEX Trading Statistics Service** - Settlement prices, margin requirements, days to maturity

##### Core Infrastructure

- **AsyncDataFetcher** - High-performance async HTTP client with browser impersonation
- **Session Caching** - Intelligent session management for 25x performance boost
- **Thai/Unicode Support** - Full UTF-8 support for Thai characters
- **Type Safety** - Complete type hints and Pydantic validation throughout
- **Smart Logging** - Beautiful logs with loguru, configurable levels

#### 📚 Documentation

- Comprehensive service documentation for all 13 services
- 13 interactive Jupyter notebook examples (11 SET + 2 TFEX)
- Complete API reference with usage examples
- Session caching and performance optimization guides

#### 🚀 Performance

- First request: ~2 seconds (session warmup)
- Subsequent requests: ~100ms (25x faster with session caching)
- Dual-site support: Separate optimized sessions for SET and TFEX APIs

#### 🔧 Technical Highlights

- **Python 3.11+** - Modern async/await patterns
- **curl_cffi** - Browser impersonation for reliable API access
- **Pydantic v2** - Runtime validation and settings management
- **loguru** - Beautiful, powerful logging with rotation and compression
- **diskcache** - Fast, persistent session caching

#### 📦 Package Information

- **License**: MIT
- **Python Support**: 3.11, 3.12, 3.13
- **Async-First**: Full async/await support throughout
- **Type Hints**: 100% type coverage for IDE support

---

For upgrade instructions and migration guides for future releases, see the documentation.
