# SET Market Holiday Service

## Overview

Fetches the official **SET market holiday calendar** for a calendar year
(`GET /api/cms/v1/holidays/year/{year}`) in English or Thai. One call returns every published
market closure for the year, with helpers for answering "is this day a holiday?".

Module: `settfex/services/set/holiday.py` · Three tiers: `get_holidays()` (one-call convenience,
the LLM tool-calling entry point) → `HolidayService.fetch_holidays()` (validated Pydantic models) →
`HolidayService.fetch_holidays_raw()` (raw `list[dict]` escape hatch).

> ### ⚠️ Four API gotchas (live-verified 2026-07-27)
>
> 1. **Only the current year is served.** With 2026 returning HTTP 200 on every interleaved
>    control request, **2024, 2025, 2027 and 2028 all returned HTTP 401**. Any year other than the
>    current one raises `FetchError`. This endpoint cannot supply history for backtests, nor next
>    year's calendar for year-boundary arithmetic.
> 2. **HTTP 401 is the only failure code, and it is ambiguous.** An unrecognized `lang`, a missing
>    `lang`, and an unserved year all return a bare `401` with an **empty body** — and so do
>    perfectly valid requests, *transiently*. The service therefore retries `401/403/429` with
>    exponential backoff before raising (see [Reliability](#reliability)).
> 3. **This is the only `/api/cms/v1/` endpoint**, and it takes `?lang=` (like the stock and news
>    endpoints), **not** `?language=` (the index endpoints). Passing the wrong one returns 401.
> 4. **Descriptions are verbatim.** A trailing `" *"` is a SET footnote marker on additional
>    special closures (e.g. `"Additional special holiday *"` on 2026-10-16) and is deliberately
>    **not** stripped — unlike other SET models, `Holiday` does not enable `str_strip_whitespace`.

## Quick Start

```python
import asyncio
from datetime import date
from settfex.services.set import get_holidays

async def main() -> None:
    # Current year in Asia/Bangkok, English descriptions
    calendar = await get_holidays()
    print(f"{calendar.count} holidays in {calendar.year}")
    for holiday in calendar.holidays:
        print(f"{holiday.holiday_date:%Y-%m-%d}  {holiday.description}")

    print(calendar.is_holiday(date(2026, 1, 1)))  # True

asyncio.run(main())
```

```python
# Thai descriptions
calendar = await get_holidays(lang="th")

# An explicit year (must be the current year — see gotcha 1)
calendar = await get_holidays(2026)

# Be patient when the endpoint is throwing transient 401s
from settfex.utils.data_fetcher import FetcherConfig
calendar = await get_holidays(config=FetcherConfig(max_retries=6, retry_delay=2.0))
```

## Models

### `Holiday`

One market holiday. Both fields are always present.

| Field | Alias | Type | Notes |
|---|---|---|---|
| `holiday_date` | `date` | `datetime` | Timezone-aware, always `+07:00` (Asia/Bangkok); time is always `00:00:00` |
| `description` | — | `str` | Holiday name in the requested language, **verbatim** — a trailing `" *"` is a SET footnote |

The field is named `holiday_date` rather than `date` so the module can use `datetime.date` freely;
`populate_by_name=True` means the API's `date` key still round-trips (`model_dump(by_alias=True)`).

### `HolidayCalendar`

Container for one year. Holidays are kept in API order (live-verified ascending, no duplicates);
none of the helpers depend on that ordering.

| Member | Description |
|---|---|
| `year` | `int` — the calendar year |
| `lang` | `'en'` or `'th'` — language the descriptions were fetched in |
| `holidays` | `list[Holiday]` — every published holiday, in API order |
| `count` | *(property)* number of holidays |
| `dates` | *(property)* `list[date]` — plain Bangkok-local calendar days, ascending |
| `is_holiday(day)` | `bool` — is this day on SET's published holiday list |
| `get_holiday(day)` | `Holiday \| None` — the matching entry, or `None` |
| `filter_by_month(month)` | `list[Holiday]` — holidays in month `1`–`12` (raises `ValueError` otherwise) |
| `next_holiday(after=None)` | `Holiday \| None` — earliest holiday strictly after `after` (default: today in Bangkok) |

`day` accepts a `date` or a `datetime`. Naive datetimes are treated as Bangkok-local; aware ones
are converted to the Bangkok calendar day first.

> ### ⚠️ `is_holiday()` is not "is the market open"
>
> The API returns **closures only** — Saturdays and Sundays are not in the payload, so
> `is_holiday(saturday)` returns `False` even though the market is shut. Answering "was the market
> open on date X?" additionally requires weekend logic (and this endpoint expresses whole-day
> closures only — it has no field for partial sessions or altered trading hours).

## Service Class

### `HolidayService(config: FetcherConfig | None = None)`

Uses the default `use_session=True`, so `SessionManager` handles the Incapsula cookie warm-up
automatically. Raise `max_retries` if you hit repeated HTTP 401s.

#### `fetch_holidays(year=None, lang="en") -> HolidayCalendar`
#### `fetch_holidays_raw(year=None, lang="en") -> list[dict]`

| Param | Type | Default | Notes |
|---|---|---|---|
| `year` | `int \| None` | `None` | Defaults to the current year in **Asia/Bangkok**, never system-local time. Only the current year is served by the API. |
| `lang` | `Language` | `"en"` | `en`/`eng`/`english` or `th`/`tha`/`thai`, normalized via `normalize_language()` |

Client-side, `year` must be an integer between `MIN_YEAR` (1975, when SET began trading) and
`MAX_YEAR` (2100). That is a **typo guard only**, not a claim about coverage — it stays permissive
so that if SET starts publishing next year's calendar, the client does not reject it.

## Convenience Function

```python
async def get_holidays(
    year: int | None = None,
    lang: Language = "en",
    config: FetcherConfig | None = None,
) -> HolidayCalendar
```

## Usage Examples

### Is the market closed today?

```python
from datetime import datetime
from zoneinfo import ZoneInfo

calendar = await get_holidays()
today = datetime.now(ZoneInfo("Asia/Bangkok")).date()

# Remember: holidays only. Weekends must be checked separately.
closed = today.weekday() >= 5 or calendar.is_holiday(today)
```

### What is the next market holiday?

```python
calendar = await get_holidays()
upcoming = calendar.next_holiday()
if upcoming:
    print(f"{upcoming.holiday_date:%d %b %Y} — {upcoming.description}")
else:
    print("No holidays left this year")
```

### Long weekends and clustered closures

```python
calendar = await get_holidays(2026)
for holiday in calendar.filter_by_month(4):      # Songkran
    print(holiday.holiday_date.date(), holiday.description)
# 2026-04-06 Chakri Memorial Day
# 2026-04-13 Songkran Festival
# 2026-04-14 Songkran Festival
# 2026-04-15 Songkran Festival
```

### Both languages side by side

```python
en = await get_holidays(2026, lang="en")
th = await get_holidays(2026, lang="th")

for a, b in zip(en.holidays, th.holidays):       # 1:1 aligned, same order
    print(f"{a.holiday_date.date()}  {a.description:45s} {b.description}")
```

## Reliability

This endpoint is noticeably less stable than the rest of the SET API, and it degrades the harder
you poll it. Measured on an unchanged, valid URL:

| Phase | Success rate |
|---|---|
| First contact (cold) | ~100% |
| After ~50 requests | ~35% |
| After ~150 requests | ~12% |

It recovers on its own after an idle period. Because `AsyncDataFetcher.fetch()` only retries
*exceptions* — never a non-2xx status — `HolidayService` retries `401`/`403`/`429` itself, using
the existing `FetcherConfig` knobs:

```python
# 7 attempts, backing off 2s, 4s, 8s, 16s, 32s, 64s
calendar = await get_holidays(config=FetcherConfig(max_retries=6, retry_delay=2.0))
```

Holiday data is static for a whole year, so cache the result in your application rather than
re-fetching it — and avoid loops that request many years.

## Error Handling

```python
from settfex.exceptions import FetchError, InvalidLanguageError
from settfex.services.set import get_holidays
from settfex.utils.parsing import ResponseParseError

try:
    calendar = await get_holidays(2026)
except ValueError as exc:            # year not an int, or outside 1975..2100
    print(f"Bad year: {exc}")
except InvalidLanguageError as exc:  # also a ValueError — catch it first
    print(f"Bad language: {exc}")
except FetchError as exc:
    print(f"HTTP {exc.status_code}: {exc}")
except ResponseParseError as exc:
    print(f"Malformed response: {exc}")
```

> `InvalidLanguageError` subclasses `ValueError`, so order the `except` clauses accordingly.
> A `FetchError` with `status_code == 401` means either *"that year is not served"* or
> *"the endpoint is saturated, retry later"* — the message spells out both, because the API
> gives no way to tell them apart.

## API Endpoint

```
GET https://www.set.or.th/api/cms/v1/holidays/year/{year}?lang={en|th}
```

Returns a **bare JSON array** (no envelope):

```json
[
  {"date": "2026-01-01T00:00:00+07:00", "description": "New Year's Day"},
  {"date": "2026-10-16T00:00:00+07:00", "description": "Additional special holiday *"}
]
```

Requires the full SET API header set (`AsyncDataFetcher.get_set_api_headers()`) — a plain request
is blocked by Incapsula with HTTP 403. Cookies are *not* required (the same request succeeds with
`use_session=False`), but the default `use_session=True` is used for consistency with the other
`www.set.or.th` services.

## Related Services

- [Stock List](list.md) — every SET/mai symbol
- [News](news.md) — company news and disclosures
- [Chart Quotation](chart_quotation.md) — latest traded price relative to now
- [Latest Historical Trading](latest_historical_trading.md) — the latest trading day's summary
- [Corporate Actions](corporate_action.md) — XD/XM dates per symbol
