# Stock Chart Quotation Service

## Overview

The Stock Chart Quotation Service fetches the **intraday (and historical) chart-quotation feed**
for an individual SET stock symbol — the per-interval price / volume / value / change series shown
on the SET price chart. On top of that raw series it provides a first-class way to retrieve the
**latest *traded* price relative to now**, correctly excluding the null-valued buckets the API
pre-populates for the remainder of the trading day.

Endpoint: `GET /api/set/stock/{symbol}/chart-quotation?period=1D&accumulated=false`

## Key Features

- **Intraday + historical** — `period` of `1D`, `5D`, `1M`, `3M`, `6M`, `1Y`, `3Y`, `5Y`, `MAX`.
- **Latest traded price vs. now** — `get_latest_price()` returns the most recent quotation that
  actually traded (non-null `volume`), skipping future / lunch-break / no-trade buckets.
- **Timezone-correct** — quotation timestamps are tz-aware (`+07:00`); `as_of` inputs (naive or any
  zone) are normalized to Asia/Bangkok before comparison.
- **Hyphen-safe symbols** — warrant symbols like `JAS-W4` are preserved (only upper-cased/trimmed).
- **Type-safe** — full Pydantic models with camelCase→snake_case aliases.
- **Bot-detection handled** — `SessionManager` warms cookies and builds the symbol-specific referer
  automatically (Incapsula bypass); no manual cookie params.

## Installation

```bash
pip install settfex
```

## Quick Start

### Latest traded price (the headline capability)

```python
import asyncio
from settfex.services.set import get_latest_price

async def main():
    quotation = await get_latest_price("CPALL")        # latest TRADED point, relative to now
    if quotation:
        print(f"{quotation.local_datetime}: {quotation.price} (vol {quotation.volume})")
    else:
        print("Nothing has traded yet today.")

asyncio.run(main())
```

### Using the Stock class

```python
from settfex.services.set import Stock

stock = Stock("CPALL")
data = await stock.get_chart_quotation(period="1D")    # full ChartQuotation series
latest = await stock.get_latest_price()                # latest traded Quotation (or None)
```

### Using the convenience function

```python
from settfex.services.set import get_chart_quotation

data = await get_chart_quotation("JAS-W4", period="1D")  # hyphenated warrant symbol is fine
print(f"Prior close: {data.prior}, points: {len(data.quotations)}")
print(f"Latest price (scalar, prior-fallback): {data.get_latest_price()}")
```

### Using the service class

```python
from settfex.services.set.stock import ChartQuotationService

service = ChartQuotationService()
data = await service.fetch_chart_quotation("CPALL", period="1D", accumulated=False)
raw = await service.fetch_chart_quotation_raw("CPALL")   # unvalidated dict
```

## Latest-price selection rule

`ChartQuotation.get_latest_quotation(as_of=None)` returns the quotation with the **greatest
timestamp that is `<= as_of` and has a non-null `volume`** — i.e. the latest minute that actually
traded. This matters because the API returns one bucket per minute for the **whole session up to
end of day**; minutes that are in the future, fall in the lunch `intermission`, or simply had no
trade carry `volume = null` (the `price` may still be carried forward).

- **`as_of`** defaults to **now in `Asia/Bangkok`**. A naive `as_of` is treated as Bangkok local
  time; an aware `as_of` (e.g. UTC) is converted. Naive and aware datetimes are never compared
  directly — both sides are normalized to Bangkok first.
- **`get_latest_price(as_of=None)`** (on the model) returns that quotation's `price`, **falling
  back to `prior`** (the previous session's close) when nothing has traded yet, or `None` if
  `prior` is also unavailable.
- **Top-level `get_latest_price(symbol, …)`** returns the full **`Quotation`** object (time, price,
  volume, change), or `None` — a single request, an O(n) scan, no re-fetching.

| Situation | `get_latest_quotation` | `model.get_latest_price` |
|---|---|---|
| Mid-session, after trades | latest traded `Quotation` | its `price` |
| Before the open / all-null series | `None` | `prior` (fallback) |
| `as_of` inside the lunch break | last morning trade | its `price` |
| Empty series, `prior` set | `None` | `prior` |
| Empty series, `prior` is `None` | `None` | `None` |

## API Reference

### Models

#### `Quotation`

| Field | Type | JSON alias | Description |
|-------|------|-----------|-------------|
| `quote_datetime` | `datetime` | `datetime` | Timestamp, timezone-aware (`+07:00`) |
| `local_datetime` | `datetime` | `localDatetime` | Same instant, naive Bangkok local time |
| `price` | `float \| None` | `price` | Trade price (may be carried forward on no-trade) |
| `volume` | `float \| None` | `volume` | Trade volume (shares); `None` = no trade this bucket |
| `value` | `float \| None` | `value` | Trade value (THB) |
| `change` | `float \| None` | `change` | Price change from prior close |
| `percent_change` | `float \| None` | `percentChange` | Percentage change from prior close |

#### `Intermission`

| Field | Type | Description |
|-------|------|-------------|
| `begin` | `datetime` | Intermission start (e.g. lunch break), naive Bangkok |
| `end` | `datetime` | Intermission end, naive Bangkok |

#### `ChartQuotation`

| Field / Method | Type | Description |
|----------------|------|-------------|
| `prior` | `float \| None` | Prior trading day's close |
| `intermissions` | `list[Intermission]` | Trading intermission periods |
| `quotations` | `list[Quotation]` | Per-interval quotation points |
| `get_latest_quotation(as_of=None)` | `Quotation \| None` | Latest *traded* quotation at/before `as_of` |
| `get_latest_price(as_of=None)` | `float \| None` | Latest traded price, falling back to `prior` |

### Service Class — `ChartQuotationService`

| Method | Returns | Description |
|--------|---------|-------------|
| `fetch_chart_quotation(symbol, period="1D", accumulated=False)` | `ChartQuotation` | Validated model |
| `fetch_chart_quotation_raw(symbol, period="1D", accumulated=False)` | `dict` | Unvalidated raw dict |

### Convenience Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `get_chart_quotation(symbol, period="1D", accumulated=False, config=None)` | `ChartQuotation` | One-line fetch |
| `get_latest_price(symbol, period="1D", accumulated=False, as_of=None, config=None)` | `Quotation \| None` | Latest traded quotation vs `as_of` |

## Usage Examples

### Example 1 — "What's the price right now?"

```python
from settfex.services.set import get_latest_price

q = await get_latest_price("PTT")
print("No trades yet" if q is None else f"{q.price} @ {q.local_datetime} (vol {q.volume})")
```

### Example 2 — Price as of a specific instant

```python
from datetime import datetime
from settfex.services.set import get_latest_price

# Naive datetime is interpreted as Asia/Bangkok local time
q = await get_latest_price("CPALL", as_of=datetime(2026, 6, 19, 11, 0))
print(q.price if q else "Nothing traded by 11:00")
```

### Example 3 — Build a simple intraday table

```python
from settfex.services.set import get_chart_quotation

data = await get_chart_quotation("CPALL", period="1D")
for q in data.quotations:
    if q.volume is not None:                 # skip null/no-trade buckets
        print(f"{q.local_datetime:%H:%M}  {q.price:>8}  {q.volume:>12,.0f}")
```

## Error Handling & Troubleshooting

- **Empty symbol** → `ValueError`.
- **Non-200 HTTP response** → `Exception` with the status code (e.g. `HTTP 403`).
- **`get_latest_price` returns `None`** → nothing has traded by `as_of` (before the open, a holiday,
  or an all-null series). Use the model's `get_latest_price()` for the `prior`-fallback scalar.
- **Markets closed** → the `1D` series for the most recent session is returned; the latest traded
  point is that session's last trade.
