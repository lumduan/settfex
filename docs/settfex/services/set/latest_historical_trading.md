# Stock Latest Historical Trading Service

## Overview

The Stock Latest Historical Trading Service fetches the **latest completed trading-day summary** for
an individual SET stock symbol — OHLC prices, volume/value, and valuation metrics (P/E, P/BV,
dividend yield, market cap, book value) for the most recent session.

Endpoint: `GET /api/set/stock/{symbol}/latest-historical-trading`

## Key Features

- **One-shot daily summary** — open/high/low/close/average, change/%change, total volume & value.
- **Valuation metrics** — P/E, P/BV, dividend yield, market cap, book value per share, listed shares.
- **Type-safe** — full Pydantic model with camelCase→snake_case aliases.
- **Symbol normalization** — lowercase input is upper-cased and trimmed.
- **Bot-detection handled** — `SessionManager` warms cookies and builds the symbol-specific referer
  automatically (Incapsula bypass); no manual cookie params.

## Installation

```bash
pip install settfex
```

## Quick Start

### Using the convenience function

```python
import asyncio
from settfex.services.set import get_latest_historical_trading

async def main():
    trading = await get_latest_historical_trading("CPALL")
    print(f"Date: {trading.date}")
    print(f"Close: {trading.close:.2f} THB ({trading.percent_change:+.2f}%)")
    print(f"P/E: {trading.pe}, P/BV: {trading.pbv}")
    print(f"Market Cap: {trading.market_cap:,.0f} THB")

asyncio.run(main())
```

### Using the Stock class

```python
from settfex.services.set import Stock

stock = Stock("CPALL")
trading = await stock.get_latest_historical_trading()
```

### Using the service class

```python
from settfex.services.set.stock import LatestHistoricalTradingService

service = LatestHistoricalTradingService()
trading = await service.fetch_latest_historical_trading("CPALL")
raw = await service.fetch_latest_historical_trading_raw("CPALL")   # unvalidated dict
```

## API Reference

### Model — `LatestHistoricalTrading`

| Field | Type | JSON alias | Description |
|-------|------|-----------|-------------|
| `date` | `datetime` | `date` | Trading date (tz-aware, +07:00) |
| `symbol` | `str` | `symbol` | Stock symbol |
| `prior` | `float \| None` | `prior` | Prior closing price |
| `open` | `float \| None` | `open` | Opening price |
| `high` | `float \| None` | `high` | Day's high |
| `low` | `float \| None` | `low` | Day's low |
| `average` | `float \| None` | `average` | Average price |
| `close` | `float \| None` | `close` | Closing price |
| `change` | `float \| None` | `change` | Change from prior close |
| `percent_change` | `float \| None` | `percentChange` | Percentage change from prior close |
| `total_volume` | `float \| None` | `totalVolume` | Total volume (shares) |
| `total_value` | `float \| None` | `totalValue` | Total value (THB) |
| `pe` | `float \| None` | `pe` | Price-to-Earnings ratio |
| `pbv` | `float \| None` | `pbv` | Price-to-Book Value ratio |
| `book_value_per_share` | `float \| None` | `bookValuePerShare` | Book value per share (THB) |
| `dividend_yield` | `float \| None` | `dividendYield` | Dividend yield (%) |
| `market_cap` | `float \| None` | `marketCap` | Market capitalization (THB) |
| `listed_share` | `float \| None` | `listedShare` | Number of listed shares |
| `par` | `float \| None` | `par` | Par value per share (THB) |
| `financial_date` | `datetime \| None` | `financialDate` | Financial data reference date |
| `nav` | `float \| None` | `nav` | Net asset value (ETF/fund) |
| `market_index` | `str \| None` | `marketIndex` | Market index name |
| `market_percent_change` | `float \| None` | `marketPercentChange` | Market index percent change |

> Note: the ratio fields are `pe` and `pbv` (not `pe_ratio` / `pb_ratio`).

### Service Class — `LatestHistoricalTradingService`

| Method | Returns | Description |
|--------|---------|-------------|
| `fetch_latest_historical_trading(symbol)` | `LatestHistoricalTrading` | Validated model |
| `fetch_latest_historical_trading_raw(symbol)` | `dict` | Unvalidated raw dict |

### Convenience Function

| Function | Returns | Description |
|----------|---------|-------------|
| `get_latest_historical_trading(symbol, config=None)` | `LatestHistoricalTrading` | One-line fetch |

## Usage Examples

### Example 1 — Daily snapshot

```python
from settfex.services.set import get_latest_historical_trading

d = await get_latest_historical_trading("PTT")
print(f"{d.symbol}: close {d.close} ({d.percent_change:+.2f}%), vol {d.total_volume:,.0f}")
```

### Example 2 — Compare valuations across symbols

```python
from settfex.services.set import get_latest_historical_trading

for sym in ["CPALL", "PTT", "KBANK"]:
    d = await get_latest_historical_trading(sym)
    print(f"{d.symbol:<8} P/E={d.pe}  P/BV={d.pbv}  Yield={d.dividend_yield}%")
```

## Error Handling & Troubleshooting

- **Empty symbol** → `ValueError`.
- **Non-200 HTTP response** → `Exception` with the status code (e.g. `HTTP 404`).
- **Markets closed / weekend** → the most recent completed session's summary is returned.

## Related Services

- [Chart Quotation & Latest Price](chart_quotation.md) — intraday per-minute series + the latest
  *traded* price relative to now.
- [Highlight Data](highlight_data.md) — P/E, P/B, market cap, dividends, 52-week range, NVDR.
