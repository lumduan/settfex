# CLAUDE.md - AI Assistant Context

This file provides context and guidelines for AI assistants (like Claude) working on the settfex project.

## Project Overview

**settfex** is a Python library designed to fetch real-time and historical data from:
- **SET** (Stock Exchange of Thailand)
- **TFEX** (Thailand Futures Exchange)

The library is built for publication on PyPI and follows modern Python development practices.

## Project Structure

```
settfex/
├── settfex/                    # Main package
│   ├── __init__.py
│   ├── services/              # Business logic and API integrations
│   │   ├── __init__.py
│   │   ├── set/              # SET-specific services
│   │   │   ├── __init__.py
│   │   │   ├── client.py     # SET API client
│   │   │   ├── realtime.py   # Real-time data fetching
│   │   │   └── historical.py # Historical data fetching
│   │   └── tfex/             # TFEX-specific services
│   │       ├── __init__.py
│   │       ├── client.py     # TFEX API client
│   │       ├── realtime.py   # Real-time data fetching
│   │       └── historical.py # Historical data fetching
│   └── utils/                # Helper functions and utilities
│       ├── __init__.py
│       ├── logging.py        # Logging utilities
│       ├── validation.py     # Data validation
│       ├── formatting.py     # Data formatting
│       ├── http.py           # HTTP utilities
│       └── data_fetcher.py   # Async data fetcher with Thai/Unicode support
├── tests/                     # Test suite
│   ├── __init__.py
│   ├── conftest.py           # Pytest configuration
│   ├── services/
│   │   ├── set/
│   │   └── tfex/
│   └── utils/
├── docs/                      # Documentation
│   ├── index.md
│   ├── installation.md
│   ├── quickstart.md
│   ├── api-reference.md
│   └── contributing.md
├── examples/                  # Usage examples
│   ├── set_realtime_example.py
│   ├── set_historical_example.py
│   ├── tfex_realtime_example.py
│   └── tfex_historical_example.py
├── scripts/                   # Utility scripts
│   ├── build.py
│   ├── release.py
│   └── test.py
├── pyproject.toml            # Project configuration
├── README.md                 # Project overview
├── LICENSE                   # MIT License
├── .gitignore               # Git ignore rules
└── CLAUDE.md                # This file
```

## Architecture Principles

1. **Modular Design**: Clear separation between SET and TFEX services
2. **Service Layer**: All external API interactions are encapsulated in the `services/` directory
3. **Utilities**: Reusable helpers in `utils/` for cross-cutting concerns
4. **Type Safety**: Full type hints and Pydantic validation
5. **Modern Python**: Targeting Python 3.11+ with modern async patterns
6. **Testing**: Comprehensive test coverage using pytest
7. **Documentation**: Clear, maintained documentation for all public APIs

## Development Guidelines

### Code Style
- Follow PEP 8 with line length of 100 characters
- Use Ruff for linting
- Use mypy for type checking with strict mode
- All functions should have type hints

### Dependencies
- **curl_cffi**: Advanced async HTTP client with browser impersonation capabilities
  - Replaced httpx (2025-10-01) for better bot detection bypass
  - Supports multiple browser impersonation modes (Chrome, Safari, Edge, etc.)
  - Fully async/await compatible with AsyncSession
- **loguru**: Beautiful, powerful logging framework
  - Replaced standard logging (2025-10-01)
  - Auto-configured with colored output, file rotation, and compression
  - Access via `from loguru import logger` or `settfex.utils.logging`
- **pydantic**: Runtime validation and settings management
- Minimize external dependencies to keep the library lightweight

### Testing
- Write tests for all new features
- Maintain high test coverage (aim for >80%)
- Use pytest fixtures in `conftest.py` for shared test setup
- Mock external API calls in tests

### Documentation
- Update relevant documentation when adding features
- Include docstrings for all public functions and classes
- Keep examples up-to-date

## Common Tasks

### Adding a New SET Service
1. Create new module in `settfex/services/set/`
2. Add corresponding tests in `tests/services/set/`
3. Update `settfex/services/set/__init__.py` to export the new service
4. Add example usage in `examples/`
5. Document in `docs/api-reference.md`

### Adding a New TFEX Service
1. Create new module in `settfex/services/tfex/`
2. Add corresponding tests in `tests/services/tfex/`
3. Update `settfex/services/tfex/__init__.py` to export the new service
4. Add example usage in `examples/`
5. Document in `docs/api-reference.md`

### Adding Utility Functions
1. Add to appropriate module in `settfex/utils/` or create new module
2. Add tests in `tests/utils/`
3. Ensure utilities are generic and reusable

## API Design Principles

1. **Consistency**: SET and TFEX services should follow similar patterns
2. **Simplicity**: Provide simple, intuitive APIs
3. **Async-first**: Prefer async/await patterns for I/O operations
4. **Error Handling**: Clear, informative error messages
5. **Validation**: Validate inputs using Pydantic models
6. **Documentation**: All public APIs should be well-documented

## Target Users

- Python developers building trading applications
- Financial analysts needing Thailand market data
- Quantitative researchers and data scientists
- Automated trading system developers

## Important Notes

- This library is not officially affiliated with SET or TFEX
- Always respect API rate limits and terms of service
- Handle sensitive data (API keys, credentials) securely
- Never commit credentials or API keys to version control

## Recent Changes

### 2025-10-01: SET Stock List Service (Updated)

**Reusable SET API Utilities (`settfex/utils/data_fetcher.py`)**
- Added two static methods for all SET services to use:
  - `get_set_api_headers()`: Returns optimized headers for SET API requests
    - Includes all Incapsula bypass headers (Sec-Fetch-*, Cache-Control, Pragma, Priority)
    - Chrome 140 user agent with proper sec-ch-ua headers
    - Configurable referer URL
  - `generate_incapsula_cookies()`: Generates Incapsula-aware randomized cookies
    - Creates realistic visitor IDs, session tokens, and load balancer IDs
    - UUID-format charlot session tokens
    - Base64-encoded Incapsula identifiers
    - Random site IDs and API counters
- Both methods are static and can be used by any future SET service
- Full documentation with examples for service developers

**New Stock List Service (`settfex/services/set/list.py`)**
- Created async service to fetch complete stock list from SET API
- Key features:
  - **Full Type Safety**: Complete Pydantic models for all data structures
  - **Thai/Unicode Support**: Proper handling of Thai company names
  - **Filtering Capabilities**: Filter by market, industry, or lookup by symbol
  - **Async-First**: Built on AsyncDataFetcher for optimal performance
  - **Shared Constants**: Reusable base URL configuration for all SET services
  - **Flexible Cookie Support**: Accepts real browser session cookies or generates them
- Implementation:
  - Three main Pydantic models:
    - `StockSymbol`: Individual stock information (symbol, names, market, industry)
    - `StockListResponse`: Complete API response with helper methods
    - `StockListService`: Main service class
  - Two fetch methods:
    - `fetch_stock_list()`: Returns validated Pydantic models
    - `fetch_stock_list_raw()`: Returns raw dictionary for debugging
  - Convenience function:
    - `get_stock_list()`: Quick one-line access to stock list
  - Helper methods on response:
    - `filter_by_market()`: Get stocks for specific market (SET, mai)
    - `filter_by_industry()`: Get stocks in specific industry
    - `get_symbol()`: Lookup specific stock by symbol
- Configuration:
  - Shared constants in `settfex/services/set/constants.py`:
    - `SET_BASE_URL`: `https://www.set.or.th/`
    - `SET_STOCK_LIST_ENDPOINT`: `/api/set/stock/list`
  - Custom headers matching browser behavior for bot detection bypass
- Usage pattern:
  ```python
  from settfex.services.set import get_stock_list

  # Quick access
  stock_list = await get_stock_list()
  print(f"Total: {stock_list.count}")

  # Filter operations
  set_stocks = stock_list.filter_by_market("SET")
  tech_stocks = stock_list.filter_by_industry("TECH")

  # Lookup specific stock
  ptt = stock_list.get_symbol("PTT")
  print(f"{ptt.symbol}: {ptt.name_en} ({ptt.name_th})")

  # Advanced usage with custom config
  from settfex.services.set import StockListService
  from settfex.utils.data_fetcher import FetcherConfig

  config = FetcherConfig(timeout=60, max_retries=5)
  service = StockListService(config=config)
  response = await service.fetch_stock_list()
  ```
- Documentation:
  - Full service documentation: `docs/settfex/services/set/list.md`
  - Manual verification script: `scripts/settfex/services/set/verify_stock_list.py`
- Purpose:
  - Foundation for stock symbol lookups and validation
  - Enables market and industry analysis
  - Provides complete SET market coverage data
  - Demonstrates service architecture pattern for future SET services

### 2025-10-01: AsyncDataFetcher Module

**New Async Data Fetcher (`settfex/utils/data_fetcher.py`)**
- Created specialized async HTTP client for SET/TFEX data fetching
- Key features:
  - **Unicode/Thai Support**: Proper UTF-8 encoding with latin1 fallback
  - **Browser Impersonation**: Uses curl_cffi to bypass bot detection
  - **Randomized Cookies**: Generates realistic cookie strings for session management
  - **Automatic Retries**: Exponential backoff retry mechanism
  - **Full Type Safety**: Complete type hints and Pydantic validation
  - **Async Compliance**: Synchronous curl_cffi wrapped with `asyncio.to_thread`
- Implementation:
  - Three main components:
    - `FetcherConfig`: Pydantic model for configuration
    - `FetchResponse`: Pydantic model for response data
    - `AsyncDataFetcher`: Main async client class
  - Two key methods:
    - `_make_sync_request()`: Synchronous HTTP request wrapped for async
    - `_generate_random_cookies()`: Creates realistic cookie strings
  - Public async methods:
    - `fetch()`: Fetch any URL with full Unicode support
    - `fetch_json()`: Fetch and parse JSON data
- Usage pattern:
  ```python
  from settfex.utils.data_fetcher import AsyncDataFetcher, FetcherConfig

  # Basic usage
  async with AsyncDataFetcher() as fetcher:
      response = await fetcher.fetch("https://www.set.or.th")
      print(response.text)  # Properly decoded Thai text

  # Custom configuration
  config = FetcherConfig(
      browser_impersonate="safari17_0",
      timeout=60,
      max_retries=5
  )
  async with AsyncDataFetcher(config=config) as fetcher:
      data = await fetcher.fetch_json("https://api.example.com")
  ```
- Testing:
  - Comprehensive test suite: `tests/utils/test_data_fetcher.py`
  - Covers all functionality including Thai/Unicode handling
  - Manual verification script: `scripts/settfex/utils/verify_data_fetcher.py`
- Documentation:
  - Full API documentation: `docs/settfex/utils/data_fetcher.md`
  - Usage examples, error handling, best practices
  - Integration examples with SET/TFEX services
- Purpose:
  - Foundation for all SET/TFEX API data fetching
  - Provides reliable bot detection bypass
  - Ensures proper Thai language character handling
  - Simplifies HTTP operations for service modules

### 2025-10-01: HTTP Client and Logging Migration

**HTTP Client Migration (httpx → curl_cffi)**
- Migrated from httpx to curl_cffi for all HTTP requests
- Benefits:
  - Browser impersonation to bypass bot detection
  - Better compatibility with anti-scraping measures
  - Full async/await support maintained
- Implementation:
  - Created `HTTPClient` class in `settfex/utils/http.py`
  - Async context manager pattern for session management
  - Supports GET, POST, PUT, DELETE methods
  - Configurable browser impersonation (default: Chrome)
  - Base URL, headers, and timeout configuration
- Usage pattern:
  ```python
  async with HTTPClient(base_url="https://api.example.com") as client:
      response = await client.get("/endpoint")
  ```

**Logging Integration (loguru)**
- Integrated loguru as the primary logging framework
- Benefits:
  - Beautiful colored console output
  - Automatic log rotation and compression
  - Better exception formatting with backtraces
  - Simple, intuitive API
- Implementation:
  - Created logging utilities in `settfex/utils/logging.py`
  - `setup_logger()` function for configuration
  - `get_logger()` function to access logger instance
  - Default INFO level with stderr output
- Usage pattern:
  ```python
  from loguru import logger
  from settfex.utils.logging import setup_logger

  # Optional: customize logging
  setup_logger(level="DEBUG", log_file="logs/app.log")

  # Use logger anywhere
  logger.info("Starting data fetch")
  logger.error("Failed to connect", exc_info=True)
  ```

**Configuration Updates**
- Updated `pyproject.toml`:
  - Removed: `httpx>=0.27.0`
  - Added: `curl-cffi>=0.6.0`
  - Added: `loguru>=0.7.0`
- Updated `.gitignore`:
  - Added `CLAUDE.md` to gitignore
  - Added `.claude/` directory
  - Added `.github/` directory
  - Added `scripts/` directory

**Documentation Updates**
- Updated `README.md` with new dependencies and features
- Added logging configuration examples
- Documented browser impersonation capabilities
- This file (`CLAUDE.md`) updated with migration details

## Future Enhancements (Ideas)

- WebSocket support for real-time streaming
- Data caching mechanisms
- Rate limiting and retry logic
- CLI tool for quick data queries
- Integration with popular data analysis libraries (pandas, polars)
- Historical data export to various formats (CSV, Parquet, etc.)

## When Working on This Project

1. **Read First**: Always check existing code patterns before implementing new features
2. **Test**: Write tests before or alongside your code
3. **Document**: Update documentation when adding features
4. **Consistency**: Follow existing patterns and naming conventions
5. **Type Safety**: Always use type hints
6. **Ask Questions**: If unclear about architecture decisions, ask for clarification

## Contact & Resources

- GitHub Repository: [yourusername/settfex]
- Documentation: See `docs/` directory
- Issues: GitHub Issues
- License: MIT

---

*This file should be kept up-to-date as the project evolves.*
