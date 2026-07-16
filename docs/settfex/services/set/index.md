# SET Market Index Service

## Overview

The Market Index services fetch data for the Stock Exchange of Thailand's market indices — the
headline indices (SET, SET50, SET50FF, SET100, SET100FF, sSET, SETCLMV, SETHD, SETESG, SETWB,
mai), industry group indices, and sector indices:

- **Index directory** — every index the SET publishes, across all three levels
- **Index quotation** — the index page header data: last value, change, %change, open/high/low,
  volume, value, market status, and the data timestamp
- **Index composition** — the securities used to calculate an index ("หลักทรัพย์ที่ใช้คำนวณดัชนี"),
  each with a full quote row (OHLC, change, best bid/offer, volume, value, market cap, P/E, ...)
- **Index chart quotation** — intraday/historical index value series, with a latest-traded-value
  accessor (reuses the stock chart-quotation models)

## Key Features

- **Unified `SetIndex` facade** — one entry point per index, mirroring the `Stock` class
- **Case-preserving symbols** — `sSET` and `AGRO-m` keep their casing; the API resolves paths
  case-insensitively, so `get_index_info("sset")` also works
- **SET vs mai industry disambiguation** — both markets share industry symbols (e.g. `AGRO`);
  the mai variants use a `-m` suffixed `query_symbol` (`AGRO-m`)
- **Bid/offer coercion** — the API sends ladder prices as strings (`"374.00"`); they are parsed
  to floats, with blank/placeholder values treated as missing
- **Dual language** — `en`/`th` support via the shared `normalize_language()`
- **SessionManager** — cookies and bot detection handled automatically
- **Async-first** — all I/O uses async/await via `AsyncDataFetcher`

## Installation

```bash
pip install settfex
```

## Quick Start

### The SetIndex Facade

```python
import asyncio
from settfex import SetIndex

async def main():
    index = SetIndex("SET50")

    # Page-header quotation
    info = await index.get_info()
    print(f"{info.symbol}: {info.last} ({info.percent_change:+.2f}%)")
    print(f"O/H/L: {info.open}/{info.high}/{info.low}")
    print(f"Volume: {info.volume:,.0f} | Value: {info.value:,.0f} THB")
    print(f"Status: {info.market_status} @ {info.market_date_time}")

    # Constituents with per-stock quotes
    composition = await index.get_composition()
    for c in composition.constituents[:5]:
        print(f"{c.symbol}: {c.last} (bid {c.best_bid} / offer {c.best_offer})")

    # Latest traded index value (intraday chart based)
    latest = await index.get_latest_price()
    if latest:
        print(f"Latest: {latest.price} @ {latest.local_datetime}")

asyncio.run(main())
```

### List All Indices

```python
from settfex.services.set import get_index_list

response = await get_index_list()
print(f"Total: {response.count}")                 # 55 entries
print([ix.symbol for ix in response.market_indices])  # the 11 headline indices
print(len(response.industries), len(response.sectors))
```

### All Index Quotations in One Call

```python
from settfex.services.set import get_index_info_list

quotes = await get_index_info_list()               # type="INDEX": the 11 headline indices
for q in quotes:
    print(f"{q.symbol:10} {q.last} ({q.percent_change:+.2f}%)")

sector_quotes = await get_index_info_list(index_type="INDUSTRY")  # industries AND sectors
```

### Convenience Functions

```python
from settfex.services.set import get_index_info, get_index_composition

info = await get_index_info("SETESG")
composition = await get_index_composition("SETESG")
print(f"SETESG members: {composition.symbols}")
```

## API Reference

### Models

#### IndexSymbol

Directory entry for one index.

| Field | Alias | Type | Description |
|---|---|---|---|
| `symbol` | — | `str` | Index symbol (e.g., `SET50`, `sSET`, `AGRO`) |
| `market` | — | `str` | `SET` or `mai` |
| `level` | — | `str` | `INDEX`, `INDUSTRY`, or `SECTOR` |
| `parent_index` | `parentIndex` | `str \| None` | Parent index (`None` for top level) |
| `query_symbol` | `querySymbol` | `str` | Symbol to use in API paths (`AGRO-m` for mai industries) |
| `name_en` / `name_th` | `nameEN` / `nameTH` | `str` | Index names |

#### IndexListResponse

Wraps the directory with helpers:

- `count` — total entries
- `market_indices` / `industries` / `sectors` — entries by level
- `filter_by_market(market)` / `filter_by_level(level)` — case-insensitive filters
- `get_index(symbol, market=None)` — lookup; resolves `query_symbol` first (so `"AGRO-m"` pins
  the mai industry), then `symbol` narrowed by `market`; warns on ambiguity

#### IndexInfo

The index quotation (page-header data). All numeric fields are `float | None`.

| Field | Alias | Description |
|---|---|---|
| `symbol`, `name_en`, `name_th` | `nameEN`/`nameTH` | Identity |
| `prior`, `open`, `high`, `low`, `last` | — | Values |
| `change`, `percent_change` | `percentChange` | Change vs prior close |
| `volume`, `value` | — | Total volume (shares) / value (THB) |
| `market_status` | `marketStatus` | e.g. `Open2`, `Closed` |
| `market_date_time` | `marketDateTime` | tz-aware timestamp (Asia/Bangkok +07:00) |
| `market_name`, `industry_name`, `sector_name`, `level`, `query_symbol` | camelCase | Context |

#### IndexConstituent

One row of the constituents quote table (~45 fields, only `symbol` required). Highlights:

- Quote: `prior`, `open`, `high`, `low`, `last`, `average`, `change`, `percent_change`,
  `floor`, `ceiling`, `total_volume`, `total_value`, `aom_volume`, `aom_value`
- Order book: `bids` / `offers` (lists of `BidOffer(volume, price)`), plus `best_bid` /
  `best_offer` shortcut properties
- Valuation: `market_cap`, `pe_ratio`, `pb_ratio`, `dividend_yield`, `high_52_weeks`,
  `low_52_weeks`, `nvdr_net_volume`, `listed_share`, `statistics_as_of`
- Context: `market_status`, `market_date_time`, `security_type`, `industry_name`,
  `sector_name`, `name_en`, `name_th`

#### IndexCompositionResponse

- `composition` — `IndexComposition` (`symbol`, names, `stock_infos`, `sub_indices`)
- `index_infos` / `index_info` — the queried index's own quotation
- `constituents` / `symbols` / `count` — shortcuts
- `get_constituent(symbol)` — case-insensitive lookup

### Services

Each service takes `config: FetcherConfig | None = None` and exposes `fetch_*` plus a
`fetch_*_raw` variant returning the unvalidated payload:

- `IndexListService.fetch_index_list(lang="en") -> IndexListResponse`
- `IndexInfoService.fetch_index_info(symbol, lang="en") -> IndexInfo`
- `IndexInfoService.fetch_index_info_list(index_type="INDEX", lang="en") -> list[IndexInfo]`
- `IndexCompositionService.fetch_composition(symbol, lang="en") -> IndexCompositionResponse`
- `IndexChartQuotationService.fetch_chart_quotation(symbol, period="1D", accumulated=False) -> ChartQuotation`

### Convenience Functions

```python
async def get_index_list(lang="en", config=None) -> IndexListResponse
async def get_index_info(symbol, lang="en", config=None) -> IndexInfo
async def get_index_info_list(index_type="INDEX", lang="en", config=None) -> list[IndexInfo]
async def get_index_composition(symbol, lang="en", config=None) -> IndexCompositionResponse
async def get_index_chart_quotation(symbol, period="1D", accumulated=False, config=None) -> ChartQuotation
async def get_index_latest_price(symbol, period="1D", accumulated=False, as_of=None, config=None) -> Quotation | None
```

## Advanced Usage

### SET vs mai Industries (`AGRO` vs `AGRO-m`)

SET and mai share industry symbols. Use the `query_symbol` (or `market=`) to pin one:

```python
response = await get_index_list()
set_agro = response.get_index("AGRO", market="SET")   # query_symbol "AGRO"
mai_agro = response.get_index("AGRO-m")               # query_symbol "AGRO-m"

await get_index_composition("AGRO-m")   # mai Agro & Food constituents
```

### SET Industry Drilldown

SET industry indices carry no direct constituents — they return their **sector quotes** instead:

```python
agro = await get_index_composition("AGRO")
print(agro.count)                                  # 0 stocks
print([s.symbol for s in agro.composition.sub_indices])  # ['AGRI', 'FOOD']

agri = await get_index_composition("AGRI")         # sectors DO return stocks
```

### Whole-Market Indices Have No Composition

`SET` and `mai` are whole markets: the composition endpoint returns HTTP 404 for them, and the
service raises with a message explaining to query a sub-index instead. Their membership is
already available as `StockSymbol.market` on the stock list.

### Index Membership per Stock

The stock list service joins the nine headline sub-index compositions into each stock —
see [Stock List Service](list.md):

```python
from settfex.services.set import get_stock_list

stock_list = await get_stock_list()                # enrichment on by default
print(stock_list.get_symbol("CPALL").indices)      # ['SET50', 'SET50FF', 'SET100', ...]
print(len(stock_list.filter_by_index("SETESG")))   # e.g. 121
```

## Error Handling

```python
try:
    composition = await get_index_composition("SET50")
except ValueError as e:
    print(f"Bad input (empty symbol / invalid language): {e}")
except Exception as e:
    print(f"Request failed: {e}")   # incl. the HTTP 404 whole-market explanation
```

## Notes

- The index API takes `?language=` (the stock endpoints use `?lang=`); the services accept the
  same `lang` argument (`en`/`th` and their aliases) as every other settfex service.
- `market_date_time` is timezone-aware (Asia/Bangkok, +07:00). `get_index_latest_price()`
  handles naive/aware `as_of` values the same way the stock service does.
- Bid/offer ladder prices arrive as strings from the API and are coerced to `float`.

## Constants

```python
SET_INDEX_LIST_ENDPOINT = "/api/set/index/list"
SET_INDEX_INFO_LIST_ENDPOINT = "/api/set/index/info/list"
SET_INDEX_INFO_ENDPOINT = "/api/set/index/{symbol}/info"
SET_INDEX_COMPOSITION_ENDPOINT = "/api/set/index/{symbol}/composition"
SET_INDEX_CHART_QUOTATION_ENDPOINT = "/api/set/index/{symbol}/chart-quotation"
```

## See Also

- [Stock List Service](list.md) — stock universe with index-membership enrichment
- [Chart Quotation Service](chart_quotation.md) — the shared chart models and latest-price logic
- [Highlight Data Service](highlight_data.md) — per-stock metrics
- Example notebook: `examples/set/15_market_index.ipynb`
