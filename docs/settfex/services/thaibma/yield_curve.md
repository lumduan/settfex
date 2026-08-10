# ThaiBMA Government Bond Yield Curve (www.thaibma.or.th)

## Overview

Fetches the **official Thai government bond yield curve** published by ThaiBMA (the Thai Bond
Market Association) — the fitted par curve, the bond quotes behind it, and whole years of daily
history. This is settfex's first fixed-income service and its first non-SET/TFEX/SEC host.

Modules: `settfex/services/thaibma/{yield_curve,history,availability,thaibma}.py` ·
Three tiers: `get_government_yield_curve()` (one-call convenience, the LLM tool-calling entry
point) → `YieldCurveService.fetch_curve()` (validated Pydantic models) →
`YieldCurveService.fetch_curve_raw()` (raw `dict` escape hatch).

Coverage runs from **1999-09-15** to the current business day — about 6,600 business days.

> ### ⚠️ Five API gotchas (live-verified 2026-08-10)
>
> 1. **The curve endpoint never 404s on a date — it rolls back silently.** It serves the most
>    recent curve *on or before* the request. A Saturday returns Friday's; a Thai public holiday
>    returns the previous business day's; **any future date returns today's** (`2030-01-01` →
>    `Asof 2026-08-10`), all with HTTP 200 and no marker. Every `YieldCurve` therefore carries
>    `requested_date`, `as_of`, `is_rolled_back` and `rollback_days`.
> 2. **`yield_percent` is in percent but `change_bps` is in basis points.** Proved by differencing
>    two consecutive business days: a `-0.005534%` move is published as `Change: -0.5534`. The
>    field names carry the units; `change_percent` is the safe-to-add derived form.
> 3. **A date before 1999-09-15 returns HTTP 200 with a body of literal `null`** — not `{}`, not a
>    404. Rejected client-side before the request; also handled defensively if it ever changes.
> 4. **Malformed dates fail in two different silent ways.** `2026-8-10` (unpadded) returns an
>    **HTML** 404 page; `2026-02-30` (well-formed but impossible) returns HTTP 200 with the
>    **latest** curve. Both are made unreachable by client-side normalization.
> 5. **The classification flags were never backfilled.** `IsBenchmark` is all-false before **2013**
>    and `IsSynthetic` all-false before **2014**. Filtering historical data on `is_benchmark`
>    yields an empty set for the first ~14 years — that is the data, not a bug. `IsPlot` was `True`
>    on every row in every era sampled, so it is not a useful filter either.

## Quick Start

```python
from settfex.services.thaibma import ThaiBMA, get_government_yield_curve

# One-call convenience
curve = await get_government_yield_curve()          # the latest published curve
print(curve.as_of, curve.yield_at("10Y"))           # 2026-08-10 2.060279
print(curve.slope_bps("2Y", "10Y"))                 # 92.73  (the 2s10s, in bp)

# Or via the facade
tbma = ThaiBMA()
curve = await tbma.get_yield_curve("2026-08-10")
history = await tbma.get_history("2020-01-01")      # 7 requests, not ~1,600
```

## History is one request per year, not per day

The obvious way to build a yield history is to walk business days through
`/yieldcurve/gov/{date}` — roughly **6,600 requests** for the full record. Two bulk endpoints
return an entire calendar year each, so the complete 1999→2026 history is **28 requests**. They are
not linked from any API index or documentation, only from the ThaiBMA website's own JavaScript.

```python
from settfex.services.thaibma import get_yield_curve_history, get_bond_yield_history

# Constant-maturity matrix: one row per business day, one column per tenor
history = await get_yield_curve_history("2020-01-01", "2026-08-10")
print(history.count, len(history.columns))       # 1608 54
print(history.series("10Y")[-1])                 # (date(2026, 8, 10), 2.060279)

df = history.to_dataframe()                      # index=as_of, columns=1M..51Y
df["10Y"].plot()

# Per-bond matrix: columns are ThaiBMA bond symbols
bonds = await get_bond_yield_history("2026-01-01")
print(bonds.series("LB776A")[-1])
```

`start_date` defaults to **1 January of the end year**, not 1999 — a bare `fetch_history()` must
never trigger a 28-request full-history pull by accident. Ask for the whole record explicitly:

```python
history = await get_yield_curve_history("1999-09-15", progress=True)
```

### The two matrices are not redundant

| Endpoint | Reproduces | Extra |
|---|---|---|
| `getintpttm` (`kind="tenor"`) | the fitted `Curve` exactly (53/53 tenors match to 1e-6) | labelled tenors instead of float `X` |
| `getbyyear` (`kind="bond"`) | `Stat.Yield` exactly (50/50 symbols) | **9 extra bonds** the daily panel omits — inflation-linked (`ILB`) and amortizing (`LBA`) issues quoted but excluded from curve fitting |

## Handling the silent roll-back

`on_rollback` controls what happens when ThaiBMA answers with a different date than you asked for:

| Policy | Behaviour |
|---|---|
| `"warn"` *(default)* | Logs a warning naming both dates and `rollback_days`; returns the curve, flagged. |
| `"raise"` | Raises `StaleDataError` carrying `requested_date`, `as_of` and `rollback_days`. |
| `"allow"` | Silent. The model flags are still set. |

`"warn"` is the default because `"raise"` would break the most natural usage — iterating a date
range hits a weekend every week — and people respond to that by wrapping everything in a bare
`except`, which is worse than the trap. `"allow"` exists so a backtest that *intends* to walk
calendar days does not emit ~100 warnings a year and teach you to filter the logger.

```python
curve = await tbma.get_yield_curve("2026-08-08")     # a Saturday
curve.is_rolled_back, curve.as_of, curve.rollback_days
# (True, datetime.date(2026, 8, 7), 1)

# A capture pipeline that must never write a wrong-dated row:
curve = await tbma.get_yield_curve(day, on_rollback="raise")
```

`is_rolled_back` and `rollback_days` are Pydantic **computed fields**, so they survive
`model_dump()` and `model_dump_json()` — a curve persisted to Parquet keeps the audit trail of what
was asked for versus what was served.

`rollback_days` is the diagnostic: 1–4 days is an ordinary weekend or public holiday; a large value
means you asked for a future date.

## Models

### `YieldCurve`

| Field / property | Type | Notes |
|---|---|---|
| `requested_date` | `date \| None` | What you asked for; `None` means "latest" |
| `as_of` | `date` | What ThaiBMA actually served |
| `is_rolled_back` | `bool` | Computed field — survives serialization |
| `rollback_days` | `int \| None` | Computed field — calendar days between the two |
| `points` | `list[CurvePoint]` | The fitted curve |
| `quotes` | `list[BondQuote]` | The underlying bonds and T-Bills |
| `count`, `tenors`, `tenor_labels` | | Curve shape |
| `benchmarks`, `bills`, `bonds` | `list[BondQuote]` | Filtered views (see gotcha 5) |
| `to_dict()` | `dict[str, float]` | `{"10Y": 2.060279, ...}` in maturity order |
| `yield_at(tenor)` | `float \| None` | Exact grid lookup; accepts `"10Y"`, `10` or `10.0` |
| `interpolate(years)` | `float` | settfex's own linear interpolation — **never extrapolates** |
| `slope_bps(short, long)` | `float` | e.g. `slope_bps("2Y", "10Y")` for the 2s10s |
| `quote(symbol)` | `BondQuote \| None` | Case-insensitive lookup |
| `to_dataframe(kind)` | `pd.DataFrame` | `"curve"` (default) or `"quotes"` |

### `CurvePoint`

| Field | Wire | Notes |
|---|---|---|
| `as_of` | `Asof` | Plain `date` |
| `tenor_years` | `X` | `0.076712`=1M, `0.249315`=3M, `0.498630`=6M, then whole years |
| `yield_percent` | `Y` | **Percent** per annum |
| `tenor_label` | — | `"1M"` / `"10Y"` — the join key to the history matrices |

The tenor↔`X` mapping is exact, not a day-count approximation: `1M = 28/365`, `3M = 91/365`,
`6M = 182/365`, `{N}Y = N`. Verified by matching all 53 `getintpttm` columns against `Curve.Y`.

### `BondQuote`

| Field | Wire | Notes |
|---|---|---|
| `symbol` | `Symbol` | `"LB776A"`, `"T-BILL1M"` |
| `maturity_date` | `MaturityDate` | **Nullable** — `None` for the four synthetic T-BILL rows |
| `ttm_years` | `Ttm` | Time to maturity |
| `yield_percent` | `Yield` | **Percent** |
| `change_bps` | `Change` | **Basis points**. **Nullable** — `None` on 1999-09-15, the first curve ever published, which has no prior day to difference against |
| `change_percent` | — | Derived: `change_bps / 100`, safe to add to `yield_percent` |
| `spread` | `Spread` | As published. What it is a spread *to* was not independently verified, so the unit is deliberately **not** baked into the field name |
| `group_order` | `GroupOrder` | 1 = T-Bill, 2 = government bond |
| `is_synthetic` / `is_benchmark` / `is_plot` | | See gotcha 5 |

### `YieldCurveHistory`

Wide matrix with **dynamic columns**: tenors grew from 14 in 1999 (`1Y`…`14Y`, no sub-year tenors
at all) to 54 in 2026 (`1M`…`51Y`); bond symbols differ every year.

| Member | Notes |
|---|---|
| `rows` | `list[HistoryRow]`, ascending; each holds only **its own year's** columns |
| `columns` | The ordered **union** across all fetched years |
| `unavailable_years` | Requested years ThaiBMA does not serve |
| `missing_years` | Years whose fetch failed and was skipped |
| `series(column, dropna=True)` | One tenor's or bond's time series |
| `row_for(day)` | **Exact match only — no roll-back here** (a Saturday returns `None`) |
| `slice(start, end)` | Narrowed copy; recomputes `columns` |
| `columns_by_year()` | Makes the year drift inspectable |
| `coverage()` | Non-null count per column — spots a bond that stopped quoting |
| `to_long()` / `to_dataframe(layout=)` | Tidy triples / `"wide"` (default) or `"long"` |

**An absent column is not a null value.** `HistoryRow.has(column)` distinguishes "this year never
had the column" from "the column exists but was not quoted that day". A wide DataFrame flattens
both to `NaN`, so use `columns_by_year()` when the difference matters.

```python
row_1999 = history.rows[0]
row_1999.has("1M")     # False — ThaiBMA published no sub-year tenors in 1999
row_1999.has("1Y")     # True
```

### `YieldCurveAvailability`

`first_date` / `last_date` / `years`, plus `span_days`, `covers(day)` and `clamp(start, end)`.
`covers()` answers *"is this day inside the published range"* — **not** *"is there a curve stamped
exactly that day"*; weekends fall inside the window but have no curve of their own.

## Service classes

| Class | Methods |
|---|---|
| `YieldCurveService` | `fetch_curve()`, `fetch_curve_raw()`, `fetch_curves()` |
| `YieldCurveHistoryService` | `fetch_history()`, `fetch_history_raw()`, `fetch_year()`, `fetch_year_raw()` |
| `YieldCurveAvailabilityService` | `fetch_availability()`, `fetch_availability_raw()` |
| `ThaiBMA` (facade) | `get_yield_curve()`, `get_history()`, `get_bond_history()`, `get_availability()` |

`fetch_curves(dates)` fetches many dates concurrently — but **for yields alone use
`fetch_history()`**, which covers a whole year in one request rather than ~245. Reach for
`fetch_curves` only when you need the per-date `Stat` block (benchmark flags, spreads, per-bond
changes), which has no bulk endpoint.

## Convenience functions

```python
from settfex.services.thaibma import (
    get_government_yield_curve,   # point-in-time curve
    get_yield_curve_history,      # constant-maturity history
    get_bond_yield_history,       # per-bond history
    get_yield_curve_availability, # what history exists
)
```

## Reliability

The host is **stateless and unprotected** — live-probed 2026-08-10 it answered with no cookies, no
`User-Agent` and no referer, in ~0.2 s per request, and served 20 concurrent requests in 0.34 s
without throttling. Consequently:

- `use_session` is **forced off** for every ThaiBMA call. Routing this host through `SessionManager`
  would warm a ThaiBMA URL against set.or.th (its auto-detect sends everything that is not
  `tfex.co.th` to the SET warm-up).
- Headers are minimal and no `Referer` is invented for a host that provably needs none.
- Default fan-out concurrency is 5 — politeness, not a limit we were pushed to. For very large
  pulls use `FetcherConfig(rate_limit_delay=...)`.

Remember `AsyncDataFetcher.fetch()` retries **exceptions only, never a non-2xx status**, so every
call goes through `fetch_thaibma_json()`, which checks the status itself.

## Error handling

| Situation | Raised |
|---|---|
| Malformed / impossible date, or one before 1999-09-15 | `InvalidDateError` — **before any request** |
| Rolled-back date under `on_rollback="raise"` | `StaleDataError` (a `FetchError` subclass) |
| Body of literal `null`, or an empty `Curve`+`Stat` envelope | `FetchError` |
| Any non-2xx status | `FetchError` |
| Non-JSON or NaN/Infinity body | `ResponseParseError` |
| Unknown `kind`, inverted date span, out-of-range year | `ValueError` |

Error bodies are **never parsed**: ThaiBMA answers some bad routes with an ASP.NET
`{"Message": ...}` JSON and others with a plain HTML 404 page, so the status code is the only
trustworthy signal.

## Verified endpoints

| Route | Returns |
|---|---|
| `GET /yieldcurve/gov[/{YYYY-MM-DD}]` | `{"Curve": [...], "Stat": [...]}` |
| `GET /yieldcurve/getintpttm?year=YYYY` | Constant-maturity matrix for a whole year |
| `GET /yieldcurve/getbyyear?year=YYYY` | Per-bond matrix for a whole year |
| `GET /yieldcurve/avail` | `["1999-09-15T00:00:00", "<latest>"]` |
| `GET /yieldcurve/availyear` | `[1999, ..., <current year>]` |

`/api/yieldcurve/...` resolves to the same handlers; this package uses the bare form, which is what
the site's own front-end calls.

### Deliberately not implemented

Recorded so nobody has to re-discover them:

- **`GET /yieldcurve/zero[/{date}]`** — the government **zero-coupon** curve. Byte-for-byte the
  same `{"Curve", "Stat"}` envelope, so it would reuse every model here. Coverage starts
  **2001-07-02** (`/yieldcurve/avail?data=zero`). There is **no bulk-year history** for it
  (`getzerobyyear` → 404), which is also why `fetch_history()` takes no curve-type argument —
  accepting one and silently returning government data would be the worst possible outcome.
- **US Treasury curve** (`GetUSTreasuryYieldCurve`) — not Thai data.
- **Corporate industry spread curves** (`GetIndustrySpreadCurve`,
  `GetIndustrySpreadCurveConfidence`, `GetAllIndustry`) — corporate, not government.

## Related services

- [SET Market Holidays](../set/holiday.md) — SET's published closures. Note ThaiBMA's roll-back
  already lands on a bond-market business day, so you rarely need a calendar to use this service.
- [SEC Documents](../sec/financial_report.md) — the other separate-host, stateless service.
