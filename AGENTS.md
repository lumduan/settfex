# AGENTS.md — calling settfex from an AI agent

**settfex** fetches real-time and historical data from the **Stock Exchange of Thailand (SET)**,
the **Thailand Futures Exchange (TFEX)**, the **Thai SEC** filing system, and the **Thai Bond
Market Association (ThaiBMA)**.

This file is for an agent **calling** the library. If you are **changing** the library, read
[`CLAUDE.md`](CLAUDE.md) instead — it carries the architecture, service-design rules and the full
Known Gotchas list. To cut a release, see [`RELEASING.md`](RELEASING.md).

---

## Start here

```bash
pip install settfex                 # core
pip install "settfex[dataframe]"    # + pandas, for every .to_dataframe() helper
```

```python
from settfex.services.set import get_highlight_data

data = await get_highlight_data("CPALL")     # everything is async
print(data.market_cap, data.pe_ratio)
```

Four rules that cover most mistakes:

1. **Everything is `async`.** Every entry point is a coroutine — `await` it. In a script, wrap in
   `asyncio.run(...)`; in Jupyter, bare `await` works.
2. **Call the flat `get_*()` functions.** They are the intended tool-calling layer and return
   validated Pydantic models.
3. **Import from `settfex.services.set`, not `settfex`** — see the trap immediately below.
4. **Never pass cookies, headers or a session.** Bot-detection bypass and cookie warming are
   automatic. There is no auth, no API key, and no rate-limit parameter.

### ⚠️ The top-level package is a *subset*

`settfex` re-exports only 24 functions; `settfex.services.set` exposes 43. These are **not** at
top level and will raise `ImportError` if you guess:

`get_balance_sheet`, `get_income_statement`, `get_cash_flow`, `get_trading_stats`,
`get_price_performance`, `get_corporate_actions`, `get_nvdr_holder_data`,
`get_board_of_directors`, `get_shareholder_data`, `get_latest_price`, `get_chart_quotation`,
`get_latest_historical_trading`, `get_index_*`, and the whole earnings-call family.

**Always import from the service package** — `settfex.services.set`, `.tfex`, `.sec`,
`.thaibma`. It is a superset of the top level in every case.

### The three tiers

| Tier | Returns | Use when |
|---|---|---|
| `get_*(...)` | validated Pydantic model | **default — this is the agent entry point** |
| `Service.fetch_*(...)` | same model, reusable service instance | many calls, or a custom `FetcherConfig` |
| `Service.fetch_*_raw(...)` | raw `dict` | debugging, or a field the model doesn't expose yet |

Do not reach for `fetch_*_raw()` to "be safe" — the model is the safer surface.

---

## Service map

Common arguments: `symbol: str` is case-insensitive (auto-uppercased); `lang: "en" | "th"` also
accepts `english`/`thai`; `config: FetcherConfig | None` tunes timeout/retries.

### SET equities — `from settfex.services.set import ...`

| I want… | Call | Returns |
|---|---|---|
| every listed stock | `get_stock_list()` | `StockListResponse` (filter by market/industry/index/asset type) |
| valuation snapshot (P/E, P/B, market cap, yield, beta) | `get_highlight_data(symbol, lang)` | `StockHighlightData` |
| listing details, ISIN, foreign limits | `get_profile(symbol, lang)` | `StockProfile` |
| company info, ESG/CG scores, management | `get_company_profile(symbol, lang)` | `CompanyProfile` |
| dividends (XD), shareholder meetings | `get_corporate_actions(symbol, lang)` | `list[CorporateAction]` |
| major shareholders, free float | `get_shareholder_data(symbol, lang)` | `ShareholderData` |
| NVDR ownership | `get_nvdr_holder_data(symbol, lang)` | `NVDRHolderData` |
| directors and officers | `get_board_of_directors(symbol, lang)` | `list[Director]` |
| trading stats over YTD…1Y | `get_trading_stats(symbol, lang)` | `list[TradingStat]` |
| stock vs sector vs market returns | `get_price_performance(symbol, lang)` | `PricePerformanceData` |
| financial statements | `get_balance_sheet` / `get_income_statement` / `get_cash_flow` `(symbol, lang)` | `list[...]`, multi-period |
| **latest traded price** | `get_latest_price(symbol)` | `Quotation` — see the DR trap below |
| intraday / historical price series | `get_chart_quotation(symbol, period="1D")` | `ChartQuotation` |
| last completed session OHLCV | `get_latest_historical_trading(symbol)` | `LatestHistoricalTrading` |
| **is it suspended? trading signs** (SP/NC/NP/CB/XD…), live quote block, best bid/offer | `get_stock_info(symbol)` | `StockInfo` — `.signs`, `.is_suspended`, `.has_sign()` |
| company news & disclosures | `get_news(lang, symbol, from_date, to_date, keyword)` | `NewsSearchResponse` |
| market-closure calendar | `get_holidays(year, lang)` | `HolidayCalendar` |
| earnings calls (OPPDAY) + YouTube | `get_earnings_calls(...)`, `get_all_earnings_calls(...)`, `get_earnings_call_detail(id)`, `get_earnings_call_transcript(id)` | calendar entries, Thai transcripts |
| **analyst target prices & research PDFs** | `get_analyst_consensus(symbol)` | `AnalystConsensus` |
| **buy/hold/sell counts** (one stock, or the whole market) | `get_consensus_overall(symbol=None, lang)` | `ConsensusOverallResponse` |
| both consensus tables as DataFrames | `get_analyst_consensus_dataframes(symbol)` | `(stats_df, brokers_df)` |
| DR issuer / underlying / ratio | `get_dr_profile(symbol, lang)` | `DrProfile` |
| DR fair value in THB | `get_dr_indicative_price(symbol)` | `DrIndicativePrice` |

Indices: `get_index_list(lang)`, `get_index_info(symbol, lang)`,
`get_index_composition(symbol, lang)` (constituents), `get_index_latest_price(symbol)`.

### TFEX — `from settfex.services.tfex import ...`

| I want… | Call |
|---|---|
| all futures/options series | `get_series_list()` |
| settlement, margin (IM/MM), days to maturity | `get_trading_statistics(symbol)` |
| the underlying's spot price | `get_underlying_price(symbol)` |

### Thai SEC filings — `from settfex.services.sec import ...`

| I want… | Call |
|---|---|
| resolve a company to its SEC id | `resolve_company(query, lang, allow_name_match=False)` |
| list filings (financial statements, 56-1, 56-2, ratios, MD&A) | `get_sec_documents(query, types=..., from_date=..., to_date=...)` |
| download the actual file(s) | `download_sec_document(target)` / `download_sec_documents(targets)` |

Dates here are **dd/mm/yyyy**. Pass a wide window to see full year history.

⚠️ **Not every SET symbol is an SEC issuer.** ETFs, warrants, DWs and `-F` foreign lines do not
file, so resolving one of them raises rather than guessing (0.24.0):

| outcome | exception | what to do |
|---|---|---|
| nothing matched | `CompanyNotFoundError` | report that no issuer exists; do not retry |
| several matched, none flagged | `AmbiguousCompanyError` | read `exc.candidates` (each a `CompanyMatch`) and ask which one, or pass an exact symbol |
| **exactly one matched, not flagged** | `AmbiguousCompanyError` | the site did not recognise your query as an *identifier*, so that row is a substring hit on a company **name**. If you meant a name, pass `allow_name_match=True`; if you meant a symbol, it is not an SEC issuer |

**Searching by company name?** Pass `allow_name_match=True` — a name never flags, so a name lookup
always lands in that third row:

```python
await get_sec_documents("CP ALL PUBLIC COMPANY LIMITED", allow_name_match=True)
await resolve_company("ปตท", allow_name_match=True)   # still raises: 17 candidates, none flagged
```

It only ever affects the **single**-candidate case. Several unflagged candidates stay ambiguous
whatever you intended.

Both are **`ValueError`s, not `FetchError`s**, because the request succeeded — retrying returns the
same answer forever, so `except FetchError: retry` must not be what catches them. Before 0.24.0 the
second case returned an arbitrary alphabetically-first company: `CHINA` (an ETF) resolved to
`ASEAN CHINA INVESTMENT FUND L.P.` and every filing listed under it was the wrong company's.

`lang="th"` works and returns the **Thai-language filing documents** — different files from the
English ones, not a translated index. Years and dates come back as **C.E.** in the model even
though the Thai page states them in the Buddhist era (`2568` → `2025`). Free-text cells
(`status`, `period`, `statement_type`, `company_name`) stay in the page's own language, so compare
on `year`/`as_of`/`category`, never on those.

**Before concluding an issuer filed nothing, read the two cross-checks.** `docs.reported_counts` /
`docs.completeness()` is what the *site* said each section holds — a shortfall is usually a long
section truncated behind "view more", so pass `follow_view_more=True` (the default) and a wide date
window. `docs.accounting` is what the *parser* did with the rows it got: `accounting.has_losses`
is the one flag to branch on, `accounting.no_link` counts rows whose download link was missing, and
`accounting.unmapped_headers` names columns the site serves that this library does not model. A
listing where **every** usable row was lost raises `IncompleteListingError` rather than returning
`[]`, so an empty list you actually receive means an empty result. The same now holds for the
transport: a failed request raises `FetchError`, and a body that is not a listing page raises
`ParseError`, instead of parsing to zero rows and looking like "this issuer filed nothing".

Two things deliberately do **not** raise. A broken "display all results" page: that section keeps
its truncated inline rows and the shortfall shows in `completeness()`. And **one failing report
code**: the others keep their documents, and the failure is recorded on
`docs.accounting.failed_codes` (with a WARNING). So after a call that returned normally, check
`docs.accounting.has_losses` before treating the result as complete — an exception is no longer how
a partial failure announces itself. `repr(docs)` states it too.

As of 2026-09-20 SEC's Thai `fs-kf` page answers HTTP 500, which is an upstream bug, not a settfex
one; it shows up as a `key_financial_ratio` shortfall on Thai listings.

As of 0.24.0 `SecDocumentList` is a **Pydantic model** `{documents, accounting, reported_counts}`
that still iterates, indexes and slices like the list it used to be — and a **slice keeps the
accounting** (of the whole call, not of the slice). So `model_dump()` and JSON carry the
completeness signal, which matters here more than anywhere: what you receive from a tool call is
JSON, so a signal that does not serialize does not reach you at all.

⚠️ `isinstance(docs, list)` is now `False` — it fails *silently*, by taking the other branch. Use
`docs.documents` where a real list is needed. `sorted(docs)` and `list(docs)` still give plain
lists, so sort `docs.documents`.

⚠️ A section whose "display all results" page failed lands on `accounting.degraded_sections` and
sets `has_losses` — that is how the live Thai `fs-kf` HTTP 500 above surfaces.

`download_sec_documents(...)` returns a `DownloadResult` — a list of the files that downloaded,
which also carries `.failed` (each with its target and reason) and `.is_complete`. Check it before
reporting a batch as done; dead links on the SEC host arrive as HTML under HTTP 200, not as errors.
Also a Pydantic model since 0.24.0 (`{files, failed, requested}` + computed `is_complete`), so the
failure report survives `model_dump()` and slicing. ⚠️ `isinstance(files, list)` is `False`; use
`files.files`.

### ThaiBMA bonds — `from settfex.services.thaibma import ...`

| I want… | Call |
|---|---|
| the government yield curve on a date | `get_government_yield_curve(curve_date=None)` |
| constant-maturity history | `get_yield_curve_history(start_date, end_date)` |
| per-bond history | `get_bond_yield_history(start_date, end_date)` |
| what dates exist (back to 1999-09-15) | `get_yield_curve_availability()` |

History is **one request per calendar year** — never loop day by day.

### Facades, when you need several things about one subject

```python
from settfex.services.set import Stock, SetIndex
from settfex.services.sec import SecCompany
from settfex.services.thaibma import ThaiBMA

stock = Stock("CPALL")           # .get_highlight_data() .get_profile() .get_latest_price()
                                 # .get_news() .get_asset_type() .get_analyst_consensus()
                                 # .get_info() .get_signs() .is_suspended() ...
index = SetIndex("SET50")        # .get_info() .get_constituents() .get_latest_price()
sec = SecCompany("CPALL")        # .list_documents() .download_all()
tbma = ThaiBMA()                 # .get_yield_curve() .get_history() .get_availability()
```

Not every service has a `Stock` accessor — financials, trading stats, price performance,
corporate actions, NVDR holders and the board list are reached through their module-level
`get_*()` functions.

---

## Traps that make an agent answer *wrongly*

These are live-probed behaviours, not theory. Each one returns a plausible-looking result while
being wrong, so none of them will announce itself.

### Errors that do not mean what their status code says

| Behaviour | What you must do |
|---|---|
| **Analyst consensus answers an uncovered symbol with HTTP 500, not 404** — and "uncovered" includes perfectly valid SET stocks (`ABICO`), DRs (`GOOG80`) and warrants (`JAS-W4`) | catch `FetchError`; report "no analyst coverage". **Do not** retry it as a typo or suggest a different symbol |
| **The DR-profile endpoint 404s for every non-DR symbol**, including `CPALL` | a 404 here means "not a DR", not "unknown symbol" |
| **The consensus summary endpoint fails silently**: an unknown symbol is HTTP 200 with `overall: []` | check `.count`, or use `.get(symbol)` which returns `None` |
| **The holiday endpoint returns HTTP 401 for any year but the current one** — and transiently on valid requests too | do not treat 401 as auth failure; there is no auth |

### Values that are placeholders, not data

| Behaviour | What you must do |
|---|---|
| **A listed stock nobody covers returns `0.0` for every consensus aggregate**, not `null` | check `AnalystConsensus.has_coverage` first. Never report a `0.0` target price as an estimate |
| **`ThaiBMA` never 404s on a date — it silently rolls back** to the previous business day, and a *future* date returns today | check `is_rolled_back` / `rollback_days` before quoting an "as of" date |
| **ThaiBMA classification flags were never backfilled**: `is_benchmark` is all-false before 2013 | filtering history on it yields an empty set, not an error |
| **A missing value in a `to_dataframe()` string column is `NaN` on pandas 3, `None` on pandas 2** — settfex supports both, so this depends on the installed pandas | test with `pd.isna(value)`, never `value is None`. Serialise with `df.to_json()` — `json.dumps(df.to_dict("records"))` emits a bare `NaN`, which is not valid JSON |

### Units and formats

| Behaviour | What you must do |
|---|---|
| **ThaiBMA rows mix units**: `yield_percent` is a percent, `change_bps` is **basis points** | never add them; use `change_percent` if you need the same unit |
| **Analyst-consensus net profit is in MILLION baht**; `*_div` is a dividend **yield in percent**, not baht per share | label your output accordingly |
| **News dates are `dd/MM/yyyy` ONLY** — an ISO date returns HTTP 400 | pass a `datetime.date`, which the service converts for you |
| **News history is a rolling 1826 days (~5 years)** | a `from_date` older than that fails the whole request; it does not clip |
| **Index endpoints use `?language=`, stock endpoints use `?lang=`** | you never build URLs yourself — but if you drop to raw HTTP, the wrong one silently returns the wrong language |

### Results that are correct but not what they look like

| Behaviour | What you must do |
|---|---|
| **`Stock.get_latest_price()` returns a TradingView *indicative* price for DRs**, not a SET trade — `volume` and `change` are `None` | divergence from the DR's SET close is expected, not a bug. Pass `prefer_dr_indicative=False` for the SET-traded price |
| **A consensus aggregate row is not any one broker's row** — every column is aggregated independently. `high.target_price` and `high.target_price_change` came from *different* brokers in a live probe | never reconstruct one field from another across an aggregate row |
| **`HolidayCalendar.is_holiday()` is not "is the market open"** — weekends are absent from the payload | combine it with a weekday check |
| **`SET` and `mai` have no constituent list** (HTTP 404) | query a sub-index such as `SET50`, a sector, or an industry |
| **The analyst-consensus table endpoint ignores `?lang=`** | there is no Thai version; `recommend` is broker-supplied English free text |
| **The stock LIST carries no trading sign** — `remark` is `""` on all 3,954 rows | a symbol's SP/NC/NP status comes from `get_stock_info(symbol)`, never from the list |
| **`sign` packs several codes into one string** (`"SP, CB, CS, CC"`) — only 1 of 28 suspended stocks had a bare `"SP"` | test with `.has_sign("SP")` or `"SP" in .signs`, never `sign == "SP"` |
| **`market_status` says `'Closed'` for every symbol after hours** — it is not a suspension flag | use `.is_suspended`, which reads the per-symbol sign |
| **A suspended symbol returns HTTP 200 with `last`/OHLC/volume all `null`** and an empty book | that is data, not an error; quote `.prior` as its last known price |
| **A market-wide sign scan via index compositions sees COMMON STOCKS only** (929 of 3,954 symbols) | suspended warrants/DWs/DRs are invisible to it — check those with `get_stock_info()` |

---

## Errors you should expect

Everything is importable from one place:

```python
from settfex.exceptions import (
    # --- the FETCH family: `except FetchError` catches all of these ---
    FetchError,              # HTTP/transport failure; carries .status_code and .symbol
    HTTPStatusError,         # a non-2xx, with .url and .report_code as data
    SymbolNotFoundError,     # HTTP 404 on a SET endpoint; may carry .suggestion
    StaleDataError,          # ThaiBMA rolled back and you asked it to raise
    ParseError,              # a response arrived intact and could not be mapped
    IncompleteListingError,  # a ParseError: rows classified, then every one was lost
    # --- INPUT errors: ValueErrors, NOT caught by `except FetchError` ---
    CompanyNotFoundError,    # SEC: the search ran and matched no issuer
    AmbiguousCompanyError,   # SEC: several matched, none flagged; carries .candidates
    InvalidSymbolError,      # empty symbol — raised before any request
    InvalidLanguageError,    # unrecognized lang
    InvalidDateError,        # malformed date string — raised before any request
)
from settfex.utils.parsing import ResponseParseError   # also a ParseError since 0.24.0
```

**The split is the thing to internalise: a `FetchError` may be worth retrying; a `ValueError`
never is.** An input error means the request *succeeded* and your argument was wrong, so a retry
loop on one spins forever. `InvalidSymbolError`, `InvalidLanguageError` and `InvalidDateError` are
raised before any network call at all.

⚠️ Two "not found" taxonomies coexist today: a SET 404 is a `SymbolNotFoundError` (a `FetchError`),
while the SEC equivalent is a `CompanyNotFoundError` (a `ValueError`). Catch both if you handle
both hosts. Unifying them is tracked on #135.

⚠️ `ResponseParseError` is also what a **WAF block page** currently surfaces as — right family,
wrong diagnosis. If you see it repeatedly from one host, **stop and back off**; do not retry.

---

## Timed instructions

If you are told to do something at a particular time, that instruction needs **a date, a clock time
and a timezone** — `2026-09-21 17:00 ICT`. Relative words (*today*, *tonight*, *after close*) are
ambiguous the moment a conversation spans midnight or is resumed later, and they give no signal
that they have gone stale.

**Check the current time before acting on one.** If the window has passed, say so and ask rather
than substituting the nearest equivalent — the reason a window was chosen (avoiding market hours,
avoiding another system's traffic) usually does not survive being moved by a day.

## Communication language

- All prose you write is in English: reports and chat replies to the operator, commit messages,
  PR descriptions, GitHub issues and comments, docs, ADRs, and code comments.
- Thai appears only as verbatim source data: document titles, labels (e.g. `สอบทาน`), company
  names, URLs, quoted page text, and fixture contents. Keep it exactly as the source has it —
  never translate or transliterate the data itself.
- When a Thai value's meaning matters to the reader, add an English gloss next to it:
  `สอบทาน` (reviewed).

## Working on the repo itself

```bash
uv sync                      # install (includes the dev group)
uv run pytest                # test suite
uv run ruff check .          # lint
uv run ruff format --check . # formatting — a SEPARATE gate; `ruff check` passing does not imply it
uv run mypy .                # type-check (strict)
```

CI runs all four. `ruff` also formats `.ipynb`, so example notebooks must satisfy it too
(`.md` files are deliberately excluded from ruff — do not remove `extend-exclude` from
`pyproject.toml`). Live-endpoint smoke probes exist as opt-in integration tests:
`uv run pytest -m integration --no-cov` (excluded from the default run; they hit the real
SET/TFEX/ThaiBMA hosts — see the Dependency policy in `CLAUDE.md` for when they are mandatory).

Deeper context lives in [`CLAUDE.md`](CLAUDE.md) (architecture, service-design patterns, the
complete Known Gotchas list) and in per-service pages under
[`docs/settfex/services/`](docs/settfex/services/). Release steps are in
[`RELEASING.md`](RELEASING.md).

---

## Please note

settfex is **not officially affiliated** with SET or TFEX. It reads **public** market data.
Browser impersonation and session caching exist to access that public data reliably and to
*reduce* request volume (~25× fewer requests) — not to evade rate limits or terms of service.
Respect both.

**If you are sweeping many symbols, budget it.** These are other people's servers, and they push
back: a 929-symbol sweep at concurrency 8 drew connection resets and then a WAF block page — an
**HTTP 200 whose body reads `Request Rejected`** — for every request for about an hour
(2026-09-20). Use concurrency 1 with jittered pauses, decide a request budget before you start,
prefer a stratified sample over a census, and **stop at the first block signal** rather than
retrying into it.
