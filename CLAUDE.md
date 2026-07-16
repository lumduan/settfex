# CLAUDE.md - AI Assistant Context

Essential context and guidelines for AI assistants working on the settfex project.

## Project Overview

**settfex** is a Python library that fetches real-time and historical data from:
- **SET** (Stock Exchange of Thailand)
- **TFEX** (Thailand Futures Exchange)

Published on PyPI, targeting Python 3.11+ with modern async patterns.

## Project Structure

```
settfex/
├── settfex/                    # Main package
│   ├── services/              # Business logic and API integrations
│   │   ├── set/              # SET-specific services
│   │   │   ├── constants.py, list.py
│   │   │   ├── index/        # Market index services: list, info (quotation),
│   │   │   │                 #   composition (constituents), chart_quotation,
│   │   │   │                 #   index.py (SetIndex facade), utils.py
│   │   │   └── stock/        # Stock services: highlight_data, profile_stock,
│   │   │                     #   profile_company, corporate_action, shareholder,
│   │   │                     #   nvdr_holder, board_of_director, trading_stat,
│   │   │                     #   price_performance, financial/, stock.py, utils.py
│   │   └── tfex/             # TFEX services: list.py, trading_statistics.py
│   └── utils/                # http.py, data_fetcher.py, session_manager.py,
│                             #   session_cache.py, logging.py
├── tests/                     # Mirror of settfex/ with test_ prefix
├── docs/                      # Service docs, guides, solutions
├── examples/                  # 15 Jupyter notebooks (13 SET + 2 TFEX)
├── scripts/                   # Verification scripts per service
├── .github/                   # CI and agent instructions
├── pyproject.toml             # uv-based config
└── README.md
```

## Architecture Principles

1. **Modular Design**: Clear separation between SET and TFEX services
2. **Service Layer**: All external API interactions encapsulated in `services/`
3. **Utilities**: Reusable helpers in `utils/` for cross-cutting concerns
4. **Type Safety**: Full type hints and Pydantic validation throughout
5. **Modern Python**: Python 3.11+ with async/await patterns
6. **Testing**: Comprehensive pytest coverage (>80% target)
7. **Documentation**: Maintained docs for all public APIs

## Development Guidelines

### Code Style
- PEP 8 with 100-char line length; Ruff linting; mypy strict mode
- All functions must have type hints

### Dependencies
- **curl_cffi**: Async HTTP with browser impersonation (replaced httpx 2025-10-01)
- **loguru**: Structured logging with colored output, rotation, compression (replaced stdlib logging 2025-10-01)
- **pydantic**: Runtime validation and settings management
- Minimize external dependencies

### Testing
- Write tests for all new features; mock external API calls
- Use pytest fixtures in `conftest.py` for shared setup
- Maintain >80% coverage

### Documentation
- Update docs when adding features; include docstrings for all public APIs
- Keep Jupyter notebook examples up-to-date

## Common Tasks

### Adding a New Service (SET or TFEX)
1. Create module in `settfex/services/{set,tfex}/`
2. Add tests in `tests/services/{set,tfex}/`
3. Update the appropriate `__init__.py` to export the service
4. Document with docstrings + create verification script in `scripts/settfex/services/`
5. Add Jupyter notebook example in `examples/`

### Adding Utility Functions
1. Add to appropriate module in `settfex/utils/` or create new one
2. Add tests in `tests/utils/`; ensure utilities are generic and reusable

## Service Design Patterns (Must Follow)

Every service follows this consistent pattern:
- **Pydantic models** for all data with full type annotations
- **Two fetch methods**: `fetch_*()` returns Pydantic models; `fetch_*_raw()` returns raw dicts
- **Convenience function**: `get_*()` top-level function for one-line access
- **Dual language**: `en`/`th` support via `normalize_language()` (accepts: en/eng/english, th/tha/thai)
- **Symbol normalization**: Auto-uppercase via `normalize_symbol()`
- **SessionManager**: All cookie/bot-detection handled automatically (no manual cookie params)
- **Async-first**: All I/O uses async/await via `AsyncDataFetcher`
- **Bot bypass**: Symbol-specific referer header + SessionManager cookies (Incapsula bypass)

Typical usage:
```python
from settfex.services.set import Stock, get_highlight_data, get_stock_list

stock = Stock("CPALL")
data = await stock.get_highlight_data()    # via unified Stock class
data = await get_highlight_data("CPALL")   # or convenience function
all_stocks = await get_stock_list()        # no cookie params needed
```

## Services Inventory (17 total)

### SET Services (15)

| # | Service | Module | Endpoint Pattern | Key Data |
|---|---|---|---|---|
| 1 | Stock List | `list.py` | `/api/set/stock/list` | All SET/MAI stocks, filter by market/industry/symbol; **index-membership enrichment** per stock (default on, `include_indices=False` to skip; `filter_by_index()`) |
| 2 | Highlight Data | `stock/highlight_data.py` | `/api/set/stock/{sym}/highlight-data` | P/E, P/B, market cap, beta, dividends, 52-wk range, NVDR |
| 3 | Stock Profile | `stock/profile_stock.py` | `/api/set/stock/{sym}/profile` | Listing details, IPO, sector, foreign limits, ISIN, warrants |
| 4 | Company Profile | `stock/profile_company.py` | `/api/set/company/{sym}/profile` | ESG rating, CG score, auditors, management, capital structure |
| 5 | Corporate Actions | `stock/corporate_action.py` | `/api/set/stock/{sym}/corporate-action` | Dividends (XD), meetings (XM/AGM/EGM), payment dates |
| 6 | Shareholders | `stock/shareholder.py` | `/api/set/stock/{sym}/shareholder` | Major holders, free float %, ownership distribution |
| 7 | NVDR Holders | `stock/nvdr_holder.py` | `/api/set/stock/{sym}/nvdr-holder` | NVDR ownership, Thai vs foreign holders |
| 8 | Board of Directors | `stock/board_of_director.py` | `/api/set/company/{sym}/board-of-director` | Directors, positions (Chairman, CEO, Independent) |
| 9 | Trading Statistics | `stock/trading_stat.py` | `/api/set/factsheet/{sym}/trading-stat` | 30+ fields: price/volume/valuation/beta, 5 periods (YTD-1Y) |
| 10 | Price Performance | `stock/price_performance.py` | `/api/set/factsheet/{sym}/price-performance` | Stock vs sector vs market (5D/1M/3M/6M/YTD), P/E, P/B |
| 11 | Financial Statements | `stock/financial/financial.py` | `/api/set/factsheet/{sym}/financialstatement` | Balance sheet, income, cash flow (multi-period, en/th) |
| 12 | Earnings Call (Opportunity Day) | `earnings_call.py` | `POST api.lcp.setgroup.or.th/.../investor/search/archive` (+ `GET /investor/vdo/{id}`, `/investor/filter/*`) | OPPDAY calendar (symbol, company, date, clip duration, YouTube URL); concurrent `fetch_all`/`get_all_earnings_calls` (+ optional `tqdm` progress); detail-by-id (`get_earnings_call_detail`); 7 filter helpers; pandas `to_dataframe()`; **Thai YouTube transcripts** for AI (`fetch_transcripts` / `get_earnings_call_transcript` / `fetch_youtube_transcript`, `EarningsCallItem.transcript`); stateless host (no SessionManager); optional extras: `dataframe` (pandas) / `progress` (tqdm) / `transcript` (youtube-transcript-api) |
| 13 | Chart Quotation / Latest Price | `stock/chart_quotation.py` | `/api/set/stock/{sym}/chart-quotation` | Intraday/historical per-minute series (price/volume/value/%chg, intermissions, prior close); **latest *traded* price relative to now** — `get_latest_price()` (→ `Quotation`), model `get_latest_quotation()`/`get_latest_price()` (→ float, `prior` fallback); skips null future/lunch/no-trade buckets; Asia/Bangkok tz-safe `as_of`; hyphen-safe symbols (`JAS-W4`) |
| 14 | Latest Historical Trading | `stock/latest_historical_trading.py` | `/api/set/stock/{sym}/latest-historical-trading` | Latest trading-day summary: OHLCV, change/%change, and valuation metrics |
| 15 | Market Index | `index/{list,info,composition,chart_quotation,index}.py` | `/api/set/index/list`, `/api/set/index/info/list`, `/api/set/index/{sym}/info`, `/api/set/index/{sym}/composition`, `/api/set/index/{sym}/chart-quotation` | 55-index directory (INDEX/INDUSTRY/SECTOR levels; mai industries use `-m` query symbols); page-header quotes (last/chg/%chg/OHLC/vol/value/marketStatus/tz-aware timestamp); constituents w/ full quote rows incl. bid/offer (string prices coerced); `SetIndex` facade + `get_index_latest_price()` (reuses stock ChartQuotation); index symbols keep casing (`sSET`, `AGRO-m`); `SET`/`mai` have no composition (404 w/ helpful error). **Note:** index API uses `?language=`, not `?lang=` |

### TFEX Services (2)

| # | Service | Module | Endpoint Pattern | Key Data |
|---|---|---|---|---|
| 1 | Series List | `list.py` | `/api/set/tfex/series/list` | Futures/options, 8 filter methods, contract details |
| 2 | Trading Statistics | `trading_statistics.py` | `/api/set/tfex/series/{sym}/trading-statistics` | Settlement, margin (IM/MM), theoretical price, days to maturity |

### Unified Stock Class (`stock/stock.py`)
Single entry point for SET stock data — initialize with symbol, access all services via lazy-init properties:
```python
stock = Stock("CPALL")
highlight = await stock.get_highlight_data()
profile = await stock.get_profile()
financials = await stock.get_balance_sheet()
latest = await stock.get_latest_price()    # latest traded price vs now
# ... all stock services accessible
```

### Unified SetIndex Class (`index/index.py`)
Same pattern for market indices:
```python
index = SetIndex("SET50")
info = await index.get_info()                  # last/chg/OHLC/vol/value/status
constituents = await index.get_constituents()  # 50 stocks w/ quote rows
latest = await index.get_latest_price()        # latest traded index value vs now
```

## API Design Principles

1. **Consistency**: SET and TFEX services follow identical patterns
2. **Simplicity**: Simple, intuitive APIs; one-line convenience functions
3. **Async-first**: async/await for all I/O operations
4. **Error Handling**: Clear, informative error messages
5. **Validation**: Pydantic models for all inputs and outputs
6. **Documentation**: All public APIs well-documented

## Key Technical Decisions

| Area | Choice | Reason |
|---|---|---|
| HTTP client | `curl_cffi` | Browser impersonation for bot detection bypass |
| Logging | `loguru` | Colored output, auto-rotation, better exception traces |
| Validation | Pydantic | Full type safety with runtime validation |
| Async | `asyncio.to_thread` | Wraps sync curl_cffi for async compatibility |
| Session mgmt | `SessionManager` | 25x speedup via cookie warming + caching |
| Build | `uv` (pyproject.toml) | Fast dependency resolution |
| Lint | Ruff + mypy strict | Modern, fast tooling |

## Target Users

- Python developers building trading applications
- Financial analysts needing Thailand market data
- Quantitative researchers and data scientists
- Automated trading system developers

## Important Notes

- This library is **not officially affiliated** with SET or TFEX
- Always respect API rate limits and terms of service
- Handle sensitive data (API keys, credentials) securely
- Never commit credentials or API keys to version control

## Recent Change History (Condensed)

### 2026-07-16
- **Market Index services (0.8.0)**: new `services/set/index/` sub-package — index directory
  (55 indices, 3 levels), quotations (single + all-at-once), constituents with bid/offer
  quote rows, chart-quotation/latest-value (reuses stock models), `SetIndex` facade
- **Stock list enrichment**: `StockSymbol.indices` (headline sub-index memberships, default
  on via 9 concurrent composition fetches, failure-tolerant) + `filter_by_index()`

### 2025-10-05
- **Jupyter Examples**: 13 notebooks covering all services with beginner guides, professional use cases, and CSV/pandas export
- **TFEX Trading Statistics**: Settlement prices, margin (IM/MM), days to maturity, theoretical pricing
- **TFEX Series List**: Complete futures/options discovery with 8 filter methods
- **Financial Service**: Balance sheet, income statement, cash flow — multi-period with en/th support, 98% test coverage

### 2025-10-04
- **Price Performance**: Stock vs sector vs market across 5 periods (5D–YTD), P/E, P/B, turnover
- **Trading Statistics (SET)**: 30+ fields across YTD/1M/3M/6M/1Y periods — price, volume, valuation, beta

### 2025-10-03
- **Board of Directors**: Director names, positions, en/th support
- **NVDR Holders**: NVDR ownership data with Thai/foreign holder identification
- **Corporate Actions**: Dividends (XD) and meetings (XM) with full detail
- **Company Profile**: ESG ratings, CG scores, management, auditors, capital structure
- **Shareholders**: Major holders, free float, ownership distribution
- **Refactoring**: Removed legacy cookie generation (~200 lines); SessionManager now handles all bot detection

### 2025-10-02
- **Stock Profile**: 30+ fields — listing, IPO, sector, foreign limits, ISIN, warrants
- **Highlight Data**: P/E, P/B, market cap, dividends, NVDR, 52-week range
- **Unified Stock class**: Single entry point for all stock services with lazy init
- **Stock utilities**: `normalize_symbol()`, `normalize_language()` shared across all services

### 2025-10-01
- **Stock List Service**: Full SET/MAI stock list with market/industry/symbol filtering
- **AsyncDataFetcher**: Core HTTP client with Unicode/Thai support, retry logic, bot impersonation
- **Migration**: httpx → curl_cffi (bot bypass), stdlib logging → loguru
- Established the service architecture pattern used by all subsequent services

## Future Enhancements (Ideas)

- WebSocket support for real-time streaming
- Data caching mechanisms, rate limiting
- CLI tool for quick data queries
- pandas/polars integration
- Historical data export (CSV, Parquet)

## When Working on This Project

1. **Read First**: Check existing code patterns before implementing
2. **Test**: Write tests before or alongside code
3. **Document**: Update docs when adding features
4. **Consistency**: Follow existing patterns and naming conventions
5. **Type Safety**: Always use type hints
6. **Ask Questions**: If unclear about architecture, ask for clarification

## Contact & Resources

- Documentation: `docs/` directory
- Issues: GitHub Issues
- License: MIT

---

*This file should be kept up-to-date as the project evolves.*
