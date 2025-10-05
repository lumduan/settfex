# CLAUDE.md - AI Assistant Context

This fil├── docs/                      # Documentation
│   ├── index.md
│   ├── session_caching.md
│   └── settfex/
│       ├── services/set/
│       └── utils/
├── scripts/                   # Utility scripts
│   ├── demo_session_cache.py
│   └── settfex/ext and guidelines for AI assistants (like Claude) working on the settfex project.

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
4. Document the service with comprehensive docstrings and usage examples
5. Create verification script in `scripts/settfex/services/set/`

### Adding a New TFEX Service

1. Create new module in `settfex/services/tfex/`
2. Add corresponding tests in `tests/services/tfex/`
3. Update `settfex/services/tfex/__init__.py` to export the new service
4. Document the service with comprehensive docstrings and usage examples
5. Create verification script in `scripts/settfex/services/tfex/`

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

### 2025-10-05: Financial Service

**New Financial Service (`settfex/services/set/stock/financial/financial.py`)**
- Created async service to fetch comprehensive financial statement data for individual stock symbols
- Key features:
  - **Full Type Safety**: Complete Pydantic models with field descriptions and constraints
  - **Dual Language Support**: Fetch data in English ('en') or Thai ('th')
  - **Multiple Statement Types**: Balance sheet, income statement, and cash flow
  - **Historical Data**: Returns multiple periods for trend analysis
  - **Quarter Code Support**: Handles '6M' (half year) and 'Q9' (full year) periods
  - **Input Normalization**: Automatic symbol uppercase and language validation
  - **Async-First**: Built on AsyncDataFetcher for optimal performance
  - **Raw Data Access**: Methods to return both structured and raw JSON data
- Implementation:
  - Four main Pydantic models:
    - `Account`: Individual financial account line item
    - `FinancialStatement`: Base model for all financial statements
    - `BalanceSheet`, `IncomeStatement`, `CashFlow`: Specific statement types
  - Six fetch methods:
    - `fetch_balance_sheet(symbol, lang)`: Returns list of BalanceSheet models
    - `fetch_income_statement(symbol, lang)`: Returns list of IncomeStatement models
    - `fetch_cash_flow(symbol, lang)`: Returns list of CashFlow models
    - `fetch_*_raw(symbol, lang)`: Raw dictionary versions for debugging
  - Three convenience functions:
    - `get_balance_sheet(symbol, lang)`: Quick balance sheet access
    - `get_income_statement(symbol, lang)`: Quick income statement access
    - `get_cash_flow(symbol, lang)`: Quick cash flow access
- Data fields include:
  - **Statement Metadata**: Symbol, quarter, year, begin/end dates, status (Audited/Reviewed/Unaudited), download URL
  - **Account Details**: Code, name, amount (in thousands), adjusted flag, hierarchy level, divider, display format
  - **Account Hierarchy**: Level -1 for totals, 0+ for detail accounts
  - **Restatement Info**: Flags and dates for restated statements
- Configuration:
  - Added to `settfex/services/set/constants.py`:
    - `SET_FINANCIAL_BALANCE_SHEET_ENDPOINT`: `/api/set/factsheet/{symbol}/financialstatement`
    - `SET_FINANCIAL_INCOME_STATEMENT_ENDPOINT`: `/api/set/factsheet/{symbol}/financialstatement`
    - `SET_FINANCIAL_CASH_FLOW_ENDPOINT`: `/api/set/factsheet/{symbol}/financialstatement`
- Usage pattern:
  ```python
  from settfex.services.set import (
      get_balance_sheet,
      get_income_statement,
      get_cash_flow
  )

  # Balance sheet
  balance_sheets = await get_balance_sheet("CPALL")
  latest = balance_sheets[0]
  print(f"Period: {latest.quarter} {latest.year}")

  # Find total assets
  total_assets = next(
      (acc for acc in latest.accounts if "Total Assets" in acc.account_name),
      None
  )
  print(f"Total Assets: {total_assets.amount:,.0f}K")

  # Income statement
  income_statements = await get_income_statement("CPALL")
  for stmt in income_statements[:3]:
      print(f"{stmt.quarter} {stmt.year}: {stmt.status}")

  # Cash flow
  cash_flows = await get_cash_flow("CPALL")
  ```
- Testing:
  - Comprehensive test suite: `tests/services/set/stock/financial/test_financial.py`
  - 23 tests covering all functionality including edge cases and error handling
  - 98% test coverage for the financial module
  - Mock-based testing for reliability without network dependency
- Documentation:
  - Full service documentation: `docs/settfex/services/set/financial.md`
  - Manual verification script: `scripts/settfex/services/set/verify_financial.py`
  - 7 verification tests covering all features and edge cases
- Module exports:
  - Updated `settfex/services/set/stock/__init__.py` to export:
    - `Account`, `FinancialStatement`, `BalanceSheet`, `IncomeStatement`, `CashFlow`
    - `FinancialService`, `get_balance_sheet`, `get_income_statement`, `get_cash_flow`
  - Updated `settfex/services/set/__init__.py` to export all financial models and functions
  - Added financial endpoint constants to both __init__ files
- Purpose:
  - Track company financial performance across multiple periods
  - Analyze balance sheet assets, liabilities, and equity
  - Monitor income statement revenue, expenses, and profitability
  - Evaluate cash flow from operating, investing, and financing activities
  - Support fundamental analysis and valuation
  - Enable trend analysis and financial ratio calculations
  - Compare current vs historical financial metrics

### 2025-10-04: Price Performance Service

**New Price Performance Service (`settfex/services/set/stock/price_performance.py`)**
- Created async service to fetch comprehensive price performance data for individual stock symbols
- Key features:
  - **Full Type Safety**: Complete Pydantic models for stock, sector, and market performance metrics
  - **Dual Language Support**: Fetch data in English ('en') or Thai ('th')
  - **Input Normalization**: Automatic symbol uppercase and language validation
  - **Async-First**: Built on AsyncDataFetcher for optimal performance
  - **Comparative Analysis**: Returns performance data for stock, sector, and market for easy comparison
  - **Multi-Period Data**: Returns price changes for 5-day, 1-month, 3-month, 6-month, and YTD periods
  - **Valuation Metrics**: P/E ratio, P/B ratio, and turnover ratio for each entity
- Implementation:
  - Two main Pydantic models:
    - `PricePerformanceMetrics`: Individual performance metrics (stock/sector/market)
    - `PricePerformanceData`: Complete performance data with stock, sector, and market
  - Two fetch methods:
    - `fetch_price_performance(symbol, lang)`: Returns validated Pydantic model
    - `fetch_price_performance_raw(symbol, lang)`: Returns raw dictionary for debugging
  - Convenience function:
    - `get_price_performance(symbol, lang)`: Quick one-line access
- Data fields include:
  - **Price Changes**: 5-day, 1-month, 3-month, 6-month, and YTD percentage changes
  - **Valuation Metrics**: P/E ratio, P/B ratio, turnover ratio
  - **Entity Identification**: Symbol for stock, sector code, and market code ("SET")
  - **Three Entities**: Stock-specific, sector aggregate, and market (SET) aggregate metrics
- Configuration:
  - Added to `settfex/services/set/constants.py`:
    - `SET_PRICE_PERFORMANCE_ENDPOINT`: `/api/set/factsheet/{symbol}/price-performance`
- Usage pattern:
  ```python
  from settfex.services.set import get_price_performance

  # Using convenience function
  data = await get_price_performance("MINT")

  # Stock performance
  print(f"Stock: {data.stock.symbol}")
  print(f"  YTD: {data.stock.ytd_percent_change:+.2f}%")
  print(f"  P/E: {data.stock.pe_ratio}, P/B: {data.stock.pb_ratio}")

  # Sector comparison
  print(f"Sector ({data.sector.symbol}): {data.sector.ytd_percent_change:+.2f}%")

  # Market comparison
  print(f"Market ({data.market.symbol}): {data.market.ytd_percent_change:+.2f}%")

  # Calculate relative performance
  vs_sector = data.stock.ytd_percent_change - data.sector.ytd_percent_change
  vs_market = data.stock.ytd_percent_change - data.market.ytd_percent_change
  print(f"vs Sector: {vs_sector:+.2f}%, vs Market: {vs_market:+.2f}%")

  # Thai language support
  data_th = await get_price_performance("MINT", lang="th")
  ```
- Documentation:
  - Full service documentation: `docs/settfex/services/set/price_performance.md`
  - Manual verification script: `scripts/settfex/services/set/verify_price_performance.py`
  - 10 verification tests covering all features and edge cases
- Module exports:
  - Updated `settfex/services/set/stock/__init__.py` to export:
    - `PricePerformanceMetrics`, `PricePerformanceData`, `PricePerformanceService`, `get_price_performance`
  - Updated `settfex/services/set/__init__.py` to export:
    - `PricePerformanceMetrics`, `PricePerformanceData`, `PricePerformanceService`, `get_price_performance`
    - `SET_PRICE_PERFORMANCE_ENDPOINT`
- Purpose:
  - Compare stock performance against sector and overall market
  - Track price changes across multiple time periods (5D, 1M, 3M, 6M, YTD)
  - Analyze valuation metrics (P/E, P/B, turnover) for stock, sector, and market
  - Support relative performance analysis for investment decisions
  - Enable sector rotation and market timing strategies

### 2025-10-04: Trading Statistics Service

**New Trading Statistics Service (`settfex/services/set/stock/trading_stat.py`)**
- Created async service to fetch comprehensive trading statistics for individual stock symbols
- Key features:
  - **Full Type Safety**: Complete Pydantic model with 30+ trading statistics fields
  - **Dual Language Support**: Fetch data in English ('en') or Thai ('th')
  - **Input Normalization**: Automatic symbol uppercase and language validation
  - **Async-First**: Built on AsyncDataFetcher for optimal performance
  - **Multi-Period Data**: Returns statistics for YTD, 1M, 3M, 6M, and 1Y periods
  - **Comprehensive Metrics**: Price, volume, valuation ratios, financial data, and volatility measures
- Implementation:
  - Main Pydantic model:
    - `TradingStat`: Individual trading statistics record with 30+ fields
  - Two fetch methods:
    - `fetch_trading_stats(symbol, lang)`: Returns list of validated Pydantic models
    - `fetch_trading_stats_raw(symbol, lang)`: Returns raw list of dictionaries for debugging
  - Convenience function:
    - `get_trading_stats(symbol, lang)`: Quick one-line access
- Data fields include:
  - **Period & Identification**: Date, period (YTD/1M/3M/6M/1Y), symbol, market, industry, sector
  - **Price Data**: Prior, open, high, low, average, close, change, percent change
  - **Volume & Value**: Total volume, total value, average daily value, turnover ratio
  - **Valuation Metrics**: P/E ratio, P/B ratio, market cap, book value per share
  - **Share Data**: Listed shares, par value
  - **Financial Metrics**: Dividend yield, dividend payout ratio, financial date
  - **Risk Metrics**: Beta coefficient
- Configuration:
  - Added to `settfex/services/set/constants.py`:
    - `SET_TRADING_STAT_ENDPOINT`: `/api/set/factsheet/{symbol}/trading-stat`
- Usage pattern:
  ```python
  from settfex.services.set import get_trading_stats

  # Using convenience function
  stats = await get_trading_stats("MINT")
  for stat in stats:
      print(f"{stat.period}: {stat.close:.2f} THB ({stat.percent_change:+.2f}%)")

  # Get specific period
  ytd = next(s for s in stats if s.period == "YTD")
  print(f"YTD Performance: {ytd.percent_change:.2f}%")
  print(f"P/E: {ytd.pe}, Market Cap: {ytd.market_cap:,.0f} THB")

  # Thai language support
  stats_th = await get_trading_stats("MINT", lang="th")
  ```
- Documentation:
  - Full service documentation: `docs/settfex/services/set/trading_stat.md`
  - Manual verification script: `scripts/settfex/services/set/verify_trading_stat.py`
  - 8 verification tests covering all features and edge cases
- Module exports:
  - Updated `settfex/services/set/stock/__init__.py` to export:
    - `TradingStat`, `TradingStatService`, `get_trading_stats`
  - Updated `settfex/services/set/__init__.py` to export:
    - `TradingStat`, `TradingStatService`, `get_trading_stats`
    - `SET_TRADING_STAT_ENDPOINT`
- Purpose:
  - Track historical trading performance across multiple periods
  - Analyze price movements, volume, and liquidity
  - Monitor valuation metrics (P/E, P/B, market cap)
  - Evaluate dividend metrics and payout ratios
  - Assess volatility and risk (beta coefficient)
  - Support investment analysis and trading decisions

### 2025-10-03: Board of Director Service

**New Board of Director Service (`settfex/services/set/stock/board_of_director.py`)**
- Created async service to fetch board of directors and management information for individual stock symbols
- Key features:
  - **Full Type Safety**: Complete Pydantic models for director information
  - **Dual Language Support**: Fetch data in English ('en') or Thai ('th')
  - **Input Normalization**: Automatic symbol uppercase and language validation
  - **Async-First**: Built on AsyncDataFetcher for optimal performance
  - **Thai/Unicode Support**: Proper handling of Thai director names
- Implementation:
  - Main Pydantic model:
    - `Director`: Individual director with name and list of positions
  - Two fetch methods:
    - `fetch_board_of_directors(symbol, lang)`: Returns list of validated Pydantic models
    - `fetch_board_of_directors_raw(symbol, lang)`: Returns raw list of dictionaries for debugging
  - Convenience function:
    - `get_board_of_directors(symbol, lang)`: Quick one-line access
- Data fields include:
  - **Director Information**: Full name and list of positions held
  - **Position Types**: Chairman, CEO, Director, Independent Director, etc.
- Configuration:
  - Added to `settfex/services/set/constants.py`:
    - `SET_BOARD_OF_DIRECTOR_ENDPOINT`: `/api/set/company/{symbol}/board-of-director`
- Usage pattern:
  ```python
  from settfex.services.set import get_board_of_directors

  # Using convenience function
  directors = await get_board_of_directors("MINT")
  for director in directors:
      positions = ", ".join(director.positions)
      print(f"{director.name}: {positions}")

  # Thai language support
  directors_th = await get_board_of_directors("MINT", lang="th")
  ```
- Documentation:
  - Full service documentation: `docs/settfex/services/set/board_of_director.md`
  - Manual verification script: `scripts/settfex/services/set/verify_board_of_director.py`
  - Comprehensive test suite with 90%+ coverage
- Module exports:
  - Updated `settfex/services/set/stock/__init__.py` to export:
    - `Director`, `BoardOfDirectorService`, `get_board_of_directors`
  - Updated `settfex/services/set/__init__.py` to export:
    - `Director`, `BoardOfDirectorService`, `get_board_of_directors`
    - `SET_BOARD_OF_DIRECTOR_ENDPOINT`
- Purpose:
  - Track board of directors and management structure
  - Identify key positions (Chairman, CEO, Independent Directors)
  - Support corporate governance analysis
  - Enable management continuity tracking

### 2025-10-03: NVDR Holder Service

**New NVDR Holder Service (`settfex/services/set/stock/nvdr_holder.py`)**
- Created async service to fetch NVDR (Non-Voting Depository Receipt) holder data for individual stock symbols
- Key features:
  - **Full Type Safety**: Complete Pydantic models for NVDR holder information
  - **Dual Language Support**: Fetch data in English ('en') or Thai ('th')
  - **Input Normalization**: Automatic symbol uppercase and language validation
  - **Async-First**: Built on AsyncDataFetcher for optimal performance
  - **Thai/Unicode Support**: Proper handling of Thai holder names
- Implementation:
  - Two main Pydantic models:
    - `NVDRHolder`: Individual NVDR holder information
    - `NVDRHolderData`: Complete NVDR holder data
  - Two fetch methods:
    - `fetch_nvdr_holder_data(symbol, lang)`: Returns validated Pydantic model
    - `fetch_nvdr_holder_data_raw(symbol, lang)`: Returns raw dictionary for debugging
  - Convenience function:
    - `get_nvdr_holder_data(symbol, lang)`: Quick one-line access
- Data fields include:
  - **Company Statistics**: Total NVDR holders, percent scriptless, book close date
  - **Major NVDR Holders**: List with sequence, name, nationality, shares, ownership percentage, Thai NVDR flag
  - **Free Float**: Typically null for NVDR data
- Configuration:
  - Added to `settfex/services/set/constants.py`:
    - `SET_NVDR_HOLDER_ENDPOINT`: `/api/set/stock/{symbol}/nvdr-holder`
- Usage pattern:
  ```python
  from settfex.services.set import get_nvdr_holder_data

  # Using convenience function
  data = await get_nvdr_holder_data("MINT")
  print(f"Symbol: {data.symbol}")  # MINT-R (includes -R suffix)
  print(f"Total NVDR Holders: {data.total_shareholder:,}")

  for holder in data.major_shareholders[:5]:
      print(f"{holder.sequence}. {holder.name}: {holder.percent_of_share:.2f}%")

  # Thai language support
  data_th = await get_nvdr_holder_data("MINT", lang="th")
  ```
- Documentation:
  - Full service documentation: `docs/settfex/services/set/nvdr_holder.md`
  - Manual verification script: `scripts/settfex/services/set/verify_nvdr_holder.py`
  - 8 verification tests covering all features and edge cases
- Module exports:
  - Updated `settfex/services/set/stock/__init__.py` to export:
    - `NVDRHolder`, `NVDRHolderData`, `NVDRHolderService`, `get_nvdr_holder_data`
  - Updated `settfex/services/set/__init__.py` to export:
    - `NVDRHolder`, `NVDRHolderData`, `NVDRHolderService`, `get_nvdr_holder_data`
    - `SET_NVDR_HOLDER_ENDPOINT`
- Purpose:
  - Track NVDR (Non-Voting Depository Receipt) holders and their ownership
  - Monitor major NVDR holder distribution
  - Identify Thai NVDR holders vs. foreign NVDR holders
  - Support ownership analysis for investment decisions
  - NVDR shares carry same rights as ordinary shares except voting rights

### 2025-10-03: Corporate Action Service

**New Corporate Action Service (`settfex/services/set/stock/corporate_action.py`)**
- Created async service to fetch corporate action data for individual stock symbols
- Key features:
  - **Full Type Safety**: Complete Pydantic model with fields for all corporate action types
  - **Dual Language Support**: Fetch data in English ('en') or Thai ('th')
  - **Input Normalization**: Automatic symbol uppercase and language validation
  - **Async-First**: Built on AsyncDataFetcher for optimal performance
  - **Multiple Action Types**: Supports XD (dividends), XM (meetings), and other corporate events
- Implementation:
  - Two main Pydantic models:
    - `CorporateAction`: Individual corporate action with 30+ fields
    - `CorporateActionService`: Main service class
  - Two fetch methods:
    - `fetch_corporate_actions(symbol, lang)`: Returns list of validated Pydantic models
    - `fetch_corporate_actions_raw(symbol, lang)`: Returns raw list of dictionaries for debugging
  - Convenience function:
    - `get_corporate_actions(symbol, lang)`: Quick one-line access
- Data fields include:
  - **Common Fields**: Symbol, action type, dates (XD date, record date, book close date)
  - **Dividend Fields (XD)**: Dividend amount, currency, payment date, source, type, operation period
  - **Meeting Fields (XM)**: Meeting type (AGM/EGM), meeting date, venue, agenda
  - **Optional Fields**: All specific fields are optional to handle different action types
- Configuration:
  - Added to `settfex/services/set/constants.py`:
    - `SET_CORPORATE_ACTION_ENDPOINT`: `/api/set/stock/{symbol}/corporate-action`
- Usage pattern:
  ```python
  from settfex.services.set import get_corporate_actions

  # Using convenience function
  actions = await get_corporate_actions("AOT")
  for action in actions:
      if action.ca_type == "XD":
          print(f"Dividend: {action.dividend} {action.currency}")
          print(f"XD Date: {action.x_date}")
          print(f"Payment Date: {action.payment_date}")
      elif action.ca_type == "XM":
          print(f"Meeting: {action.meeting_type}")
          print(f"Agenda: {action.agenda}")

  # Thai language support
  actions_th = await get_corporate_actions("AOT", lang="th")

  # Using service class
  from settfex.services.set.stock import CorporateActionService

  service = CorporateActionService()
  actions = await service.fetch_corporate_actions("PTT", lang="en")
  ```
- Testing:
  - Comprehensive test suite: `tests/services/set/test_corporate_action.py`
  - Covers all functionality including edge cases, error handling, and multiple action types
  - Tests for Pydantic model validation, API field aliases, and optional fields
  - Mock-based testing for reliability without network dependency
- Documentation:
  - Full service documentation: `docs/settfex/services/set/corporate_action.md`
  - Manual verification script: `scripts/settfex/services/set/verify_corporate_action.py`
  - 8 verification tests covering all features and edge cases
- Module exports:
  - Updated `settfex/services/set/stock/__init__.py` to export:
    - `CorporateAction`, `CorporateActionService`, `get_corporate_actions`
  - Updated `settfex/services/set/__init__.py` to export:
    - `CorporateAction`, `CorporateActionService`, `get_corporate_actions`
    - `SET_CORPORATE_ACTION_ENDPOINT`
- Purpose:
  - Track dividend announcements and payment schedules
  - Monitor shareholder meetings (AGM, EGM) with agenda and venue details
  - Support corporate event analysis for investment decisions
  - Enable automated alerts for corporate actions

### 2025-10-03: Company Profile Service

**New Company Profile Service (`settfex/services/set/stock/profile_company.py`)**
- Created async service to fetch comprehensive company profile data for individual stock symbols
- Key features:
  - **Full Type Safety**: Complete Pydantic models with nested structures for auditors, management, and capital
  - **Dual Language Support**: Fetch data in English ('en') or Thai ('th')
  - **Input Normalization**: Automatic symbol uppercase and language validation
  - **Async-First**: Built on AsyncDataFetcher for optimal performance
  - **Comprehensive Data**: 30+ fields including governance scores, ESG ratings, management, auditors, and capital structure
- Implementation:
  - Seven Pydantic models:
    - `CompanyProfile`: Main company profile with all company information
    - `Auditor`: Auditor information (name, company, audit end date)
    - `Management`: Management/executive information (position, name, start date)
    - `Capital`: Capital structure (authorized, paid-up, par value, currency)
    - `VotingRight`: Voting rights information (symbol, shares, ratio)
    - `VotingShare`: Voting shares by date
    - `ShareStructure`: Share structure (listed, voting rights, treasury shares)
    - `CompanyProfileService`: Main service class
  - Two fetch methods:
    - `fetch_company_profile(symbol, lang)`: Returns validated Pydantic model
    - `fetch_company_profile_raw(symbol, lang)`: Returns raw dictionary for debugging
  - Convenience function:
    - `get_company_profile(symbol, lang)`: Quick one-line access
- Data fields include:
  - **Basic Info**: Symbol, name, market, sector, industry, logo URL
  - **Business Info**: Business type, website, established date, dividend policy
  - **Contact**: Address, telephone, fax, email
  - **Governance & ESG**: CG score (0-5), ESG rating (AAA-CCC), CAC certification flag
  - **Audit**: Audit end date, audit opinion, list of auditors
  - **Management**: List of executives with positions and start dates
  - **Capital Structure**: Common and preferred stock capital and share structures
  - **Voting Rights**: Voting rights information and voting shares by date
- Configuration:
  - Added to `settfex/services/set/constants.py`:
    - `SET_COMPANY_PROFILE_ENDPOINT`: `/api/set/company/{symbol}/profile`
- Usage pattern:
  ```python
  from settfex.services.set import get_company_profile

  # Using convenience function
  profile = await get_company_profile("CPN")
  print(f"Company: {profile.name}")
  print(f"Website: {profile.url}")
  print(f"CG Score: {profile.cg_score}/5")
  print(f"ESG Rating: {profile.setesg_rating}")
  print(f"CAC Certified: {'Yes' if profile.cac_flag else 'No'}")
  print(f"Management: {len(profile.managements)} executives")
  print(f"Auditors: {len(profile.auditors)}")

  # Thai language support
  profile_th = await get_company_profile("CPN", lang="th")

  # Using service class
  from settfex.services.set.stock import CompanyProfileService

  service = CompanyProfileService()
  profile = await service.fetch_company_profile("PTT", lang="en")
  ```
- Documentation:
  - Full service documentation: `docs/settfex/services/set/profile_company.md`
  - Manual verification script: `scripts/settfex/services/set/verify_profile_company.py`
- Module exports:
  - Updated `settfex/services/set/stock/__init__.py` to export:
    - `CompanyProfile`, `CompanyProfileService`, `get_company_profile`
  - Updated `settfex/services/set/__init__.py` to export:
    - `CompanyProfile`, `CompanyProfileService`, `get_company_profile`
    - `SET_COMPANY_PROFILE_ENDPOINT`
- Purpose:
  - Provide comprehensive company information for investment research
  - Enable governance and ESG analysis with CG scores and ESG ratings
  - Support management and auditor tracking for due diligence
  - Foundation for corporate governance and compliance monitoring

### 2025-10-03: Shareholder Service

**New Shareholder Service (`settfex/services/set/stock/shareholder.py`)**
- Created async service to fetch shareholder data for individual stock symbols
- Key features:
  - **Full Type Safety**: Complete Pydantic models for shareholder and free float data
  - **Dual Language Support**: Fetch data in English ('en') or Thai ('th')
  - **Input Normalization**: Automatic symbol uppercase and language validation
  - **Async-First**: Built on AsyncDataFetcher for optimal performance
  - **Thai/Unicode Support**: Proper handling of Thai shareholder names
- Implementation:
  - Four main Pydantic models:
    - `MajorShareholder`: Individual shareholder information
    - `FreeFloat`: Free float statistics
    - `ShareholderData`: Complete shareholder data
    - `ShareholderService`: Main service class
  - Two fetch methods:
    - `fetch_shareholder_data(symbol, lang)`: Returns validated Pydantic model
    - `fetch_shareholder_data_raw(symbol, lang)`: Returns raw dictionary for debugging
  - Convenience function:
    - `get_shareholder_data(symbol, lang)`: Quick one-line access
- Data fields include:
  - **Company Statistics**: Total shareholders, percent scriptless, book close date
  - **Major Shareholders**: List with sequence, name, nationality, shares, ownership percentage, NVDR flag
  - **Free Float**: Percentage, number of holders, book close date, CA type
- Configuration:
  - Added to `settfex/services/set/constants.py`:
    - `SET_STOCK_SHAREHOLDER_ENDPOINT`: `/api/set/stock/{symbol}/shareholder`
- Usage pattern:
  ```python
  from settfex.services.set import get_shareholder_data, Stock

  # Using convenience function
  data = await get_shareholder_data("MINT")
  print(f"Total Shareholders: {data.total_shareholder:,}")
  print(f"Free Float: {data.free_float.percent_free_float:.2f}%")

  for sh in data.major_shareholders[:5]:
      print(f"{sh.sequence}. {sh.name}: {sh.percent_of_share:.2f}%")

  # Thai language support
  data_th = await get_shareholder_data("MINT", lang="th")

  # Using Stock class
  stock = Stock("MINT")
  data = await stock.get_shareholder_data()
  ```
- Testing:
  - Comprehensive test suite: `tests/services/set/test_shareholder.py`
  - 22 tests covering all functionality, edge cases, and error handling
  - 89% test coverage
  - Tests for Pydantic model validation, API field aliases, and NVDR identification
  - Mock-based testing for reliability without network dependency
- Documentation:
  - Full service documentation: `docs/settfex/services/set/shareholder.md`
  - Manual verification script: `scripts/settfex/services/set/verify_shareholder.py`
  - 8 verification tests covering all features and edge cases
- Module exports:
  - Updated `settfex/services/set/stock/__init__.py` to export:
    - `ShareholderData`, `ShareholderService`, `get_shareholder_data`
  - Updated `settfex/services/set/__init__.py` to export:
    - `ShareholderData`, `ShareholderService`, `get_shareholder_data`
    - `SET_STOCK_SHAREHOLDER_ENDPOINT`
- Stock class integration:
  - Added `_shareholder_service` property to `Stock` class
  - Added `shareholder_service` property for lazy initialization
  - Added `get_shareholder_data(lang)` method
- Purpose:
  - Track major shareholders and ownership distribution
  - Monitor free float percentage and number of holders
  - Identify NVDR (Non-Voting Depositary Receipt) shareholders
  - Support ownership analysis for investment decisions
  - Enable tracking of ownership changes over time

### 2025-10-03: Service Module Refactoring and Cleanup

**Code Cleanup and Simplification**
- Removed legacy cookie generation methods from `AsyncDataFetcher`:
  - Removed `_generate_random_cookies()` method (unused, replaced by SessionManager)
  - Removed `generate_incapsula_cookies()` static method (unused, replaced by SessionManager)
- Cleaned up unused imports in `data_fetcher.py`:
  - Removed `base64`, `random`, `secrets`, `uuid` (no longer needed)
- Simplified `AsyncDataFetcher.fetch()` and `fetch_json()` methods:
  - Removed `cookies` and `use_random_cookies` parameters
  - Cookie management now fully handled by SessionManager (automatic warmup + caching)
  - All services now rely on SessionManager for bot detection bypass

**Service Module Updates**
All SET stock services have been refactored to use SessionManager:
- **StockHighlightDataService** (`highlight_data.py`):
  - Removed `session_cookies` and `use_cookies` parameters
  - Simplified constructor and fetch methods
  - All cookie handling delegated to SessionManager
- **StockProfileService** (`profile_stock.py`):
  - Removed `session_cookies` and `use_cookies` parameters
  - Simplified constructor and fetch methods
  - All cookie handling delegated to SessionManager
- **StockListService** (`list.py`):
  - Removed `session_cookies` parameter
  - Simplified constructor and fetch methods
  - All cookie handling delegated to SessionManager

**Key Benefits**
- **Simpler API**: No more cookie parameters in service constructors
- **Automatic Performance**: 25x speedup after first request (via SessionManager cache)
- **Auto-Retry**: SessionManager handles bot detection and re-warming automatically
- **Cleaner Code**: Removed ~200 lines of unused cookie generation code
- **Better Architecture**: Clear separation of concerns (SessionManager handles all cookies)

**Updated Usage Pattern**
```python
from settfex.services.set import Stock, get_stock_list, get_profile

# All services now use SessionManager automatically
stock_list = await get_stock_list()  # No cookie params needed!

stock = Stock("CPALL")
highlight = await stock.get_highlight_data()  # SessionManager handles everything

profile = await get_profile("PTT")  # Clean, simple API
```

**Documentation Updates**
- Updated `README.md`: Removed cookie generation examples, added session caching info
- Updated `CLAUDE.md`: Added this refactoring summary
- Updated `docs/settfex/utils/data_fetcher.md`: Removed cookie generation docs (pending)

### 2025-10-02: Stock Profile Service

**Stock Profile Service (`settfex/services/set/stock/profile_stock.py`)**
- Created async service to fetch comprehensive profile data for individual stock symbols
- Key features:
  - **Full Type Safety**: Complete Pydantic model with 30+ profile fields
  - **Dual Language Support**: Fetch data in English ('en') or Thai ('th')
  - **Input Normalization**: Automatic symbol uppercase and language validation
  - **Async-First**: Built on AsyncDataFetcher for optimal performance
  - **Flexible Cookie Support**: Accepts real browser session cookies or generates them
- Implementation:
  - Two main Pydantic models:
    - `StockProfile`: Complete company and listing information (30+ fields)
    - `StockProfileService`: Main service class
  - Two fetch methods:
    - `fetch_profile(symbol, lang)`: Returns validated Pydantic model
    - `fetch_profile_raw(symbol, lang)`: Returns raw dictionary for debugging
  - Convenience function:
    - `get_profile(symbol, lang)`: Quick one-line access
- Data fields include:
  - Company identification: Name, symbol, market
  - Classification: Sector (code and name), industry (code and name)
  - Listing details: Listed date, first trade date, status, IPO price
  - Share structure: Par value, listed shares, free float percentage
  - Foreign ownership: Foreign limit, foreign room, available shares
  - ISIN codes: Local, foreign, and NVDR trading
  - Fiscal year: Fiscal year end date and display format, account form
  - Derivative data: Exercise price, exercise ratio, underlying (for warrants)
- Configuration:
  - Added to `settfex/services/set/constants.py`:
    - `SET_STOCK_PROFILE_ENDPOINT`: `/api/set/stock/{symbol}/profile`
- Usage pattern:
  ```python
  from settfex.services.set import get_profile

  # Using convenience function
  profile = await get_profile("PTT")
  print(f"Company: {profile.name}")
  print(f"Sector: {profile.sector_name}")
  print(f"Listed: {profile.listed_date}")
  print(f"IPO: {profile.ipo} {profile.currency}")

  # Thai language support
  profile_th = await get_profile("PTT", lang="th")

  # Using service class
  from settfex.services.set.stock import StockProfileService

  service = StockProfileService()
  profile = await service.fetch_profile("CPALL", lang="en")
  ```
- Documentation:
  - Full service documentation: `docs/settfex/services/set/profile_stock.md`
  - Manual verification script: `scripts/settfex/services/set/verify_profile_stock.py`
- Module exports:
  - Updated `settfex/services/set/stock/__init__.py` to export:
    - `StockProfile`, `StockProfileService`, `get_profile`
  - Updated `settfex/services/set/__init__.py` to export:
    - `StockProfile`, `StockProfileService`, `get_profile`
    - `SET_STOCK_PROFILE_ENDPOINT`
- Purpose:
  - Provide detailed company and listing information for stocks
  - Enable sector and industry classification analysis
  - Support foreign ownership limit tracking
  - Foundation for investment research and compliance checks

### 2025-10-02: Stock Highlight Data Service & Unified Stock Class

**Stock Utilities Module (`settfex/services/set/stock/utils.py`)**
- Created shared utilities for all stock-related services
- Key functions:
  - `normalize_symbol()`: Normalize stock symbols to uppercase
  - `normalize_language()`: Normalize language codes to 'en' or 'th'
- Purpose:
  - Provide consistent input normalization across all stock services
  - Support multiple language input formats (en, eng, english, th, tha, thai)
  - Reusable by future stock services

**Stock Highlight Data Service (`settfex/services/set/stock/highlight_data.py`)**
- Created async service to fetch highlight data for individual stock symbols
- Key features:
  - **Full Type Safety**: Complete Pydantic model with 30+ fields
  - **Dual Language Support**: Fetch data in English ('en') or Thai ('th')
  - **Input Normalization**: Automatic symbol uppercase and language validation
  - **Async-First**: Built on AsyncDataFetcher for optimal performance
  - **Flexible Cookie Support**: Accepts real browser session cookies or generates them
- Implementation:
  - Two main Pydantic models:
    - `StockHighlightData`: Individual stock metrics (P/E, P/B, market cap, etc.)
    - `StockHighlightDataService`: Main service class
  - Two fetch methods:
    - `fetch_highlight_data(symbol, lang)`: Returns validated Pydantic model
    - `fetch_highlight_data_raw(symbol, lang)`: Returns raw dictionary for debugging
  - Convenience function:
    - `get_highlight_data(symbol, lang)`: Quick one-line access
- Data fields include:
  - Valuation metrics: Market cap, P/E ratio, P/B ratio, beta
  - Dividend data: Yield, amount, ex-dividend date
  - Trading data: 52-week high/low, turnover ratio
  - NVDR data: Buy/sell volume and value, net position
  - Share data: Listed shares, outstanding shares, free float
- Configuration:
  - Added to `settfex/services/set/constants.py`:
    - `SET_STOCK_HIGHLIGHT_DATA_ENDPOINT`: `/api/set/stock/{symbol}/highlight-data`
- Usage pattern:
  ```python
  from settfex.services.set import Stock, get_highlight_data

  # Using Stock class (recommended)
  stock = Stock("CPALL")
  data = await stock.get_highlight_data()
  print(f"P/E: {data.pe_ratio}, P/B: {data.pb_ratio}")

  # Using convenience function
  data = await get_highlight_data("CPALL", lang="en")
  print(f"Market Cap: {data.market_cap:,.0f}")

  # Thai language support
  data = await get_highlight_data("CPALL", lang="th")
  ```
- Documentation:
  - Full service documentation: `docs/settfex/services/set/highlight_data.md`
  - Manual verification script: `scripts/settfex/services/set/verify_highlight_data.py`

**Unified Stock Class (`settfex/services/set/stock/stock.py`)**
- Created unified `Stock` class as main entry point for all stock-related services
- Key features:
  - **Single Symbol Focus**: Initialize with one stock symbol
  - **Service Aggregation**: Access multiple services through one interface
  - **Lazy Initialization**: Services created only when needed
  - **Extensible Design**: Easy to add new services (shareholders, financials, etc.)
- Implementation:
  - Constructor accepts symbol, config, and session_cookies
  - Property for each service (e.g., `highlight_data_service`)
  - Method for each data type (e.g., `get_highlight_data()`)
  - Ready for future services (shareholders, financials, company profile)
- Usage pattern:
  ```python
  from settfex.services.set import Stock

  # Create Stock instance
  stock = Stock("CPALL")

  # Fetch highlight data
  highlight = await stock.get_highlight_data()

  # Future services (planned):
  # shareholders = await stock.get_shareholders()
  # financials = await stock.get_financials()
  # profile = await stock.get_company_profile()
  ```
- Purpose:
  - Provide clean, object-oriented interface for stock data
  - Centralize configuration and authentication
  - Enable easy addition of future services
  - Simplify code for users fetching multiple data types

**Module Structure**
- Created `settfex/services/set/stock/` subdirectory
- Files:
  - `__init__.py`: Exports Stock class and all stock services
  - `utils.py`: Shared utility functions
  - `highlight_data.py`: Highlight data service
  - `profile_stock.py`: Stock profile service
  - `stock.py`: Unified Stock class
- Updated `settfex/services/set/__init__.py` to export:
  - `Stock` class
  - `StockHighlightData`, `StockHighlightDataService`, `get_highlight_data`
  - `StockProfile`, `StockProfileService`, `get_profile`
  - `normalize_symbol`, `normalize_language`

### 2025-10-01: SET Stock List Service (Updated)

**Reusable SET API Utilities (`settfex/utils/data_fetcher.py`)**
- Added two static methods for all SET services to use:
  - `get_set_api_headers()`: Returns optimized headers for SET API requests
    - Includes all Incapsula bypass headers (Sec-Fetch-*, Cache-Control, Pragma, Priority)
    - Chrome 140 user agent with proper sec-ch-ua headers
    - Configurable referer URL (critical for bot detection bypass)
  - `generate_incapsula_cookies()`: Generates Incapsula-aware randomized cookies
    - Creates realistic visitor IDs, session tokens, and load balancer IDs
    - UUID-format charlot session tokens
    - Base64-encoded Incapsula identifiers
    - Random site IDs and API counters
    - **Landing URL Cookie Support**: Accepts optional `landing_url` parameter for symbol-specific requests
      - Critical for symbols with stricter Incapsula rules (e.g., CPN)
      - Should match the referer header for best results
      - Format: `landing_url=https://www.set.or.th/en/market/product/stock/quote/{symbol}/price`
- Both methods are static and can be used by any future SET service
- Full documentation with examples for service developers

**Bot Detection Bypass Pattern (Critical for All Stock Services)**
All stock-related services (highlight_data, profile_stock, etc.) now implement a two-part bot detection bypass:
1. **Symbol-Specific Referer Header**: Each request includes a referer matching the stock being fetched
2. **Landing URL Cookie**: Cookie value matching the referer for symbols with stricter Incapsula rules

Implementation pattern:
```python
# Build symbol-specific referer URL
referer = f"https://www.set.or.th/en/market/product/stock/quote/{symbol}/price"

# Get headers with symbol-specific referer
headers = AsyncDataFetcher.get_set_api_headers(referer=referer)

# Generate cookies with landing_url matching referer
cookies = (
    self.session_cookies
    or AsyncDataFetcher.generate_incapsula_cookies(landing_url=referer)
)
```

This pattern ensures:
- Bypass of Incapsula/Imperva bot detection for all symbols
- Support for concurrent requests without delays
- Compatibility with symbols having stricter security rules (CPN, etc.)

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
