# SET Earnings Call (Opportunity Day) Service

## Overview

The Earnings Call Service fetches the SET **"Earnings Call (OPPDAY)"** calendar — the
Opportunity Day presentations listed at
<https://opportunity-day.setgroup.or.th/en/earnings-call>. It returns typed Pydantic models
and an optional pandas DataFrame whose columns are exactly what an earnings-call dashboard
needs: `stock_name`, `company_name`, `earnings_call_date`, `video_clip_time`, `youtube_url`.

Unlike the main SET API, the opportunity-day backend (`https://api.lcp.setgroup.or.th/api/v1`)
is **stateless** — no Incapsula bot wall, no cookies, no auth. The service therefore uses a
plain sessionless fetcher (no cookie warm-up).

## Quick Start

```python
import asyncio
from settfex.services.set import get_earnings_calls, get_earnings_calls_dataframe

async def main():
    # Typed models
    response = await get_earnings_calls()
    for item in response.items:
        print(item.symbol, item.company_name_clean, item.youtube_url)

    # …or straight to a DataFrame (requires: pip install settfex[dataframe])
    df = await get_earnings_calls_dataframe()
    print(df)

asyncio.run(main())
```

## The 5 DataFrame columns

| Column | Source |
|---|---|
| `stock_name` | `symbol` (e.g. `HANN`) |
| `company_name` | `company_name` with the leading `"<SYMBOL>: "` prefix stripped |
| `earnings_call_date` | `meeting_date` (tz-aware UTC) as a `date` |
| `video_clip_time` | `period` — the clip **duration** shown on the card, e.g. `"45:00"` |
| `youtube_url` | derived from the thumbnail `image_path`, e.g. `https://www.youtube.com/watch?v=…` |

`youtube_url` (and `youtube_video_id`) are `None` for upcoming items with no recording.

> ⚠️ **The `period` field has two meanings.** In the **list** response (used for
> `video_clip_time`) it is the clip **duration** (`"45:00"`, MM:SS). In the **detail**
> response (enrichment) it is the meeting **clock-time range** (`"16:15 - 17:00"`), surfaced
> separately as `EarningsCallDetail.meeting_time`. The list duration is authoritative and is
> never overwritten by enrichment.

## Models

### `EarningsCallItem`

- `id: int`, `name: str` (Thai presentation title), `symbol: str`, `industry: str`
- `company_name: str` — raw, e.g. `"HANN: MUKDAHAN INTERNATIONAL HOSPITAL …"`
- `meeting_date: datetime` — tz-aware UTC
- `image_path: str | None`, `view_mode: bool | None`, `period: str | None`
- **Derived** (computed): `company_name_clean: str`, `youtube_video_id: str | None`,
  `youtube_url: str | None`
- `detail: EarningsCallDetail | None` — populated only when `enrich=True`

### `EarningsCallResponse`

- `no_records: int` — total records across all pages
- `items: list[EarningsCallItem]`, `count` property
- `to_dataframe(columns=None) -> pandas.DataFrame` — defaults to the 5 columns above;
  additional selectable columns: `company_name_raw`, `earnings_call_datetime`,
  `youtube_video_id`, `id`, `name`, `industry`, `view_mode`. Unknown column → `ValueError`;
  pandas missing → `ImportError`.

### `EarningsCallDetail` (enrichment / detail-by-id)

`video_link`, `company_name_th`, `meeting_time` (the clock-time range), `document_link`,
`snapshot_link`, `round_name`, `type`, `type_id`, `year`, `round`, `has_qa`, `image_path`, …
plus **derived** `youtube_video_id` / `youtube_url` (built from the clean `image_path`, so a
malformed `video_link` can't break the link — `video_link` itself is also whitespace-cleaned,
since a few legacy records embed a stray newline mid-URL).

### `FilterOption`

`id: int | str`, `name: str` (ids are ints for types/years/trusts/stages, string codes for
industries/markets/themes).

## Service Class

### `EarningsCallService(config: FetcherConfig | None = None)`

`use_session` is always coerced to `False` for this stateless host; all other `FetcherConfig`
settings (timeout, retries, impersonation, rate limit) are honored.

#### `fetch_earnings_calls(...) -> EarningsCallResponse`

```python
response = await EarningsCallService().fetch_earnings_calls(
    type_id=1,        # 1=Earnings Call/OPPDAY, 2=Digital Roadshow, 3=C-Sign
    quarter_id=0,     # 0=all quarters; see fetch_filter_years()
    keyword=None,     # free-text symbol/company search (normalized)
    industries_id=None,
    start=1,          # 1-based page number
    page_size=12,
    language="en",    # "en" or "th"
    enrich=False,     # opt-in per-item detail (bounded concurrency)
)
```

#### `fetch_all_earnings_calls(..., page_size=200, max_concurrency=5, progress=False, progress_callback=None, max_records=None, max_pages=None)`

Auto-paginates the **whole** archive **concurrently**: fetches page 1 to learn the total, then
fetches the remaining pages in parallel (bounded by `max_concurrency`, default 5) and reassembles
items in order. Far faster than one page at a time — fetching all ~9520 records drops from
**~150 s to ~15 s (~10× faster)** at the default concurrency, and more with a higher
`max_concurrency`.

- **Speed**: `page_size` is **not** capped by the API (a larger page = fewer requests); the
  default is 200. `max_concurrency` bounds simultaneous load (politeness).
- **Progress**: pass `progress=True` for a `tqdm` bar (`pip install "settfex[progress]"`), or a
  `progress_callback(done, total)` for a dependency-free hook. Both cover the page phase and,
  when `enrich=True`, the enrichment phase.

```python
service = EarningsCallService()
response = await service.fetch_all_earnings_calls(progress=True)   # whole archive, with a bar
df = response.to_dataframe()

# bounded + a custom progress hook:
response = await service.fetch_all_earnings_calls(
    max_records=2000, max_concurrency=8, progress_callback=lambda done, total: None
)
```

#### `fetch_earnings_calls_raw(...) -> dict`

Raw JSON dict (no validation), for debugging.

#### `fetch_earnings_call_detail(id, language="en") -> EarningsCallDetail`

Fetch one OPPDAY presentation directly by its id — the number in a
`https://opportunity-day.setgroup.or.th/en/vdo/{id}` URL:

```python
detail = await EarningsCallService().fetch_earnings_call_detail(6319)
print(detail.symbol, detail.round_name, detail.youtube_url)
# SCB  YE/2021  https://www.youtube.com/watch?v=eOC0S8A4QEE
```

#### Filter helpers

`fetch_filter_types()`, `fetch_filter_years()`, `fetch_filter_industries()`,
`fetch_filter_markets()`, `fetch_filter_themes()`, `fetch_filter_trusts()`,
`fetch_filter_stages()` → `list[FilterOption]`.

## Convenience Functions

- `get_earnings_calls(...) -> EarningsCallResponse`
- `get_earnings_calls_dataframe(..., columns=None) -> pandas.DataFrame`
- `get_earnings_call_detail(id, language="en") -> EarningsCallDetail`
- `get_all_earnings_calls(..., progress=False, max_concurrency=5) -> EarningsCallResponse` — the
  whole calendar in one concurrent call

`get_earnings_calls(...)` fetches a **single page** by default (mirroring `get_stock_list`); use
`get_all_earnings_calls(progress=True)` (or `fetch_all_earnings_calls`) for the full calendar,
then `to_dataframe()`.

## Usage Examples

### Filter by quarter and type

```python
service = EarningsCallService()
years = await service.fetch_filter_years()          # find the quarter id you want
q1_2026 = next(y for y in years if y.name == "Quater 1/2026").id
response = await service.fetch_earnings_calls(type_id=1, quarter_id=q1_2026, page_size=50)
```

### Search a single company

```python
response = await get_earnings_calls(keyword="HANN")
for item in response.items:
    print(item.meeting_date.date(), item.youtube_url)
```

### Enrich with detail (video link, Thai name, meeting time)

```python
response = await get_earnings_calls(page_size=10, enrich=True)
for item in response.items:
    if item.detail:
        print(item.symbol, item.detail.meeting_time, item.detail.video_link)
```

## Optional dependency: pandas

`to_dataframe()` / `get_earnings_calls_dataframe()` need pandas, which is an **optional**
extra (the rest of the service works without it):

```bash
pip install "settfex[dataframe]"   # or: uv add pandas
```

## API Endpoints

```
POST https://api.lcp.setgroup.or.th/api/v1/investor/search/archive      # list (primary)
GET  https://api.lcp.setgroup.or.th/api/v1/investor/vdo/{id}            # detail (enrich)
GET  https://api.lcp.setgroup.or.th/api/v1/investor/filter/{name}       # filter options
```

## Related Services

- [Stock List Service](list.md) — discover all SET/mai stocks
- [AsyncDataFetcher](../../utils/data_fetcher.md) — low-level HTTP client (now supports POST)
