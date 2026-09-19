# Stock Info Service (Live Quote Block & Trading Signs)

## Overview

Fetches the payload behind the header of a set.or.th quote page: the trading **sign**
(`SP`/`NC`/`NP`/`CB`/`XD`…), the current price and OHLC, the best bid/offer, and the reference
data SET shows alongside them (par, tick size, 52-week range, underlying, exercise terms,
iNAV).

**Endpoint:** `GET https://www.set.or.th/api/set/stock/{symbol}/info`

This is the only endpoint in the package that carries `sign`, and it serves **every** listed
security type — the stock list has no sign field at all, and index compositions cover common
stocks only.

## Key Features

- **Trading signs for any symbol** — including warrants, DWs and DRs, which no other route reaches
- **Parsed sign helpers** — `signs`, `has_sign()`, `is_suspended` instead of string matching
- **Every security type** — stocks, foreign (`-F`), preferred (`-P`/`-Q`), warrants, DWs, DRs,
  ETFs, unit trusts; type-specific fields are `None` where they do not apply
- **Best bid/offer** — `best_bid` / `best_offer` convenience properties
- **Computed fields** — `signs` and `is_suspended` survive `model_dump()` into Parquet/JSON
- **Asset type** — `asset_type` maps `securityType` to the friendly `AssetType` enum

## Installation

```bash
uv add settfex
```

## Quick Start

### Using the convenience function

```python
import asyncio
from settfex.services.set import get_stock_info


async def main():
    info = await get_stock_info("INGRS")
    print(info.signs)          # ['SP']
    print(info.is_suspended)   # True
    print(info.market_status)  # 'Suspend'
    print(info.last, info.prior)  # None 0.09  (a halted symbol has no last trade)


asyncio.run(main())
```

### Using the Stock class

```python
from settfex.services.set import Stock

stock = Stock("GRAND")
info = await stock.get_info()        # full quote block
signs = await stock.get_signs()      # ['SP', 'CB', 'CS', 'CC']
halted = await stock.is_suspended()  # True
```

`get_info()` is deliberately **not cached** — it is live trading state, unlike
`get_asset_type()` or `get_dr_profile()`.

### Using the service class

```python
from settfex.services.set.stock.info import StockInfoService
from settfex.utils.data_fetcher import FetcherConfig

service = StockInfoService(config=FetcherConfig(timeout=60))
info = await service.fetch_stock_info("CPALL")
raw = await service.fetch_stock_info_raw("CPALL")   # unvalidated dict
```

## API Reference

### Model — `StockInfo`

**Identity and signs**

- `symbol: str` — ticker
- `sign: str | None` — active signs, comma-separated (`"SP, CB, CS, CC"`); `""` when untagged
- `signs: list[str]` — *computed*: parsed sign codes (`['SP', 'CB', 'CS', 'CC']`)
- `is_suspended: bool` — *computed*: whether `SP` is active
- `has_sign(code) -> bool` — case-insensitive exact-code test
- `asset_type: AssetType` — derived from `security_type`
- `security_type: str | None` — SET code (`'S'`, `'W'`, `'V'`, `'X'`, `'L'`, …)
- `name_en` / `name_th: str | None` — security name in both languages (always both)

**Price and activity**

- `prior`, `last`, `open`, `high`, `low`, `average`, `floor`, `ceiling: float | None`
- `change`, `percent_change: float | None`
- `total_volume`, `total_value`, `tr_volume`, `tr_value`, `aom_volume`, `aom_value: float | None`
- `bids`, `offers: list[BidOffer]` — ladder, best first; `price` arrives as a string and is
  coerced to float
- `best_bid`, `best_offer: float | None` — first ladder level, or `None` when the book is empty

**Market state**

- `market_status: str | None` — `'Open2'`, `'Closed'`, `'Suspend'`, …
- `market_date_time: datetime | None` — tz-aware `+07:00` snapshot time

**Reference data**

- `market_name`, `industry_name`, `sector_name: str | None` — the last two are `""` for
  warrants/DWs/DRs/ETFs
- `tick_size`, `par`, `high_52_weeks`, `low_52_weeks: float | None`
- `underlying: str | None`, `is_npg`, `is_iff`, `is_pfund: bool | None`

**Derivative / fund specifics** (`None` for ordinary stocks)

- `inav: Inav | None` — ETFs only; `.inav`, `.change`, `.percent_change`
- `multiplier: float | None`, `exercise_ratio: float | str | None` (verbatim, e.g. `'3,000 : 1'`)
- `exercise_price: float | None`, `exercise_price_unit: str | None` (`'THB'`, `'USD'`, `'Point'`)
- `maturity_date`, `last_trading_date: datetime | None`, `ttm: int | None` (days)
- `moneyness_status: str | None` (`'ITM'`/`'ATM'`/`'OTM'`), `moneyness_percent: float | None`

**Valuation** (as of `statistics_as_of`)

- `market_cap`, `pe_ratio`, `pb_ratio`, `dividend_yield`, `nvdr_net_volume`, `listed_share`

### Service Class — `StockInfoService`

- `StockInfoService(config: FetcherConfig | None = None)`
- `async fetch_stock_info(symbol: str) -> StockInfo`
- `async fetch_stock_info_raw(symbol: str) -> dict[str, Any]`

### Convenience Function

- `async get_stock_info(symbol: str, config: FetcherConfig | None = None) -> StockInfo`

### Helper

- `parse_signs(sign: str | None) -> list[str]` — split SET's comma-separated sign string into
  uppercase codes; `""`/`None` give `[]`

### No `lang` argument — on purpose

The endpoint has **no language dimension**: `?lang=en` and `?lang=th` return byte-identical
payloads, and both names are always present as `name_en` / `name_th`. Do not add a `lang`
parameter "for consistency" — it would be silently ignored. (Same shape as the analyst-consensus
table endpoint.)

## Usage Examples

### Example 1 — Screen a watchlist for suspensions

```python
import asyncio
from settfex.services.set import get_stock_info

WATCHLIST = ["CPALL", "PTT", "INGRS", "GRAND", "KBANK"]


async def main():
    infos = await asyncio.gather(*(get_stock_info(s) for s in WATCHLIST))
    for info in infos:
        flag = ", ".join(info.signs) or "-"
        print(f"{info.symbol:8s} {flag:20s} last={info.last}")


asyncio.run(main())
```

### Example 2 — Every symbol currently carrying SP (market-wide)

One request per symbol would be ~4,000 requests. Index compositions carry the same `sign`
field for all 929 common stocks in ~36 requests:

```python
import asyncio
from settfex.services.set.index.composition import IndexCompositionService
from settfex.services.set.index.list import IndexListService
from settfex.services.set.stock.info import parse_signs


async def symbols_with_sign(code: str = "SP") -> dict[str, str]:
    index_list = await IndexListService().fetch_index_list()
    # SET sectors + mai industries ('-m'). SET's own INDUSTRY compositions come back EMPTY.
    targets = [
        ix for ix in index_list.indices
        if ix.level == "SECTOR" or ix.query_symbol.endswith("-m")
    ]
    service = IndexCompositionService()
    results = await asyncio.gather(
        *(service.fetch_composition(ix.query_symbol) for ix in targets),
        return_exceptions=True,
    )
    flagged: dict[str, str] = {}
    for result in results:
        if isinstance(result, BaseException):
            continue
        for constituent in result.composition.stock_infos:
            if code in parse_signs(constituent.sign):
                flagged[constituent.symbol] = constituent.sign or ""
    return dict(sorted(flagged.items()))


print(asyncio.run(symbols_with_sign("SP")))
```

Coverage note: this reaches common stocks (`securityType == 'S'`) only. A suspended **warrant,
DW, DR, ETF or unit trust** is invisible to it — check those individually with
`get_stock_info()`.

### Example 3 — Derivative warrant terms

```python
info = await get_stock_info("AAV13C2610A")
print(info.underlying)           # 'AAV'
print(info.exercise_price)       # 1.45
print(info.exercise_ratio)       # '0.36 : 1'  (verbatim display string)
print(info.ttm)                  # 12   (days to maturity)
print(info.moneyness_status)     # 'OTM'
```

## Trading Signs

Names below are SET's own, from the Trading Signs table on
[set.or.th → Market → News and Alert → Sign Posting](https://www.set.or.th/en/market/news-and-alert/sign-posting)
(verified 2026-09-19):

| Sign | Meaning |
|---|---|
| `SP` | Suspend — trading suspended |
| `H` | Halt — trading halted intraday |
| `P` | Pause / Auto Pause |
| `NP` | Notice Pending |
| `NC` | Non-Compliance |
| `CB` | Caution - Business |
| `CS` | Caution - Financial Statement |
| `CF` | Caution - Free Float |
| `CC` | Caution - Non-Compliance |
| `XD` | Excluding Dividend |
| `XR` | Excluding Right |
| `XW` | Excluding Warrant |
| `XE` | ESOP |

Signs combine freely: `"SP, CB, CS, CC"` is a real payload value. Always test with
`has_sign()` or membership in `signs`, never with `sign == "SP"`.

**Company vs security counts.** SET's page counts both. On 2026-09-18 it reported SP on
18 SET + 10 mai **companies** (28) and 40 SET + 13 mai **securities** (53). The
composition scan in Example 2 returned exactly those 28 companies; the remaining 25 securities
are the warrant, foreign (`-F`) and preferred (`-P`/`-Q`) lines of the same issuers, which only
`get_stock_info()` can reach.

## Error Handling & Troubleshooting

| Situation | Behavior |
|---|---|
| Unknown symbol | HTTP 404 `{"message": "Invalid Stock Name"}` → `SymbolNotFoundError` (with a "did you mean?" suggestion when a stock list was fetched earlier this session) |
| Empty/whitespace symbol | `InvalidSymbolError` before any request |
| Other HTTP failure | `FetchError` with `status_code` |
| Unparseable body | `ResponseParseError` |

Notes:

- A halted symbol returns HTTP 200 with `last`/`open`/`high`/`low`/volume all `null` and an
  empty book — that is data, not an error. Use `prior` for the last known price.
- `market_status` reads `'Closed'` for every symbol outside trading hours, so it cannot stand in
  for `is_suspended`, which reads the per-symbol sign.
- `market_date_time` arrives with **nanosecond** precision (9 fractional digits); Python
  datetimes hold microseconds, so it is truncated on parse.
- Over plain HTTP the ladder carries the **best level only**; the full 5-level depth on the SET
  website comes from its websocket feed.

## Related Services

- [`list.md`](list.md) — the stock directory (no sign field; `remark` is empty on every row)
- [`index.md`](index.md) — index/sector compositions, the market-wide `sign` source
- [`latest_historical_trading.md`](latest_historical_trading.md) — previous session's OHLCV summary
- [`chart_quotation.md`](chart_quotation.md) — intraday series and latest traded price
