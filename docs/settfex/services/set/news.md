# SET News Service

## Overview

Fetches news and disclosures from the SET news search API (`GET /api/set/news/search`) —
**market-wide by default**: one call returns the latest-trading-day company news for **all
stocks** on SET/mai, in English or Thai. Optional filters narrow the result by symbol, date
window, headline keyword, and source.

Module: `settfex/services/set/news.py` · Three tiers: `get_news()` (one-call convenience,
the LLM tool-calling entry point) → `NewsService.fetch_news()` (validated Pydantic models) →
`NewsService.fetch_news_raw()` (raw `dict` escape hatch). Also available per-stock as
`Stock("CPALL").get_news()`.

> ### ⚠️ Two API gotchas (live-verified 2026-07-19)
>
> 1. **Dates are dd/MM/yyyy ONLY.** `fromDate`/`toDate` reject ISO `yyyy-MM-dd` with an
>    opaque HTTP 400. The service converts `datetime.date`/`datetime` objects automatically
>    and eagerly validates strings, raising `InvalidDateError` *before* any request.
> 2. **`sourceId` is not validated.** Any value other than `company` (including empty) is
>    silently ignored by the API and returns news from **all** sources (a superset that
>    includes TFEX rows and `set-releases` items). `"company"` is the only verified filter
>    value; pass `source_id=None` for the explicit all-sources behavior. Unverified values
>    log a warning.

## Quick Start

```python
import asyncio
from settfex.services.set import get_news

async def main() -> None:
    # Latest trading day, ALL stocks, company disclosures, English headlines
    news = await get_news()
    print(f"{news.count} items")
    for item in news.news_info_list[:5]:
        print(f"{item.news_datetime:%Y-%m-%d %H:%M}  {item.symbol:8s} {item.headline}")

asyncio.run(main())
```

```python
# Thai headlines
news = await get_news(lang="th")

# One symbol only
news = await get_news(symbol="CPALL")

# A date window (date objects are converted to dd/MM/yyyy automatically)
from datetime import date
news = await get_news(from_date=date(2026, 7, 1), to_date=date(2026, 7, 17))

# Headline keyword
news = await get_news(keyword="dividend")

# All sources (SET-issued releases, TFEX, funds, ... — superset of company news)
news = await get_news(source_id=None)
```

## Models

### `NewsItem`

One news/disclosure item. All 13 fields are always present in the API response.

| Field | Alias | Type | Notes |
|---|---|---|---|
| `id` | — | `str` | Numeric string; ids differ per language |
| `news_datetime` | `datetime` | `datetime` | Timezone-aware (Asia/Bangkok, +07:00) |
| `symbol` | — | `str` | Security the news belongs to |
| `source` | — | `str` | Disclosing source code (usually the symbol) |
| `url` | — | `str` | Full news-detail page URL on set.or.th |
| `headline` | — | `str` | Thai or English per requested `lang` |
| `is_today_news` | `isTodayNews` | `bool` | Published-today flag |
| `view_clarification` | `viewClarification` | `bool \| str \| None` | Only `null` observed as of 2026-07 |
| `market_alert_type_id` | `marketAlertTypeId` | `int \| str \| None` | Only `null` observed as of 2026-07 |
| `percent_price_change` | `percentPriceChange` | `float \| None` | Only `null` observed as of 2026-07 |
| `tag` | — | `str` | Observed: `''`, `financial-statement`, `nav`, `ca`, `set-releases` |
| `product` | — | `str` | Observed: `S`, `L`, `U`, `V`, `X`, `TFEX` |
| `lang` | — | `str` | `'th'` or `'en'` (item data, not the request param) |

The three alert fields have never been observed non-null (checked across 3,378 items); they
are typed permissively so a future non-null value cannot break parsing.

### `NewsSearchResponse`

| Member | Description |
|---|---|
| `total_count: int` | Total matches reported by the API |
| `news_info_list: list[NewsItem]` | The items (a `null` list parses as empty) |
| `count` (property) | `len(news_info_list)` — matches `total_count`; a mismatch logs a pagination-canary warning |
| `filter_by_symbol(symbol)` | Case-insensitive symbol filter |
| `filter_today()` | Items with `is_today_news=True` |
| `filter_by_tag(tag)` | Case-insensitive exact tag match |

## Service Class

### `NewsService(config: FetcherConfig | None = None)`

#### `fetch_news(...) -> NewsSearchResponse` / `fetch_news_raw(...) -> dict`

Both take the same parameters:

| Param | Type | Default | Notes |
|---|---|---|---|
| `lang` | `Language` | `"en"` | `en`/`th` (aliases `eng`/`english`/`tha`/`thai` accepted) |
| `symbol` | `str \| None` | `None` | Auto-uppercased; `None` = all stocks |
| `from_date` | `date \| str \| None` | `None` | `datetime.date`/`datetime`, or a dd/MM/yyyy string |
| `to_date` | `date \| str \| None` | `None` | Same formats as `from_date` |
| `keyword` | `str \| None` | `None` | Headline keyword; URL-encoded automatically |
| `source_id` | `str \| None` | `"company"` | `None` = all sources (see gotcha #2) |

Without dates the API returns the **latest trading day** only (~150–200 items). No
pagination has been observed — a 17-day window returned 2,804 items in one response — so
keep windows modest.

## Convenience Function

```python
async def get_news(
    lang="en", symbol=None, from_date=None, to_date=None,
    keyword=None, source_id="company", config=None,
) -> NewsSearchResponse
```

## Usage Examples

### Today's disclosures, grouped by tag

```python
news = await get_news()
print(f"financial statements: {len(news.filter_by_tag('financial-statement'))}")
print(f"NAV reports:          {len(news.filter_by_tag('nav'))}")
print(f"published today:      {len(news.filter_today())}")
```

### Per-stock news via the unified Stock class

```python
from settfex.services.set import Stock

stock = Stock("CPALL")
news = await stock.get_news(from_date="01/07/2026", to_date="17/07/2026")
for item in news.news_info_list:
    print(f"{item.news_datetime:%Y-%m-%d}  {item.headline}")
```

### Export to pandas

```python
import pandas as pd

news = await get_news()
df = pd.DataFrame([item.model_dump() for item in news.news_info_list])
df = df.sort_values("news_datetime", ascending=False)
```

## Error Handling

```python
from settfex import FetchError, InvalidDateError
from settfex.exceptions import InvalidLanguageError, InvalidSymbolError

try:
    news = await get_news(from_date="2026-07-15")   # ISO date -> caught BEFORE any request
except InvalidDateError as exc:
    print(exc)   # Invalid from_date '2026-07-15': expected dd/MM/yyyy (e.g. '15/07/2026') ...
except InvalidLanguageError:
    ...          # bad lang value
except FetchError as exc:
    ...          # HTTP/transport failure; exc.status_code when available
```

`ResponseParseError` (a `ValueError`) is raised for malformed/non-finite JSON, and
`SymbolNotFoundError` for an HTTP 404.

## API Endpoint

```
GET https://www.set.or.th/api/set/news/search?sourceId=company&lang={en|th}
    [&symbol={SYMBOL}] [&fromDate=dd/MM/yyyy] [&toDate=dd/MM/yyyy] [&keyword={TEXT}]
```

Same host and Incapsula bot wall as the other SET services — `SessionManager` cookie
warm-up is automatic (plain `curl` is blocked).

## Related Services

- [Stock List](list.md) — the symbol universe to join news onto
- [Corporate Actions](corporate_action.md) — structured XD/XM events (vs. free-text news)
- [Earnings Call (Opportunity Day)](earnings_call.md) — OPPDAY calendar and transcripts
