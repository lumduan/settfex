# Analyst Consensus (IAA) Service

Broker target prices, earnings forecasts and research PDF links for a SET stock — the data behind
the **Analyst Consensus** table on Settrade's quote page.

## Overview

This service returns the IAA (Investment Analysts Association) consensus that Settrade publishes
at `https://www.settrade.com/th/equities/quote/{SYMBOL}/analyst-consensus` (HTML table id
`tableAnalystConcensus`). That page is a client-rendered Nuxt app, so the table is **not** in the
server HTML — this service calls the JSON endpoints the page's own bundle calls. No HTML parsing
is involved, and the JSON carries full float precision plus the broker/research ids the rendered
table rounds away.

The payload splits naturally into the two tables the service exposes as two DataFrames:

- **Aggregate rows** — `average`, `median`, `high`, `low`
- **Broker rows** — one per covering broker, with analyst name, recommendation, target price and
  a link to that broker's research **PDF**

```
Endpoint: GET https://www.settrade.com/api/set-fund/consensus/stock/{symbol}/consensus
Endpoint: GET https://www.settrade.com/api/set-fund/consensus/stock/overall?lang=&symbol=
```

> **Host note.** This is the library's only `www.settrade.com` service. It is SET Group's retail
> portal, not `www.set.or.th`, and it has its own Incapsula cookie domain — handled automatically
> by `SessionManager(warmup_site="settrade")`. Nothing extra is required of callers.

## Key Features

- **Two ready-made DataFrames** — `stats_to_dataframe()` (4 aggregate rows) and `to_dataframe()`
  (one row per broker, with the PDF link)
- **Research PDF links** — `last_research_url` per broker, plus `research_urls` for `(broker, url)`
  pairs
- **Whole-market screener** — `get_consensus_overall()` with no symbol returns every covered SET
  stock's buy/hold/sell counts in one request
- **`has_coverage` guard** — an explicit flag for the uncovered case, where Settrade returns zeros
  rather than nulls
- **Fully nullable numerics** — every forecast field is `float | None`, matching what brokers
  actually publish
- **Timezone-aware timestamps** — `last_update_date` and `market_time` carry `+07:00`
- **Automatic cookie handling** — no cookie or header parameters to pass

## Installation

```bash
pip install settfex
# DataFrame helpers need the optional extra:
pip install "settfex[dataframe]"
```

## Quick Start

### Convenience function

```python
from settfex.services.set import get_analyst_consensus

data = await get_analyst_consensus("GULF")

print(f"{data.count} brokers cover {data.symbol}")
print(f"Average target: {data.average.target_price}")
print(f"Range: {data.low.target_price} – {data.high.target_price}")

for row in data.brokers[:3]:
    print(f"{row.broker_name:<10} {row.recommend:<20} {row.target_price}  {row.research_url}")
```

### The two DataFrames

```python
from settfex.services.set import get_analyst_consensus_dataframes

stats_df, brokers_df = await get_analyst_consensus_dataframes("GULF")

stats_df.set_index("statistic")["target_price"]
# average    78.75
# median     78.50
# high       91.00
# low        72.00

brokers_df[["broker_name", "analyst_name", "recommend", "target_price", "research_url"]]
```

Equivalently, from a fetched model:

```python
data = await get_analyst_consensus("GULF")
stats_df = data.stats_to_dataframe()   # 4 rows: average / median / high / low
brokers_df = data.to_dataframe()       # one row per covering broker
```

### Unified `Stock` class

```python
from settfex.services.set import Stock

stock = Stock("GULF")
data = await stock.get_analyst_consensus()      # cached on the instance
summary = await stock.get_consensus_overall()   # not cached (carries a live last_price)
```

### Service class (and the raw escape hatch)

```python
from settfex.services.set import AnalystConsensusService

service = AnalystConsensusService()
data = await service.fetch_analyst_consensus("GULF")
raw = await service.fetch_analyst_consensus_raw("GULF")   # verbatim dict
```

## API Reference

### Model — `AnalystConsensusRow`

The same wire shape serves both the aggregate rows and the broker rows, so every field is
optional.

| Field | Type | JSON alias | Description |
|---|---|---|---|
| `id` | `int \| None` | `id` | Settrade research row id |
| `symbol` | `str \| None` | `symbol` | Stock symbol |
| `broker_name` | `str \| None` | `brokerName` | Covering broker's short name, e.g. `ASPS` |
| `broker_url` | `str \| None` | `brokerURL` | Broker's own website |
| `analyst_name` | `str \| None` | `analystName` | Analyst who published the estimate |
| `current_year_eps` | `float \| None` | `currentYearEps` | Forecast EPS, current year (THB) |
| `next_year_eps` | `float \| None` | `nextYearEps` | Forecast EPS, next year (THB) |
| `current_year_net_profit` | `float \| None` | `currentYearNetProfit` | Forecast net profit, current year — **million baht** |
| `next_year_net_profit` | `float \| None` | `nextYearNetProfit` | Forecast net profit, next year — **million baht** |
| `current_year_pe` | `float \| None` | `currentYearPe` | Forecast P/E, current year |
| `next_year_pe` | `float \| None` | `nextYearPe` | Forecast P/E, next year |
| `current_year_pbv` | `float \| None` | `currentYearPbv` | Forecast P/BV, current year |
| `next_year_pbv` | `float \| None` | `nextYearPbv` | Forecast P/BV, next year |
| `current_year_div` | `float \| None` | `currentYearDiv` | Forecast dividend **yield**, current year — **percent** |
| `next_year_div` | `float \| None` | `nextYearDiv` | Forecast dividend **yield**, next year — **percent** |
| `target_price` | `float \| None` | `targetPrice` | Target price (THB) |
| `target_price_change` | `float \| None` | `targetPriceChange` | Target minus the broker's *previous* target (THB) |
| `target_price_percent_change` | `float \| None` | `targetPricePercentChange` | The same change, as a percent of the previous target |
| `recommend` | `str \| None` | `recommend` | Broker free text: `Buy`, `Outperform Market`, … (English only) |
| `recommend_type` | `str \| None` | `recommendType` | Short code, e.g. `B` |
| `last_update_date` | `datetime \| None` | `lastUpdateDate` | When the broker last updated the row (`+07:00`) |
| `last_research_url` | `str \| None` | `lastResearchURL` | Latest research **PDF** (null when none published) |
| `full_research_url` | `str \| None` | `fullResearchURL` | Full-report PDF (rarely populated) |
| `last_research_id` | `int \| None` | `lastResearchId` | Settrade id of the latest research |
| `full_research_id` | `int \| None` | `fullResearchId` | Settrade id of the full research |

Properties: `research_url` (latest, else full), `has_research`, `recommend_group`
(`"buy"`/`"hold"`/`"sell"`, or `None` for an unmapped code).

### Model — `ConsensusStatistic`

`AnalystConsensusRow` plus `statistic: "average" | "median" | "high" | "low"`. The label is not
on the wire — the container stamps it from the payload key, so an aggregate row still identifies
itself when passed around alone or dumped to Parquet.

### Model — `AnalystConsensus`

| Field | Type | JSON alias | Description |
|---|---|---|---|
| `symbol` | `str` | — | Injected by the service (the payload has no top-level symbol) |
| `current_year` | `int \| None` | `currentYear` | Year the `current_year_*` columns refer to |
| `next_year` | `int \| None` | `nextYear` | Year the `next_year_*` columns refer to |
| `target_price_year` | `int \| None` | `targetPriceYear` | Year the target prices refer to |
| `average` / `median` / `high` / `low` | `ConsensusStatistic \| None` | same | The four aggregate rows |
| `consensuses` | `list[AnalystConsensusRow]` | `consensuses` | One row per covering broker |
| `has_coverage` | `bool` | *computed* | False when no broker covers the symbol |

Properties and methods: `count`, `brokers` (alias of `consensuses`), `statistics`,
`broker_names`, `with_research`, `research_urls`, `latest_update`, `broker(name)`,
`to_dataframe(columns=None)`, `stats_to_dataframe(columns=None)`.

### Model — `ConsensusOverall` / `ConsensusOverallResponse`

| Field | Type | JSON alias | Description |
|---|---|---|---|
| `symbol` | `str` | `symbol` | Stock symbol |
| `last_price` | `float \| None` | `lastPrice` | Last traded price (THB) |
| `total_coverage` | `int \| None` | `totalCoverage` | Number of covering brokers |
| `buy` / `hold` / `sell` | `int \| None` | same | Recommendation counts |
| `recommend_type` | `str \| None` | `recommendType` | Consensus recommendation, e.g. `buy` |
| `median_target_price` | `float \| None` | `medianTargetPrice` | Median target price (THB) |
| `average_target_price` | `float \| None` | `averageTargetPrice` | Average target price (THB) |
| `bullish` / `bearish` | `float \| None` | same | Share of covering brokers, in percent |

`ConsensusOverallResponse` holds `market_time` and `overall`, plus `count`, `get(symbol)` and
`to_dataframe(columns=None)`.

### Service Class

```python
class AnalystConsensusService:
    def __init__(self, config: FetcherConfig | None = None) -> None: ...

    async def fetch_analyst_consensus(self, symbol: str) -> AnalystConsensus
    async def fetch_analyst_consensus_raw(self, symbol: str) -> dict[str, Any]
    async def fetch_overall(
        self, symbol: str | None = None, lang: Language = "en"
    ) -> ConsensusOverallResponse
    async def fetch_overall_raw(
        self, symbol: str | None = None, lang: Language = "en"
    ) -> dict[str, Any]
```

### Convenience Functions

```python
async def get_analyst_consensus(symbol, config=None) -> AnalystConsensus
async def get_consensus_overall(symbol=None, lang="en", config=None) -> ConsensusOverallResponse
async def get_analyst_consensus_dataframes(symbol, config=None) -> tuple[DataFrame, DataFrame]
```

## Usage Examples

### Example 1 — Rank brokers by upside

```python
data = await get_analyst_consensus("CPALL")
df = data.to_dataframe()
df["upside_vs_avg"] = df["target_price"] - data.average.target_price
print(df.nlargest(5, "target_price")[["broker_name", "target_price", "upside_vs_avg"]])
```

### Example 2 — Collect the research PDFs

```python
data = await get_analyst_consensus("GULF")
for broker, url in data.research_urls:
    print(f"{broker:<12} {url}")
print(f"{len(data.with_research)} of {data.count} brokers published a PDF")
```

### Example 3 — Whole-market consensus screener

```python
market = await get_consensus_overall()
df = market.to_dataframe()

widely_covered = df[df["total_coverage"] >= 15]
unanimous_buys = widely_covered[widely_covered["hold"].eq(0) & widely_covered["sell"].eq(0)]
print(unanimous_buys[["symbol", "total_coverage", "buy", "average_target_price"]])
```

### Example 4 — Skip uncovered names safely

```python
from settfex.exceptions import FetchError

for symbol in ["GULF", "CPALL", "ABICO"]:
    try:
        data = await get_analyst_consensus(symbol)
    except FetchError as exc:
        print(f"{symbol}: no consensus record (HTTP {exc.status_code})")
        continue
    if not data.has_coverage:
        print(f"{symbol}: listed but no broker covers it")
        continue
    print(f"{symbol}: {data.count} brokers, median target {data.median.target_price}")
```

### Example 5 — Timestamps and freshness

```python
data = await get_analyst_consensus("GULF")
print(f"Most recent broker update: {data.latest_update}")   # tz-aware, +07:00

df = data.to_dataframe()

# `last_update_date` already arrives as a tz-aware datetime64 column (NaT where a broker has no
# update date) — the resolution is `[ns, +07:00]` on pandas 2 and `[us, +07:00]` on pandas 3.
# Convert only if you specifically want the values normalised to UTC:
df["last_update_date"] = pd.to_datetime(df["last_update_date"], utc=True)
```

> **Missing values differ by pandas major.** settfex supports `pandas>=2.0.0`. On **pandas 3** a
> string column is typed `str` and a missing value is `NaN`; on **pandas 2** it was `object` and
> `None`. Test with `pd.isna(value)`, never `value is None`. Serialise with `df.to_json()` —
> `json.dumps(df.to_dict("records"))` emits a bare `NaN`, which is not valid JSON.

## Error Handling & Troubleshooting

| Situation | What happens | What to do |
|---|---|---|
| Symbol has no consensus record | **`FetchError`** with `status_code=500` | Catch `FetchError`; 500 is Settrade's "no record", *not* a 404 — and it fires for valid SET stocks, DRs and warrants alike |
| Listed stock nobody covers | HTTP 200, `count == 0`, aggregates all `0.0` | Check **`has_coverage`** before using the aggregates — those zeros are placeholders |
| Unknown symbol on the summary endpoint | HTTP 200 with an empty list | Check `count`, or use `.get(symbol)` which returns `None` |
| Blocked (HTTP 403) | `FetchError` mentioning bot protection | Usually transient; `SessionManager` re-warms and retries once |
| `ImportError` from a DataFrame method | pandas is not installed | `pip install "settfex[dataframe]"` |
| Empty symbol | `InvalidSymbolError` | Raised before any request is made |
| Bad `lang` on the summary endpoint | `InvalidLanguageError` | Use `en`/`th` (aliases `english`/`thai` also work) |

### Gotchas worth knowing

- **The table endpoint has no `lang`.** `?lang=` is ignored — the `th` and `en` payloads are
  byte-identical, and `recommend` is broker-supplied English free text. Only the *summary*
  endpoint honours `lang`. `fetch_analyst_consensus()` therefore takes no `lang` argument.
- **An aggregate row is not any one broker's row.** Every column is aggregated independently:
  on GULF (2026-08-16) `high.target_price` was `91.0` from one broker while
  `high.target_price_change` was `12.0` from a *different* broker whose target was `79.0`. Never
  reconstruct one field from another across an aggregate row.
- **The change columns only aggregate brokers who revised.** `average.target_price_change` is
  *not* `average.target_price` minus some previous average — only 2 of GULF's 16 brokers had
  revised, and only those 2 are in that average.
- **Every numeric is nullable.** Real CPALL rows carry `null` for `targetPriceChange`,
  `nextYearPe`, `currentYearPbv` and `nextYearDiv`.
- **`last_research_url` is often null.** Only 9 of GULF's 16 brokers published a PDF.
- **Units:** net profit is in **million baht** and `*_div` is a dividend **yield in percent** —
  confirmed against the rendered column headers (`กำไรสุทธิ (ล้านบาท)`, `DIV (%)`).

## Related Services

- [Highlight Data](highlight_data.md) — P/E, P/B, market cap, dividend yield
- [Price Performance](price_performance.md) — stock vs sector vs market returns
- [Financial Statements](financial.md) — reported balance sheet, income and cash flow
- [Earnings Call (OPPDAY)](earnings_call.md) — management presentations and transcripts
- [SEC Documents](../sec/financial_report.md) — raw disclosure filings from `market.sec.or.th`
