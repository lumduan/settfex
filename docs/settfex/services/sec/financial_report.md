# SEC Document Service (market.sec.or.th)

## Overview

Lists and downloads **raw disclosure documents** filed with the Thai SEC's information-disclosure
system (IDISC), for any SET/mai-listed issuer. Unlike the SET services (which return *modeled*
market data), this returns the **original source files** companies file — e.g. the
`FINANCIAL_STATEMENTS.XLSX` package, and the annual Form 56-1 / 56-2 PDFs.

Covers **five document categories**: financial statements, Form 56-1 (Annual Registration
Statement), Form 56-2 (Annual Report / "One Report"), Key Financial Ratio, and MD&A.

Modules: `settfex/services/sec/` · Host: `https://market.sec.or.th` (an ASP.NET WebForms app —
stateless, no login; `curl_cffi` browser impersonation passes its bot wall). Three tiers, as
everywhere in settfex:

- `get_sec_documents()` / `download_sec_document(s)()` — flat convenience (LLM entry points).
- `FinancialReportService.fetch_documents()` / `DocumentDownloadService.download()` — validated
  Pydantic models.
- `FinancialReportService.fetch_documents_raw()` — raw parsed rows (escape hatch).

Also available as a facade: `SecCompany("CPALL")`.

> ### ⚠️ API gotchas (live-verified 2026-07-20)
>
> 1. **HTML, not JSON.** The search is an ASP.NET WebForms postback returning HTML tables; the
>    service replays it (GET fresh `__VIEWSTATE`/`__EVENTVALIDATION` tokens → form POST) and
>    parses the tables. Omitting the tokens does **not** error — it silently returns a wrong,
>    broader result set — so fresh tokens are fetched before every search.
> 2. **Dates are dd/mm/yyyy.** `from_date`/`to_date` accept `datetime.date`/`datetime` objects
>    (converted automatically) or dd/mm/yyyy strings; ISO strings raise `InvalidDateError`.
> 3. **Soft 404s.** A dead download link returns an HTML "file not found" page under **HTTP
>    200** (notably some recent `dat/annual/` 56-2 rows). Downloads validate the content-type
>    and raise `FetchError` instead of returning the error page as bytes.
> 4. **Large sections truncate** inline and expose a "display all results" ViewMore link; the
>    listing follows it (default `follow_view_more=True`) so results are complete.

## Quick Start

```python
import asyncio
from settfex.services.sec import get_sec_documents, download_sec_document

async def main() -> None:
    # List all disclosure documents for CPALL in a date window
    docs = await get_sec_documents("CPALL", from_date="01/01/2025", to_date="31/12/2026")
    print(f"{len(docs)} documents")
    for d in docs[:5]:
        print(f"{d.category.value:20} {d.year} {d.period or ''} {d.file_kind} -> {d.file_url}")

    # Download the first financial-statement package (a zip with the original XLSX)
    fs = next(d for d in docs if d.category.value == "financial_statement" and d.file_kind == "zip")
    file = await download_sec_document(fs, dest_dir="./sec_docs")
    print(f"saved {file.filename} ({file.size:,} bytes)")

asyncio.run(main())
```

```python
from datetime import date

# Only certain categories
docs = await get_sec_documents(
    "PTT", types=["financial_statement", "form_56_1"],
    from_date=date(2024, 1, 1), to_date=date(2026, 12, 31),
)

# Download everything, concurrently, into a folder
from settfex.services.sec import download_sec_documents
files = await download_sec_documents(docs, dest_dir="./out", max_concurrency=5, progress=True)
```

## Language (`lang="en"` / `lang="th"`)

Both languages are supported and return the **same documents** — same count, same categories, same
reporting years and dates.

```python
docs_en = await get_sec_documents("PTT", lang="en", from_date="01/01/2025", to_date="30/06/2025")
docs_th = await get_sec_documents("PTT", lang="th", from_date="01/01/2025", to_date="30/06/2025")
len(docs_en) == len(docs_th)          # True
```

Three things to know before you compare or archive across languages:

1. **`lang` selects the document language, not just the page's.** The Thai and English listings
   link to *different files* for the same filing — every MD&A pdf and most financial-statement
   zips exist in both editions, with distinct `file_url`/`file_id`. (IPOS-hosted rows are shared.)
   That is usually the point of asking for Thai, but it means `file_url` is **not** comparable
   across languages.
2. **Years and dates are normalized to C.E.** The Thai pages state the Buddhist era — `2568`,
   `30/06/2568`, sometimes in Thai numerals — and `year`/`as_of`/`receive_date` come back as
   `2025` and `date(2025, 6, 30)` either way. Compare on these.
3. **Free-text cells stay in the page's own language.** `company_name`, `status`, `period`,
   `statement_type` and `section` are what the site printed (`สอบทาน` vs `Reviewed`,
   `ไตรมาสที่ 2` vs `Q2`). They are deliberately not translated — the payload is recorded, not
   rewritten. Key your comparisons on `category`, `year` and `as_of`.

> **Closed (was a known gap):** the `Receive Date` column of the 56-1/56-2 sections had
> no Thai mapping, so a Thai 56-1/56-2 listing returned `receive_date=None` while every other field
> populated — and for an annual report that is the only filing timestamp the model exposes. The
> Thai header was observed on 2026-09-21 (`วันที่ได้รับข้อมูล`, same column position as the English
> one) and is mapped; `12/03/2569` parses to `date(2026, 3, 12)`, exactly what the English page
> yields for the same filing.

## Completeness: what the site said vs what you got

Each results section states its own record count (`( 27 record(s) found)` /
`(จำนวนรายการที่พบ 27 รายการ)`). That number is kept:

```python
docs.reported_counts          # {'financial_statement': 6, 'key_financial_ratio': 2, 'mda': 2}
docs.completeness()           # {'financial_statement': (6, 6), ...}  -> (held, site's number)
```

A shortfall is **not** automatically an error: a long section is truncated behind a "view more"
link, so with `follow_view_more=False` the site's number is legitimately larger. It is there as a
cross-check — a section reporting 27 records that yields 0 documents is the shape of a bug.

You do not have to run that check yourself: `fetch_documents` runs it and the summary log line
is derived from it, so `Listed 0 SEC document(s)` can no longer read like a success.

## Accounting: what the parser did with every row

`completeness()` compares what you hold against **the site's printed number**, so a shortfall there
is usually legitimate truncation. `docs.accounting` is the other half — what the parser did with
each row it actually received, needing no record-count marker at all:

```python
docs.accounting.documents        # rows that became a SecDocument
docs.accounting.no_link          # rows LOST: a data row whose download link was missing
docs.accounting.placeholders     # "Data not found" / "ไม่พบข้อมูล" — the site saying it has none
docs.accounting.navigation       # "display all results" rows — how a long section truncates
docs.accounting.unmapped_headers # columns the site serves that map to no field
docs.accounting.has_losses       # the one flag worth branching on
docs.accounting.by_category      # the same tally per DocumentCategory
```

The three drop reasons used to share one counter, so the only one that is a defect looked exactly
like the two that are the site working normally. They are separated because `no_link` is the signal
worth escalating and the other two must never be able to trigger it.

## Errors

`ParseError` (a subclass of `FetchError`, so existing handlers keep working) is raised when a page
carries data rows and **none** of them can be classified — the signature of a site-side change.
An issuer with no filings still returns an empty list and does **not** raise: the check keys on
unrecognised section headings, not on emptiness.

`IncompleteListingError` (a subclass of `ParseError`) is its sibling: rows classified fine and
then **every** usable one was dropped for want of a download link. Deliberately
narrow — a *partial* loss does not raise, it warns and lands on `accounting.no_link`, because a
partial result is still usable once the loss is named. An unmodelled **column** never raises at
all: it is reported on `accounting.unmapped_headers`, since a column the site added is not lost
data and must not be able to fail a listing.

## Document categories

`DocumentCategory` values (pass as enum members or their string values):

| Value | Meaning | Download payload |
|---|---|---|
| `financial_statement` | Quarterly/annual financial statements | zip: `FINANCIAL_STATEMENTS.XLSX` + auditor report + notes |
| `form_56_1` | Annual Registration Statement (56-1) | zip containing the One-Report PDF |
| `form_56_2` | Annual Report / One Report (56-2) | zip containing the One-Report PDF |
| `key_financial_ratio` | Key financial ratios | file (via IPOS) |
| `mda` | Management Discussion & Analysis | PDF |

A single financial-statement search returns the statement, KFR **and** MD&A sections together;
the service maps requested categories to the minimal set of underlying queries automatically.

## List available years, then download them all

The listing calls (`get_sec_documents`, `FinancialReportService.fetch_documents`,
`SecCompany.list_documents`) return a **`SecDocumentList`** — a plain `list[SecDocument]` (so it
still indexes, iterates, and can be passed straight to `download_sec_documents(...)`) with a few
helpers for exactly this:

| Method | Returns |
|---|---|
| `years_by_category()` | `dict[str, list[int]]` — available years per category (newest first) |
| `available_years(category=None)` | `list[int]` — years across all docs, or one category |
| `filter(category=None, year=None)` | a new `SecDocumentList` (a subset) |
| `categories()` | the distinct `DocumentCategory` values present |
| `summary()` | a ready-to-`print()` block of years per category |

> ⚠️ **Pass a wide date window to see the full history.** Without `from_date`/`to_date` the SEC
> form returns only a recent window. Use e.g. `from_date="01/01/2010", to_date="31/12/2026"` to
> enumerate every available year. (MD&A rows carry a *date*, not a reporting *year*, so they show
> no years.)

```python
from settfex.services.sec import get_sec_documents, download_sec_documents

# 1) List everything (wide window), then see which years exist per category
docs = await get_sec_documents("CPALL", from_date="01/01/2010", to_date="31/12/2026")

print(docs.summary())
# financial_statement : 2026, 2025, 2024, 2023, 2022, 2021, 2020, ...
# form_56_1           : 2025, 2024, 2023, 2022, 2021, 2020
# form_56_2           : 2025, 2024, 2023, 2022, 2021, 2020, ...

docs.years_by_category()          # -> {'financial_statement': [2026, 2025, ...], 'form_56_1': [...]}
docs.available_years("form_56_1")  # -> [2025, 2024, 2023, 2022, 2021, 2020]

# 2) Download them all — pass the whole list, or a filtered subset
await download_sec_documents(docs, dest_dir="./out")                                 # everything
await download_sec_documents(docs.filter(category="form_56_1"), dest_dir="./out")    # just 56-1
await download_sec_documents(docs.filter(category="financial_statement", year=2025),
                             dest_dir="./out")                                       # one year
```

With the `SecCompany` facade, `await sec.download_all(docs, dest_dir="./out")` does the same.
`download_all`/`download_sec_documents` run bounded-concurrent downloads, **dedupe by URL**
(a statement's Company & Consolidated rows share one zip — downloaded once), and (by default)
skip dead links rather than failing the whole batch.

They return a **`DownloadResult`** — still a `list[DownloadedFile]` of the successes, so
anything that iterated it keeps working, and now also carrying the ones that failed:

```python
files = await sec.download_all(docs, dest_dir="./out")
files.is_complete                          # False if anything failed
[f.target for f in files.failed]           # what did not download
files.failed[0].error_type, files.failed[0].error   # 'FetchError', '...soft 404...'
files.requested                            # unique files attempted (duplicates already collapsed)
```

Before that, a failed item was logged and dropped from the result, so a partial batch was shaped
exactly like a complete one.

### Tuning downloads (timeout & concurrency)

Form 56‑1/56‑2 "One Reports" are large (**15–25 MB**). Downloads default to a **180 s** per-file
timeout and **`max_concurrency=3`**; raise the timeout / lower the concurrency for big batches on
a slow link:

| Batch | `max_concurrency` | `timeout` |
|---|---|---|
| Form 56‑1 / 56‑2 (10–25 MB) | **1–2** | **180–300 s** |
| Financial statements (~0.4–1 MB zips) | 3 (default) | 180 (default) |
| Slow / shared connection, still timing out | **1** | **300** (max) |

```python
await download_sec_documents(docs.filter(category="form_56_1"),
                             dest_dir="./out", max_concurrency=2, timeout=300)
```

**Memory:** when `dest_dir` is set, each returned `DownloadedFile` has its `content` emptied after
the file is written (bytes live on disk; `size` and `path` remain) so a big batch doesn't sit in
RAM. Pass `keep_bytes=True` to keep the bytes in memory too; omit `dest_dir` and the bytes are
returned (the only way to get them).

## Models

### `SecDocument`

| Field | Type | Notes |
|---|---|---|
| `company_name` | `str` | Issuer name (row 'Name' cell, or resolved fallback for MD&A) |
| `unique_id` | `str` | SEC uniqueIDReference the search was run for |
| `category` | `DocumentCategory` | One of the five categories |
| `section` | `str` | Raw section heading (record-count suffix stripped) |
| `title` | `str \| None` | Document heading (MD&A rows carry this instead of a Name) |
| `year` | `int \| None` | Reporting year |
| `period` | `str \| None` | `'Q1'`/`'Q2'`/`'Q3'`/`'Year'` (statements) |
| `statement_type` | `str \| None` | `'Company'` or `'Consolidated'` |
| `status` | `str \| None` | `'Reviewed'` or `'Audited'` |
| `business_type` | `str \| None` | KFR rows only |
| `as_of` | `date \| None` | Row date ('As Of' for statements, 'Date' for MD&A) |
| `receive_date` | `date \| None` | Filing date (56-1/56-2) |
| `file_url` | `str` | Absolute download URL |
| `file_id` | `str \| None` | FILEID path, or a synthetic `'ipos:<id>'` / `'fsdl:<blob>'` / `'viewdoc:<id>-<n>'` for the other three download shapes |
| `file_kind` | `str \| None` | `'zip'`/`'pdf'`/… |

### `CompanyMatch`

`company_name` (alias `Text`), `unique_id` (alias `Value`), `is_primary` (alias `Flag`, True for
the symbol's listed company).

### `DownloadedFile`

`filename`, `content: bytes` (empty if dropped after saving — see memory note above), `content_type`,
`size` (always the real byte count), `file_url`, `path: Path | None` (set when saved),
`document: SecDocument | None`, plus `.save(dest)` — writes to `dest/<filename>` if `dest` is a
directory (else to `dest`) and records `.path`.

## Service classes

### `FinancialReportService`

```python
fetch_documents(unique_id, *, company_name=None, types=None, from_date=None, to_date=None,
                lang="en", follow_view_more=True) -> SecDocumentList
fetch_documents_raw(unique_id, *, code, from_date=None, to_date=None, lang="en") -> list[dict]
```

### `DocumentDownloadService(config=None, *, timeout=None)`

```python
download(target, *, fetcher=None, referer=...) -> DownloadedFile   # target: SecDocument|URL|FILEID
download_all(targets, *, dest_dir=None, max_concurrency=3, continue_on_error=True,
             keep_bytes=None, progress=False) -> DownloadResult
```

`download_all` dedupes by URL, runs bounded-concurrent downloads (default `timeout=180 s` per
file, set on the service), and with `continue_on_error=True` (default) records a failed item
(e.g. a soft-404 dead link) on the result's `.failed` and carries on rather than failing the
batch. `keep_bytes` controls whether returned objects retain `content` (default: drop when saving
to `dest_dir`). `DownloadResult` **is** a `list[DownloadedFile]`, so the return type is additive.

## Convenience functions

```python
resolve_company(query, lang="en") -> CompanyMatch | None
get_sec_documents(query, *, types=None, from_date=None, to_date=None,
                  lang="en", follow_view_more=True) -> SecDocumentList
download_sec_document(target, *, dest_dir=None, timeout=None) -> DownloadedFile
download_sec_documents(targets, *, dest_dir=None, max_concurrency=3, continue_on_error=True,
                       keep_bytes=None, timeout=None, progress=False) -> DownloadResult
```

## Unified facade — `SecCompany`

```python
from settfex.services.sec import SecCompany

sec = SecCompany("CPALL")
company = await sec.resolve()                       # CompanyMatch (cached)
docs = await sec.list_documents(types="financial_statement", from_date="01/01/2025")
file = await sec.download(docs[0], dest_dir="./out")
files = await sec.download_all(docs, dest_dir="./out")
```

## Error handling

```python
from settfex import FetchError, InvalidDateError

try:
    docs = await get_sec_documents("CPALL", from_date="2026-01-01")  # ISO -> caught locally
except InvalidDateError as exc:
    print(exc)   # expected dd/mm/yyyy

file = await download_sec_document(doc)  # dead link -> FetchError ("soft 404")
```

## Verified endpoints

```
POST /public/idisc/api/company/valuebyuniqueId      {"lang","content"} -> [{"Text","Value","Flag"}]
GET  /public/idisc/{lang}/FinancialReport/{TYPE}     -> page + __VIEWSTATE tokens
POST /public/idisc/{lang}/FinancialReport/{TYPE}     form postback -> result HTML
GET  /public/idisc/{lang}/ViewMore/{slug}?...        -> complete section (fs-norm/fs-kf/fs-mda)
GET  /public/idisc/Download?FILEID=<path>            -> zip/pdf bytes
GET  /ipos/Common/IPOSGetFile.aspx?id=<id>&sq=0&v=10 -> zip bytes
GET  /public/idisc/Views/FinancialStatementDownload?query=<blob> -> zip bytes (recent KFR rows)
GET  /public/idisc/views/viewdoc?...&TransId=<id>&FileSeq=<n>    -> TIFF bytes (older KFR rows)
```
`{TYPE}` ∈ `FS` (statements + KFR + MD&A) · `R561` · `R562` · `KFR`.

## Related services

- [Financial Statements (SET factsheet)](../set/financial.md) — *modeled* balance sheet / income
  / cash flow from SET (vs. the raw XLSX package here).
- [News](../set/news.md) — SET company news/disclosures.
