"""SEC financial-report document models and the HTML-row → model mapper.

The listing service (added on top of this module) replays the SEC search and turns each parsed
result-table row into a :class:`SecDocument`. Models + mapping live here; the service that does
the HTTP orchestration is appended below (see ``FinancialReportService``).
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from html import unescape
from typing import Literal
from urllib.parse import urljoin

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, computed_field

from settfex.exceptions import (
    FetchError,
    IncompleteListingError,
    InvalidDateError,
    ParseError,
)
from settfex.services.sec.company import resolve_company
from settfex.services.sec.constants import (
    SEC_BASE_URL,
    SEC_FINANCIAL_REPORT_ENDPOINT,
    SEC_FORM_DATE_FORMAT,
    SEC_FORM_FIELD_COMPANY,
    SEC_FORM_FIELD_COMPANY_TEXT,
    SEC_FORM_FIELD_COMPANY_VALUE,
    SEC_FORM_FIELD_DATE_FROM,
    SEC_FORM_FIELD_DATE_TO,
    SEC_FORM_FIELD_REPORT_TYPE,
    SEC_FORM_FIELD_SEARCH,
    SEC_REFERER,
)
from settfex.services.sec.utils import (
    ReportRow,
    build_sec_headers,
    classify_download_href,
    extract_aspnet_tokens,
    parse_dmy_date,
    parse_report_tables,
    parse_year,
    split_section_count,
)
from settfex.services.set.stock.utils import Language, normalize_language
from settfex.utils.data_fetcher import AsyncDataFetcher, FetcherConfig


class DocumentCategory(StrEnum):
    """The five disclosure-document categories exposed by the SEC IDISC search.

    A :class:`enum.StrEnum`, so ``str(cat)`` and ``f"{cat}"`` render the bare value
    (``"financial_statement"``) rather than ``"DocumentCategory.FINANCIAL_STATEMENT"``.
    Equality with the plain string, ``.value`` and JSON serialization are unchanged.
    """

    FINANCIAL_STATEMENT = "financial_statement"
    FORM_56_1 = "form_56_1"
    FORM_56_2 = "form_56_2"
    KEY_FINANCIAL_RATIO = "key_financial_ratio"
    MDA = "mda"


# Requested category -> the search ddlReportType code that returns it. A single "FS" search
# returns the financial-statement, KFR and MD&A sections together, so those three share it.
CATEGORY_TO_REPORT_TYPE: dict[DocumentCategory, str] = {
    DocumentCategory.FINANCIAL_STATEMENT: "FS",
    DocumentCategory.KEY_FINANCIAL_RATIO: "FS",
    DocumentCategory.MDA: "FS",
    DocumentCategory.FORM_56_1: "R561",
    DocumentCategory.FORM_56_2: "R562",
}


class SecDocument(BaseModel):
    """A single downloadable disclosure document parsed from a SEC result row."""

    company_name: str = Field(description="Issuer name (row 'Name' cell, or resolved fallback)")
    unique_id: str = Field(description="SEC uniqueIDReference the search was run for")
    category: DocumentCategory = Field(description="Document category (from the section heading)")
    section: str = Field(description="Raw section heading (record-count suffix stripped)")
    title: str | None = Field(
        default=None, description="Document heading/title (MD&A rows carry this instead of Name)"
    )
    year: int | None = Field(default=None, description="Reporting year, if the row has one")
    period: str | None = Field(default=None, description="Period, e.g. 'Q1', 'Q3', 'Year'")
    statement_type: str | None = Field(
        default=None, description="'Company' or 'Consolidated' (financial statements only)"
    )
    status: str | None = Field(
        default=None, description="'Reviewed' or 'Audited' (financial statements only)"
    )
    business_type: str | None = Field(
        default=None, description="Business type (Key Financial Ratio rows only)"
    )
    as_of: date | None = Field(
        default=None, description="Row date column ('As Of' for statements, 'Date' for MD&A)"
    )
    receive_date: date | None = Field(default=None, description="'Receive Date', if present")
    file_url: str = Field(description="Absolute download URL for this document")
    file_id: str | None = Field(
        default=None, description="FILEID path (or 'ipos:<id>' for IPOS-hosted files)"
    )
    file_kind: str | None = Field(default=None, description="File extension: 'zip'/'pdf'/…")

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)


def _coerce_category(value: DocumentCategory | str) -> DocumentCategory:
    """Coerce a DocumentCategory or its string value into a DocumentCategory."""
    return value if isinstance(value, DocumentCategory) else DocumentCategory(value)


class RowTally(BaseModel):
    """What became of one section's rows: one document, or one of three reasons it is not.

    ``rows == documents + placeholders + navigation + no_link`` — every row lands in exactly one
    bucket, which is the point: before this, all three "not a document" outcomes shared a single
    counter and only one of them is a defect.
    """

    rows: int = Field(default=0, description="Data rows seen for this category")
    documents: int = Field(default=0, description="Rows that became a SecDocument")
    placeholders: int = Field(
        default=0, description="'Data not found' / 'ไม่พบข้อมูล' rows — the site saying it has none"
    )
    navigation: int = Field(
        default=0, description="'Display all results' ViewMore rows — a link to a page, not a file"
    )
    no_link: int = Field(
        default=0, description="A data row that should have carried a download link and did not"
    )

    def plus(self, other: RowTally) -> RowTally:
        """Return the element-wise sum of two tallies (used when merging search codes)."""
        return RowTally(
            rows=self.rows + other.rows,
            documents=self.documents + other.documents,
            placeholders=self.placeholders + other.placeholders,
            navigation=self.navigation + other.navigation,
            no_link=self.no_link + other.no_link,
        )


class ListingAccounting(BaseModel):
    """Where every row and column of a listing went — the parser's own account of itself.

    This is the second of two independent cross-checks, and the two answer different questions.
    :meth:`SecDocumentList.completeness` compares what we hold against **the number the site
    printed**, so a shortfall there is usually legitimate "view more" truncation. This one is
    internal: it says what the parser did with each row it actually received, and needs no
    record-count marker at all. ``no_link``, ``unknown_sections`` and ``unmapped_headers`` are
    defects; ``skipped``, ``placeholders`` and ``navigation`` are rows dropped on purpose.

    The totals are **computed fields**, so they survive ``model_dump()`` into JSON or Parquet
    rather than being recomputed by every consumer.
    """

    rows: int = Field(default=0, description="Data rows this listing was built from")
    skipped: int = Field(
        default=0, description="Rows in revision-tracking sections — dropped by design"
    )
    unknown_rows: int = Field(
        default=0, description="Rows in sections that could not be classified"
    )
    by_category: dict[str, RowTally] = Field(
        default_factory=dict, description="Per-category row tally, keyed by category value"
    )
    unknown_sections: list[str] = Field(
        default_factory=list, description="Section headings that could not be classified"
    )
    unmapped_headers: list[str] = Field(
        default_factory=list,
        description="Column headers in a read section that map to no field and are not ignored",
    )
    unverifiable_sections: list[str] = Field(
        default_factory=list,
        description="Read sections whose heading has no record-count marker — not checkable",
    )

    model_config = ConfigDict(populate_by_name=True)

    def _sum(self, attribute: str) -> int:
        return sum(getattr(tally, attribute) for tally in self.by_category.values())

    @computed_field  # type: ignore[prop-decorator]
    @property
    def documents(self) -> int:
        """Rows that became a document."""
        return self._sum("documents")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def placeholders(self) -> int:
        """Rows that were the site's own "nothing here" placeholder."""
        return self._sum("placeholders")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def navigation(self) -> int:
        """Rows that were a "display all results" link rather than a filing."""
        return self._sum("navigation")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def no_link(self) -> int:
        """Rows lost: a real data row whose download link was missing."""
        return self._sum("no_link")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_losses(self) -> bool:
        """True if anything was lost or not understood — the one flag worth branching on."""
        return bool(self.no_link or self.unknown_sections or self.unmapped_headers)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_balanced(self) -> bool:
        """``rows == skipped + unknown_rows + Σ by_category[*].rows`` — the accounting identity."""
        return self.rows == self.skipped + self.unknown_rows + self._sum("rows")

    def absorb(self, other: ListingAccounting) -> None:
        """Add another page's accounting into this one (one search code per page)."""
        self.rows += other.rows
        self.skipped += other.skipped
        self.unknown_rows += other.unknown_rows
        for key, tally in other.by_category.items():
            current = self.by_category.get(key)
            # Copy rather than alias: the merged accounting outlives the one it absorbed.
            self.by_category[key] = tally.model_copy() if current is None else current.plus(tally)
        self._merge_names(other)

    def supersede(self, category: str, other: ListingAccounting) -> None:
        """Replace one category's tally with the ViewMore page's, which holds the complete list.

        The inline rows for that category are not *also* returned — they are replaced — so adding
        both would double-count them and break :attr:`is_balanced`.
        """
        previous = self.by_category.pop(category, None)
        if previous is not None:
            self.rows -= previous.rows
        replacement = other.by_category.get(category)
        if replacement is not None:
            self.by_category[category] = replacement.model_copy()
            self.rows += replacement.rows
        self._merge_names(other)

    def _merge_names(self, other: ListingAccounting) -> None:
        """Union the diagnostic name lists, preserving first-seen order."""
        for attribute in ("unknown_sections", "unmapped_headers", "unverifiable_sections"):
            merged: list[str] = getattr(self, attribute)
            for name in getattr(other, attribute):
                if name not in merged:
                    merged.append(name)


class SecDocumentList(list[SecDocument]):
    """A ``list[SecDocument]`` with convenience helpers for years / categories / filtering.

    It **is** a plain list — indexing, iteration, ``len()``, slicing and passing it to
    ``download_sec_documents(...)`` all work unchanged. The extra methods make the common
    "see which years exist → pick a subset → download them" flow a one-liner.
    """

    def __init__(
        self,
        iterable: Iterable[SecDocument] = (),
        *,
        reported_counts: Mapping[str, int] | None = None,
        accounting: ListingAccounting | None = None,
    ) -> None:
        super().__init__(iterable)
        self.reported_counts: dict[str, int] = dict(reported_counts or {})
        """How many records the site said each section holds, keyed by category value.

        This describes the **sections the search returned**, not this list's contents, and it
        stays true after filtering — which is the point: you compare what you have against what
        the site said existed. See :meth:`completeness`.
        """
        self.accounting: ListingAccounting = accounting or ListingAccounting()
        """What the parser did with every row and column it received.

        The other half of the cross-check, and deliberately not folded into
        :attr:`reported_counts`: that one is the **site's** number, this one is **ours**. A
        shortfall against the site's number is usually truncation; a non-zero
        ``accounting.no_link`` is always a loss. See :class:`ListingAccounting`.
        """

    def completeness(self) -> dict[str, tuple[int, int]]:
        """Per category: ``(documents here, records the site said that section holds)``.

        A shortfall is **not** automatically an error. A long section is truncated behind a "view
        more" link, so with ``follow_view_more=False`` the site's number is legitimately larger
        than what was returned. It is the cross-check that makes a silent parse failure visible:
        a section reporting 27 records that yields 0 documents is the shape of a bug, and without
        this the caller has to re-derive the number from the raw HTML to notice.
        """
        held: dict[str, int] = {}
        for document in self:
            held[document.category.value] = held.get(document.category.value, 0) + 1
        keys = {*held, *self.reported_counts}
        return {
            k: (held.get(k, 0), self.reported_counts[k]) for k in keys if k in self.reported_counts
        }

    def categories(self) -> list[DocumentCategory]:
        """Distinct categories present, in ``DocumentCategory`` enum order."""
        present = {d.category for d in self}
        return [c for c in DocumentCategory if c in present]

    def available_years(self, category: DocumentCategory | str | None = None) -> list[int]:
        """
        Sorted-descending unique reporting years, optionally restricted to one category.

        Documents without a year (``year is None``) are ignored.
        """
        cat = _coerce_category(category) if category is not None else None
        years = {d.year for d in self if d.year is not None and (cat is None or d.category == cat)}
        return sorted(years, reverse=True)

    def years_by_category(self) -> dict[str, list[int]]:
        """
        Available years for each category present, keyed by the category **string value**
        (e.g. ``"form_56_1"``) for clean printing; iterated in enum order.

        Example:
            >>> docs.years_by_category()
            {'financial_statement': [2026, 2025, 2024], 'form_56_1': [2025, 2024, 2023]}
        """
        return {c.value: self.available_years(c) for c in self.categories()}

    def filter(
        self,
        *,
        category: DocumentCategory | str | None = None,
        year: int | None = None,
    ) -> SecDocumentList:
        """Return a new ``SecDocumentList`` matching the given category and/or year (AND)."""
        cat = _coerce_category(category) if category is not None else None
        # Carry the reported counts across, narrowed to the category kept. A `year` filter does
        # not narrow them: they describe what the SITE said each section holds, which a
        # client-side year filter cannot change. Without this the cross-check would evaporate
        # exactly when someone narrows a result.
        counts = (
            self.reported_counts
            if cat is None
            else {k: v for k, v in self.reported_counts.items() if k == cat.value}
        )
        return SecDocumentList(
            (
                d
                for d in self
                if (cat is None or d.category == cat) and (year is None or d.year == year)
            ),
            reported_counts=counts,
            # Carried whole, for the same reason: it describes the PARSE that produced these
            # documents, which no client-side filter can change. Narrowing it would hide a loss
            # from exactly the caller who narrowed the result.
            accounting=self.accounting,
        )

    def summary(self) -> str:
        """A ready-to-``print()`` block of the available years per category."""
        by_cat = self.years_by_category()
        if not by_cat:
            return "(no documents)"
        width = max(len(k) for k in by_cat)
        return "\n".join(
            f"{cat:<{width}} : {', '.join(str(y) for y in years) or '-'}"
            for cat, years in by_cat.items()
        )


def _clean_section(heading: str) -> str:
    """Strip the record-count suffix (either language) from a section heading."""
    return split_section_count(heading)[0]


# Why a section was not mapped. "skipped" is deliberate; "unknown" is a bug or a site change and
# is escalated by the caller -- the distinction is the whole point, because before it existed
# both outcomes were an indistinguishable `None`.
_SectionDisposition = Literal["mapped", "skipped", "unknown"]

# Revision-tracking sections, in both languages. `แก้ไข` ("amend/revise") covers both Thai forms:
# `งบการเงินที่อยู่ระหว่างการแก้ไข` and `งบการเงินที่สำนักงานแจ้งให้แก้ไข`.
_SKIP_TOKENS = ("revis", "amend", "order", "แก้ไข")


def _section_disposition(heading: str) -> tuple[DocumentCategory | None, _SectionDisposition]:
    """
    Classify a result-section heading into (category, disposition), in English or Thai.

    Tolerant of the site's "Finanacial" misspelling. The record-count suffix is stripped first,
    in either language, so it can never affect the match.
    """
    lower = _clean_section(heading).lower()

    # ASCII form numbers first: the Thai headings embed them verbatim ("แบบ 56-1 One Report").
    if "56-1" in lower:
        return DocumentCategory.FORM_56_1, "mapped"
    if "56-2" in lower:
        return DocumentCategory.FORM_56_2, "mapped"

    # ORDER IS LOAD-BEARING. The Thai heading for statements *being revised*
    # (`งบการเงินที่อยู่ระหว่างการแก้ไข`) CONTAINS the heading for financial statements
    # (`งบการเงิน`) as a prefix, so probing for the latter first files every amended-statement
    # section under FINANCIAL_STATEMENT. This is the same reason the English chain has always
    # tested revis/amend/order before finan+statement.
    if any(token in lower for token in _SKIP_TOKENS):
        return None, "skipped"  # status-tracking sections, not downloadable disclosures

    if "key financial ratio" in lower or "อัตราส่วน" in lower:
        return DocumentCategory.KEY_FINANCIAL_RATIO, "mapped"
    if "discussion and analysis" in lower or "md&a" in lower or "คำอธิบายและวิเคราะห์" in lower:
        return DocumentCategory.MDA, "mapped"
    if ("finan" in lower and "statement" in lower) or "งบการเงิน" in lower:
        return DocumentCategory.FINANCIAL_STATEMENT, "mapped"
    return None, "unknown"


def category_for_section(heading: str) -> DocumentCategory | None:
    """
    Classify a result-section heading into a DocumentCategory (or None to skip).

    Skips the revision-tracking sections ("… need to be revised", "… ordered to amend", and their
    Thai equivalents). Use :func:`_section_disposition` when you need to tell a deliberate skip
    apart from an unrecognised heading.
    """
    return _section_disposition(heading)[0]


# Result column header (lower-cased) -> SecDocument field. Sections differ: financial
# statements use Name/Year/Status/Type/Period/As Of; MD&A uses Date/Time/Heading/Link; Key
# Financial Ratio REORDERS the columns it shares with financial statements (Year moves from
# position 2 to 5, and Business Type stands where Status does). Matching on the header NAME
# rather than the column index is what makes that reordering a non-event.
#
# The Thai half is an exact MIRROR of the English half: the same fields, no more and no fewer,
# so the same page in either language produces the same document. Terms observed on the English
# pages that map to nothing (Details, Link, Description, Time, Company Name, Order Date,
# Reviewed Financial Statement) are deliberately absent from BOTH halves.
#
# That omission is what resolves `รายละเอียด`, which is one Thai word for three English headers
# -- Details, Link and Description -- and appears TWICE IN ONE HEADER ROW on the ordered-to-amend
# table (Thai `['ชื่อ', 'รายละเอียด', 'รายละเอียด']` against English
# `['Name', 'Description', 'Details']`). A flat dict cannot distinguish those three, but it does
# not have to: all three are unmapped in English, so "no entry" is the right answer in all three
# places. Do not add it.
#
# `Receive Date` was the one gap left by the #123 work: the corpus behind it was FS searches only,
# so the Thai spelling was never observed and a guessed header was refused. It was OBSERVED on
# 2026-09-21 -- `วันที่ได้รับข้อมูล`, in the same column position as the English header on PTT 56-1,
# PTT 56-2 and ADVANC 56-1 -- and is mapped below. Era handling already turns `12/03/2569` into
# `2026-03-12`, which is exactly what the English page yields for the same filing (issue #127 P4).
_HEADER_FIELD_MAP: dict[str, str] = {
    # English
    "name": "company_name",
    "heading": "title",
    "year": "year",
    "status": "status",
    "type": "statement_type",
    "period": "period",
    "as of": "as_of",
    "date": "as_of",
    "receive date": "receive_date",
    "business type": "business_type",
    # Thai -- every pair VERIFIED 5/5 issuer-pairs by column position in the captured corpus
    "ชื่อ": "company_name",
    "หัวข้อข่าว": "title",
    "ประจำปี": "year",
    "ประเภทงบ": "status",
    "ชนิดงบ": "statement_type",
    "งวด": "period",
    "สิ้นสุดวันที่": "as_of",
    "วันที่": "as_of",
    "วันที่ได้รับข้อมูล": "receive_date",
    "ประเภทธุรกิจ": "business_type",
}

# Headers that appear in a MAPPED section, carry no value this model records, and are therefore
# ignored on purpose. Anything outside this set and `_HEADER_FIELD_MAP` is reported (never raised):
# an unmodelled column is "the site has more than we model", not lost data, so it must not be able
# to fail a listing -- but it must not be invisible either, because that is how P4 survived.
#
# Deliberately ABSENT, and not an oversight: `Description`, `Company Name`, `Order Date`,
# `Reviewed Financial Statement`, `ชื่อบริษัท`, `วันที่สั่งการ/ขอผ่อนผัน` and
# `งบการเงินที่ต้องแก้ไข/ขอผ่อนผัน`. Every one of them occurs ONLY in the revision-tracking sections,
# whose rows are skipped before a single cell is read, so they never reach this check. Adding them
# would make the ignore-list look like it covers more than it does.
_IGNORED_HEADERS: frozenset[str] = frozenset(
    {
        "details",
        "รายละเอียด",  # one Thai word for Details/Link/Description -- see the note above
        "link",
        "time",
        "เวลา",
    }
)

# A results row that states the section is empty, in either language. It is not a dropped document:
# the section reports 0 records and this row is the site saying so.
_EMPTY_ROW_MARKERS = ("data not found", "ไม่พบข้อมูล")


def row_to_document(
    row: ReportRow, unique_id: str, *, company_name: str | None = None
) -> SecDocument | None:
    """
    Map one parsed :class:`ReportRow` to a :class:`SecDocument`, or None if it isn't a real
    downloadable row (unknown/skipped section, "Data not found", or no download link).

    Args:
        row: A parsed result-table row.
        unique_id: The uniqueIDReference the search was run for.
        company_name: Fallback issuer name for rows without a 'Name' cell (e.g. MD&A) — the
            listing service passes the resolved company name here.
    """
    category = category_for_section(row["section"])
    if category is None:
        return None

    href = row.get("href")
    file_url, file_id, file_kind = classify_download_href(href)
    if not file_url:
        return None  # e.g. a "Data not found" placeholder row

    headers = [h.lower() for h in row["headers"]]
    cells = row["cells"]
    values: dict[str, str] = {}
    for header, cell in zip(headers, cells, strict=False):
        field = _HEADER_FIELD_MAP.get(header)
        if field:
            values[field] = cell

    resolved_name = values.get("company_name", "").strip() or (company_name or "").strip()

    return SecDocument(
        company_name=resolved_name,
        unique_id=unique_id,
        category=category,
        section=_clean_section(row["section"]),
        title=values.get("title") or None,
        year=parse_year(values.get("year")),
        period=values.get("period") or None,
        statement_type=values.get("statement_type") or None,
        status=values.get("status") or None,
        business_type=values.get("business_type") or None,
        as_of=parse_dmy_date(values.get("as_of")),
        receive_date=parse_dmy_date(values.get("receive_date")),
        file_url=file_url,
        file_id=file_id,
        file_kind=file_kind,
    )


# The three ways a row can produce no document. Named exactly as the RowTally fields they
# increment, so the counter can be picked by name instead of a three-branch if.
_DropReason = Literal["placeholders", "navigation", "no_link"]

# The path fragment of a "display all results" link. A row whose only anchor points there is
# navigation, not a filing -- it is how the site truncates a long section, and counting it as a
# lost document would make every truncated section look like a defect.
_VIEWMORE_PATH_MARKER = "/viewmore/"


def _drop_reason(row: ReportRow, *, reported: int | None) -> _DropReason:
    """Why a row produced no document: 'placeholders', 'navigation' or 'no_link' (a real loss).

    Before this existed the three shared one counter, so the only one that is a defect was
    indistinguishable from the two that are the site working normally.
    """
    href = str(row.get("href") or "").lower()
    if _VIEWMORE_PATH_MARKER in href:
        return "navigation"
    text = " ".join(str(cell) for cell in row["cells"]).strip().lower()
    if not text or reported == 0 or any(marker in text for marker in _EMPTY_ROW_MARKERS):
        return "placeholders"
    return "no_link"


# A listing response is an ASP.NET result panel: a sequence of `card-heading` divs, each with a
# `<table>`. An error page has neither. Measured over every page this repo holds -- 8 committed
# fixtures, 3 listing test constants and a real 104 KB ViewMore capture -- every genuine listing
# body carries at least one of each, INCLUDING the one whose section is genuinely empty (MOTHER's
# Key Financial Ratio, which reports 0 records). The two error-shaped bodies in the evidence, a
# real HTTP 505 page and a capital.sec.or.th indirection page, carry neither.
#
# NOTE it deliberately does NOT key on `ctl00_CPH_pnlControl` alone: the real ViewMore capture has
# that id and the trimmed `FS_VIEWMORE_HTML` test constant does not, so a panel-id rule would call
# a legitimate page an error.
_LISTING_MARKERS = ("card-heading", "<table")


def _require_ok(status_code: int, url: str, code: str) -> None:
    """Raise ``FetchError`` unless the listing response is 2xx (issue #131).

    The listing path used to read ``response.text`` without ever looking at the status, so an
    error page parsed to zero rows and was returned as an empty list -- indistinguishable from an
    issuer with no filings, and worse than a parse bug because it is intermittent.

    Raised as a plain :class:`FetchError`, **not** through ``raise_for_status``: that helper maps
    404 to ``SymbolNotFoundError`` and would consult the symbol suggester, which is wrong here.
    The unique_id was already resolved, so a 404 on this endpoint means the route or the host is
    wrong, not that an issuer does not exist -- the same reasoning that gives the DR-profile and
    analyst-consensus endpoints their own handling (see CLAUDE.md's Known Gotchas).
    """
    if 200 <= status_code < 300:
        return
    message = (
        f"SEC listing request failed: HTTP {status_code} for report code {code!r} "
        f"at {url}. The response was not parsed — an error page yields zero rows, which is "
        f"indistinguishable from an issuer that filed nothing."
    )
    logger.error(message)
    raise FetchError(message, status_code=status_code)


def _require_listing_page(html: str, url: str, code: str) -> None:
    """Raise ``ParseError`` when a 2xx body is not a listing page at all (issue #131).

    The status check above catches the evidenced case (a real HTTP 505). This is the companion for
    an error or interstitial page served with HTTP 200, which no status check can see. It is
    deliberately the weakest rule that separates the two populations, so that a genuinely empty
    listing -- the thing that must never raise -- cannot trip it. See :data:`_LISTING_MARKERS`.
    """
    lowered = html.lower()
    if any(marker in lowered for marker in _LISTING_MARKERS):
        return
    message = (
        f"SEC listing response for report code {code!r} at {url} carries no result table and no "
        f"section heading, so it is not a listing page (HTTP 200 error or interstitial page?). "
        f"Raised rather than returned as an empty list, which would be indistinguishable from an "
        f"issuer that filed nothing."
    )
    logger.error(message)
    raise ParseError(message, url=url, rows_parsed=0)


def _view_more_is_usable(status_code: int, html: str, url: str, code: str) -> bool:
    """Is this "display all results" page fit to replace its section's inline rows?

    Returns False (with a WARNING) instead of raising, so a broken ViewMore page costs the caller
    the *completeness* of one section rather than the whole listing. See the call site for why.
    """
    if not 200 <= status_code < 300:
        logger.warning(
            f"The 'display all results' page for report code {code!r} at {url} answered HTTP "
            f"{status_code}. Keeping the truncated inline rows for that section instead of "
            f"replacing them; `completeness()` will show the shortfall."
        )
        return False
    lowered = html.lower()
    if not any(marker in lowered for marker in _LISTING_MARKERS):
        logger.warning(
            f"The 'display all results' page for report code {code!r} at {url} is not a listing "
            f"page (no result table, no section heading). Keeping the truncated inline rows for "
            f"that section; `completeness()` will show the shortfall."
        )
        return False
    return True


# ViewMore slug -> the category whose complete list that page holds.
@dataclass
class _MapResult:
    """What one results page yielded, and why the rest of it did not.

    The legacy scalars (``rows`` / ``skipped`` / ``no_href`` / ``unknown_sections``) are views onto
    :attr:`accounting`, so there is one set of numbers rather than two that can drift apart.
    """

    documents: list[SecDocument] = field(default_factory=list)
    accounting: ListingAccounting = field(default_factory=ListingAccounting)
    reported_counts: dict[str, int] = field(default_factory=dict)

    @property
    def rows(self) -> int:
        """Data rows parsed from the page."""
        return self.accounting.rows

    @property
    def skipped(self) -> int:
        """Rows in revision-tracking sections — dropped on purpose."""
        return self.accounting.skipped

    @property
    def no_href(self) -> int:
        """Rows that produced no document for want of a usable download link.

        The sum of the three reasons, kept as one number for continuity. Branch on
        ``accounting.no_link`` instead: this one is non-zero on perfectly healthy pages.
        """
        acc = self.accounting
        return acc.placeholders + acc.navigation + acc.no_link

    @property
    def unknown_sections(self) -> list[str]:
        """Section headings that could not be classified."""
        return self.accounting.unknown_sections


def _map_rows(
    rows: Sequence[ReportRow],
    unique_id: str,
    *,
    company_name: str | None,
    source: str,
    wanted: set[DocumentCategory] | None = None,
) -> _MapResult:
    """Map parsed rows to documents, account for every drop, and escalate a total loss.

    The accounting exists because a row used to vanish three different ways behind one ``None``: a
    section we skip deliberately, a placeholder row with no download link, and a heading we do
    not recognise at all. Only the third is a defect, and it was indistinguishable from the other
    two -- and from an issuer with no filings. ``no_href`` is now split again, because the "no
    download link" bucket was itself three things (see :func:`_drop_reason`).

    ``wanted`` scopes the escalation to the categories the caller asked for; ``None`` means all. A
    single "FS" search returns three sections, so without it a loss in a section that was filtered
    out on request would raise for a caller who never wanted it.
    """
    if not rows:
        # Reachable only for a body that looked like a listing and yielded no data row at all.
        # Within this package that cannot be a real listing: every captured page — including the
        # ones whose sections are empty — carries at least the revision-tracking placeholder row.
        # Returning [] here is the exact silent loss of issue #131, one layer below the transport.
        message = (
            f"No result rows were parsed from {source}. A SEC listing always carries at least one "
            f"row, including the placeholder an empty section serves, so this body is not a "
            f"listing — raised rather than returned as an empty list."
        )
        logger.error(message)
        raise ParseError(message, url=source, rows_parsed=0)

    result = _MapResult()
    accounting = result.accounting
    accounting.rows = len(rows)
    unknown: dict[str, None] = {}  # ordered set
    unmapped: dict[str, None] = {}
    unverifiable: dict[str, None] = {}
    for row in rows:
        heading = str(row["section"])
        category, disposition = _section_disposition(heading)
        text, count = split_section_count(heading)
        if count is not None and category is not None:
            result.reported_counts[category.value] = count
        if disposition == "skipped":
            accounting.skipped += 1
            continue
        if disposition == "unknown":
            unknown.setdefault(text, None)
            accounting.unknown_rows += 1
            continue
        if category is None:  # unreachable: 'mapped' always carries a category
            accounting.unknown_rows += 1  # ...but still account for the row if it ever happens
            continue
        tally = accounting.by_category.setdefault(category.value, RowTally())
        tally.rows += 1
        # Column coverage, for READ sections only. A header inside a revision-tracking section is
        # never consulted, so reporting it would be noise -- see the note on _IGNORED_HEADERS.
        for header in row["headers"]:
            name = str(header).strip()
            key = name.lower()
            if key and key not in _HEADER_FIELD_MAP and key not in _IGNORED_HEADERS:
                unmapped.setdefault(name, None)
        if count is None:
            unverifiable.setdefault(text, None)
        document = row_to_document(row, unique_id, company_name=company_name)
        if document is None:
            reason = _drop_reason(row, reported=count)
            setattr(tally, reason, getattr(tally, reason) + 1)
            continue
        tally.documents += 1
        result.documents.append(document)

    accounting.unknown_sections = list(unknown)
    accounting.unmapped_headers = list(unmapped)
    accounting.unverifiable_sections = list(unverifiable)
    logger.debug(
        f"Parsed {accounting.rows} row(s) from {source}: {len(result.documents)} mapped, "
        f"{accounting.skipped} skipped (revision-tracking), {accounting.placeholders} placeholder, "
        f"{accounting.navigation} navigation, {accounting.no_link} without a download link, "
        f"{len(accounting.unknown_sections)} unrecognised section(s)"
    )

    if accounting.unknown_sections:
        listed = ", ".join(repr(h) for h in accounting.unknown_sections)
        if not result.documents:
            message = (
                f"{accounting.rows} row(s) parsed from {source} but NONE could be classified; "
                f"unrecognised section heading(s): {listed}. The page structure or its language "
                f"may have changed. This is raised rather than returned as an empty list because "
                f"an empty list is indistinguishable from an issuer with no filings."
            )
            logger.error(message)
            raise ParseError(
                message,
                url=source,
                rows_parsed=accounting.rows,
                unknown_sections=accounting.unknown_sections,
            )
        logger.warning(
            f"{len(accounting.unknown_sections)} unrecognised section heading(s) in {source} were "
            f"dropped: {listed}. {len(result.documents)} document(s) from the recognised sections "
            f"were kept."
        )

    _escalate_losses(accounting, result.reported_counts, source=source, wanted=wanted)
    return result


def _escalate_losses(
    accounting: ListingAccounting,
    reported_counts: dict[str, int],
    *,
    source: str,
    wanted: set[DocumentCategory] | None,
) -> None:
    """Raise on a total loss, warn on a partial one, and name every column we did not understand.

    The severity ladder is the one the unrecognised-heading check already uses, for the same
    reason: an empty result is the case a caller cannot diagnose, a partial result is one they can
    act on once the loss is named. Raising on a single lost row would turn one bad row in a long
    listing into no listing at all.
    """
    in_scope = (
        accounting.by_category
        if wanted is None
        else {k: v for k, v in accounting.by_category.items() if k in {c.value for c in wanted}}
    )
    lost = sum(tally.no_link for tally in in_scope.values())
    kept = sum(tally.documents for tally in in_scope.values())
    if lost:
        sections = ", ".join(
            f"{name} ({tally.no_link} of {tally.rows})"
            for name, tally in in_scope.items()
            if tally.no_link
        )
        if not kept:
            message = (
                f"{accounting.rows} row(s) parsed from {source} and every usable one was dropped "
                f"for want of a download link: {sections}. The site reports "
                f"{reported_counts or 'no'} record(s) for these sections, so this is a loss, not "
                f"an empty result — raised rather than returned as an empty list because the two "
                f"are otherwise indistinguishable."
            )
            logger.error(message)
            raise IncompleteListingError(
                message,
                url=source,
                rows_parsed=accounting.rows,
                lost_rows=lost,
                reported=reported_counts,
            )
        logger.warning(
            f"{lost} row(s) in {source} carried no download link and were dropped: {sections}. "
            f"{kept} document(s) were kept — see `accounting.no_link` on the returned list."
        )

    if accounting.unmapped_headers:
        logger.warning(
            f"{len(accounting.unmapped_headers)} column header(s) in {source} map to no field and "
            f"are not on the ignore-list: "
            f"{', '.join(repr(h) for h in accounting.unmapped_headers)}. Any value in those "
            f"columns is dropped; the site may have added a column."
        )
    if accounting.unverifiable_sections:
        logger.warning(
            f"{len(accounting.unverifiable_sections)} section(s) in {source} carry no record-count "
            f"marker, so completeness cannot be checked for them: "
            f"{', '.join(repr(h) for h in accounting.unverifiable_sections)}."
        )


# Every slug the site serves a "display all results" page under. The `fs-` prefix is the site's,
# not a category hint: `fs-r561` and `fs-r562` belong to the 56-1 / 56-2 searches, not to the FS
# one. Live-probed 2026-09-20 across CPALL/PTT/SCB in both languages.
#
# The last two were MISSING until 0.22.2, so a 56-1 or 56-2 section over the ~10-row inline cap
# was truncated even with `follow_view_more=True`. 0.22.0's notes predicted exactly this and said
# the shortfall WARNING would surface it; it did, from a downstream consumer reading
# `completeness()`. Scale, with a 2000-2026 window: CPALL Thai 56-1 served 11 of 23, PTT Thai 56-1
# 11 of 25, PTT 56-2 10 of 15 in BOTH languages -- so this was never a Thai-only gap.
_CATEGORY_FOR_VIEWMORE_SLUG: dict[str, DocumentCategory] = {
    "fs-norm": DocumentCategory.FINANCIAL_STATEMENT,
    "fs-kf": DocumentCategory.KEY_FINANCIAL_RATIO,
    "fs-mda": DocumentCategory.MDA,
    "fs-r561": DocumentCategory.FORM_56_1,
    "fs-r562": DocumentCategory.FORM_56_2,
}

_VIEWMORE_HREF = re.compile(r'href="([^"]*?/ViewMore/([a-z0-9-]+)[^"]*)"', re.IGNORECASE)


def _normalize_categories(
    types: list[DocumentCategory | str] | DocumentCategory | str | None,
) -> list[DocumentCategory]:
    """Coerce the ``types`` argument into a de-duplicated list of DocumentCategory (all if None)."""
    if types is None:
        return list(DocumentCategory)
    if isinstance(types, (DocumentCategory, str)):
        types = [types]
    out: list[DocumentCategory] = []
    for t in types:
        cat = t if isinstance(t, DocumentCategory) else DocumentCategory(t)
        if cat not in out:
            out.append(cat)
    return out


def _format_sec_date(value: date | str | None, param_name: str) -> str:
    """Format a from/to date into the form's dd/MM/yyyy wire value ('' when None)."""
    if value is None:
        return ""
    if isinstance(value, date):  # datetime subclasses date
        return value.strftime(SEC_FORM_DATE_FORMAT)
    text = value.strip()
    if not text:
        return ""
    try:
        datetime.strptime(text, SEC_FORM_DATE_FORMAT)
    except ValueError as exc:
        error_msg = (
            f"Invalid {param_name} '{value}': expected dd/mm/yyyy (e.g. '31/12/2025') or a "
            f"datetime.date/datetime object."
        )
        logger.error(error_msg)
        raise InvalidDateError(error_msg) from exc
    return text


def _log_listing_summary(
    listing: SecDocumentList, *, unique_id: str, follow_view_more: bool
) -> None:
    """Emit the caller-facing summary, derived from the accounting rather than from ``len()``.

    This is where :meth:`SecDocumentList.completeness` finally gets an internal caller. The
    cross-check existed from 0.21.0 and nothing in the package ran it, so the one line an operator
    actually sees said "Listed 0 SEC document(s)" in the same words, at the same level, as a
    complete success.

    Two different shortfalls are deliberately given two different levels. With
    ``follow_view_more=False`` a section truncated behind "display all results" is *expected* to
    fall short of the site's number -- warning about what the caller asked for trains people to
    ignore warnings. With ``follow_view_more=True`` the ViewMore page holds the complete list, so a
    residual shortfall has nothing left to explain it and is worth a warning.
    """
    accounting = listing.accounting
    total_reported = sum(listing.reported_counts.values())
    short = {k: v for k, v in listing.completeness().items() if v[0] < v[1]}
    head = f"Listed {len(listing)} SEC document(s) for uid={unique_id}"

    if accounting.has_losses:
        logger.warning(
            f"{head}, but the parse was not clean: {accounting.no_link} row(s) lost to a missing "
            f"download link, {len(accounting.unknown_sections)} unrecognised section(s), "
            f"{len(accounting.unmapped_headers)} unmapped column(s). The site reports "
            f"{total_reported} record(s). Inspect `.accounting` on the returned list."
        )
        return
    if short and follow_view_more:
        logger.warning(
            f"{head} of {total_reported} the site reports; short in {sorted(short)} even after "
            f"following the 'display all results' pages, which should have returned each section "
            f"in full. Compare `.completeness()` on the returned list."
        )
        return
    if short:
        logger.info(
            f"{head} of {total_reported} the site reports; {sorted(short)} truncated because "
            f"follow_view_more=False. Pass follow_view_more=True for the complete sections."
        )
        return
    logger.info(f"{head} (the site reports {total_reported})")


class FinancialReportService:
    """
    List downloadable SEC disclosure documents for an issuer.

    Replays the ASP.NET WebForms search (GET fresh VIEWSTATE tokens → form POST), parses the
    result tables into :class:`SecDocument` models, and (by default) follows the "display all
    results" ViewMore pages so large sections are returned in full. Stateless host — no
    SessionManager (``use_session`` is forced off).
    """

    def __init__(self, config: FetcherConfig | None = None) -> None:
        base = config or FetcherConfig()
        self.config = base.model_copy(update={"use_session": False})
        logger.info("FinancialReportService initialized (host=market.sec.or.th)")

    async def fetch_documents(
        self,
        unique_id: str,
        *,
        company_name: str | None = None,
        types: list[DocumentCategory | str] | DocumentCategory | str | None = None,
        from_date: date | str | None = None,
        to_date: date | str | None = None,
        lang: Language = "en",
        follow_view_more: bool = True,
    ) -> SecDocumentList:
        """
        List documents for a resolved ``unique_id`` (10-digit SEC uniqueIDReference).

        Args:
            unique_id: The issuer's SEC uniqueIDReference (see ``resolve_company``).
            company_name: Issuer name used as a fallback for rows lacking a Name cell (MD&A).
            types: One or more :class:`DocumentCategory` (or their string values); None = all 5.
            from_date / to_date: Window bounds — ``date``/``datetime`` or dd/mm/yyyy string.
                Pass a **wide** window to see the full year history — without dates the SEC form
                returns only a recent window.
            lang: 'en' or 'th'.
            follow_view_more: Follow ViewMore pages so truncated sections are returned in full.

        Returns:
            A :class:`SecDocumentList` (a ``list[SecDocument]`` with ``years_by_category()`` /
            ``available_years()`` / ``filter()`` / ``summary()`` helpers).
        """
        lang = normalize_language(lang)
        categories = _normalize_categories(types)
        date_from = _format_sec_date(from_date, "from_date")
        date_to = _format_sec_date(to_date, "to_date")

        # Minimal set of ddlReportType codes covering the requested categories.
        codes = list(dict.fromkeys(CATEGORY_TO_REPORT_TYPE[c] for c in categories))
        wanted = set(categories)

        async with AsyncDataFetcher(config=self.config) as fetcher:
            results = await asyncio.gather(
                *(
                    self._search_code(
                        fetcher,
                        code,
                        unique_id,
                        company_name,
                        date_from,
                        date_to,
                        lang,
                        follow_view_more,
                        wanted,
                    )
                    for code in codes
                )
            )
        docs = [d for group, _, _ in results for d in group]
        reported: dict[str, int] = {}
        accounting = ListingAccounting()
        for _, counts, part in results:
            reported.update(counts)
            accounting.absorb(part)
        listing = SecDocumentList(docs, reported_counts=reported, accounting=accounting)
        _log_listing_summary(listing, unique_id=unique_id, follow_view_more=follow_view_more)
        return listing

    async def fetch_documents_raw(
        self,
        unique_id: str,
        *,
        code: str,
        from_date: date | str | None = None,
        to_date: date | str | None = None,
        lang: Language = "en",
    ) -> list[dict[str, object]]:
        """
        Escape hatch: return the raw parsed result rows (section/headers/cells/href dicts) for a
        single ddlReportType ``code`` ('FS'/'R561'/'R562'/'KFR'), without model mapping.
        """
        lang = normalize_language(lang)
        date_from = _format_sec_date(from_date, "from_date")
        date_to = _format_sec_date(to_date, "to_date")
        async with AsyncDataFetcher(config=self.config) as fetcher:
            html, _ = await self._run_search(
                fetcher, code, unique_id, None, date_from, date_to, lang
            )
        return [dict(r) for r in parse_report_tables(html)]

    async def _run_search(
        self,
        fetcher: AsyncDataFetcher,
        code: str,
        unique_id: str,
        company_name: str | None,
        date_from: str,
        date_to: str,
        lang: Language,
    ) -> tuple[str, str]:
        """GET fresh tokens then POST the search form; return (result HTML, the URL used)."""
        report_url = (
            f"{SEC_BASE_URL}{SEC_FINANCIAL_REPORT_ENDPOINT.format(lang=lang, report_type=code)}"
        )
        get_resp = await fetcher.fetch(report_url, headers=build_sec_headers(referer=SEC_REFERER))
        # This leg was already guarded by accident: an error page carries no __VIEWSTATE, so the
        # check below fired. It reported the wrong cause, though — "the page structure may have
        # changed" for what was really an HTTP 500 — so the status is now read first.
        _require_ok(get_resp.status_code, report_url, code)
        tokens = extract_aspnet_tokens(get_resp.text)
        if not tokens.get("__VIEWSTATE"):
            raise FetchError(
                "SEC search page returned no __VIEWSTATE token — the page structure may have "
                "changed, or the request was blocked."
            )
        form = {
            **tokens,
            SEC_FORM_FIELD_REPORT_TYPE: code,
            SEC_FORM_FIELD_COMPANY: company_name or "",
            SEC_FORM_FIELD_COMPANY_TEXT: company_name or "",
            SEC_FORM_FIELD_COMPANY_VALUE: unique_id,
            SEC_FORM_FIELD_DATE_FROM: date_from,
            SEC_FORM_FIELD_DATE_TO: date_to,
            SEC_FORM_FIELD_SEARCH: "Search",
        }
        post_resp = await fetcher.fetch(
            report_url,
            headers=build_sec_headers(referer=report_url, origin=True),
            method="POST",
            data=form,
        )
        _require_ok(post_resp.status_code, report_url, code)
        return post_resp.text, report_url

    async def _search_code(
        self,
        fetcher: AsyncDataFetcher,
        code: str,
        unique_id: str,
        company_name: str | None,
        date_from: str,
        date_to: str,
        lang: Language,
        follow_view_more: bool,
        wanted: set[DocumentCategory],
    ) -> tuple[list[SecDocument], dict[str, int], ListingAccounting]:
        """Run one search code, map rows, and (optionally) complete sections via ViewMore."""
        html, url = await self._run_search(
            fetcher, code, unique_id, company_name, date_from, date_to, lang
        )
        wanted_values = {c.value for c in wanted}
        _require_listing_page(html, url, code)
        mapped = _map_rows(
            parse_report_tables(html),
            unique_id,
            company_name=company_name,
            source=url,
            wanted=wanted,
        )
        accounting = mapped.accounting
        # Only for the categories the caller asked for. A single "FS" search returns the
        # financial-statement, Key Financial Ratio and MD&A sections together, so without this
        # `completeness()` would report 0-of-2 for sections that were filtered out on request --
        # a shortfall that is pure noise, in the one place meant to make a real shortfall visible.
        reported = {k: v for k, v in mapped.reported_counts.items() if k in wanted_values}
        inline = [d for d in mapped.documents if d.category in wanted]
        if not follow_view_more:
            return inline, reported, accounting

        # Follow each ViewMore link whose category is wanted; its page holds the COMPLETE list
        # for that section, so it replaces the truncated inline rows for that category.
        replacements: dict[DocumentCategory, list[SecDocument]] = {}
        seen_slugs: set[str] = set()
        vm_targets: list[tuple[DocumentCategory, str]] = []
        for href, slug in _VIEWMORE_HREF.findall(html):
            slug = slug.lower()
            cat = _CATEGORY_FOR_VIEWMORE_SLUG.get(slug)
            if cat is None or cat not in wanted or slug in seen_slugs:
                continue
            seen_slugs.add(slug)
            vm_targets.append((cat, urljoin(SEC_BASE_URL, unescape(href))))

        if vm_targets:
            pages = await asyncio.gather(
                *(
                    fetcher.fetch(url, headers=build_sec_headers(referer=SEC_REFERER))
                    for _, url in vm_targets
                )
            )
            for (cat, url), page in zip(vm_targets, pages, strict=True):
                # A ViewMore page holds the COMPLETE list for its section and REPLACES the inline
                # rows, so an unusable one here does not merely add nothing -- on 0.22.0 it
                # silently deleted the whole section, the inline rows included.
                #
                # It is DEGRADED rather than raised, which is the same severity ladder the rest of
                # this module uses: a failed ViewMore is a PARTIAL loss, because the truncated
                # inline rows are still a real answer -- exactly the one `follow_view_more=False`
                # would have given. Skipping the replacement keeps them, and the shortfall then
                # shows up on its own through `completeness()` and the WARNING in
                # `_log_listing_summary`, which already treats "short even after following the
                # view-more pages" as the case worth warning about.
                #
                # This is not hypothetical: on 2026-09-20 the live Thai `fs-kf` page answered
                # HTTP 500 on every attempt while the other five slug/language pairs answered 200.
                if not _view_more_is_usable(page.status_code, page.text, url, code):
                    continue
                vm = _map_rows(
                    parse_report_tables(page.text),
                    unique_id,
                    company_name=company_name,
                    source=url,
                    wanted=wanted,
                )
                reported.update({k: v for k, v in vm.reported_counts.items() if k in wanted_values})
                replacements[cat] = [d for d in vm.documents if d.category == cat]
                # The ViewMore page holds the COMPLETE list for this section, so it replaces
                # the truncated inline rows -- in the accounting too, or they double-count.
                accounting.supersede(cat.value, vm.accounting)

        result = [d for d in inline if d.category not in replacements]
        for docs in replacements.values():
            result.extend(docs)
        return result, reported, accounting


async def get_sec_documents(
    query: str,
    *,
    types: list[DocumentCategory | str] | DocumentCategory | str | None = None,
    from_date: date | str | None = None,
    to_date: date | str | None = None,
    lang: Language = "en",
    follow_view_more: bool = True,
    config: FetcherConfig | None = None,
) -> SecDocumentList:
    """
    Convenience: resolve a symbol/name and list its SEC disclosure documents (all 5 categories
    by default). This is the flat, one-call entry point (LLM tool-calling friendly).

    Args:
        query: Symbol or company name (e.g. "CPALL").
        types: One or more :class:`DocumentCategory` (or string values); None = all.
        from_date / to_date: Window bounds — ``date``/``datetime`` or dd/mm/yyyy string. Pass a
            **wide** window to see the full year history (default returns only a recent window).
        lang: 'en' or 'th'.
        follow_view_more: Follow ViewMore pages for complete large sections.
        config: Optional fetcher configuration.

    Returns:
        A :class:`SecDocumentList` (a list with ``years_by_category()`` / ``available_years()`` /
        ``filter()`` / ``summary()`` helpers); empty if the company cannot be resolved.
    """
    company = await resolve_company(query, lang, config=config)
    if company is None:
        logger.warning(f"No SEC company matched query={query!r}; returning no documents")
        return SecDocumentList()
    service = FinancialReportService(config=config)
    return await service.fetch_documents(
        company.unique_id,
        company_name=company.company_name,
        types=types,
        from_date=from_date,
        to_date=to_date,
        lang=lang,
        follow_view_more=follow_view_more,
    )
