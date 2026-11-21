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

> ### ⚠️ Three API gotchas (live-verified 2026-07-19/20)
>
> 1. **Dates are dd/MM/yyyy ONLY.** `fromDate`/`toDate` reject ISO `yyyy-MM-dd` with an
>    opaque HTTP 400. The service converts `datetime.date`/`datetime` objects automatically
>    and eagerly validates strings, raising `InvalidDateError` *before* any request.
> 2. **`sourceId` is not validated.** Any value other than `company` (including empty) is
>    silently ignored by the API and returns news from **all** sources (a superset that
>    includes TFEX rows and `set-releases` items). `"company"` is the only verified filter
>    value; pass `source_id=None` for the explicit all-sources behavior. Unverified values
>    log a warning.
> 3. **History is a rolling ~5-year window (1826 days).** The endpoint serves only the
>    trailing **1826 days** (= 5 calendar years incl. the leap day). A `from_date` older than
>    `today − 1826 days` is rejected with HTTP 400 — surfaced as `FetchError`, **not**
>    `InvalidDateError`. The check is on the window's *start*, and the API does **not** clip
>    to the allowed range: one day too old fails the whole request. The boundary is rolling
>    (`today − 1826 days`, never a fixed calendar date). See [Historical news](#historical-news).

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

### `NewsDetail` (0.30.0)

One item's detail record, from `get_news_detail()`:
- `id`, `news_datetime` (alias `datetime`), `symbol`, `source`, `headline`, `tag`;
- `download_url`: the attachment's URL, verbatim, or `None`;
- `file_type`: `'ZIP'`, `'PDF'`;
- `content`: the item's HTML body, verbatim;
- the computed field **`file_path`**: the attachment's path on `weblink.set.or.th`, e.g.
  `dat/news/202611/0737FIN111120261328030954T.zip`. It survives `model_dump()`.

## News detail and attachments (0.30.0)

The search says a disclosure exists. `get_news_detail()` says what was attached to it.

```python
from settfex.services.set import get_news, get_news_detail

news = await get_news(lang="th", symbol="CPALL", from_date="11/11/2026", to_date="14/11/2026")
[item] = news.filter_by_tag("financial-statement")
detail = await get_news_detail(item)          # the item's own id, symbol and language
detail.download_url   # 'https://weblink.set.or.th/dat/news/202611/0737FIN111120261328030954T.zip'
detail.file_path      # 'dat/news/202611/0737FIN111120261328030954T.zip'
await get_news_detail("17943525757510")       # or a bare id (lang defaults to 'en')
```

Live-verified 2026-11-20 on CPALL's Q3/2569 items:
- **A statement's attachment is the SEC filing.** `file_path` is the same string as SEC's
  `Download?FILEID=` for that filing, and the files are byte-identical (see the
  [SEC document service](../sec/financial_report.md#financial-statements-download-from-sec-or-from-sets-link)).
- **Thai and English are separate items with separate ids.** Each links its own language's file:
  Thai `…T.zip` (id `17943525757301`), English `…E.zip` (id `17943525757510`). Pass a `NewsItem`
  and its language is used; with a bare id, pass the item's own `lang`.
- **Not only statements.** The MD&A item carries its PDF (`file_type='PDF'`, tag `''`).
- **The endpoint is `GET /api/set/news/{id}/detail?symbol=&lang=`.** It appears in no index, and
  was found in the site's own JavaScript (`getNewsDetail`). `symbol` is optional.
- **An unknown id answers HTTP 404** `{"message": "Invalid News [<id>] "}`, raised as
  **`NewsNotFoundError`**: a `FetchError` and a `NotFoundError`, so do not retry it. A non-numeric
  id raises `ValueError` before any request, because the id goes into the URL path.

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
keep windows modest. History reaches back a **rolling ~5 years (1826 days)**; an older
`from_date` raises `FetchError` (HTTP 400) — see gotcha #3 and [Historical news](#historical-news).

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

### Historical news

Historical queries work for any window inside the **rolling ~5-year (1826-day)** limit. The
check is on the window's *start* (`from_date`), and the API does **not** clip to the allowed
range — a `from_date` even one day too old fails the whole request with HTTP 400 (raised as
`FetchError`, *not* `InvalidDateError`). Keep windows modest (no pagination).

```python
from datetime import date, timedelta
from settfex.exceptions import FetchError

# A historical window ~1 year back (well inside the limit)
to_d = date.today() - timedelta(days=365)
from_d = to_d - timedelta(days=5)
news = await get_news(from_date=from_d, to_date=to_d)
print(f"{from_d} -> {to_d}: {news.count} items")

# The boundary: today − 1826 days is the oldest servable date
oldest_ok = date.today() - timedelta(days=1826)   # served (HTTP 200)
too_old = date.today() - timedelta(days=1827)      # rejected (HTTP 400)
try:
    await get_news(from_date=too_old, to_date=too_old)
except FetchError:
    print(f"{too_old} is older than the 5-year window — rejected")
```

> The boundary is **rolling**: it advances one day each day, so `today − 1826 days` is always
> the earliest servable `from_date` — not a fixed calendar date.

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

> **`InvalidDateError` vs `FetchError` for dates.** A *malformed* date string (e.g. ISO
> `yyyy-MM-dd`) raises `InvalidDateError` locally, before any request. A *well-formed but
> too-old* `from_date` (older than `today − 1826 days`) is rejected by the API with HTTP 400
> and raised as `FetchError` — it is not caught locally. Catch both if you accept arbitrary
> historical windows.

`ResponseParseError` (a `ValueError`) is raised for malformed/non-finite JSON, and
`SymbolNotFoundError` for an HTTP 404. On `get_news_detail()` a 404 is `NewsNotFoundError` (an
unknown news id) instead.

## API Endpoint

```
GET https://www.set.or.th/api/set/news/search?sourceId=company&lang={en|th}
    [&symbol={SYMBOL}] [&fromDate=dd/MM/yyyy] [&toDate=dd/MM/yyyy] [&keyword={TEXT}]
```

```
GET https://www.set.or.th/api/set/news/{id}/detail?lang={en|th}[&symbol={SYMBOL}]   (0.30.0)
```

`fromDate` must fall within the last **1826 days** (rolling ~5-year window); an older value
returns HTTP 400. Same host and Incapsula bot wall as the other SET services —
`SessionManager` cookie warm-up is automatic (plain `curl` is blocked).

## Related Services

- [Stock List](list.md) — the symbol universe to join news onto
- [Corporate Actions](corporate_action.md) — structured XD/XM events (vs. free-text news)
- [Earnings Call (Opportunity Day)](earnings_call.md) — OPPDAY calendar and transcripts
