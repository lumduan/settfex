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
│   │   │   └── stock/        # Stock services: info (quote block + signs),
│   │   │                     #   highlight_data, profile_stock,
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
├── examples/                  # 25 Jupyter notebooks (20 SET + 3 TFEX + 1 SEC + 1 ThaiBMA)
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
6. **Testing**: Comprehensive pytest coverage (**85% CI floor**, currently 86.87%)
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
- Maintain coverage at or above the **85%** CI floor (`--cov-fail-under=85` in `pyproject.toml`); currently 86.87%. `--cov-branch` is in the pytest defaults so a local `uv run pytest` reports the same number CI does

### Live probes — politeness budget (these are other people's servers)

Live probing is how almost every real bug in this repo was found, and it is also how you get the
whole project blocked. **Earned 2026-09-20:** a sweep of 929 symbols against `market.sec.or.th` at
concurrency 8 drew `curl: (56) Connection reset by peer`, then a WAF block page — **HTTP 200 with
an HTML body reading `Request Rejected`** — for every subsequent request, for roughly an hour. The
evidence from that sweep was unusable, and the host stayed hostile long after the script stopped.

- **Concurrency 1** for any sweep over more than a handful of symbols, with **jittered** sleeps
  (~1-2 s) between requests. The concurrency limits in the services are for a *user's* workload,
  not for a research sweep.
- **Set an explicit request budget before starting** — "≤ 60 requests" — and make the script stop
  at it. A probe with no budget becomes a load test by accident.
- **Stop at the first WAF signal** and do not retry: a connection reset, an HTTP 200 whose body is
  a block page, or a 429. Retrying deepens the block, and fast retries deepen it fastest.
- **A sample beats a census.** 156 symbols across all nine `securityType` codes answered the
  `resolve_company` question as well as 929 would have, at a sixth of the cost.
- **A block page is not a parse failure.** It currently surfaces as `ResponseParseError` — right
  family, wrong diagnosis, and a caller retrying "a bad response" will make things worse. A
  dedicated `BlockedError` is tracked on #135 for 0.25.0.

### Scheduled actions need an absolute time — relative words are ambiguous

A time-bound instruction must carry **a date, a clock time and a timezone**: *"at or after
2026-09-21 17:00 ICT"*. If one is missing, **ask** — do not infer it from when the message appears
to have been written.

**Earned 2026-09-20/21.** A GO reading *"after 17:00 ICT today"* was written on a Sunday and acted
on the following Monday morning. By then "today" had silently re-pointed at a new date, and the
window it named had not only passed — the replacement window landed in the middle of SET's live
trading session, on the machine that carries non-backfillable market capture. The instruction was
perfectly clear when written and wrong when read, and nothing in it could show that.

- **Relative words are the hazard**: *today, tonight, tomorrow, this evening, in an hour, later,
  after close*. A conversation can be paused, compacted, resumed the next day, or forwarded — the
  word survives the day it was written in.
- **Anchor to the event, not the hour, when the event is what matters**: "after the SET close"
  means 16:30 ICT on a *trading day*, which is not the same instruction on a Sunday.
- **Check the clock before acting on any timed instruction**, and if the named window has passed,
  say so and re-ask rather than substituting the nearest equivalent. A window chosen to avoid
  market hours does not survive being shifted by a day.
- Write times back the same way. A report saying *"probe at 17:00"* inherits the same defect.

### Documentation
- Update docs when adding features; include docstrings for all public APIs
- Keep Jupyter notebook examples up-to-date

## Communication language

- All prose you write is in English: reports and chat replies to the operator, commit messages,
  PR descriptions, GitHub issues and comments, docs, ADRs, and code comments.
- Thai appears only as verbatim source data: document titles, labels (e.g. `สอบทาน`), company
  names, URLs, quoted page text, and fixture contents. Keep it exactly as the source has it —
  never translate or transliterate the data itself.
- When a Thai value's meaning matters to the reader, add an English gloss next to it:
  `สอบทาน` (reviewed).

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

## Services Inventory (26 total)

### SET Services (21)

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
| 21 | Stock Info (quote block + trading signs) | `stock/info.py` | `/api/set/stock/{sym}/info` | The quote-page header payload, and the **only** source of a symbol's trading `sign` (`SP`/`NC`/`NP`/`CB`/`CS`/`CC`/`XD`…) — the stock list has no sign field and index compositions cover common stocks only. Serves **every** security type (stocks, `-F`/`-P`/`-Q`, warrants, DWs, DRs, ETFs, unit trusts) with type-specific fields null where they do not apply: price/OHLC, floor/ceiling, best bid/offer (HTTP gives the **best level only**), market status, par/tick/52-wk, underlying, exercise terms + `ttm`/moneyness (warrants/DWs), nested `inav` (ETFs), and the valuation block. Signs arrive **comma-separated in one string** (`"SP, CB, CS, CC"`) — computed fields `signs`/`is_suspended` (they survive `model_dump()`), plus `has_sign()`, `best_bid`/`best_offer`, `asset_type`, and the `parse_signs()` helper. `Stock.get_info()` / `get_signs()` / `is_suspended()` (never cached — live state). **No `lang` argument** (the endpoint has no language dimension).

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
| 1 | SEC Documents | `sec/{company,financial_report,download,sec}.py` | `POST /public/idisc/api/company/valuebyuniqueId`; `GET`/`POST /public/idisc/{lang}/FinancialReport/{FS\|R561\|R562\|KFR}`; `GET /public/idisc/{lang}/ViewMore/{slug}`; `GET /public/idisc/Download?FILEID=`; `GET /ipos/Common/IPOSGetFile.aspx?id=`; `GET /public/idisc/Views/FinancialStatementDownload?query=`; `GET /public/idisc/views/viewdoc?TransId=` | List + download **raw disclosure documents** for any issuer across 5 categories (`DocumentCategory`: financial_statement/form_56_1/form_56_2/key_financial_ratio/mda). Company resolver (`resolve_company` → 10-digit uniqueIDReference); listing replays the ASP.NET WebForms search (GET `__VIEWSTATE` → form POST → stdlib HTML-table parse), follows ViewMore for complete large sections; downloads return raw bytes (`DownloadedFile.save()`), concurrent `download_all`, soft-404 detection (dead links = HTML "file not found" under HTTP 200 → `FetchError`). Listing returns a **`SecDocumentList`** (since 0.24.0 a **Pydantic model** `{documents, accounting, reported_counts}` that still iterates/indexes/slices like the list it was — but `isinstance(x, list)` is now `False`) with `years_by_category()`/`available_years()`/`filter(category=,year=)`/`categories()`/`summary()` helpers — pass a **wide** date window to see full year history. `SecCompany("CPALL")` facade; `get_sec_documents()`/`download_sec_document(s)()`. dd/mm/yyyy dates. Stateless host (no SessionManager). **Bilingual** — `lang="th"` returns the Thai-language filing documents (different files from the English ones), with Buddhist-era years/dates normalized to C.E. in the model; free-text cells stay in the page's language. `SecDocumentList.reported_counts`/`completeness()` carry what the site said each section holds, and an unclassifiable page raises `ParseError` instead of returning `[]`. **Row/column accounting** (`docs.accounting`: `no_link`/`placeholders`/`navigation`/`unmapped_headers`/`unverifiable_sections`/`by_category`, computed totals) makes every drop visible in the return value; a **total** loss raises `IncompleteListingError`, a partial one warns; a section whose ViewMore page failed lands on `accounting.degraded_sections` and sets `has_losses`. `download_all` returns a `DownloadResult` (a Pydantic model `{files, failed, requested}` + computed `is_complete`) carrying `.failed`. **Transport guards** on every listing leg (non-2xx → `HTTPStatusError`, non-listing body → `ParseError`); **per-code isolation** so one failing `ddlReportType` keeps its siblings' documents and records a `CodeFailure` on `accounting.failed_codes`. |

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
info = await stock.get_info()              # live quote block: sign, price, depth (never cached)
signs = await stock.get_signs()            # ['SP', 'NC'] — trading signs, any security type
halted = await stock.is_suspended()        # True when the SP sign is active
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

## Deprecation policy (from 0.24.0)

Anything public that is **removed or changes behaviour** emits a `DeprecationWarning` for **at
least one full minor release** first, naming the replacement and the release it will change in.

0.24.0 is the last release exempt: its breaks are the ones the fault-injection audit forced, and
they are documented in the CHANGELOG's **Data completeness advisory** and **Migration** sections
instead. Everything after it gets the warning period.

A `DeprecationWarning` is part of the **L1 surface** — `tests/golden/api_surface.json` records it,
so *removing the warning* is itself the breaking change and the golden diff shows it. That is what
stops a deprecation being announced and then quietly skipped.

## Dependency policy

How dependencies are constrained, upgraded, and verified. (Established with the 0.19.2
dependency refresh; the enforcement tests it references live in `tests/`.)

- **Constraint style:** `>=` floors only, no upper caps. A floor is raised ONLY for a proven
  incompatibility with the old bound; a cap is added ONLY with evidence that the next major
  breaks settfex (justify either in `CHANGELOG.md`). Upgrades move `uv.lock`, not the floors.
- **Cadence & detection:** Dependabot proposes bumps weekly; the `dependency-drift.yml`
  workflow posts a monthly whole-picture outdated report as a standing issue. `uv lock --check`
  in CI fails any commit whose lock is stale vs `pyproject.toml`.
- **Upgrade protocol:** one package per commit — `uv lock --upgrade-package <name>==<target>`,
  then the full gates (`pytest`, `ruff check`, `ruff format --check`, `mypy settfex/`); the lock
  diff must move only the named package + its dependency closure, enumerated in the commit body.
  Never batch a major bump with anything else. Read the upstream release notes before bumping.
- **Backward compatibility = 4 levels, all enforced:**
  - **L1 API surface** — no removed/renamed exports, changed signatures, or changed exception
    MROs. Enforced by `tests/test_public_api_surface.py` vs `tests/golden/api_surface.json`.
  - **L2 resolution** — `requires-python >= 3.11` and dependency floors unchanged.
  - **L3 behavior** — Pydantic field names/types/optionality/aliases and
    `model_dump(mode="json")` output unchanged. Enforced by `tests/test_model_contract.py`
    vs `tests/golden/model_contract/`.
  - **L4 runtime** — live SET/TFEX/ThaiBMA calls still succeed:
    `uv run pytest -m integration --no-cov`.
- **curl_cffi bumps REQUIRE the live-probe protocol** — a green unit suite is not evidence
  (HTTP is mocked; the failure mode is a TLS-fingerprint/impersonate change that only the real
  Incapsula origins can reveal). Run the integration probes before and after with
  `SETTFEX_PROBE_DIR=tmp/live_{before,after} SETTFEX_PROBE_CLEAR_CACHE=1` and diff the shapes;
  `tests/test_impersonate_target.py` additionally pins every shipped impersonate default to the
  installed curl_cffi's accepted-target enumeration.
  - **Reading the diff (learned the hard way on 0.16.3, 2026-09-19):** diff the **shapes** — added
    or removed fields, and fields that newly went null. On a **closed market** (any weekend or Thai
    holiday) SET serves a *frozen* snapshot, so the before/after payloads come back **byte-identical
    in value**, `marketDateTime` included. That looks exactly like a cache replay and is not one —
    do not conclude either "clean" or "broken" from value equality. Likewise a big runtime drop
    between the two runs (18 s → 3 s was observed) is Python bytecode warmup after `uv sync`, not
    the network.
  - **The decisive check is a cold-cache fetch, not the probe diff.** `SETTFEX_PROBE_CLEAR_CACHE=1`
    clears the SessionManager singletons and the on-disk cache, but nothing in the probe output
    *proves* it did. Confirm separately: `rm -rf ~/.settfex/cache`, then one live `get_*()` call. If
    it returns 200, a genuinely fresh TLS handshake was accepted by Incapsula with no cached cookie
    to hide behind — that, not the shape diff, is what clears a fingerprint change. (0.16.3 shipped
    one: upstream PR #833, *"fix tls_signed_cert_timestamps not applied"*.)
  - `test_live_set_holidays` fails transiently with a bare HTTP 401 by design (see the holiday
    gotchas below) — re-run it alone before reading it as a curl_cffi regression.
- **Golden files are gates, not fixtures:** never regenerate `tests/golden/**` to make a
  dependency bump pass — a diff there IS the finding. Regenerate only for an intended, reviewed
  surface/behavior change (`--regen` entry points in the two test modules).
- **Hand-pinned, Dependabot-invisible spots:** the setup-uv `version:` input (all workflows) and
  ruff (server-side-ignored; bump lock + `.pre-commit-config.yaml` rev in lockstep, keep
  `extend-exclude = ["*.md"]`). The monthly drift report watches all three: it compares the uv
  pin against the latest uv release, reports ruff staleness in the outdated table, and checks
  that the lock and the pre-commit rev still agree. (Until 2026-09-19 it only *said* it watched
  the uv pin — it printed the pin as a hardcoded literal and compared it to nothing, which is
  how 0.11.33 sat 53 days behind uv 0.12.)

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
- **SEC listings are BILINGUAL now, and the Thai page is not a translation of the English one:** `lang="th"` used to return an empty list for every issuer — `category_for_section` probed English substrings only, so every Thai heading fell through to `None` and `row_to_document` dropped the row at its first statement, with no exception, no warning and no DEBUG line (issue #123, fixed 2026-09-19). Classification and the header map are now bilingual and the Thai half is an exact **mirror** of the English half — same fields, no more and no fewer — so the same query in either language yields the same documents. Two live traps if you touch `_section_disposition`: (1) **order is load-bearing** — the Thai heading for statements *being revised* (`งบการเงินที่อยู่ระหว่างการแก้ไข`) **contains** the heading for financial statements (`งบการเงิน`) as a prefix, so the skip tokens must be tested first or every amended-statement section files under `FINANCIAL_STATEMENT`; (2) `รายละเอียด` is **one Thai word for three English headers** (Details/Link/Description) and appears **twice in one header row** on the ordered-to-amend table — all three are unmapped in English, so "no entry" is right in all three places. **Do not add it to `_HEADER_FIELD_MAP`.**
- **Thai SEC cells carry BUDDHIST-ERA years, and the conversion keys on the VALUE not on `lang`:** the Thai pages state `2568`/`30/06/2568`; `parse_year` and `parse_dmy_date` subtract 543 for any year `>= 2400` and normalize Thai numerals (`๒๕๖๘`) first. Keying on the requested language would be wrong — the **English** pages serve Thai cell values too (`งบรวม`, `3 เดือน`). This was *masked* before the fix: Thai rows died before their cells were read, so a partial fix (header map without era handling) would have turned an empty list into silent `2568 → 2568 CE` corruption, which is far harder to notice. **`parse_int` is deliberately left pure** — a `+543` rule hidden inside something named "parse_int" is a trap for the next caller. If another service ever needs B.E. handling, move `to_christian_year`/`normalize_thai_digits` to `settfex/utils/parsing.py`; SEC is the only consumer today.
- **`lang` selects the DOCUMENT language, not just the page's:** the Thai and English listings link to **different files** for the same filing — every MD&A pdf and most FS zips exist in both editions with distinct FILEIDs (generated seconds apart), while IPOS-hosted rows (`IPOSGetFile.aspx`) are shared. A cross-language `file_url` equality assertion is therefore wrong, and an archiver that switches to `lang="th"` downloads different artifacts (usually the point). Tests pin this so it is not "fixed".
- **~~`Receive Date` has no Thai mapping~~ — CLOSED 2026-09-21, the header was captured:** until then the corpus behind the Thai support was FS searches only, so the Thai spelling of the 56-1/56-2 `Receive Date` column was never observed and a guess was refused; a Thai 56-1/56-2 listing yielded `receive_date=None` while every other field populated — and for an annual report that is the only filing timestamp the model exposes (11 dates lost across 2 issuers × 2 forms). The header is `วันที่ได้รับข้อมูล`, observed 2026-09-21 in the **same column position** as the English one, and is mapped (issue #127 P4). Era handling already existed, so `12/03/2569` → `2026-03-12`, exactly what the English page yields. It does **not** collide with `วันที่` → `as_of`: the lookup is on the whole header, not a prefix.
- **An unclassifiable SEC page RAISES now (`ParseError`), where it used to return `[]`:** if a results page carries data rows and **none** of them maps to a known section, `_map_rows` raises `ParseError` (a `FetchError` subclass, so existing `except FetchError` handlers keep working) naming the unrecognised headings. Rows skipped *by design* (the revision-tracking sections) and pages with no rows at all still return `[]` and never raise — the raise keys on unrecognised headings, not on emptiness, which is what keeps a genuine "this issuer filed nothing" quiet. Partial losses log a `warning`; every page logs a `debug` breadcrumb with rows/mapped/skipped/no-link/unknown counts.
- **A SEC `FS` search returns three categories at once:** querying `ddlReportType=FS` returns financial statements **+** Key Financial Ratio **+** MD&A sections in one HTML response (each its own table); large sections truncate inline and expose a `ViewMore/{fs-norm|fs-kf|fs-mda}` link the listing follows (`follow_view_more=True`). MD&A rows use different columns (Date/Time/Heading/Link, no Name) — the mapper fills `company_name` from the resolved company as a fallback.
- **`DocumentCategory` is a `StrEnum`, deliberately — do not "restore" `(str, Enum)`:** ruff 0.15+ rejects the `(str, Enum)` pattern via `UP042`. As a `StrEnum`, `str(cat)` / `f"{cat}"` give the bare value (`"financial_statement"`), **not** `"DocumentCategory.FINANCIAL_STATEMENT"` — use `cat.name` or `repr(cat)` if you need the qualified form. Equality with the plain string, `.value`, JSON output and all `SecDocumentList` helpers are unaffected (tests guard this). Note `years_by_category()` keys on `.value` on purpose, which is why `summary()` never depended on the enum's `__str__`.
- **The uv version in CI is pinned by hand — Dependabot will not bump it:** all eight `astral-sh/setup-uv` steps (`ci.yml` ×2, `release.yml` ×2, `security.yml` ×2, `dependency-drift.yml` ×1, `pre-commit.yml` ×1) pass `version: "0.12.17"` instead of `"latest"`, so a uv release cannot silently change a build (this matters most in `release.yml`, which builds the published artifact). Dependabot's `github-actions` ecosystem bumps the *action ref*, never an action *input*, so this pin only moves when someone edits it — the monthly drift report flags it against the latest uv release (and flags the seven steps disagreeing with each other), but flagging is all it does. Note pinning does **not** make setup-uv network-free: on a GitHub-hosted runner uv is not in the tool cache, so `getArtifact` still fetches `raw.githubusercontent.com/astral-sh/versions` for the download URL — a fetch that has been observed to fail transiently. Re-run the job when it does. (Bumped 0.11.33 → 0.12.17 on 2026-09-19. uv 0.12 is a **breaking** minor line — PEP 625 sdist formats and some wheel entry points are now rejected, *including when referenced by an existing lockfile* — so the pin was moved only after running every uv command CI runs against the real tree: `lock --check` (the lock is accepted unchanged), `sync --frozen`, the four gates, `run python -m build` + the py.typed wheel assertion, bandit and pip-audit. A green unit suite alone would not have covered the release path.)
- **Ruff is UNFROZEN (since 2026-08-31, at 0.16.5; the live pin is `uv.lock` + `.pre-commit-config.yaml`, not this sentence) — Markdown is permanently excluded via `extend-exclude = ["*.md"]`:** ruff 0.16+ formats Python code blocks inside Markdown by default, which would collapse the intentionally column-aligned inline comments in ~40 doc files (`CLAUDE.md`, `README.md`, `AGENTS.md`, `docs/`) — the reason ruff was frozen at 0.13.2 from 2026-08-25 to 2026-08-31 (Dependabot bumps rejected 3×: #61 → #78 → #88). The freeze's deferred question was settled by the `extend-exclude = ["*.md"]` line under `[tool.ruff]`: it preserves pre-0.16 behavior byte-identically (0.13.2 never touched `.md`), so **do not remove it** when tidying config. A ruff bump is a **2-place change**: the dev-group lock (`uv lock -P ruff==X`) and the `rev:` in `.pre-commit-config.yaml` — keep them in lockstep. Note Dependabot STILL never proposes ruff bumps (the `@dependabot ignore` from PR #88 lives in Dependabot's server-side state and was deliberately left in place); the monthly dependency-drift workflow reports ruff staleness instead, and bumps are applied by hand. That report also checks the two places agree, because a half-applied 2-place change fails nothing on its own.
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
- **pandas 3 changed what `to_dataframe()` returns for missing values — and the library supports BOTH majors (`pandas>=2.0.0`), so the same call differs by install:** on pandas 3 a string column is typed `str` and a missing value is **`NaN`**; on pandas 2 it was `object` and **`None`**. `value is None` therefore silently stops matching — **`pd.isna(value)` is the only portable check** (two tests were pinned on `is None` and went red on the 3.0.5 bump; they now use `pd.isna`). Two further differences found by differencing the two majors on the same fixture: tz-aware datetime columns move `datetime64[ns, +07:00]` → `datetime64[us, +07:00]` (**no test caught this** — resolution, not values), and `NaN` is **invalid strict JSON**, so `json.dumps(df.to_dict("records"))` now emits a bare `NaN` token that Python's tolerant loader accepts but `JSON.parse` and other strict parsers reject — use `df.to_json()`, which correctly writes `null`. **`df.attrs` survives** copy, column selection and `head()` on pandas 3, so the year metadata on the analyst-consensus frames is safe. pyarrow is **not** required by pandas 3 — the `str` dtype falls back to a numpy object store.
- **The stock LIST has no trading-sign field — `remark` is empty on every row:** live-probed 2026-09-19, all **3,954** rows of `/api/set/stock/list` return `remark: ""` and the payload has **no `sign` key at all**. `StockSymbol.remark` looks like the natural place for SP/NC/NP and never carries it; the list is a static directory (name/market/industry/sector/securityType), not trading state. The sign lives on `/api/set/stock/{sym}/info` (per symbol, every security type) and on index-composition rows (`IndexConstituent.sign`, common stocks only). Note the list payload also carries an `oldSymbols` key that `StockSymbol` does not model — reachable via `fetch_stock_list_raw()`.
- **SET's `sign` packs MULTIPLE codes into ONE comma-separated string — `sign == "SP"` is a bug:** real values include `"SP, NC"`, `"SP, CB, CS"` and `"SP, CB, CS, CC"`; only 1 of the 28 suspended stocks on 2026-09-19 had a bare `"SP"`. Use `StockInfo.signs` / `has_sign()` / `is_suspended`, or the module-level `parse_signs()` on a raw composition row. `parse_signs` also uppercases and drops empty segments, so `"sp, , nc"` → `['SP', 'NC']`.
- **`market_status` is NOT a suspension flag:** it reads `'Closed'` for every symbol outside trading hours, so a suspended symbol looks identical to a normal one after 16:30. `StockInfo.is_suspended` deliberately reads the per-symbol **sign**, never `market_status` (a test pins both directions). A halted symbol also answers HTTP 200 with `last`/OHLC/volume all `null` and an empty book — data, not an error; use `prior` for its last known price.
- **SET's INDUSTRY-level index compositions return ZERO constituents — mai's `-m` ones do not:** live-probed 2026-09-19, `AGRO`, `CONSUMP`, `FINCIAL`, `INDUS`, `PROPCON`, `RESOURC`, `SERVICE` and `TECH` all return `stockInfos: []` (HTTP 200, no error), while `AGRO-m`…`TECH-m` return their real members. A market-wide scan must therefore use **SECTOR** for SET + **`-m` INDUSTRY** for mai — 36 requests covering 929 symbols, which is exactly the 929 `securityType == 'S'` common stocks in the stock list. (`MINE` is a genuinely empty sector; do not treat an empty composition as a failure.)
- **The composition route reaches COMMON STOCKS ONLY — count companies, not securities:** on 2026-09-18 SET's own Sign Posting page reported SP on 18 SET + 10 mai **companies** (28) and 40 + 13 **securities** (53). The sector scan returns exactly those 28; the other 25 are the warrant, `-F` and `-P`/`-Q` lines of the same issuers, reachable only one-by-one via `get_stock_info()`. A "suspended symbols" list built from compositions is therefore complete for stocks and silently missing every warrant/DW/DR.
- **The stock-info endpoint has NO language dimension, and its timestamp is nanosecond-precision:** `?lang=en` and `?lang=th` return byte-identical payloads (both `nameEN` and `nameTH` always present), so `fetch_stock_info()` deliberately takes **no** `lang` argument — do not add one "for consistency" (same shape as the analyst-consensus table endpoint). Separately, `marketDateTime` carries **9 fractional digits** (`...783886192+07:00`) — unique among the SET endpoints here; pydantic and `datetime.fromisoformat` both truncate to microseconds on 3.11+, and a test pins that it is truncated rather than rejected.
- **Over plain HTTP the quote block serves the BEST bid/offer level only:** `bids`/`offers` come back with one entry each, not the 5-level ladder shown on the set.or.th page (that depth is websocket-fed). Ladder `price` arrives as a **string** (`"44.75"`) and is coerced by the shared `BidOffer` model, which `stock/info.py` imports from `index/composition.py` rather than duplicating.
- **A stock-info 404 means "unknown symbol" — unlike the DR-profile 404:** `/api/set/stock/{sym}/info` answers an unknown ticker with HTTP 404 `{"message": "Invalid Stock Name"}` and resolves every real one, so `SymbolNotFoundError` is raised **with** the "did you mean?" suggester enabled (the opposite of `/api/set/dr/{sym}/profile`, which 404s for valid non-DRs and must pass `suggest=False`).
- **The session cache dir is forced to `0700`, and a caller-supplied one is deliberately NOT — do not "make it consistent":** `diskcache` reads cached values back with **pickle**, so write access to `~/.settfex/cache` is code execution in the caller's process (CVE-2025-69872 / PYSEC-2026-2447 — **no fixed release**, upstream's last release was 2023; it is the only advisory `pip-audit` still reports and the only one on a *runtime* dependency). `_secure_cache_dir()` therefore creates the directory `0700` and **chmods an existing default one in place** (a real side effect on the user's filesystem, logged at INFO). A directory the caller passed is created `0700` when new but, if it already exists group/other-writable, is **reported and left alone** — a shared cache can be deliberate, and silently breaking a multi-account layout is worse than the warning. Windows is skipped outright (POSIX bits do not express this), and every permission step is inside `try/except OSError` because a cache that cannot be chmod'd is still a usable cache. Tests pin all four behaviours in `tests/utils/test_session_cache.py`.
- **SEC serves FOUR download-URL shapes; two of them were silently dropping live filings:** `classify_download_href` knew `Download?FILEID=<path>` and `ipos/Common/IPOSGetFile.aspx?id=`. **Key Financial Ratio** rows use two more, and both fell through to "not a download link" and made the row vanish — live-probed 2026-09-20 on CPALL, both real downloads: (1) recent rows (2026 Q1/Q2) link through `/public/idisc/Views/FinancialStatementDownload?query=<opaque base64>`, answering `application/zip` — a **134 KB zip of the real PDFs**; (2) older rows (2018, 2019) link through `/public/idisc/views/viewdoc?…&TransId=<id>&FileSeq=<n>`, answering `application/.tif` — a **36 KB scan of the original**. Mapped now as `file_id="fsdl:<blob>"` / `"viewdoc:<id>-<n>"`, both `file_kind=None` (neither URL states a type; `Content-Disposition` names the file at download time). After the fix, CPALL 2015-2026 returns **177 documents with `completeness()` exact in all five categories** — `key_financial_ratio` was `(13, 15)`. ⚠️ **Three things this should teach the next reader.** (a) **It falsifies the reporting issue's own finding:** its corpus scan of 39 captured pages found *zero* natural instances of a dropped row and stated P1 "has not been observed in the wild"; the first two live runs of the new accounting found four. A captured corpus can only show what was captured. (b) **The window is load-bearing:** a narrow recent window passed clean while the 2018/2019 rows were being dropped — **old filings use old URL shapes**, so a probe that only checks recent data cannot see them. (c) **Do NOT generalise the allowlist** into "any link under /public/idisc/ with a query is a download": the "display all results" ViewMore link has exactly that shape, and would become a phantom filing in every truncated section. Expect the list to grow; `ListingAccounting.no_link` is the mechanism that makes the next one visible, and a test pins the ViewMore link as not-a-download. Note `_fallback_filename` keys on the **colon**, not on an `ipos:` prefix: a real FILEID path never contains one, so every synthetic id is safely excluded from being sliced like a path.
- **The SEC LISTING path checks its HTTP status now — and a ViewMore failure DEGRADES rather than raising (issue #131):** `_run_search` used to return `post_resp.text` without ever reading `status_code`, so an error page parsed to zero rows and came back as `[]` with `has_losses == False` — indistinguishable from an issuer that filed nothing, and intermittent, so a backfill recorded the window as covered. Evidenced by a real **HTTP 505** from the listing host (2026-09-20). Two rules: non-2xx → `FetchError`; a 2xx body with **no result table and no section heading** → `ParseError`. The content rule is deliberately the weakest one that separates the populations, because the case it must never trip is a **genuinely empty listing** — a test pins it against every page this repo holds. It does **not** key on `ctl00_CPH_pnlControl`: the real ViewMore capture has that id and the trimmed `FS_VIEWMORE_HTML` constant does not, so a panel-id rule would call a legitimate page an error. ⚠️ **The severity ladder differs by leg, on purpose.** The POST leg raises (a total loss — nothing to fall back on). A **ViewMore** page is different: it *replaces* its section's inline rows, so 0.22.0's unconditional replacement meant a failing page **deleted the whole section, inline rows included, in silence**. A broken ViewMore is a *partial* loss, so it now keeps the inline rows, warns, and lets `completeness()` show the shortfall. `_map_rows` additionally refuses a **zero-row** input: within this package that can only be a non-listing body, since every captured page carries at least the placeholder row an empty section serves.
- **The live Thai `fs-kf` ViewMore page has been answering HTTP 500 since at least 2026-09-20 — an UPSTREAM bug, and it is why the degrade path exists:** probed 3× each, `th/fs-kf` returned 500 every time while `th/fs-norm`, `th/fs-mda` and all three `en/*` returned 200. On 0.22.0 this silently removed CPALL's entire Thai Key Financial Ratio section; now the listing returns 177 documents with `key_financial_ratio: (10, 15)` stated in `completeness()` plus two WARNINGs. **If you see a Thai KFR shortfall, check whether SEC has fixed their page before looking in settfex.**
- **~~`fs-r561` is an UNMAPPED ViewMore slug~~ — CLOSED in 0.22.2, and `fs-r562` with it:** `_CATEGORY_FOR_VIEWMORE_SLUG` used to map only `fs-norm`/`fs-kf`/`fs-mda`, the three sections one `FS` search returns, so a **56-1 or 56-2** section over the site's ~10-row inline cap truncated **even with `follow_view_more=True`**. 0.22.0's notes predicted it and said the shortfall WARNING would surface it — it did, reported by a downstream consumer reading `completeness()`. Both slugs were **live-probed, never guessed** (2026-09-20, CPALL/PTT/SCB × th/en), and the scale was larger than first reported: over a 2000-2026 window CPALL th 56-1 served **11 of 23**, PTT th 56-1 **11 of 25**, PTT 56-2 **10 of 15 in BOTH languages** — so it was never a Thai-only gap. Now 23/23, 25/25, 15/15, 15/15. ⚠️ **The `fs-` prefix is the site's own and is NOT a category hint** — `fs-r561` is served by the *56-1* search, not the FS one; a mapping keyed on the prefix would be wrong. Two surfaces state this fact: `_CATEGORY_FOR_VIEWMORE_SLUG` (used) and the public `SEC_VIEWMORE_SLUGS` in `constants.py` (**used nowhere**, so nothing would notice it going stale) — a test pins them equal.
- **SEC's old-format filings are on a FIFTH host and behind a JavaScript indirection (issue #133):** `capital.sec.or.th/…/get_zip_all_public_page.php` carries pre-2014 `.DOC`/`.XLS` filings. The URL answers **HTTP 200 with a 2 KB HTML page whose entire body is `document.location = '/tmp/<id>.zip'`** — so recognising the link is necessary but not sufficient, and `download()` resolves the redirect at download time (one extra request). Three properties the code depends on: the target is **minted per request** (`XP`/`sD`/`V1` for the same filing across three captures), so `file_url` stays the stable indirection URL and the `/tmp/…` one is never stored; it is **per-language** (the Thai request mints a different archive, so `lang` is part of the `capfin:<comp_id>-<year>-<period>-<lang>` id); and `comp_id` is a **different id space from `set_id`** in the same query — they are not interchangeable. The redirect pattern accepts an absolute URL on purpose, so the same-host check is live rather than dead code.
- **These old-format zips are MEMBER-STABLE, not byte-stable — do not key an archive on the container hash:** re-minting the same filing produced a different container sha256 while every member payload stayed byte-identical. Exactly **12 bytes of 334,498** differ, in four 3-byte runs, one per member: the Info-ZIP extended-timestamp (`UT`) extra field, i.e. the pack time. **Judge integrity per member.** A consumer that hashes the container will see a legitimate re-fetch as a new — or corrupted — object. (Also observed: one sample's embedded pack time *predated* the request that minted it, suggesting the server sometimes hands back a previously generated archive. INFERRED from two samples.)
- **~~`DownloadResult` loses `.failed` the moment you derive a new list~~ — CLOSED in 0.24.0 (issue #134), and the fix has one silent cost:** `.failed`/`.requested`/`.is_complete` were instance attributes on a `list` subclass, so slicing, `sorted()`, `list()`, concatenation and comprehensions all returned a plain `list` without them — 6 of 7 ordinary operations. Both containers are **Pydantic models** now, so the report is a *field*: it survives `model_dump()`, JSON and every boundary an agent or a pipeline crosses, which is the real reason a model was chosen (function-calling results are JSON, so an unserialized signal does not exist at the tool boundary). `is_complete` is a **computed field** for the same reason. ⚠️ **`isinstance(x, list)` is now `False`, and that is the one break that fails *silently*** — it takes the other branch rather than raising. Everything else is kept: `len()`, `bool()`, iteration, integer indexing, `in`, and **slicing, which returns a model**. `sorted()`/`list()` still yield plain lists because iteration is kept — sort `docs.documents` / `files.files`. `dict(model)` now raises; use `model_dump()`.
- **One failing report code no longer discards the others — and `has_losses` is now the only reliable "was it complete?" check:** `fetch_documents` collapses the requested categories to up to three `ddlReportType` codes run concurrently; the gather had no `return_exceptions=True`, so the first exception propagated before the collecting line ran and a total loss in `R562` threw away the `FS` documents that had parsed fine (issue #132). Now: **partial loss reports, total loss raises** — one code failing keeps its siblings' documents and records a `CodeFailure` on `accounting.failed_codes`; every code failing re-raises the first cause with its type and traceback intact. ⚠️ **Anything that is not a `FetchError` propagates untouched** — a settfex bug must not be laundered into an accounting row, where it would be buried in a field most callers never read. ⚠️ **Deliberately NOT an `ExceptionGroup`** despite the 3.11+ floor: `except FetchError` does not catch one, so it would silently break every existing handler. When every code fails, the other causes ride along as **PEP 678 notes** (`exc.add_note`) on the raised one — otherwise re-raising a single exception would quietly drop them, breaking the rule that a caller can always tell which code failed and why. **"First" means first in report-code order, not first to fail in time** (`gather` returns positionally), so the raised cause is deterministic across runs; a test pins that by making the last code fail instantly while the first yields 20 times. ⚠️ **Upgrade trap:** a `try/except FetchError` that treated "no exception" as "complete" now sees a partial result as a whole one — check `has_losses` / `failed_codes`. The same `return_exceptions` treatment was applied to the ViewMore gather, so a transport error there costs one section's completeness rather than the call.
- **`unlinked_hrefs` is sampled for DIVERSITY, not "the first 20" — and that is the whole point:** `RowTally.unlinked_hrefs` keeps a capped sample of the hrefs behind `no_link`, because every unknown download shape so far (`fsdl`, `viewdoc`, `capfin`) was found by a human looking at a dropped row's URL, and each time that meant re-parsing the page by hand. The sampler takes **one href per distinct `(host, path)` first**, then fills to the cap of 20 — so thirty instances of an already-known shape can never crowd out the single instance of a new one, which is exactly the row worth seeing. `no_link` stays the true total, and `plus()` **re-samples** on merge rather than concatenating, or a merge could exceed the cap or lose the property the sample exists for.
- **`IncompleteListingError` could not carry `unknown_sections` until 0.23.0 — a field that looked answered and was not:** it is inherited from `ParseError`, but the subclass's `__init__` never accepted it, so it was **always `[]`**. Anyone who inspected it concluded "no unrecognised headings" from a value that had never been populated. Fixed by accepting and forwarding it; a page can lose every row to a missing link *and* carry a heading nobody recognises.
- **A SLICE of a `SecDocumentList` carries the accounting of the WHOLE CALL, not of the slice** — deliberate, and the one thing about the 0.24.0 redesign that is not guessable: `docs[0:0]` still reports the rows the *listing* lost. It is the rule `filter()` has followed since 0.22.0 — narrowing a result must never hide a loss from exactly the caller who narrowed it — and `reported_counts` behaves the same way (a `year` filter does not narrow it, because it describes what the **site** said each section holds, which no client-side filter can change). The failed-code WARNING that existed because "a log line cannot be sliced away" is kept even though slicing no longer drops anything: it is now redundancy rather than the only carrier.
- **`no_href` was three different things, and only one is a defect:** a dropped SEC listing row is a `ไม่พบข้อมูล`/`Data not found` **placeholder** (the site saying the section is empty), a "display all results" **ViewMore navigation row** (how a long section truncates — 24% of live sections), or a **real data row whose download link is gone** (`no_link`). They shared one counter, which is why P1 could not be escalated: any rule strict enough to catch a genuine loss also fired on every truncated section. Split (`ListingAccounting.placeholders`/`navigation`/`no_link`), `no_link` is **0 on every real page captured** and non-zero only on a page derived to exhibit the bug — so it can be escalated without a record-count marker at all. `_MapResult.no_href` is kept as the sum of the three; **branch on `accounting.no_link`, never on `no_href`** (it is non-zero on perfectly healthy pages).
- **Two cross-checks on a SEC listing, and they answer different questions:** `completeness()`/`reported_counts` compares what you hold against **the number the site printed** — a shortfall there is usually legitimate "view more" truncation, so it is reported and never raised. `docs.accounting` is **ours**: what the parser did with each row it received. A shortfall is a maybe; `accounting.no_link > 0` is always a loss. Do not fold one into the other.
- **`IncompleteListingError` fires only on a TOTAL loss:** rows classified fine and *every* usable one was dropped for want of a download link. A **partial** loss warns and lands on `accounting.no_link` instead — raising there would turn one bad row in a 200-row listing into no listing at all, and unlike a total loss a partial one is visible in the return value. Same severity ladder as the 0.21.0 `ParseError` for unrecognised headings, and it is a `ParseError` subclass so `except ParseError`/`except FetchError` keep working. The escalation is scoped to the **requested** categories (a single `FS` search returns three sections) — the same principle PR #125 applied to `completeness()`.
- **An unmapped COLUMN is reported, never raised — and the ignore-list is 5 entries, not 13:** the issue that reported this measured "100% of sections carry an unmapped header", but that count includes the revision-tracking sections, **whose rows are skipped before a single cell is read**. Restricted to sections actually read, the whole corpus serves exactly six unmapped headers, five of which have no model field (`Details`, `รายละเอียด`, `Link`, `Time`, `เวลา` → `_IGNORED_HEADERS`) and the sixth was the real loss (`วันที่ได้รับข้อมูล`, now mapped). So the corpus is 100% clean and the first header this check ever names will be a genuine site change. It **warns**, because an unmodelled column is "the site has more than we model", not lost data — raising would turn a cosmetic change into an outage. Do **not** add the revision-section headers (`Order Date`, `Company Name`, `ชื่อบริษัท`, …) to the ignore-list: they never reach the check, and listing them would make it look broader than it is.
- **`download_all` returns a `DownloadResult`, not a bare list — a partial batch used to be shaped like a complete one:** with `continue_on_error=True` (still the default) a failure became `None` and was filtered out, so the difference between "I downloaded the filings" and "I downloaded some of the filings" existed only in a log line. `DownloadResult` **is** a `list[DownloadedFile]` (same trick as `SecDocumentList`), so `len()`/iteration/indexing/pass-through are unchanged; it additionally carries `.failed` (target, source document, error, error type), `.requested` and `.is_complete`. `continue_on_error=False` still propagates the first failure.
- **The SEC listing summary log is derived from the accounting, and its LEVEL is load-bearing:** `Listed 0 SEC document(s)` used to be the same sentence at the same level as a complete success, with the contradicting number already in scope three lines above. Now: a lossy parse → WARNING; a shortfall **with** `follow_view_more=True` → WARNING (the ViewMore page should have returned the section in full, so nothing is left to explain the gap); a shortfall with `follow_view_more=False` → INFO (that truncation is what the caller asked for — warning about it trains people to ignore warnings). This WARNING is not theoretical: it is what surfaced the unmapped `fs-r561`/`fs-r562` slugs (closed in 0.22.2, see above) — a downstream consumer read the shortfall out of `completeness()` and reported it.
- **`Stock.get_latest_price()` is DR-aware by default:** for DRs it returns a `DrIndicativeQuotation` (TradingView indicative price; `volume`/`change` are `None` — it's a fair value, not a SET trade) and falls back to SET chart data on ANY TradingView failure. The switch only applies when `as_of is None` (TV can't answer historical instants); opt out per-call with `prefer_dr_indicative=False`. DR-ness is detected by one cached DR-profile probe per `Stock` instance (a 404 marks non-DR permanently for that instance; transient errors are never cached). Indicative vs SET-close divergence is EXPECTED (probe: 5.94 indicative vs 5.75 SET close after a US-session move) — not a bug.

---

*This file should be kept up-to-date as the project evolves.*
