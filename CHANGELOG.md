# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
