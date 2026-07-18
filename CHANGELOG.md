# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.10.1] - 2026-07-18

### Fixed

- **Company Profile: tolerate `startDate: null` on management entries.** SET reports a vacant or
  undisclosed executive seat with `"startDate": null` (and an empty `name`) — e.g. `VIBE` lists
  its top finance-responsibility position that way — so `fetch_company_profile()` raised a
  `ValidationError` (`Management.start_date` was a required `datetime`). It is now
  `datetime | None`. Every prior release (0.1.0–0.10.0) is affected; upgrading is the fix.

## [0.10.0] - 2026-07-17

### Added

- **"Did you mean?" suggestions on `SymbolNotFoundError`**: a mistyped SET stock symbol now carries
  a `.suggestion` attribute (the closest known symbol, via stdlib `difflib`) that agents can read
  programmatically, and the hint is appended to the error message (e.g. `… HTTP 404 — did you mean
  'CPALL'?`). Also exposes a `suggest_symbol()` helper. The suggestion is computed **network-free**:
  it only consults the stock list already fetched earlier in the session (`get_stock_list()`), so a
  404 never triggers an extra fetch, and `.suggestion` is `None` when no list has been fetched yet.
  Index lookups are excluded from stock-symbol matching (`raise_for_status(..., suggest=False)`).

## [0.9.0] - 2026-07-17

### Added

- **Typed exception hierarchy** (`settfex.exceptions`, re-exported from the top-level `settfex`
  namespace): `FetchError` (carrying `status_code`/`symbol`), `SymbolNotFoundError` (HTTP 404),
  `InvalidSymbolError` and `InvalidLanguageError`. The validation errors subclass `ValueError` and
  the fetch errors subclass `Exception`, so existing `except ValueError`/`except Exception`
  handlers keep working. Adds a `Language` (`Literal["en", "th"]`) type alias.

### Changed

- Service calls now raise the typed exceptions above instead of bare `Exception`/`ValueError`
  (e.g. `except SymbolNotFoundError`); `board_of_director` list-shape errors now raise
  `ResponseParseError`, consistent with sibling services. **Backward-compatible at runtime.**
- **`lang`/`language` parameters are now typed `Literal["en", "th"]`** on all public entry points
  (`get_*`, `fetch_*`, `Stock.*`, `SetIndex.*`); `type_id` on the earnings-call APIs is now
  `Literal[1, 2, 3]`. This is a static-typing tightening only — `normalize_language()` stays
  internal and still accepts `eng`/`english`/`tha`/`thai` at runtime.
- Excluded `tests/` and `scripts/` (untyped helper code) from the strict `mypy` gate so
  `uv run mypy .` type-checks the shipped package.

## [0.8.0] - 2026-07-16

### Added

- **Market Index services** — a new `settfex.services.set.index` sub-package covering the
  SET index API (`/api/set/index/...`):
  - **Index directory** — `get_index_list()` / `IndexListService`: all 55 indices across three
    levels (headline `INDEX`: SET, SET50, SET50FF, SET100, SET100FF, sSET, SETCLMV, SETHD,
    SETESG, SETWB, mai; `INDUSTRY`; `SECTOR`), with `filter_by_market()`/`filter_by_level()`
    helpers and `get_index()` lookup that disambiguates the SET-vs-mai industry pairs
    (e.g. `AGRO` vs `AGRO-m`).
  - **Index quotation** — `get_index_info()` / `IndexInfoService`: the index page header data
    (last, change, %change, open/high/low, volume, value, market status, tz-aware timestamp);
    `get_index_info_list()` fetches all headline (or all industry/sector) quotes in one call.
  - **Index composition** — `get_index_composition()` / `IndexCompositionService`: the
    securities used to calculate an index, each with a full quote row (OHLC, change, best
    bid/offer — string prices coerced to float —, volume, value, market cap, P/E, P/B,
    dividend yield, 52-week range, NVDR net volume). SET industries return their sector
    drilldown in `sub_indices`; `SET`/`mai` raise a helpful error (no composition endpoint).
  - **Index chart quotation / latest value** — `get_index_chart_quotation()` and
    `get_index_latest_price()` reuse the stock chart-quotation models and latest-traded scan.
  - **`SetIndex` facade** — `SetIndex("SET50")` with `get_info()`, `get_composition()`,
    `get_constituents()`, `get_chart_quotation()`, `get_latest_price()`, mirroring `Stock`.
  - Index symbols preserve casing (`sSET`, `AGRO-m`); the API resolves paths case-insensitively.
- **Stock list index membership** — `StockSymbol.indices` lists each stock's headline
  sub-index memberships (e.g. CPALL → `['SET50', 'SET50FF', 'SET100', 'SET100FF', 'SETESG',
  'SETWB']`), plus a case-insensitive `StockListResponse.filter_by_index()`.
- Example notebook `examples/set/15_market_index.ipynb` and service documentation
  `docs/settfex/services/set/index.md`.

### Changed

- `get_stock_list()` / `StockListService.fetch_stock_list()` now enrich each stock with its
  index memberships **by default** (one index-directory request plus nine concurrent
  composition requests, ~10 extra requests total). Pass `include_indices=False` for the
  previous single-request behavior. Enrichment failures are logged and degrade to empty
  `indices` lists — they never fail the stock list call. `fetch_stock_list_raw()` is unchanged.

## [0.7.1] - 2026-06-21

### Fixed

- `get_latest_historical_trading`, `LatestHistoricalTrading`, and `LatestHistoricalTradingService`
  are now importable from the top-level `settfex.services.set` (previously only from
  `settfex.services.set.stock`) — the documented top-level import raised `ImportError` on 0.7.0.
- The README "Latest Historical Trading" example used the non-existent fields `pe_ratio` / `pb_ratio`;
  the model fields are `pe` / `pbv`.

### Added

- Documentation page and example notebook for the Latest Historical Trading service.

## [0.7.0] - 2026-06-21

### Added

- **Latest traded price for SET stocks** — on top of the existing chart-quotation service, a
  first-class way to get the most recent *traded* price relative to now. The SET intraday feed
  pre-populates the rest of the session with null/no-trade buckets; these are excluded
  automatically.
  - `get_latest_price(symbol, period="1D", accumulated=False, as_of=None) -> Quotation | None` —
    top-level convenience returning the latest traded quotation (time, price, volume, change), or
    `None` if nothing has traded yet.
  - `ChartQuotation.get_latest_quotation(as_of=None) -> Quotation | None` and
    `ChartQuotation.get_latest_price(as_of=None) -> float | None` (scalar, falls back to `prior`) —
    pure, timezone-safe selection in Asia/Bangkok; `as_of` defaults to now (naive values are
    treated as Bangkok local time).
  - `Stock.get_latest_price(period="1D", accumulated=False, as_of=None)` on the unified Stock class.
  - Hyphenated warrant symbols (e.g. `JAS-W4`) are preserved.
  - The chart-quotation models, service, and `get_chart_quotation` are now also exported from
    `settfex.services.set` (previously only from `settfex.services.set.stock`).

## [0.6.0] - 2026-06-19

### Added

- **Thai YouTube transcripts for earnings calls** (raw text for AI/LLM use), behind a new optional
  `transcript` extra (`pip install "settfex[transcript]"`, backed by `youtube-transcript-api`):
  - `fetch_youtube_transcript(video_id, *, languages=("th",), proxies=None) -> str | None` — a
    generic async wrapper that returns the caption text as one string, or `None` when the video has
    no matching captions / they're disabled / the request is blocked (never raises for those).
  - `fetch_transcripts(items, ...) -> list[EarningsCallItem]` — fills `EarningsCallItem.transcript`
    for every item that has a YouTube video (bounded concurrency, default 3; optional progress bar;
    per-item tolerant; items without a video are skipped).
  - `get_earnings_call_transcript(id, ...) -> str | None` — one presentation's transcript by id.
  - New `EarningsCallItem.transcript: str | None` field (populated only by the above).

## [0.5.0] - 2026-06-19

### Added

- **Concurrent `fetch_all_earnings_calls` + an optional progress bar.** Fetching the whole OPPDAY
  archive now fetches pages **concurrently** (bounded by `max_concurrency`, default 5) after
  learning the total from page 1, so the full ~9520-record crawl drops from **~150 s to ~15 s
  (~10× faster)** at the default concurrency. Opt into a `tqdm` progress bar with `progress=True`
  (new optional `progress` extra:
  `pip install "settfex[progress]"`), or pass a dependency-free `progress_callback(done, total)`;
  both also cover the `enrich=True` phase.
- **`get_all_earnings_calls(...)`** convenience — fetch the entire calendar in one concurrent call.

### Changed

- `fetch_all_earnings_calls` defaults: `page_size` 50 → 200 (fewer requests; the API does not cap
  `page_size`) and `throttle` 0.3 → 0.0 (the concurrency bound now governs load). Results and item
  ordering are unchanged.

## [0.4.1] - 2026-06-19

### Added

- **`get_earnings_call_detail(id)`** / `EarningsCallService.fetch_earnings_call_detail(id)` —
  fetch a single OPPDAY presentation directly by its id (the number in an opportunity-day
  `/vdo/{id}` URL), without going through a list + `enrich`.
- `EarningsCallDetail` now exposes derived **`youtube_video_id` / `youtube_url`** (built from the
  clean `image_path`) and strips stray whitespace from `video_link` — a few legacy records embed
  a newline mid-URL (e.g. `vdo/6319`); `image_path` was added to the model.

### Fixed

- **Earnings Call: tolerate `industry: null`.** The OPPDAY list returns `industry: null` for a
  handful of newly-listed companies (e.g. `ISTORE22`), so fetching deeper pages or a large
  `page_size` raised a `ValidationError` (`EarningsCallItem.industry` was a required string). It
  is now `str | None`. Note: `page_size` is **not** capped by the API — a single request can
  return the entire archive; an earlier doc note claiming a ~100 cap was incorrect and has been
  removed.

## [0.4.0] - 2026-06-19

### Added

- **SET Earnings Call (Opportunity Day) service** (`get_earnings_calls`,
  `get_earnings_calls_dataframe`, `EarningsCallService`, `EarningsCallItem`,
  `EarningsCallResponse`, `EarningsCallDetail`, `FilterOption`): fetches the SET
  "Earnings Call (OPPDAY)" calendar from the stateless opportunity-day backend
  (`POST https://api.lcp.setgroup.or.th/api/v1/investor/search/archive`). Returns typed
  Pydantic models with derived `company_name_clean` / `youtube_video_id` / `youtube_url`
  fields, plus an optional pandas DataFrame (`to_dataframe()`) whose default columns are
  `stock_name, company_name, earnings_call_date, video_clip_time, youtube_url`. Includes
  bounded auto-pagination (`fetch_all_earnings_calls`), opt-in concurrent detail enrichment
  (`enrich=True`), seven filter helpers, and a `*_raw` variant. This host needs no
  cookies/Incapsula bypass, so it uses a plain sessionless fetcher. Not stock-scoped (not on
  the `Stock` class). Adds the `docs/settfex/services/set/earnings_call.md` doc and the
  `examples/set/12_earnings_call.ipynb` notebook.
- **`AsyncDataFetcher` POST support**: `fetch()` / `fetch_json()` now accept keyword-only
  `method="GET"` (default — fully backward compatible) and `json_body`. POST runs through the
  standalone (sessionless) path and the same NaN-rejecting JSON decoder; POST via a persistent
  session is intentionally unsupported (raises `NotImplementedError`).

### Changed

- pandas is now available as an optional `dataframe` extra
  (`pip install "settfex[dataframe]"`); it is required only for the DataFrame convenience and
  is imported lazily, so importing the library never requires pandas.

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
