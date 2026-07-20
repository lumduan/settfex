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
│   │   │   ├── constants.py, list.py, earnings_call.py, news.py
│   │   │   ├── index/        # Market index services: list, info (quotation),
│   │   │   │                 #   composition (constituents), chart_quotation,
│   │   │   │                 #   index.py (SetIndex facade), utils.py
│   │   │   └── stock/        # Stock services: highlight_data, profile_stock,
│   │   │                     #   profile_company, corporate_action, shareholder,
│   │   │                     #   nvdr_holder, board_of_director, trading_stat,
│   │   │                     #   price_performance, chart_quotation,
│   │   │                     #   latest_historical_trading, financial/, stock.py, utils.py
│   │   ├── tfex/             # TFEX services: list.py, trading_statistics.py, underlying_price.py
│   │   └── sec/              # SEC IDISC (market.sec.or.th) document services: constants.py,
│   │                         #   company.py, financial_report.py, download.py, sec.py, utils.py
│   └── utils/                # http.py, data_fetcher.py, session_manager.py,
│                             #   session_cache.py, logging.py
├── tests/                     # Mirror of settfex/ with test_ prefix
├── docs/                      # Service docs, guides, solutions
├── examples/                  # 20 Jupyter notebooks (16 SET + 3 TFEX + 1 SEC)
├── scripts/                   # Verification scripts per service
├── .github/                   # CI and agent instructions
├── pyproject.toml             # uv-based config
└── README.md
```

## Commands

```bash
uv sync              # install dependencies (includes the dev group)
uv run pytest        # run the test suite
uv run ruff check .  # lint
uv run mypy .        # type-check (strict mode)
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
6. Update `CLAUDE.md` (Services Inventory count + table row, Project Structure tree, and Known Gotchas if any) and add the release entry to `CHANGELOG.md` — the canonical release history

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

**Why the three tiers (for humans *and* AI agents):** `get_*()` is a flat, one-call convenience function — the intended **LLM tool-calling entry point** (do not remove this layer when "simplifying"); `fetch_*()` returns validated Pydantic models, giving structured, schema-checked output that lowers hallucination risk for agents; `fetch_*_raw()` returns the raw API dict as an escape hatch for debugging or fields not yet modeled.

Typical usage:
```python
from settfex.services.set import Stock, get_highlight_data, get_stock_list

stock = Stock("CPALL")
data = await stock.get_highlight_data()    # via unified Stock class
data = await get_highlight_data("CPALL")   # or convenience function
all_stocks = await get_stock_list()        # no cookie params needed
```

## Services Inventory (20 total)

### SET Services (16)

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
| 15 | Market Index | `index/{list,info,composition,chart_quotation,index}.py` | `/api/set/index/list`, `/api/set/index/info/list`, `/api/set/index/{sym}/info`, `/api/set/index/{sym}/composition`, `/api/set/index/{sym}/chart-quotation` | 55-index directory (INDEX/INDUSTRY/SECTOR levels; mai industries use `-m` query symbols); page-header quotes (last/chg/%chg/OHLC/vol/value/marketStatus/tz-aware timestamp); constituents w/ full quote rows incl. bid/offer (string prices coerced); `SetIndex` facade + `get_index_latest_price()` (reuses stock ChartQuotation); index symbols keep casing (`sSET`, `AGRO-m`); `SET`/`mai` have no composition (404 w/ helpful error). |
| 16 | News | `news.py` | `/api/set/news/search` | Company news/disclosures for **all stocks** in one call (default `sourceId=company`, latest-trading-day window); filters: `symbol`, `fromDate`/`toDate` (**dd/MM/yyyy only** — ISO → HTTP 400; validated eagerly via `InvalidDateError`), `keyword`, `source_id` (`None` = all sources; unrecognized values silently ignored by the API), en/th; helpers `count`/`filter_today()`/`filter_by_tag()`/`filter_by_symbol()`; `Stock.get_news()` accessor; no pagination — keep date windows modest |

### TFEX Services (3)

| # | Service | Module | Endpoint Pattern | Key Data |
|---|---|---|---|---|
| 1 | Series List | `list.py` | `/api/set/tfex/series/list` | Futures/options, 8 filter methods, contract details |
| 2 | Trading Statistics | `trading_statistics.py` | `/api/set/tfex/series/{sym}/trading-statistics` | Settlement, margin (IM/MM), theoretical price, days to maturity |
| 3 | Underlying Price | `underlying_price.py` | `/api/set/tfex/series/{sym}/underlying-price` | Underlying instrument price (SET50 index spot for index futures/options): last/prior/high/low, change, total volume/value, P/E, P/BV |

### SEC Services (1)

Host is **`market.sec.or.th`** (the Thai SEC IDISC system), NOT set.or.th — a separate top-level package `services/sec/`.

| # | Service | Module | Endpoint Pattern | Key Data |
|---|---|---|---|---|
| 1 | SEC Documents | `sec/{company,financial_report,download,sec}.py` | `POST /public/idisc/api/company/valuebyuniqueId`; `GET`/`POST /public/idisc/{lang}/FinancialReport/{FS\|R561\|R562\|KFR}`; `GET /public/idisc/{lang}/ViewMore/{slug}`; `GET /public/idisc/Download?FILEID=`; `GET /ipos/Common/IPOSGetFile.aspx?id=` | List + download **raw disclosure documents** for any issuer across 5 categories (`DocumentCategory`: financial_statement/form_56_1/form_56_2/key_financial_ratio/mda). Company resolver (`resolve_company` → 10-digit uniqueIDReference); listing replays the ASP.NET WebForms search (GET `__VIEWSTATE` → form POST → stdlib HTML-table parse), follows ViewMore for complete large sections; downloads return raw bytes (`DownloadedFile.save()`), concurrent `download_all`, soft-404 detection (dead links = HTML "file not found" under HTTP 200 → `FetchError`). Listing returns a **`SecDocumentList`** (a `list[SecDocument]` subclass, backward compatible) with `years_by_category()`/`available_years()`/`filter(category=,year=)`/`categories()`/`summary()` helpers — pass a **wide** date window to see full year history. `SecCompany("CPALL")` facade; `get_sec_documents()`/`download_sec_document(s)()`. dd/mm/yyyy dates. Stateless host (no SessionManager). |

### Unified Stock Class (`stock/stock.py`)
Single entry point for SET stock data — initialize with symbol, access all services via lazy-init properties:
```python
stock = Stock("CPALL")
highlight = await stock.get_highlight_data()
profile = await stock.get_profile()
financials = await stock.get_balance_sheet()
latest = await stock.get_latest_price()    # latest traded price vs now
news = await stock.get_news()              # company news/disclosures for this symbol
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

### Unified SecCompany Class (`sec/sec.py`)
Entry point for an issuer's SEC disclosure documents (host `market.sec.or.th`):
```python
sec = SecCompany("CPALL")
docs = await sec.list_documents(from_date="01/01/2010", to_date="31/12/2026")  # wide = full history
print(docs.summary())                       # available years per category
subset = docs.filter(category="form_56_1")  # SecDocumentList subset
files = await sec.download_all(subset, dest_dir="./out")  # concurrent; pass `docs` for everything
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
- The `curl_cffi` browser impersonation and `SessionManager` cookie caching exist to access **public** market data reliably and to **reduce** request volume (session/cookie caching yields ~25× fewer requests) — not to evade rate limits or terms of service. Continue to respect both.
- Handle sensitive data (API keys, credentials) securely
- Never commit credentials or API keys to version control

## Release History

See [`CHANGELOG.md`](CHANGELOG.md) for the full, versioned release history — this project follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and [Semantic Versioning](https://semver.org/). `CHANGELOG.md` is the single source of truth; do not maintain a parallel change log here.

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

## Known Gotchas

- **Index API query param:** the SET *index* endpoints (`/api/set/index/...`) use `?language=`, whereas the SET *stock* endpoints use `?lang=`. Passing the wrong one silently returns the wrong-language payload instead of erroring.
- **No composition for whole-market indices:** `SET` and `mai` have no `/composition` endpoint (the API returns HTTP 404) — query a sub-index (e.g. `SET50`), a sector, or an industry instead. The service raises with a helpful message.
- **Two distinct `chart_quotation.py` modules:** `services/set/stock/chart_quotation.py` (per-stock) and `services/set/index/chart_quotation.py` (per-index) are different files — don't conflate them.
- **Company-profile management `startDate` can be null:** SET reports a vacant/undisclosed executive seat with `"startDate": null` and an empty `name` (e.g. `VIBE`) — `Management.start_date` is `datetime | None`; guard before calling `.strftime()` on it.
- **News API date format (dd/MM/yyyy ONLY):** `fromDate`/`toDate` on `/api/set/news/search` reject ISO `yyyy-MM-dd` with an opaque HTTP 400. The news service converts `datetime.date`/`datetime` objects automatically and validates strings eagerly, raising `InvalidDateError` before any request is made.
- **News API `sourceId` is not validated:** any value other than `company` (including empty) is silently ignored and returns ALL sources (a superset incl. TFEX rows and `set-releases` items). `source_id=None` is the intended all-sources switch; `"company"` is the only verified filter value — the service logs a warning for unverified values.
- **News API history is a rolling ~5-year window (1826 days):** the `/api/set/news/search` endpoint serves only the trailing **1826 days** (= 5 calendar years incl. the leap day) — live-probed 2026-07-20: `from_date` = today−1826d works, today−1827d and older → **HTTP 400**. The check is on `from_date` (the window's *start*); if it predates the cutoff the whole request 400s (it does **not** clip to the allowed range). This surfaces as `FetchError`, **not** `InvalidDateError` (the latter is only for malformed dd/MM/yyyy strings). The boundary is rolling — always `today − 1826 days`.
- **SEC service is a different host + HTML, not JSON:** `services/sec/` targets `market.sec.or.th` (Thai SEC IDISC), an ASP.NET WebForms app — NOT set.or.th. The document search has no JSON list endpoint; it is a form postback returning HTML tables that the service parses (stdlib `html.parser`). It reuses `AsyncDataFetcher` with `use_session=False` (stateless, like `earnings_call.py`); dates are **dd/mm/yyyy** (note: SET news is dd/MM/yyyy — same digits, but the SEC form is its own endpoint). Do not route SEC URLs through SessionManager (its auto-detect would mis-warm them as SET).
- **SEC VIEWSTATE tokens are mandatory and must be fresh:** the search POST must echo `__VIEWSTATE`/`__VIEWSTATEGENERATOR`/`__EVENTVALIDATION` scraped from a fresh GET of the same page. Omitting them does **not** error — it silently returns a wrong, broader result set (43 vs 7 rows in testing). `FinancialReportService` always GETs tokens immediately before each POST; no cookie/session binding is needed (cross-request works).
- **SEC downloads can be soft-404s (HTTP 200 + HTML):** a dead `Download?FILEID=` link returns an HTML page `ไม่พบไฟล์ที่ระบุ` ("file not found") under **HTTP 200**, notably for some recent `dat/annual/` (56-2) rows whose file actually lives under `dat/f56/`. `DocumentDownloadService.download` validates the content-type and raises `FetchError` instead of returning the garbage bytes; `download_all(..., continue_on_error=True)` skips such items.
- **A SEC `FS` search returns three categories at once:** querying `ddlReportType=FS` returns financial statements **+** Key Financial Ratio **+** MD&A sections in one HTML response (each its own table); large sections truncate inline and expose a `ViewMore/{fs-norm|fs-kf|fs-mda}` link the listing follows (`follow_view_more=True`). MD&A rows use different columns (Date/Time/Heading/Link, no Name) — the mapper fills `company_name` from the resolved company as a fallback.

---

*This file should be kept up-to-date as the project evolves.*
