# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Internal

- `docs/guide/PYTHON_LIBRARY_BEST_PRACTICES.md` still said "Aim for >80% coverage". It reads as
  generic advice but is explicitly a document about *this* library ("best practices followed in the
  `settfex` library"), so it was a repo claim sitting **below the enforced 85% floor** — the last
  one left after the 0.19.1 prompt sweep. It now names `--cov-fail-under=85` and says the floor is
  enforced rather than aspirational. `CLAUDE.md` needed no change: both of its figures already read
  86.65% and remain accurate.

## [0.19.1] - 2026-08-26

### Internal

- The AI-agent prompt files under `.github/prompts/` asked for **90% coverage** while the enforced
  gate is **85%** (`--cov-fail-under`), so an agent following them was working to a number the repo
  does not check. All now state 85% and name the setting that enforces it, so the figure points at
  its instrument rather than drifting again — five surfaces across three files:
  `Coding.prompt.md` (the requirement and the completion checklist), `Python-Architect.prompt.md`
  (the strategy guidance and the review checklist), and `Prompt-Engineer.prompt.md`, where the
  number sat inside a worked example of a well-formed prompt — not a requirement, but precisely the
  kind of sample that propagates a stale figure into generated prompts.
- `Coding.prompt.md`'s separate **"100% coverage for public APIs"** requirement was removed rather
  than rescaled. It was the last coverage figure in the repo that nothing measured: coverage is
  enforced repo-wide by `--cov-fail-under`, which has no notion of a public-API subset, so the line
  could never pass or fail anything. The enforced 85% floor is now the single coverage number an
  agent is asked to meet.

## [0.19.0] - 2026-08-25

### Changed

- **pandas 3 support (2.3.3 → 3.0.5), and it changes what `to_dataframe()` gives you.** settfex
  still supports `pandas>=2.0.0`, so **the same call now differs by installed pandas**:
  - A **missing value in a string column is `NaN` on pandas 3** (column typed `str`) where it was
    **`None` on pandas 2** (column typed `object`). `value is None` silently stops matching —
    **`pd.isna(value)` is the portable check.** This is user-visible on every nullable string the
    library exposes, e.g. `research_url` for a broker that published no PDF, or `youtube_url` for
    an upcoming earnings call.
  - Tz-aware datetime columns move `datetime64[ns, +07:00]` → `datetime64[us, +07:00]`. Values are
    unchanged; only the resolution differs. **No test caught this** — it was found by running the
    same fixture through both majors and diffing.
  - `NaN` is **not valid JSON**, so `json.dumps(df.to_dict("records"))` emits a bare `NaN` token.
    Python's own `json.loads` accepts it, but strict parsers (`JSON.parse`, most non-Python
    consumers) reject it. Use `df.to_json()`, which correctly writes `null`.
  - Verified safe: **`df.attrs` survives** copy, column selection and `head()`, so the forecast-year
    metadata on the analyst-consensus frames is intact — and **pyarrow is not required** by
    pandas 3; the `str` dtype falls back to a numpy object store.

  The suite is green on **both** majors (882 passed under 3.0.5 and under 2.3.3). Documented in
  `CLAUDE.md`, as an agent-facing trap in `AGENTS.md`, and in the analyst-consensus service doc.

### Fixed

- `AnalystConsensus.to_dataframe()`'s docstring claimed `last_update_date` is typed `object`
  because it "mixes timezone-aware datetimes with None". It is not, and was not on pandas 2
  either — all SET timestamps share the `+07:00` offset, so pandas coerces the column to a
  tz-aware `datetime64` with `NaT` for the missing entries. The same stale claim was repeated as
  an `# object -> datetime64` comment in `docs/settfex/services/set/analyst_consensus.md`; both
  now describe what actually happens.

### Internal

- **Coverage floor raised 45% → 85%** (`--cov-fail-under` in `pyproject.toml`). The old floor was
  set "just below current coverage (~49%)" with an "80% goal"; actual coverage had since reached
  **86.65%**, so both halves of that comment were wrong and the gate was guarding a level cleared
  long ago — a regression could have halved coverage without turning CI red. Headroom at the new
  floor is ~115 new all-uncovered statements, so landing a large service with no tests is meant to
  trip it. Verified in both directions: the suite passes at 85 and fails at 95.
- **`--cov-branch` added to the pytest defaults so a local run measures what CI measures.** CI
  passes `--cov-branch` explicitly, and branch coverage scores ~1.3 points below statement-only
  (86.65% vs 87.99%) — but `--cov-fail-under` applied to both, so the *same* floor meant two
  different things depending on where it ran, and the local number was the falsely reassuring one:
  a change sitting at 85.5% locally would have failed CI at ~84.2%. Both now report 86.65%.
  Every surface restating the old floor moved with it — the `pyproject.toml` comment,
  `CONTRIBUTING.md` ("target ≥80%" → the enforced 85% floor), the two ">80% coverage" claims in
  `CLAUDE.md`, and the historical `COMPREHENSIVE_AUDIT.md` metric row, which keeps its
  point-in-time "gate = 45%" value but is now labelled as history with a pointer to what
  superseded it.

- Dev/CI dependency bumps (lockfile only — no `pyproject.toml` constraint changes): notebook
  7.6.0 → **7.6.2**, pre-commit 4.6.0 → **4.6.2**, tqdm 4.69.0 → **4.70.0**, twine 6.2.0 → 7.0.0.
  (notebook, pre-commit and tqdm landed in two rounds — the second round was raised by Dependabot
  only after the queue below was unblocked.) `twine` is a break-glass tool
  only — the release path publishes through `pypa/gh-action-pypi-publish` over OIDC and invokes
  no workflow that uses it.
- `astral-sh/setup-uv` bumped v9.0.0 → v10.0.1 across all six workflow steps
  (`ci.yml`, `release.yml`, `security.yml`). The hand-maintained `version: "0.11.33"` **input** is
  unchanged — Dependabot bumps action refs, never action inputs, so that pin still moves only by
  hand.
- **ruff is frozen at 0.13.2 and removed from Dependabot's watch list.** Ruff 0.16+ formats Python
  code blocks inside Markdown, so `ruff format --check` wants to reformat 34 `.md` files and
  collapse the column-aligned inline comments in every doc code sample. The bump was proposed and
  rejected three times (#61 → #78 → #88); #88 was closed with `@dependabot ignore this dependency`,
  which ends the cycle permanently. Re-enabling means re-opening #88, and settling the
  `extend-exclude = ["*.md"]` question first — see the "Ruff is FROZEN at 0.13.2" gotcha in
  `CLAUDE.md`.
- Dependency-queue cleanup: the `uv` ecosystem was sitting at its `open-pull-requests-limit: 5`
  with all five slots consumed by stale PRs, which blocked Dependabot from opening **any** new
  `uv` PR — a security bump included. Clearing the stale backlog took open PRs 6 → 1, and
  Dependabot immediately re-scanned the freed slots and proposed four updates it had been unable
  to raise (notebook 7.6.2, pandas 3.0.5, tqdm 4.70.0, pre-commit 4.6.2) — direct evidence the
  channel had been blocked rather than merely untidy. **No ruff PR was raised in that re-scan**,
  confirming the ignore holds.
- **curl-cffi 0.13.0 → 0.16.1** (#96, superseding #89) — the core HTTP dependency behind browser
  impersonation and the Incapsula bypass. Six `# type: ignore` comments on `impersonate=` were
  removed as part of the bump (`utils/http.py:40`, `utils/session_manager.py:360`/`:423`,
  `utils/data_fetcher.py:240`/`:247`/`:253`): curl-cffi 0.16 widened that parameter to
  `Optional[Union[BrowserTypeLiteral, str, Fingerprint]]`, so passing a plain `str` is legal and
  `mypy --strict` flagged all six as `unused-ignore`. The package still ships `py.typed`, so the
  call sites remain type-checked — this removes redundant suppression, not the check itself.
- **The curl-cffi bump was verified live, because the unit suite cannot verify it.** All 882 tests
  mock the HTTP layer, so every one of them passes whether or not impersonation still defeats bot
  detection. Each distinct network path was therefore exercised for real against 0.16.1: a
  session-warmed SET GET, the large SET stock-list payload (3,954 securities), Settrade on its
  separate Incapsula cookie domain, the stateless TradingView scanner POST, and ThaiBMA — 5/5.
  A control probe confirms the check is not vacuous: the same SET endpoint answers **403** to a
  bare `AsyncSession` request *even with `impersonate="chrome120"` set*, so it is the
  `SessionManager` cookie warmup plus referer that carries the bypass, and that chain is intact.

## [0.18.0] - 2026-08-16

### Added

- **Analyst Consensus (IAA) service** (`settfex/services/set/stock/analyst_consensus.py`) — broker
  target prices, earnings forecasts and research PDF links for a SET stock, from the library's
  first **`www.settrade.com`** host. This is the data behind the `tableAnalystConcensus` table on
  Settrade's quote page; the page is a client-rendered Nuxt app, so the service calls the JSON
  endpoints its bundle calls rather than parsing HTML.
  - `GET /api/set-fund/consensus/stock/{symbol}/consensus` →
    `AnalystConsensusService.fetch_analyst_consensus()` / `get_analyst_consensus()` returning an
    `AnalystConsensus`: four aggregate rows (`average`/`median`/`high`/`low`, typed
    `ConsensusStatistic` and labelled by their payload key) plus one `AnalystConsensusRow` per
    covering broker with analyst name, recommendation, target price and `last_research_url` (the
    research PDF). Helpers: `count`, `brokers`, `statistics`, `broker_names`, `with_research`,
    `research_urls`, `latest_update`, `broker(name)`.
  - `GET /api/set-fund/consensus/stock/overall?lang=&symbol=` →
    `fetch_overall()` / `get_consensus_overall()` returning a `ConsensusOverallResponse` of
    `ConsensusOverall` rows (last price, coverage count, buy/hold/sell, bullish/bearish, median
    and average target price). **Omit the symbol and it returns every covered SET stock in one
    request** — a market-wide consensus screener.
  - **Two DataFrames**, the feature's headline: `stats_to_dataframe()` for the four aggregate rows
    (labelled by a `statistic` column) and `to_dataframe()` for the per-broker rows including the
    PDF link; `get_analyst_consensus_dataframes()` fetches straight into both. Column names are
    year-agnostic and the year labels ride in `df.attrs`. Requires the optional `dataframe` extra.
  - `Stock.get_analyst_consensus()` (cached per instance) and `Stock.get_consensus_overall()`.
  - `has_coverage` is a **computed** field: a listed stock nobody covers returns HTTP 200 with an
    empty broker list and aggregates zero-filled to `0.0` rather than null, so the flag survives
    `model_dump()` into Parquet. A symbol Settrade has no record of returns **HTTP 500, not 404**
    — including valid SET stocks, DRs and warrants — and is raised as a plain `FetchError`, never
    `SymbolNotFoundError`.
  - Every numeric field is `float | None`: real broker rows null `targetPriceChange`,
    `nextYearPe`, `currentYearPbv` and `nextYearDiv`.
- **`SessionManager` gained a third warmup site, `"settrade"`** (`settfex/utils/session_manager.py`),
  auto-detected from the URL host by `get_session_for_url()`. Incapsula cookies are per-domain: a
  session warmed on `www.set.or.th` is rejected with HTTP 403 on `www.settrade.com`, so a settrade
  URL must never fall through to the SET warmup. Warmup URLs now live in a `WARMUP_URLS` map.
- **`AGENTS.md`** at the repo root — the calling contract for AI agents and LLM tool use: the
  service map across all four hosts, the `get_*()` / `fetch_*()` / `fetch_*_raw()` tiers, the
  warning that the top-level `settfex` package re-exports only a subset of
  `settfex.services.set`, and the failure modes that silently produce wrong answers (HTTP 500 as
  "uncovered", zero-filled aggregates, dd/MM/yyyy news dates, ThaiBMA's silent roll-back,
  percent-vs-basis-point units). `CLAUDE.md` remains the guide for *changing* the library.

### Fixed

- **`SessionManager.reset_instance(site)` no longer resets unrelated sites.** Instance keys are
  `f"{warmup_site}_{browser}"` and the filter used a bare `key.startswith(warmup_site)`, so
  `reset_instance("set")` also matched `settrade_chrome120` and would have silently closed the
  Settrade session. It now matches on the `"<site>_"` prefix. Latent before this release (no two
  existing site names were prefixes of one another).

## [0.17.0] - 2026-08-10

### Added

- **ThaiBMA government bond yield curve services** (`settfex/services/thaibma/`) — the library's
  first fixed-income data and its fourth host (`www.thaibma.or.th`, the Thai Bond Market
  Association). Covers the fitted par curve, the bond quotes behind it, and daily history back to
  **1999-09-15**:
  - `GET /yieldcurve/gov[/{date}]` → `YieldCurveService.fetch_curve()` / `get_government_yield_curve()`
    returning a `YieldCurve` of `CurvePoint` (the standard tenor grid, 1M/3M/6M then whole years)
    plus `BondQuote` rows (yield, day-on-day change, maturity, benchmark/synthetic flags).
    Helpers: `yield_at()`, `interpolate()`, `slope_bps()` (the 2s10s in one call), `to_dict()`,
    `benchmarks`/`bills`/`bonds`, `quote()`, `to_dataframe()`.
  - **Bulk-year history at one request per year** — `GET /yieldcurve/getintpttm?year=` (the
    constant-maturity matrix) and `GET /yieldcurve/getbyyear?year=` (the per-bond matrix) via
    `YieldCurveHistoryService.fetch_history()` / `get_yield_curve_history()` /
    `get_bond_yield_history()`. The full 27-year record is **28 requests** rather than the ~6,600
    a per-day loop would cost; these routes are undocumented and appear only in the ThaiBMA
    website's own JavaScript. Returns a `YieldCurveHistory` whose `rows` carry per-year dynamic
    columns and whose `columns` is the ordered union, with `series()`, `slice()`,
    `columns_by_year()`, `coverage()`, `to_long()` and `to_dataframe(layout="wide"|"long")`.
  - `GET /yieldcurve/avail` + `/availyear` → `YieldCurveAvailabilityService` /
    `get_yield_curve_availability()`, which also clamps history spans so a year ThaiBMA does not
    serve is reported in `unavailable_years` instead of silently vanishing.
  - `ThaiBMA` facade (`get_yield_curve()`, `get_history()`, `get_bond_history()`,
    `get_availability()`) with lazily-constructed, cached services.
- **`StaleDataError`** (a `FetchError` subclass, in `settfex/exceptions.py`) — raised when an API
  answers HTTP 200 with data for a **different date** than was requested. ThaiBMA's curve endpoint
  never 404s on a date: a weekend, a Thai public holiday, or **any future date** silently returns
  the most recent earlier curve. Every `YieldCurve` therefore carries `requested_date`, `as_of`
  and the Pydantic **computed fields** `is_rolled_back` / `rollback_days` (so the audit trail
  survives `model_dump()`), and `on_rollback` selects `"warn"` (default), `"raise"` or `"allow"`.
- Docs at `docs/settfex/services/thaibma/yield_curve.md`, a runnable
  `examples/thaibma/01_government_yield_curve.ipynb`, and a live verification script.

### Notes

Five API behaviours are documented in CLAUDE.md's Known Gotchas, all live-verified 2026-08-10:
the silent roll-back; `yield_percent` in **percent** while `change_bps` is in **basis points**
(proved by differencing consecutive business days); a body of literal `null` for pre-1999-09-15
dates; malformed dates failing two different silent ways (`2026-8-10` → HTML 404, `2026-02-30` →
HTTP 200 with the *latest* curve, both neutralized client-side); and `IsBenchmark`/`IsSynthetic`
never being backfilled before 2013/2014.

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
