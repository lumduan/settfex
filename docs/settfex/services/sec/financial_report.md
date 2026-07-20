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
await download_sec_documents(docs, dest_dir="./out", max_concurrency=5)              # everything
await download_sec_documents(docs.filter(category="form_56_1"), dest_dir="./out")    # just 56-1
await download_sec_documents(docs.filter(category="financial_statement", year=2025),
                             dest_dir="./out")                                       # one year
```

With the `SecCompany` facade, `await sec.download_all(docs, dest_dir="./out")` does the same.
`download_all`/`download_sec_documents` run bounded-concurrent downloads and (by default) skip
any dead links rather than failing the whole batch.

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
| `file_id` | `str \| None` | FILEID path, or `'ipos:<id>'` for IPOS-hosted files |
| `file_kind` | `str \| None` | `'zip'`/`'pdf'`/… |

### `CompanyMatch`

`company_name` (alias `Text`), `unique_id` (alias `Value`), `is_primary` (alias `Flag`, True for
the symbol's listed company).

### `DownloadedFile`

`filename`, `content: bytes`, `content_type`, `size`, `file_url`, `document: SecDocument | None`,
plus `.save(dest)` — writes to `dest/<filename>` if `dest` is a directory, else to `dest`.

## Service classes

### `FinancialReportService`

```python
fetch_documents(unique_id, *, company_name=None, types=None, from_date=None, to_date=None,
                lang="en", follow_view_more=True) -> list[SecDocument]
fetch_documents_raw(unique_id, *, code, from_date=None, to_date=None, lang="en") -> list[dict]
```

### `DocumentDownloadService`

```python
download(target, *, referer=...) -> DownloadedFile          # target: SecDocument | URL | FILEID
download_all(targets, *, dest_dir=None, max_concurrency=5,
             continue_on_error=True, progress=False) -> list[DownloadedFile]
```

`download_all` runs bounded-concurrent downloads; with `continue_on_error=True` (default) a
failed item (e.g. a soft-404 dead link) is logged and skipped rather than failing the batch.

## Convenience functions

```python
resolve_company(query, lang="en") -> CompanyMatch | None
get_sec_documents(query, *, types=None, from_date=None, to_date=None,
                  lang="en", follow_view_more=True) -> SecDocumentList
download_sec_document(target, *, dest_dir=None) -> DownloadedFile
download_sec_documents(targets, *, dest_dir=None, max_concurrency=5,
                       continue_on_error=True, progress=False) -> list[DownloadedFile]
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
```
`{TYPE}` ∈ `FS` (statements + KFR + MD&A) · `R561` · `R562` · `KFR`.

## Related services

- [Financial Statements (SET factsheet)](../set/financial.md) — *modeled* balance sheet / income
  / cash flow from SET (vs. the raw XLSX package here).
- [News](../set/news.md) — SET company news/disclosures.
