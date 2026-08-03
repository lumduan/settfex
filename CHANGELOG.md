# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.16.0] - 2026-08-03

### Added

- **Asset-type classification** — new `AssetType` StrEnum (`stock`, `stock_foreign`,
  `preferred_stock`, `preferred_stock_foreign`, `warrant`, `dw`, `etf`, `unit_trust`, `dr`,
  `unknown`) mapping SET's `securityType` codes (`S/F/P/Q/W/V/L/U/X`, live-probed
  2026-08-03), exposed as `StockProfile.asset_type` and `StockSymbol.asset_type` properties,
  a `StockListResponse.filter_by_asset_type()` helper (accepts the enum, its value, or a raw
  SET code), and a cached `Stock.get_asset_type()` accessor. Unrecognized codes degrade to
  `AssetType.UNKNOWN` (never raises). There is deliberately no `BOND` member — bonds do not
  appear in SET's stock APIs at all.
- **DR profile service** (`stock/profile_dr.py`) — `GET /api/set/dr/{symbol}/profile` for
  Depositary Receipts (GOOG80, MICRON01, …): issuer/underlying details, verbatim conversion
  ratio, DRx `fractionalTrade` flag, and the TradingView **"Indicative Price"** link
  (`indicativePriceSymbol` expression + `indicativePriceUrl`). `DrProfile.indicative_expression`
  parses the expression and recovers it from the URL's `symbol` query param when the symbol
  field is null (observed for HERMES80/BYDCOM80/NDX01). New `Stock.get_dr_profile()` (cached
  per language) and `Stock.get_tradingview_url()` (`None` for non-DRs). Non-DR symbols get
  HTTP 404 `Invalid DR` → `SymbolNotFoundError` without a "did you mean?" suggestion (the
  endpoint 404s for valid non-DR symbols, so a suggestion would echo the symbol back).
- **DR indicative price from TradingView** (`stock/dr_indicative_price.py`) — evaluates the
  DR's fair-value expression (`underlying × FX ÷ ratio`, in THB) with ONE batch
  `POST scanner.tradingview.com/global/scan` for all legs. The `close` column is the last
  price (~15-min delayed for exchange legs, streaming for FX); the host is stateless and is
  never routed through SessionManager. New models `TradingViewQuote`, `DrIndicativePrice`
  (legs, ratio, `is_delayed`, aware-Bangkok `as_of`) and `DrIndicativeQuotation` (a
  `Quotation` subclass carrying `.indicative` provenance); `get_dr_indicative_price()`
  convenience and `Stock.get_indicative_price()`.

### Changed

- **`Stock.get_latest_price()` is now DR-aware** — for DR symbols it returns the TradingView
  indicative price as a `DrIndicativeQuotation` (its `price` is the fair value; `volume`,
  `value`, `change`, `percent_change` are `None` since nothing traded), falling back to SET
  chart data on any TradingView failure. Non-DR symbols are unchanged (first call per `Stock`
  instance adds one cached DR-profile probe). Opt out per call with
  `prefer_dr_indicative=False`; passing an explicit `as_of` always uses the SET chart path
  (TradingView cannot answer historical instants).
- **`DocumentCategory` is now an `enum.StrEnum`** (was `class DocumentCategory(str, Enum)`).
  The observable difference is string coercion: `str(cat)` and `f"{cat}"` now render the bare
  value (`"financial_statement"`) instead of `"DocumentCategory.FINANCIAL_STATEMENT"`, and a
  format spec such as `f"{cat:<25}"` is now honoured rather than silently ignored. **Everything
  else is unchanged** — equality with the plain string, `.value`, `.name`, `repr()`,
  `json.dumps()`, `isinstance(cat, str)`, `SecDocument.model_dump()` /
  `model_dump(mode="json")` / `model_dump_json()`, and every `SecDocumentList` helper
  (`categories()`, `available_years()`, `years_by_category()`, `filter()`, `summary()`) all
  behave exactly as before; `summary()` output is byte-identical because
  `years_by_category()` already keyed on `.value`.

  If you interpolate a category into a string and depended on the old
  `"DocumentCategory.FINANCIAL_STATEMENT"` form, use `repr(cat)` or `cat.name`. New tests in
  `tests/services/sec/test_financial_report.py` pin this contract.

  This unblocks ruff 0.15+, whose `UP042` rule rejects the `(str, Enum)` pattern.

### Fixed

- **A non-DR symbol no longer logs an `ERROR` on its first `get_latest_price()`** — the DR probe
  behind the auto-switch asks `/api/set/dr/{symbol}/profile`, which answers every non-DR symbol
  with HTTP 404. That 404 is routine control flow ("not a DR"), so it is now logged at `debug`;
  other non-2xx statuses still log at `error`. Without this, every ordinary stock cried wolf in
  the logs once per `Stock` instance.
- **SEC downloads now accept a plain `list[SecDocument]`** — `DocumentDownloadService.download_all`,
  `SecCompany.download_all` and `download_sec_documents` typed `targets` as
  `list[SecDocument | str]`, which (because `list` is invariant) rejected the output of
  `list_documents()` under a type checker — i.e. the documented
  `docs = await sec.list_documents(...)` → `sec.download_all(docs)` flow was a type error for
  every typed consumer, despite working fine at runtime. `targets` is now
  `Sequence[SecDocument | str]`; the parameter only widens, so existing callers are unaffected.

### Internal

- The uv version used by CI is now pinned (`version: "0.11.33"` on all six
  `astral-sh/setup-uv` steps) instead of `"latest"`, so a same-day uv release can no longer
  change a build unreviewed — including `release.yml`, which builds the published artifact.
  Dependabot bumps action refs but never action inputs, so this pin is maintained by hand.
- `uv run mypy .` is green again across all 125 files (package, `tests/`, local `scripts/`). It had
  been failing on stale `CompanyMatch(...)` constructions in `tests/services/sec/` that predate the
  model's required `company_name` / `unique_id` fields, plus one `in` test against the optional
  `SecDocument.file_id`. The CI gate is narrower (`mypy settfex/`), so this never showed up there.
- Dev-dependency bumps: mypy 1.18.2 → 2.3.0, matplotlib 3.10.6 → 3.11.1, notebook 7.4.7 → 7.6.0,
  tqdm 4.68.3 → 4.69.0 (lockfile only — no `pyproject.toml` constraint changes).
- GitHub Actions bumped off the deprecated Node 20 runtime, which the runners had been
  force-upgrading to Node 24: `actions/checkout` v4 → v7, `astral-sh/setup-uv` v5 → v9.0.0,
  `codecov/codecov-action` v4 → v7, `actions/upload-artifact` v4 → v7,
  `actions/download-artifact` v4 → v8, `softprops/action-gh-release` v2 → v3.
  `pypa/gh-action-pypi-publish` stays on the rolling `release/v1` branch (upstream's
  recommended pin). `setup-uv` is pinned to an exact version because it stopped publishing
  floating major tags at v8 — `@v9` does not resolve.

### Documentation

- New service docs `docs/settfex/services/set/profile_dr.md` and `dr_indicative_price.md`, plus a
  new executed example notebook `examples/set/18_dr_and_asset_type.ipynb` (asset-type
  classification, DR profiles, the TradingView URL, and the indicative-price arithmetic).
  README, `examples/README.md`, `examples/set/README.md` and `13_chart_quotation.ipynb` now cover
  the new services and the DR behavior of `Stock.get_latest_price()`.
- Corrected two pre-existing doc errors found while auditing: the README chart-quotation snippet
  called `Quotation.close`, which does not exist (the field is `price`), and `CLAUDE.md` advertised
  `stock.get_balance_sheet()`, a method the `Stock` class has never had.

## [0.15.0] - 2026-07-27

### Added

- **SET Market Holiday service** (`settfex.services.set.holiday`) — the official SET market-closure
  calendar for a year, in English or Thai, via `GET /api/cms/v1/holidays/year/{year}`. Follows the
  standard three tiers: `get_holidays()` → `HolidayService.fetch_holidays()` →
  `HolidayService.fetch_holidays_raw()`.
  - **`Holiday`** — `holiday_date` (timezone-aware, always `+07:00`, `00:00:00` time component;
    aliased from the API's `date` key) and `description`. Descriptions are preserved **verbatim**:
    unlike every other SET model, `str_strip_whitespace` is deliberately **off**, because a
    trailing `" *"` is a SET footnote marker for additional special closures.
  - **`HolidayCalendar`** — container exposing `count`, `dates`, `is_holiday()`, `get_holiday()`,
    `filter_by_month()` and `next_holiday()`. Query methods accept `date` or `datetime` (naive
    datetimes are treated as Bangkok-local, aware ones converted) and do not depend on payload
    ordering.
  - `year` defaults to the current year in **Asia/Bangkok**, never system-local time. Client-side
    validation (`MIN_YEAR` 1975 … `MAX_YEAR` 2100) is a typo guard only.
  - New constant `SET_HOLIDAY_ENDPOINT`; `get_holidays` and `HolidayCalendar` are re-exported from
    the top-level `settfex` package.
  - Docs: `docs/settfex/services/set/holiday.md`; example: `examples/set/17_holiday.ipynb`.

### Fixed

- **The holiday service retries transient HTTP 401s** instead of failing the call. This endpoint
  uses a bare `401` with an empty body as its *only* failure code — for an unrecognized `lang`, a
  missing `lang`, an unserved year, **and** transiently on perfectly valid requests — while
  `AsyncDataFetcher.fetch()` retries exceptions only and never a non-2xx status. `HolidayService`
  therefore retries `401`/`403`/`429` with exponential backoff driven by the existing
  `FetcherConfig.max_retries` / `retry_delay` knobs (no new API surface). On exhaustion the
  `FetchError` message names both possible causes, since the API gives no way to tell them apart.

### Documentation

- Recorded three live-probed limits of the holiday endpoint (2026-07-27), in the module docstring,
  the docs page and `CLAUDE.md` Known Gotchas:
  - **Only the current year is served.** With 2026 returning 200 on every interleaved control
    request, 2024, 2025, 2027 and 2028 all returned HTTP 401 — so this endpoint cannot supply
    history for backtests or next year's calendar for year-boundary arithmetic.
  - **Success rate degrades under polling** (~100% cold → ~35% after ~50 requests → ~12% after
    ~150) and recovers on its own when left idle. Cache the result; holiday data is static.
  - **`is_holiday()` answers "published holiday", not "market closed"** — weekends are absent from
    the payload, and only whole-day closures are expressed (no partial sessions or altered hours).

## [0.14.0] - 2026-07-20

### Changed

- **SEC downloads are now robust for large files by default.** Form 56‑1/56‑2 "One Reports" run
  15–25 MB and were timing out under the 30 s default. The download path now:
  - **Defaults to a 180 s per-file timeout** (`DEFAULT_DOWNLOAD_TIMEOUT`) instead of 30 s, with a
    new `timeout=` parameter on `download_sec_document(s)` / `DocumentDownloadService` (an explicit
    `timeout` wins; a caller-supplied `config` is otherwise honored; max 300 s).
  - **Lowers the default `max_concurrency` from 5 → 3** for `download_all` /
    `download_sec_documents` / `SecCompany.download_all` (large files share bandwidth, so fewer at
    once finish more reliably).
  - **Dedupes by URL:** a statement's *Company* and *Consolidated* rows point to the same zip, so
    `download_all` now downloads each unique file once and returns one result per unique URL
    (e.g. an 18‑year all‑category batch drops from 229 fetches to 153).
- **`download_all` no longer holds every file's bytes in memory when saving to disk.** With
  `dest_dir` set, each returned `DownloadedFile` has `content` emptied after the file is written
  (bytes are on disk; `size` and the new `path` field remain), bounding memory on large batches.
  New `keep_bytes` parameter overrides this (`True` = always keep, default keeps bytes only when
  not saving). Single-file `download_sec_document` still returns the bytes.

### Added

- **`DownloadedFile.path`** — the on-disk `Path` a file was saved to (set by `.save()` and by
  `download_all` when `dest_dir` is used).

## [0.13.0] - 2026-07-20

### Added

- **`SecDocumentList`** — the SEC listing calls (`get_sec_documents`,
  `FinancialReportService.fetch_documents`, `SecCompany.list_documents`) now return a
  `SecDocumentList`, a `list[SecDocument]` **subclass** (fully backward compatible — it is a
  list) with convenience helpers so you can see what's available and download in bulk:
  - `years_by_category() -> dict[str, list[int]]` and `available_years(category=None)` — the
    available reporting years (newest first) per category / overall.
  - `filter(category=None, year=None) -> SecDocumentList` — a subset (e.g.
    `docs.filter(category="form_56_1")`), which composes directly with
    `download_sec_documents(subset, dest_dir=…)` to **download all** of a category/year.
  - `categories()` and `summary()` (a ready-to-`print()` block of years per category).
  - Exported from `settfex.services.sec` and the top-level `settfex` namespace.
  - Note: pass a **wide** `from_date`/`to_date` window to enumerate the full year history — the
    default fetch returns only a recent window. MD&A rows carry a date, not a reporting year.

### Documentation

- The SEC service doc and example notebook (`examples/sec/01_financial_report.ipynb`) now show
  listing the available years and downloading them all (or a filtered subset) — the
  download-all path (`download_sec_documents` / `SecCompany.download_all`) is surfaced clearly.

## [0.12.0] - 2026-07-20

### Added

- **SEC IDISC document services** (`settfex.services.sec`) — list and download the **raw
  disclosure documents** companies file with the Thai SEC (`market.sec.or.th`), for any
  SET/mai-listed issuer. Covers **five categories**: financial statements (the original
  `FINANCIAL_STATEMENTS.XLSX` package), Form 56-1, Form 56-2, Key Financial Ratio, and MD&A.
  - Three tiers: `get_sec_documents()` / `download_sec_document(s)()` (flat convenience, LLM
    entry points) → `FinancialReportService.fetch_documents()` / `DocumentDownloadService`
    (typed `SecDocument` / `DownloadedFile` models) → `fetch_documents_raw()` (raw parsed rows).
  - Unified `SecCompany("CPALL")` facade; company resolver `resolve_company()` /
    `search_companies()` (maps a symbol/name → SEC `uniqueIDReference`).
  - Listing replays the ASP.NET WebForms search (GET fresh `__VIEWSTATE` tokens → form POST →
    HTML-table parse via the stdlib `html.parser`, no new dependency) and follows the
    "display all results" ViewMore pages so large sections are returned in full
    (`follow_view_more=True`). Category filtering, `en`/`th`, and dd/mm/yyyy date windows
    (`datetime.date`/`datetime` objects or strings; ISO strings raise `InvalidDateError`).
  - Downloads return the raw bytes as `DownloadedFile` (with `.save(dest)`), with concurrent
    `download_all()` (bounded, tolerant of per-item failures, optional `tqdm` progress).
    Dead links are detected: the SEC host answers a missing file with an HTML "file not found"
    page under HTTP 200, which raises `FetchError` instead of returning a garbage payload.
  - Verified `market.sec.or.th` endpoints: `POST …/api/company/valuebyuniqueId`,
    `GET`/`POST …/{lang}/FinancialReport/{FS|R561|R562|KFR}`, `GET …/{lang}/ViewMore/{slug}`,
    `GET …/Download?FILEID=…`, `GET …/ipos/Common/IPOSGetFile.aspx?id=…`.
- **`AsyncDataFetcher` extensions** (backward-compatible): form-encoded POST via a new `data=`
  argument (alongside `json_body=`), and a `decode_text=False` flag to fetch binary payloads
  (zip/xlsx/pdf) without the wasteful text decode. Both default to current behavior.
- Example notebook `examples/sec/01_financial_report.ipynb` and service doc
  `docs/settfex/services/sec/financial_report.md`.

## [0.11.0] - 2026-07-19

### Added

- **SET News service** (`settfex.services.set.news`) — company news/disclosures for **all
  stocks** in one call, from `GET /api/set/news/search`: `get_news()` /
  `NewsService.fetch_news()` (typed `NewsSearchResponse` with `count`, `filter_by_symbol()`,
  `filter_today()`, `filter_by_tag()`) / `fetch_news_raw()`, plus a `Stock.get_news()` accessor
  with the symbol pre-filled. Filters: `symbol`, `from_date`/`to_date` (accepts
  `datetime.date`/`datetime` objects or dd/MM/yyyy strings — the API rejects ISO dates with an
  opaque HTTP 400, so strings are validated **eagerly** via the new `InvalidDateError`),
  `keyword`, `source_id` (default `"company"`; pass `None` for all sources — the API silently
  ignores unrecognized values, which the service warns about), and `lang` (`en`/`th`).
  Tz-aware timestamps, SessionManager/Incapsula bypass, and permissive typing for the three
  never-observed alert fields (`viewClarification`/`marketAlertTypeId`/`percentPriceChange`)
  so a future non-null value cannot break parsing. Without date filters the API returns the
  latest-trading-day window (~150–200 items); no pagination observed, so keep windows modest.
- **`InvalidDateError`** in `settfex.exceptions` (subclasses `ValueError`), re-exported from
  the top-level `settfex` namespace, and the `SET_NEWS_SEARCH_ENDPOINT` constant.
- Example notebook `examples/set/16_news.ipynb` and service doc
  `docs/settfex/services/set/news.md`.

### Fixed

- **Docs: corrected the stale services inventory** in `CLAUDE.md`/`README.md` — the TFEX
  underlying-price service (shipped in 0.3.0) was missing from the inventory, the TFEX
  notebook list, and the notebook counts. Totals are now 19 services (16 SET + 3 TFEX) and
  19 notebooks.

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
