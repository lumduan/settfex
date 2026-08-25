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
│   │   │   ├── constants.py, list.py, earnings_call.py, news.py, holiday.py,
│   │   │   │   asset_type.py (AssetType StrEnum ← securityType codes)
│   │   │   ├── index/        # Market index services: list, info (quotation),
│   │   │   │                 #   composition (constituents), chart_quotation,
│   │   │   │                 #   index.py (SetIndex facade), utils.py
│   │   │   └── stock/        # Stock services: highlight_data, profile_stock,
│   │   │                     #   profile_company, corporate_action, shareholder,
│   │   │                     #   nvdr_holder, board_of_director, trading_stat,
│   │   │                     #   price_performance, chart_quotation,
│   │   │                     #   latest_historical_trading, profile_dr,
│   │   │                     #   dr_indicative_price (TradingView),
│   │   │                     #   analyst_consensus (IAA, settrade.com),
│   │   │                     #   financial/, stock.py, utils.py
│   │   ├── tfex/             # TFEX services: list.py, trading_statistics.py, underlying_price.py
│   │   ├── sec/              # SEC IDISC (market.sec.or.th) document services: constants.py,
│   │   │                     #   company.py, financial_report.py, download.py, sec.py, utils.py
│   │   └── thaibma/          # ThaiBMA (www.thaibma.or.th) government bond yield curve:
│   │                         #   constants.py, utils.py, yield_curve.py, history.py,
│   │                         #   availability.py, thaibma.py
│   └── utils/                # http.py, data_fetcher.py, session_manager.py,
│                             #   session_cache.py, logging.py
├── tests/                     # Mirror of settfex/ with test_ prefix
├── docs/                      # Service docs, guides, solutions
├── examples/                  # 24 Jupyter notebooks (19 SET + 3 TFEX + 1 SEC + 1 ThaiBMA)
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

## Services Inventory (25 total)

### SET Services (20)

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
| 17 | Market Holidays | `holiday.py` | `/api/cms/v1/holidays/year/{year}` | Official SET market-closure calendar for a year (en/th): tz-aware `+07:00` dates + verbatim descriptions (trailing `" *"` = SET footnote, never stripped). `HolidayCalendar` container with `count`/`dates`/`is_holiday()`/`get_holiday()`/`filter_by_month()`/`next_holiday()`; `year=None` → current **Asia/Bangkok** year. **Only the current year is served** (2024/2025/2027/2028 → HTTP 401); 401 is the endpoint's *only* failure code and also fires transiently, so the service retries 401/403/429 via `FetcherConfig.max_retries`/`retry_delay`. Holidays only — **weekends are not in the payload** |

| 18 | DR Profile | `stock/profile_dr.py` | `/api/set/dr/{sym}/profile` | Depositary Receipt details: issuer, underlying (symbol/name/exchange/url), conversion ratio (verbatim `"2,000 : 1"`), `fractionalTrade` (DRx), trading session, and the **TradingView "Indicative Price" link** — `indicativePriceSymbol` expression (e.g. `NASDAQ:GOOG*FX_IDC:USDTHB/2000.0`; sometimes null) + `indicativePriceUrl` (always present; expression recoverable from its `symbol` query param via `DrProfile.indicative_expression`). Non-DR symbols → 404 `Invalid DR` → `SymbolNotFoundError` w/ **no** suggestion. `Stock.get_dr_profile()` (cached per lang) / `get_tradingview_url()` (None for non-DR) |
| 19 | DR Indicative Price | `stock/dr_indicative_price.py` | `POST scanner.tradingview.com/global/scan` (stateless foreign host) | DR fair value in THB: evaluates the expression (`product of leg closes ÷ ratio`) with ONE batch scan for all legs; `close` column = last price (~15-min delayed for exchange legs, streaming FX); `DrIndicativePrice` (legs/ratio/`is_delayed`/aware-Bangkok `as_of`) + `DrIndicativeQuotation` (a `Quotation` subclass, `volume=None`); **`Stock.get_latest_price()` auto-returns this for DRs** (opt-out `prefer_dr_indicative=False`; explicit `as_of` forces SET path; any failure falls back to SET chart data); `get_dr_indicative_price()` |
| 20 | Analyst Consensus (IAA) | `stock/analyst_consensus.py` | `GET www.settrade.com/api/set-fund/consensus/stock/{sym}/consensus`; `GET .../consensus/stock/overall?lang=&symbol=` | Broker research consensus — the data behind the `tableAnalystConcensus` table on Settrade's quote page (a Nuxt SPA, so this calls the JSON its bundle calls; **no HTML parsing**). Returns four aggregate rows (`average`/`median`/`high`/`low` as `ConsensusStatistic`, labelled by payload key) + one `AnalystConsensusRow` per covering broker (analyst, recommend, target price, EPS/net-profit/PE/PBV/div forecasts, `last_research_url` = **the research PDF**). **Two DataFrames**: `stats_to_dataframe()` (aggregates) and `to_dataframe()` (brokers) — or `get_analyst_consensus_dataframes()` for both; year-agnostic column names with the years in `df.attrs`. Second endpoint = buy/hold/sell summary (`ConsensusOverallResponse`); **omit the symbol → every covered SET stock in one request** (a market-wide screener). `Stock.get_analyst_consensus()` (cached) / `get_consensus_overall()`. Uses `SessionManager(warmup_site="settrade")` |

### AssetType classification (`asset_type.py`)

`AssetType` StrEnum + `AssetType.from_security_type(code)` map SET's `securityType` codes to friendly types (live-probed 2026-08-03): `S`→stock (930), `F`→stock_foreign (864), `P`→preferred_stock (8), `Q`→preferred_stock_foreign (8), `W`→warrant (85), `V`→dw (1651), `L`→etf (13), `U`→unit_trust (2), `X`→dr (493); anything else → `unknown` (never raises). Exposed as `StockProfile.asset_type` / `StockSymbol.asset_type` properties, `StockListResponse.filter_by_asset_type()`, and `Stock.get_asset_type()` (one profile fetch, cached per instance). **No `BOND` member** — bonds do not appear in SET's stock APIs.

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

### ThaiBMA Services (1)

Host is **`www.thaibma.or.th`** (the Thai Bond Market Association) — a stateless JSON API, a fourth top-level package `services/thaibma/`. The library's only fixed-income data.

| # | Service | Module | Endpoint Pattern | Key Data |
|---|---|---|---|---|
| 1 | Government Bond Yield Curve | `thaibma/{yield_curve,history,availability,thaibma}.py` | `GET /yieldcurve/gov[/{YYYY-MM-DD}]`; `GET /yieldcurve/getintpttm?year=`; `GET /yieldcurve/getbyyear?year=`; `GET /yieldcurve/avail`; `GET /yieldcurve/availyear` | The **official Thai government yield curve** back to **1999-09-15**. Point-in-time: `YieldCurve` = fitted `CurvePoint` grid (1M/3M/6M then whole years, `X` in years / `Y` in **percent**) + `BondQuote` rows (yield, `change_bps`, maturity, `GroupOrder` 1=T-Bill/2=bond, benchmark/synthetic flags); helpers `yield_at()`, `interpolate()` (never extrapolates), `slope_bps()`, `to_dict()`, `benchmarks`/`bills`/`bonds`, `quote()`, `to_dataframe()`. **History is one request per YEAR** (the full 27-year record = 28 requests, not ~6,600): `getintpttm` = constant-maturity matrix (reproduces `Curve` exactly), `getbyyear` = per-bond matrix (a *superset* of the daily `Stat` panel — also carries ILB/LBA issues); `YieldCurveHistory` carries per-year dynamic columns + their ordered union, with `series()`/`slice()`/`columns_by_year()`/`coverage()`/`to_long()`/`to_dataframe(layout=)`. Roll-back-aware: `requested_date` + `as_of` + computed `is_rolled_back`/`rollback_days`, `on_rollback="warn"|"raise"|"allow"` (`"raise"` → `StaleDataError`). `ThaiBMA` facade; `get_government_yield_curve()` / `get_yield_curve_history()` / `get_bond_yield_history()` / `get_yield_curve_availability()`. Stateless host (no SessionManager); no `lang` (the payload has no language dimension). |

### Unified ThaiBMA Class (`thaibma/thaibma.py`)
```python
tbma = ThaiBMA()
curve = await tbma.get_yield_curve()                 # latest; or a date, or on_rollback="raise"
history = await tbma.get_history("2020-01-01")       # 7 requests -> ~1,600 days x 54 tenors
bonds = await tbma.get_bond_history("2026-01-01")    # columns are bond symbols
avail = await tbma.get_availability()                # 1999-09-15 .. today, 28 years
```

### Unified Stock Class (`stock/stock.py`)
Single entry point for SET stock data — initialize with symbol, access all services via lazy-init properties:
```python
stock = Stock("CPALL")
highlight = await stock.get_highlight_data()
profile = await stock.get_profile()
latest = await stock.get_latest_price()    # latest traded price vs now (DRs: TradingView indicative)
news = await stock.get_news()              # company news/disclosures for this symbol
asset = await stock.get_asset_type()       # AssetType: stock/etf/dr/dw/warrant/... (cached)
iaa = await stock.get_analyst_consensus()  # broker targets + research PDFs (cached; settrade.com)
rec = await stock.get_consensus_overall()  # buy/hold/sell counts (live last_price, not cached)
# DR symbols only (e.g. Stock("GOOG80")):
dr = await stock.get_dr_profile()          # issuer/underlying/ratio + TradingView link (cached)
url = await stock.get_tradingview_url()    # "Indicative Price" chart URL (None for non-DR)
ind = await stock.get_indicative_price()   # underlying x FX / ratio via TradingView
```
Not every service has a `Stock` accessor yet — financial statements, trading stats, price
performance, corporate actions, NVDR holders and the board list are reached through their
module-level `get_*()` functions (e.g. `await get_balance_sheet("CPALL")`).

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

- **Calling** the library from an AI agent: [`AGENTS.md`](AGENTS.md) — service map, the `get_*()`
  contract, and the traps that produce wrong answers. This file (`CLAUDE.md`) covers **changing**
  the library; keep the two in sync when a service is added or a gotcha is found.
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
- **Holiday endpoint lives on a different path prefix:** `/api/cms/v1/holidays/year/{year}` is the **only** `/api/cms/v1/` endpoint in the package — everything else on `www.set.or.th` is under `/api/set/`. It takes `?lang=` (like stock/news), **not** `?language=` (like index).
- **The holiday endpoint serves ONLY the current year:** live-probed 2026-07-27 — with 2026 returning HTTP 200 on every interleaved control request, **2024, 2025, 2027 and 2028 all returned HTTP 401**. There is no history and no next-year lookahead, so this endpoint alone cannot back a multi-year trading calendar or a backtest.
- **HTTP 401 is the holiday endpoint's only failure code — and it is ambiguous:** an unrecognized `lang`, a missing `lang`, and an unserved year all return a bare `401` with an **empty body**, and so do valid requests *transiently*. Success degrades the harder you poll (~100% cold → ~35% after ~50 requests → ~12% after ~150), recovering on its own when left idle. `HolidayService` therefore retries 401/403/429 itself with exponential backoff (`FetcherConfig.max_retries`/`retry_delay`) — note `AsyncDataFetcher.fetch()` retries **exceptions only**, never a non-2xx status, so any other service is one flaky response away from a hard failure.
- **`HolidayCalendar.is_holiday()` is not "is the market open":** the API returns published closures only, so weekends are absent and `is_holiday(saturday)` is `False`. It also expresses whole-day closures only — no field for partial sessions or altered hours. Weekend logic must live in the caller.
- **Do not enable `str_strip_whitespace` on `Holiday`:** unlike every other SET model, it is deliberately off — a trailing `" *"` in a description is a SET footnote marker for additional special closures and must survive verbatim (a test guards this).
- **A SEC `FS` search returns three categories at once:** querying `ddlReportType=FS` returns financial statements **+** Key Financial Ratio **+** MD&A sections in one HTML response (each its own table); large sections truncate inline and expose a `ViewMore/{fs-norm|fs-kf|fs-mda}` link the listing follows (`follow_view_more=True`). MD&A rows use different columns (Date/Time/Heading/Link, no Name) — the mapper fills `company_name` from the resolved company as a fallback.
- **`DocumentCategory` is a `StrEnum`, deliberately — do not "restore" `(str, Enum)`:** ruff 0.15+ rejects the `(str, Enum)` pattern via `UP042`. As a `StrEnum`, `str(cat)` / `f"{cat}"` give the bare value (`"financial_statement"`), **not** `"DocumentCategory.FINANCIAL_STATEMENT"` — use `cat.name` or `repr(cat)` if you need the qualified form. Equality with the plain string, `.value`, JSON output and all `SecDocumentList` helpers are unaffected (tests guard this). Note `years_by_category()` keys on `.value` on purpose, which is why `summary()` never depended on the enum's `__str__`.
- **The uv version in CI is pinned by hand — Dependabot will not bump it:** all six `astral-sh/setup-uv` steps pass `version: "0.11.33"` instead of `"latest"`, so a uv release cannot silently change a build (this matters most in `release.yml`, which builds the published artifact). Dependabot's `github-actions` ecosystem bumps the *action ref*, never an action *input*, so this pin only moves when someone edits it. Note pinning does **not** make setup-uv network-free: on a GitHub-hosted runner uv is not in the tool cache, so `getArtifact` still fetches `raw.githubusercontent.com/astral-sh/versions` for the download URL — a fetch that has been observed to fail transiently. Re-run the job when it does.
- **Ruff is FROZEN at 0.13.2 and excluded from Dependabot — because 0.16+ formats Python code blocks inside Markdown by default:** upgrading past 0.16.0 makes `ruff format --check` want to reformat **34** files (`CLAUDE.md`, `docs/`, `.github/instructions/`), collapsing the intentionally column-aligned inline comments in the code samples. Dependabot proposed the bump three times and it was rejected all three (#61 → #78 → #88); on **2026-08-25** #88 was closed with `@dependabot ignore this dependency`, so **no further ruff PR will ever be opened**. That ignore lives in Dependabot's own state, **not** in `.github/dependabot.yml` — the reversal is to **re-open PR #88** (Dependabot's own wording: *"I won't notify you about ruff again, unless you re-open this PR"*), or `@dependabot unignore ruff` on any other Dependabot PR. Before re-enabling, settle the question this freeze deferred: accept the markdown churn, or set `extend-exclude = ["*.md"]` under `[tool.ruff]` first.
- **Classify asset types by `securityType` CODE, never by `securityTypeName`:** the API's own display name for code `Q` carries a typo ("Prefered Foreign Stocks"), and names are localizable. `AssetType.from_security_type()` maps codes case-insensitively and returns `UNKNOWN` for anything new (never raises). There is deliberately no `AssetType.BOND` — bonds appear nowhere in SET's stock APIs (no `/api/set/bond/list`, none in the stock list; live-probed 2026-08-03).
- **The DR-profile endpoint 404s for perfectly valid non-DR symbols:** `/api/set/dr/{sym}/profile` answers ANY non-DR (even `CPALL`) with HTTP 404 `{"message":"Invalid DR"}` — so the service raises `SymbolNotFoundError` with `suggest=False`; letting the symbol suggester run would produce the absurd "'CPALL' not found — did you mean 'CPALL'?". A 404 here means "not a DR", not "unknown symbol".
- **`indicativePriceSymbol` is sometimes null while `indicativePriceUrl` is not:** several DRs (HERMES80, BYDCOM80, NDX01 in live probes) return `indicativePriceSymbol: null` but still carry the full expression URL-encoded in `indicativePriceUrl`'s `symbol` query param. `DrProfile.indicative_expression` recovers it from the URL automatically — don't treat a null symbol field as "no expression".
- **TradingView scanner is a stateless foreign host — and `lp` is a websocket-only column:** never route `scanner.tradingview.com` through SessionManager (auto-detect would mis-warm it as SET, and the batch scan is a POST, which persistent sessions don't support) — `DrIndicativePriceService` forces `use_session=False` for TV calls only. Over plain HTTP request the `close` column for the last price (~15-min delayed for exchange legs, `update_mode: delayed_streaming_900`; FX_IDC legs stream); `lp`/`lp_time`/`last_price` come back null. Unknown tickers return HTTP 200 with the row simply missing (the service raises `FetchError` for missing rows). Remember `AsyncDataFetcher.fetch()` retries exceptions only — the service checks the status explicitly.
- **ThaiBMA's curve endpoint NEVER 404s on a date — it rolls back silently:** `/yieldcurve/gov/{date}` serves the most recent curve *on or before* the request. A weekend returns Friday's curve, a Thai holiday the previous business day's, and **any future date returns today's** (`2030-01-01` → `Asof 2026-08-10`) — all HTTP 200, no marker. `YieldCurve` therefore always carries `requested_date` **and** `as_of` plus the Pydantic **computed fields** `is_rolled_back`/`rollback_days` (computed, so the audit trail survives `model_dump()` into Parquet). `on_rollback` is `"warn"` (default) / `"raise"` (→ `StaleDataError`) / `"allow"`. `"warn"` is the default deliberately: `"raise"` would break every weekend of a date-range loop and train people into bare `except`, while `"allow"` exists so an intentional calendar-day walk does not emit ~100 warnings a year. `rollback_days` is the diagnostic — 1-4 = weekend/holiday, a large value = you asked for the future.
- **ThaiBMA mixes units in one row — `Yield` is PERCENT, `Change` is BASIS POINTS:** proved by differencing consecutive business days (a `-0.005534%` move is published as `Change: -0.5534`). Modelled as `yield_percent` / `change_bps` so the unit rides in the identifier, with `change_percent` as the safe-to-add derived form; a test pins the relationship against two real days. `Spread` is deliberately named just `spread` — ThaiBMA states the unit but what it is a spread *to* was never verified, and a wrong unit baked into a name is worse than an unqualified one.
- **Two nullable fields in the ThaiBMA `Stat` payload, and the second is easy to miss:** `MaturityDate` is null on the four synthetic T-BILL rows (expected), and **`Change` is null for every row on 1999-09-15** — the first curve ever published has no prior business day to difference against. Every other date in 27 years has both populated. A `float` (non-optional) `change_bps` blows up on exactly one date in the entire history.
- **ThaiBMA yield history is ONE REQUEST PER YEAR — never loop over days:** `getintpttm?year=` and `getbyyear?year=` each return a whole calendar year of business-day rows, so the full 1999→2026 record is **28 requests** versus ~6,600 for a per-day walk. Neither route is linked from any API index or documentation — they appear only in the site's own JS (`/EN/Market/YieldCurve/scripts/government-page.js`). `fetch_curves(dates)` exists only for the per-date `Stat` block (benchmark flags, spreads, per-bond changes), which has no bulk endpoint. `start_date` defaults to **1 Jan of the end year**, not 1999, so a bare `fetch_history()` cannot trigger a full-history pull by accident.
- **ThaiBMA history matrices are WIDE with per-year dynamic columns, and absent ≠ null:** tenors went 14 in 1999 (`1Y`..`14Y`, **no sub-year tenors at all**) → 20 in 2005 → 54 in 2026 (`1M`..`51Y`); bond symbols differ every year. Fixed Pydantic fields are impossible — each `HistoryRow` holds only its own year's columns in `values`, and the ordered union lives on the container. `HistoryRow.has(col)` distinguishes "that year never had the column" from "present but not quoted that day"; `to_dataframe()` flattens both to `NaN`, so use `columns_by_year()` when the difference matters. Note `YieldCurveHistory.row_for()` deliberately does **not** roll back — a Saturday returns `None`.
- **ThaiBMA's classification flags were never backfilled:** `IsBenchmark` is all-false before **2013** and `IsSynthetic` all-false before **2014** (probed: 2012-01-04 → 0/0, 2013-01-04 → 8/0, 2014-01-06 → 5/17). A backtest filtering history on `is_benchmark` gets **an empty set for the first ~14 years** rather than an error. `IsPlot` was `True` on every row in every era sampled, so it is not a useful filter either.
- **ThaiBMA fails malformed input in two different SILENT ways, plus a `null` body:** `2026-8-10` (unpadded) → an **HTML** 404 page; `2026-02-30` (well-formed but impossible) → HTTP 200 with the **latest** curve; a date before 1999-09-15 → HTTP 200 with a body of literal `null` (not `{}`, not 404); `getbyyear` with an out-of-range year → `[]`, with a non-numeric year → HTTP 400. `normalize_curve_date()` makes the first two unreachable (it re-emits every date zero-padded and rejects impossible days during `date` construction, before any request). Because error bodies are sometimes ASP.NET JSON and sometimes HTML, **never parse a non-2xx body** — the status is the only trustworthy signal.
- **No bulk history for ThaiBMA's zero-coupon curve — and it is deliberately not implemented:** `/yieldcurve/zero/{date}` exists and returns a byte-identical `{"Curve","Stat"}` envelope (coverage starts 2001-07-02), but `getzerobyyear` 404s. `fetch_history()` therefore takes **no** curve-type argument on purpose: accepting one and silently returning government data would be the worst possible outcome. The US Treasury curve and the corporate industry-spread curves on the same controller are out of scope (not Thai / not government); all are recorded in `docs/settfex/services/thaibma/yield_curve.md` so nobody re-discovers them.
- **Settrade is a SEPARATE Incapsula cookie domain — and the `Referer` is mandatory:** `www.settrade.com` (the analyst-consensus service) is SET Group's retail portal but a different host from `www.set.or.th`, with its own cookie jar. Proved by a 2×3 warm-URL/referer matrix (live-probed 2026-08-16): a session warmed on `www.set.or.th` → **403**; a warmed settrade session with **no** `Referer` → **403**; a warmed settrade session **plus** any `www.settrade.com` referer → 200. The warm URL need not be symbol-specific and one warmed session serves every symbol, so `SessionManager` gained a third `warmup_site="settrade"` (warms `https://www.settrade.com/th/home`) and `get_session_for_url()` routes by host. **Never let a settrade URL fall through to the SET warmup** — it would 403 every request.
- **`SessionManager.reset_instance()` matches on `"<site>_"`, not the bare site name:** instance keys are `f"{warmup_site}_{browser}"`, so the old bare `startswith(warmup_site)` made `reset_instance("set")` also match `settrade_chrome120` and silently close the Settrade session. Harmless until `settrade` landed (no two earlier site names were prefixes of one another); a test now pins it. Any future site name that extends an existing one has the same hazard.
- **The analyst-consensus endpoint answers an uncovered symbol with HTTP 500, not 404:** `/api/set-fund/consensus/stock/{sym}/consensus` returns 500 for anything it has no consensus record for — **including valid SET common stocks** (`ABICO`), DRs (`GOOG80`) and warrants (`JAS-W4`). It is therefore raised as a plain `FetchError(status_code=500)`, never `SymbolNotFoundError`: the suggester would emit the absurd "'ABICO' not found — did you mean 'ABICO'?" (the mirror of the DR-profile 404 gotcha above). A genuine server error is indistinguishable, so retry once before concluding a symbol is uncovered.
- **A listed stock nobody covers returns ZEROS, not nulls:** `TCC`/`MORE`/`PROUD` answer HTTP 200 with `consensuses: []` **and every aggregate row filled with `0.0`** — a 0.0 target price is indistinguishable from a real one. The zeros are kept verbatim (repo convention: record the anomaly, never rewrite the payload); `AnalystConsensus.has_coverage` is the guard, and it is a **computed field** so it survives `model_dump()` into Parquet. The service also logs a warning.
- **An analyst-consensus AGGREGATE row is not any one broker's row:** every column in `average`/`median`/`high`/`low` is aggregated independently. On GULF (2026-08-16) `high.target_price` was `91.0` from one broker while `high.target_price_change` was `12.0` from a *different* broker whose target was `79.0` — so never reconstruct one field from another across an aggregate row. Worse, the change columns only aggregate the brokers who actually revised (2 of 16), so `average.target_price_change` is **not** `average.target_price` minus a previous average.
- **The analyst-consensus table endpoint has NO language dimension:** `?lang=` is silently ignored and the `th`/`en` payloads are byte-identical (`recommend` is broker-supplied English free text like `"Buy"` / `"Outperform Market"`). `fetch_analyst_consensus()` deliberately takes **no** `lang` argument — do not add one "for consistency". Only the *overall* summary endpoint honours `lang`. That summary also fails silently: an unknown symbol is HTTP 200 with `overall: []`, never an error.
- **Analyst-consensus units come from the rendered column headers, not a guess:** `currentYearNetProfit` is in **million baht** (`กำไรสุทธิ (ล้านบาท)`) and `currentYearDiv`/`nextYearDiv` are a dividend **yield in percent** (`DIV (%)`), not baht per share — both confirmed against `tableAnalystConcensus` on 2026-08-16. Every numeric field is nullable on real broker rows (`targetPriceChange`, `nextYearPe`, `currentYearPbv`, `nextYearDiv` all observed null on CPALL), and `lastResearchURL` is null for many covering brokers (only 9 of GULF's 16 published a PDF).
- **`Stock.get_latest_price()` is DR-aware by default:** for DRs it returns a `DrIndicativeQuotation` (TradingView indicative price; `volume`/`change` are `None` — it's a fair value, not a SET trade) and falls back to SET chart data on ANY TradingView failure. The switch only applies when `as_of is None` (TV can't answer historical instants); opt out per-call with `prefer_dr_indicative=False`. DR-ness is detected by one cached DR-profile probe per `Stock` instance (a 404 marks non-DR permanently for that instance; transient errors are never cached). Indicative vs SET-close divergence is EXPECTED (probe: 5.94 indicative vs 5.75 SET close after a US-session move) — not a bug.

---

*This file should be kept up-to-date as the project evolves.*
