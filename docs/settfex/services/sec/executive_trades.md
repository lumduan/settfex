# SEC Form 59: executive trades

Every director and executive of a Thai listed company must report each change in their holdings
of the company's securities and derivatives to the SEC on **Form 59 (แบบ 59)**. The SEC publishes
the reports at `https://market.sec.or.th/public/idisc/{th|en}/r59`. This service reads that
listing and, optionally, the report behind each row.

```python
from datetime import date
from settfex.services.sec import get_executive_trades, get_executive_trade_report

today = await get_executive_trades()                                # received by SEC today
spali = await get_executive_trades(symbol="SPALI", date_type="transaction",
                                   start="2026-09-01", end="2026-09-30")
print(spali.economic_trades().to_table())                           # the Thai summary table

detailed = await get_executive_trades(date(2026, 10, 2), with_details=True)
report = await get_executive_trade_report("592001352610")           # one report, all its trades
```

## Three things the listing does not say on its face

**1. The named executive is the reporter, not necessarily who traded.** The `ชื่อผู้บริหาร`
(Name of Management) column is who **filed**. A row can be a trade by the reporter's spouse, a
minor child, or a company the family controls; that trader is named in parentheses in the
relationship cell and identified by the row link's `executor` id.

| Field | Meaning |
|---|---|
| `reporter_name`, `reporter_id` | who filed |
| `executor_name`, `executor_id` | who traded (`CTRL_P_`/`TEMP_P_` a person, `CTRL_C_`/`TEMP_C_` a company) |
| `relationship` | the trader relative to the reporter, e.g. `ผู้รายงาน` (the reporter), `คู่สมรส/ผู้ที่อยู่กินด้วยกันฉันสามีภริยา` (spouse) |
| `is_self` | `reporter_id == executor_id`; `None` when an id is missing |

**2. One trade can appear twice.** When both spouses are executives of the same company, both
report the trade, so the listing shows it once per reporter (the site's own footnote says so).
Such a row gets `duplicate_of` = the `trans_id` of the original; rows are never dropped.

- With `with_details=True`, holdings decide: the same symbol, security type, date, quantity,
  holding before and holding after is one trade.
- Without details, a narrow rule decides. A row is a copy when its executor is a `CTRL_P_` person
  other than its reporter, and that person's **own** row shows the same trade.

A related-person row is **not** always a copy. On 2026-09-14 a KCG executive and his spouse each
bought 5,000 at 9.95, and the reports show two different holdings: 2,515,000 → 2,520,000 for him,
910,000 → 915,000 for her.

Checked against holdings for every September 2026 pair (28 pairs), the listing rule agreed on 26.

| Case | Holdings | Listing rule | Result |
|---|---|---|---|
| SPALI, both spouses executives (11 pairs) | identical | copy | copy |
| KCG, spouse without an executive id (7) | different | separate | separate |
| CREDIT, reporter and spouse both `CTRL_P_` (2) | identical, from 0 | separate | **copy with details, separate without** |
| CREDIT, one reporter's two filings (1) | different | separate | separate |
| STX, two reporters, one company executor (7) | 70,000 apart | separate | separate (probably one trade, filed inconsistently) |

**3. Revoked filings stay listed.** A filing the reporter withdrew shows its quantity struck through,
with `Revoked by Reporter`. On 2026-10-07 that was 4,366 of 91,245 rows, mostly re-filings: the same
trades submitted again in a later batch, so one trade can appear up to four times, three of them
revoked. Such rows carry `is_revoked=True` and keep the struck quantity.

`economic_trades()` drops both revoked rows and copies. Count trades on it, never on the raw list.

## Dates: received vs transaction, and why "today" is not the site's default page

| `date_type` | Filters on |
|---|---|
| `"received"` (default) | the day SEC received the report (`วันที่ สนง.รับเอกสาร`) |
| `"transaction"` | the trade date (`วันที่ได้มา/จำหน่าย`) |

- `get_executive_trades()` with no arguments means **received today** (Asia/Bangkok). Today's set
  can still grow during the day.
- It is **not** the page the site shows by default. That page lists what was *recorded into the
  system* today, and only trades up to a month old. On 2026-10-07 it had 27 rows, against 21
  received that day, 18 of them in common.
- The site's default view cannot be requested for a past day.
- Weekends are not empty: a report was received on Sunday 2026-10-04.
- `received_date` on a row is set only when the query asked for exactly one received day.

All dates in the models are Christian era. The Thai page states Buddhist-era years (`06/10/2569`),
and the conversion handles B.E. leap days (`29/02/2567` → 2024-02-29).

## Completeness

The search page renders at most **100** rows (it stated 112 and showed 100), so this service never
uses it. It reads the site's own "display all results" page instead: a plain GET,
`/public/idisc/{lang}/ViewMore/r59-2?[UniqueIdReference=…&]DateType=…&DateFrom=yyyyMMdd&DateTo=yyyyMMdd`.
That page returned every row for every window probed (112, 732, 736, 1,640, 7,651).

Every response's stated count (`(จำนวนรายการที่พบ N รายการ)`, "N items found") must equal the rows
parsed, or `ParseError` is raised. A short page cannot pass as a complete one.

- Ranges are fetched in windows of at most 366 days. `reported_count` is the sum of the stated
  counts, and `len(result) == reported_count` on a freshly fetched list.
- The URL builder refuses to build the page without both dates. Undated, it returns the **whole
  database** (91,245 rows, 70 MB).

## Values

| Field | Notes |
|---|---|
| `price` | the listing's price, **rounded to 2 dp** (`8.73` for a filed `8.7333`); `None` where the page shows `-` (transfers, and some buys and sells). Prefer `detail.avg_price` |
| `quantity` | an int; `0` occurs (10 rows in the history). For a revoked row, the struck figure |
| `transaction_date` | `None` for an empty cell (30 rows in the history) |
| `method`, `security_type` | verbatim labels; the vocabulary is open (10 Thai methods in the history) |
| `side` | `buy` / `sell` / `transfer_in` / `transfer_out` / `other`; unmapped labels are `other` and counted on `unknown_labels` |
| `batch_no`, `trans_id`, `report_url` | from the row's link; `None` for the 19% of the history (mostly before 2016) with no link |
| `remark` | text in the remark column other than the link, e.g. `แก้ไขข้อมูล` (data corrected) |
| `symbol` | the company cell's `(SYMBOL)` suffix, verbatim, so `BANPU ยุติ` (BANPU, deactivated after a merger) survives |

A cell the parser does not recognise raises; nothing is coerced. That covers a bracketed amount
(never seen in 91,245 rows), a non-numeric price, an impossible date, an unknown column layout and
a struck quantity without the revocation note.

## The report behind a row (`with_details=True`, `get_executive_trade_report`)

The row's "Link" page (`/r59/{lang}/report`) is rendered by JavaScript. Its data is a JSON POST to
`/r59/publicapi/report` with `{"BatchNo", "Lang"}`, and one call returns the whole batch: every
transaction in that filing (PEACE: 53).

| `ExecutiveTradeReport` | |
|---|---|
| `batch_no`, `company_name`, `reporter_name`, `position` | header |
| `submitted_at` | when SEC received it, Asia/Bangkok |
| `business_type_code` | `0106300010` securities, `0106300015` trust units |
| `symbol` | `None` from the API; filled when fetched through the listing |

| `ExecutiveTradeDetail` | |
|---|---|
| `holding_before`, `quantity`, `holding_after` | ints; a `*` on a holding is stripped and noted in `remark` |
| `avg_price` | full precision as filed (up to 4 dp) |
| `method`, `side` | finer than the listing, e.g. `โอน (โอนให้บุตร)` (transfer to a child) |
| `market_source` | channel and broker, e.g. `ทำรายการผ่านตลาดหลักทรัพย์ (Auto Matching) (…)` (on-exchange) or `ทำรายการนอกตลาดหลักทรัพย์ (…)` (off-exchange) |
| `counterparty` | the purchaser or transferee as filed |
| `record_status` | `NORMAL`, `EFFECTED`, `EDITED`, `CANCELED`; it does not mirror the listing's revoked flag one-to-one |
| `holding_consistent` | before ± quantity == after; a mismatch is flagged, never raised |
| `trans_id` | the listing row it was linked to |

How the enrichment behaves:

- **One request per distinct batch**, sequentially, at most **100** per call. Above the cap,
  `ValueError` is raised before any detail request is sent.
- **A failed batch is recorded** on `detail_failures`, and its rows keep `detail=None`. If every
  batch fails, the call raises. A block page stops everything at once.
- **Linking is by unique match only.** The API carries no transaction id and orders by date, so a
  row is matched on date, quantity, method, security type and price (within the listing's
  rounding), plus the reporter's name. A key that repeats inside a batch is left unmatched rather
  than guessed. That was 1.3% of linked rows on 2026-10-07; the count is on `detail_unmatched`.

## Output

- `to_table(include_revoked=False, with_details=False)` renders a Markdown table in Thai.
  - Rows are ordered sells first, then buys, then the other sides; within a side by symbol, then
    date.
  - `**` after a name marks a trader who is not the reporter.
  - Any `ใบสำคัญแสดงสิทธิที่จะซื้อหุ้น…` (warrant) shows as `Warrant`.
  - Dates are dd/mm/B.E.
  - `with_details=True` adds `ถือก่อน` (held before), `ถือหลัง` (held after), `ราคาเฉลี่ย` (average
    price, full precision) and `ทำรายการผ่าน` (traded through).
- `to_dataframe()` (needs `pip install settfex[dataframe]`) gives one row per listing row, with the
  detail columns. Prices are floats there; the models keep `Decimal`.
- The container slices like a list and serializes: `revoked_count`, `duplicate_count`,
  `unknown_labels` and `detail_unmatched` are computed fields, so they survive `model_dump()`.

## Tiers

| Tier | Listing | Report |
|---|---|---|
| `get_*` | `get_executive_trades(received_date=None, *, symbol, date_type, start, end, lang, with_details, config)` | `get_executive_trade_report(batch_no, lang="th")` |
| `fetch_*` | `fetch_executive_trades(start, end, *, unique_id, date_type, lang, with_details, config)` | `fetch_executive_trade_report(batch_no, lang)` |
| `fetch_*_raw` | `fetch_executive_trades_raw(...)`: the nine cells, link params, `revoked`, `quantity_note` as strings | `fetch_executive_trade_report_raw(batch_no, lang)`: the API's `Report` object |

`symbol` is resolved strictly with `resolve_company` (no name matching). An unknown symbol raises
`CompanyNotFoundError`.

## Errors

| Exception | When |
|---|---|
| `InvalidDateError` | conflicting or malformed date arguments |
| `CompanyNotFoundError` / `AmbiguousCompanyError` | the symbol does not resolve to one issuer |
| `ParseError` | a page whose stated count differs from its rows, an unknown layout, a cell that does not parse, a malformed detail envelope |
| `HTTPStatusError` | non-2xx |
| `FetchError` | transport; a detail answered with `ResponseStatus` other than `Y` |
| `BlockedError` | the SEC's WAF block page; stop sending |
| `ValueError` | more than 100 batches with `with_details=True`; a `batch_no` that is not digits |

## robots.txt

`https://market.sec.or.th/robots.txt`, read 2026-10-07, is exactly:

```
User-agent: *
Disallow: /public/idisc/*.aspx$
```

No URL this service requests matches it. The service requests `/public/idisc/{lang}/r59`,
`/public/idisc/{lang}/ViewMore/r59-2?…`, `/r59/{lang}/report` and `/r59/publicapi/report`.

The host is stateless, and requests go out with `use_session=False`, like every SEC service.
