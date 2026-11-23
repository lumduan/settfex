# Bank of Thailand API (gateway.api.bot.or.th)

New in settfex **1.0.0**. Six Bank of Thailand (BOT) API products behind one package,
`settfex.services.bot`, with a facade, `BankOfThailand`.

**Each user brings their own tokens.** BOT gives them out free, one per product. settfex only
connects: it reads the token, sends it in the `Authorization` header, and never logs it or puts it
in an error.

Verified live on **2026-11-23**, 11:30-11:58 ICT:
- all **32 operations** across the six products, with one token per product, 50 requests in total;
- compared with the **17 official OpenAPI documents** the portal serves.

Where the docs and the API disagree, settfex follows the API (see
[Where the official docs are wrong](#where-the-official-docs-are-wrong)).

## Get your tokens

Guide: **https://portal.api.bot.or.th/manual**

1. Go to https://portal.api.bot.or.th → **Log in** → **Sign up Now**. Register with your email (you
   get a verification code), a password and your name.
2. **[Catalogues](https://portal.api.bot.or.th/portal/catalogue-products)** → pick a product → choose
   its plan → **Access with this plan**.
3. Cart icon → **create an application** → submit it for approval.
4. On the approved app's page, copy each credential's **Token** (not *Token Hash*).

Each credential is bound to **one** product plan. A Statistics token sent to an Interest Rates
endpoint gets HTTP 403 `{"error": "Access to this API has been disallowed"}`.

## Give settfex the tokens

settfex looks, in order, at:

1. the `token=` argument of the call or service;
2. the product's own environment variable, `BANK_OF_THAILAND_TOKEN_<PRODUCT>`;
3. `BANK_OF_THAILAND_TOKEN`, the fallback for any product;
4. the same two names in a `.env` file in the working directory (`env_file=` chooses another,
   `None` skips it).

| Product | Variable | Rate limit (portal plan, 2026-11-23) |
|---|---|---|
| Interest Rates | `BANK_OF_THAILAND_TOKEN_INTEREST_RATES` | 200 calls/hour |
| Statistics | `BANK_OF_THAILAND_TOKEN_STATISTICS` | 2000 calls/hour |
| Exchange Rates | `BANK_OF_THAILAND_TOKEN_EXCHANGE_RATES` | 200 calls/hour |
| Debt Securities Auction | `BANK_OF_THAILAND_TOKEN_DEBT_SECURITIES_AUCTION` | 200 calls/hour |
| Others (financial institutions' holidays) | `BANK_OF_THAILAND_TOKEN_OTHERS` | 100 calls/hour |
| License Check | `BANK_OF_THAILAND_TOKEN_LICENSE_CHECK` | 100 calls/hour |

A template is in [`.env.example`](../../../../.env.example). With no token anywhere, a call raises
`BotTokenMissingError` (a `ValueError`) before sending anything.

## Quick start

```python
from settfex.services.bot import (
    KNOWN_SERIES, BankOfThailand, get_bibor, get_exchange_rates, get_policy_rate,
    get_stat_observations,
)

rate = await get_policy_rate()                            # PolicyRate(rate=1.0, announcement_date=2026-10-28, ...)
bibor = await get_bibor("2026-11-16", "2026-11-20")       # BotReport[BiborRate]
bibor.rows[0].three_months                                # 1.15
thor = await get_stat_observations(KNOWN_SERIES["thor"], "2026-11-01")
thor.latest                                               # StatObservation(period='2026-11-23', value=...)
usd = await get_exchange_rates("monthly", "2026-08", "2026-10", currency="USD")

bot = BankOfThailand()                                    # the same, as one object
auctions = await bot.debt_securities.fetch_auction_results("2026-11-01", "2026-11-20")
```

## What each product gives

| Product | Call (convenience) | Service method | Endpoint | Rows |
|---|---|---|---|---|
| Interest Rates | `get_policy_rate()` | `InterestRatesService.fetch_policy_rate()` | `PolicyRate/v3/policy_rate/` | `PolicyRate` (rate, announcement, MPC text) |
| | `get_bibor(start, end, average=True, bank=)` | `fetch_bibor_average()` / `fetch_bibor()` | `BIBOR/v2/bibor_avg_rate/`, `/bibor_rate/` | `BiborRate` (O/N, 1W, 1M, 2M, 3M, 6M, 9M, 1Y) |
| | `get_deposit_rates(start, end, ranges=False)` | `fetch_deposit_rates()` / `fetch_deposit_rate_ranges()` | `DepositRate/v2/deposit_rate/`, `/avg_deposit_rate/` | `DepositRate` (saving, 3/6/12/24M min-max) |
| | `get_loan_rates(start, end, averages=False)` | `fetch_loan_rates()` / `fetch_loan_rate_averages()` | `LoanRate/v2/loan_rate/`, `/avg_loan_rate/` | `LoanRate` (MOR, MLR, MRR, ceiling, default, credit card) |
| | `get_interbank_rates(start, end, term=)` | `fetch_interbank_rates()` | `Stat-InterbankTransactionRate/v2/INTRBNK_TXN_RATE/` | `InterbankRate` (min/max/mode/weighted average) |
| | — (empty since 2024-12-27) | `fetch_external_rates()`, `fetch_spot_rates()`, `fetch_swap_points()`, `fetch_implied_rates()` | `Stat-ExternalInterestRate/…`, `Stat-SpotRate/…`, `Stat-SwapPoint/…`, `Stat-ThaiBahtImpliedInterestRate/…` | `RateTypeQuote`, `SpotRate`, `SwapPoint` |
| Statistics | `get_stat_categories()` | `StatisticsService.fetch_categories()` | `categorylist/category_list/` | `StatCategory` (403 on 2026-11-23) |
| | `get_stat_series_list(category)` | `fetch_series_list()` | `categorylist/series_list/` | `StatSeriesInfo` |
| | `search_stat_series(keyword)` | `search_series()` | `search-series/` | `StatSeriesInfo` (at most 100; adds frequency, unit, lag, release schedule) |
| | `get_stat_observations(code, start, end=None, sort=)` | `fetch_observations()` | `observations/` | `StatSeries` with `StatObservation`s, `.latest` |
| Exchange Rates | `get_exchange_rates(frequency, start, end, currency=)` | `ExchangeRatesService.fetch_exchange_rates()` | `Stat-ExchangeRate/v2/{DAILY,MONTHLY,QUARTERLY,ANNUAL}_AVG_EXG_RATE/` | `ExchangeRate` (buying sight/transfer, selling, mid) |
| | `get_reference_rates(frequency, start, end)` | `fetch_reference_rates()` | `Stat-ReferenceRate/v2/{…}_REF_RATE/` | `ReferenceRate` (THB/USD weighted average) |
| Debt Securities Auction | `get_bond_auction_results(start, end)` | `DebtSecuritiesAuctionService.fetch_auction_results()` | `BondAuction/bond_auction_v2/` | `BondAuctionResult` (yields, amounts, bid coverage) |
| Others | `get_financial_institution_holidays(year)` | `HolidaysService.fetch_holidays()` | `financial-institutions-holidays/` | `FinancialInstitutionHoliday` |
| License Check | `search_licensed_entities(keyword, page=, limit=)` | `LicenseCheckService.search()` | `BotLicenseCheckAPI/SearchAuthorized` | `LicenseSearchResult` of `LicensedEntity` |
| | `get_licensed_entity(id)` | `fetch_entity()` | `BotLicenseCheckAPI/AuthorizedDetail` | `LicensedEntityDetail` (entity, licences, branches) |
| | `get_license_document(auth_id, doc_id)` | `fetch_document()` | `BotLicenseCheckAPI/License` | `LicenseDocument` (the file: a PDF) |

Every service also has `fetch_raw(path, params)`, which returns any endpoint of that product as
decoded JSON (the escape hatch).

## Periods and defaults

| Frequency | Format | Example |
|---|---|---|
| daily | `YYYY-MM-DD` | `2026-11-20` |
| monthly | `YYYY-MM` | `2026-10` |
| quarterly | `YYYY-QN` | `2026-Q3` |
| annual | `YYYY` | `2025` |

- `datetime.date` objects are converted for any frequency. A malformed string raises
  `InvalidDateError` before any request.
- **Daily endpoints always send both periods**, because BOT answers a call without them with HTTP
  404. If you leave both out you get the last 7 calendar days in Asia/Bangkok (30 for auctions); if
  you give only a start you get that one day.
- Statistics observations need a start date; the end is optional.

## Responses

Most calls return a `BotReport[Row]`:

- `api`, `timestamp`: BOT's own label and time.
- `header` (`ReportHeader`, on the Stat-* tables):
  - the report's name and unit, and `last_updated`;
  - `sources` and `remarks`, verbatim;
  - a computed `is_discontinued`: BOT's own remark says the table is discontinued.
- `rows`: the product's row model.
- a computed `has_values`: some row carries a number.

**Units: rates are in PERCENT, not fractions.**
- Interest rates (policy rate, BIBOR, deposit, loan, interbank) are percent per annum: `1.15`
  means 1.15 %.
- A Statistics `value` is in its series' `unit_eng`, which is `"Percent"` for THOR, the THOR
  averages and the government yields: `0.99566` means 0.99566 %, i.e. `0.0099566` as a fraction.
- Exchange rates are baht per unit of foreign currency.
- **If your code expects a fraction, divide by 100.** A missed `/100` is the classic bug here.

**Every BOT value arrives as a string, and a missing one as `""`.**
- Numeric fields are `float | None` (`""` and `"-"` become `None`).
- Text stays text: `BondAuctionResult.coupon_rate` is `'2.44'`, `'Discount'` or
  `'Compounded THOR  0.05'`.
- Daily-only tables give `date` periods. FX and Statistics keep BOT's period text, because the
  frequency varies.

## Errors

| Raised | When | Do |
|---|---|---|
| `BotTokenMissingError` (`ValueError`) | no token for that product (nothing was sent) | get one (above); the message names the variables |
| `BotAccessDeniedError` (`HTTPStatusError`) | HTTP 401/403: the token is not for this product, or the *Token Hash* was copied | check that product's variable and the app's subscriptions |
| `BotApiError` (`FetchError`) | HTTP 200 whose `result` says `success: "false"` (e.g. an auction call without periods) | `.errors` carries BOT's codes and messages |
| `BotSeriesNotFoundError` (`FetchError`, `NotFoundError`) | an unknown Statistics series code: BOT answers HTTP 200 with every field `null` | fix the code; do not retry |
| `HTTPStatusError` | any other non-2xx (BOT's own message is in the text) | |
| `ResponseParseError` | a body that is not the expected JSON | |

## Traps worth knowing

- **Four Interest Rates tables have returned only empty rows since 2024-12-27,** while still
  answering HTTP 200:
  - external interest rates, the spot rate and swap points carry BOT's remark *"This table has
    been discontinued due to redundancy…"*, so `header.is_discontinued` is `True`;
  - THB implied rates has the same empty rows and the same `last_updated`, but no such remark.
  - **Check `report.has_values`, not `len(report)`.**
- **Government T-bill and bond yields are monthly averages only.**
  - The codes are `FMRTINTM00284`-`00306` (1M ... 20Y). They are published on the 10th of the
    following month (e.g. 2026-10 was published 2026-11-10).
  - **The series search lists discontinued codes first:** `FMRTINTM00027`-`49` ended in 2025-07.
    Check `observation_end`.
- **For a daily short rate,** use THOR or BIBOR:
  - THOR (`FMRTTHORD00003`) and the THOR averages 1M/3M/6M are updated the same day;
  - BIBOR (`get_bibor`) is daily.
- **Bank holidays are not the SET calendar.** Use `settfex.services.set.get_holidays()` for market
  closures.

`KNOWN_SERIES` holds the codes verified on 2026-11-23:

| Key | Code | Frequency |
|---|---|---|
| `thor` | `FMRTTHORD00003` | daily |
| `thor_average_1m` / `_3m` / `_6m` | `FMRTTHORAVG1MD00004` / `3MD00005` / `6MD00006` | daily |
| `government_yield_1m` / `_3m` / `_6m` / `_1y` / `_10y` | `FMRTINTM00284` / `285` / `286` / `287` / `296` | monthly |

## Where the official docs are wrong

Checked against the 17 OpenAPI documents the catalogue loads (2026-11-23):

| What the docs say | What the API does | Endpoints |
|---|---|---|
| `data_detail` is an object | it is a **list** | deposit ×2, loan ×2, interbank, daily reference rate, monthly/quarterly average FX |
| `report_remark`, `report_source_of_data` are objects | they are **lists** | external rates, spot rate, swap points |
| `observations` is an object | it is a **list** | Statistics observations |
| the holidays response is a bare list | it is wrapped: `{"result": {"api", "timestamp", "data": [...]}}` | financial institutions' holidays |
| (auth scheme named `X-IBM-Client-Id`) | the header is `Authorization`, as for every product | financial institutions' holidays |
| (no response schema) | see the models | daily average FX, License search and detail |
| (not documented) | `success`, `unit_eng`, `series_categories[].category`, `lag_time`, release schedule, descriptions | auction, search-series |

The field **names** matched in every case. Only shapes and wrappers differ.

## Gateway

- `https://gateway.api.bot.or.th/<path>`, with the header `Authorization: <token>`.
- The old channel (`https://apigw1.bot.or.th/bot/public`, `X-IBM-Client-Id`) is replaced, per the
  portal's migration page.
- The gateway is stateless: settfex runs it with `use_session=False`, and needs no cookies.
