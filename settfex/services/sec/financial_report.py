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
from pydantic import BaseModel, ConfigDict, Field

from settfex.exceptions import InvalidDateError, ParseError
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
    ) -> None:
        super().__init__(iterable)
        self.reported_counts: dict[str, int] = dict(reported_counts or {})
        """How many records the site said each section holds, keyed by category value.

        This describes the **sections the search returned**, not this list's contents, and it
        stays true after filtering — which is the point: you compare what you have against what
        the site said existed. See :meth:`completeness`.
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
# statements use Name/Year/Status/Type/Period/As Of; MD&A uses Date/Time/Heading/Link.
_HEADER_FIELD_MAP: dict[str, str] = {
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
}


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


# ViewMore slug -> the category whose complete list that page holds.
@dataclass
class _MapResult:
    """What one results page yielded, and why the rest of it did not."""

    documents: list[SecDocument] = field(default_factory=list)
    rows: int = 0
    skipped: int = 0  # revision-tracking sections -- dropped on purpose
    no_href: int = 0  # "Data not found" placeholders and rows without a download link
    unknown_sections: list[str] = field(default_factory=list)
    reported_counts: dict[str, int] = field(default_factory=dict)


def _map_rows(
    rows: Sequence[ReportRow],
    unique_id: str,
    *,
    company_name: str | None,
    source: str,
) -> _MapResult:
    """Map parsed rows to documents, tallying every drop, and escalate an all-unknown page.

    The tally exists because a row used to vanish three different ways behind one ``None``: a
    section we skip deliberately, a placeholder row with no download link, and a heading we do
    not recognise at all. Only the third is a defect, and it was indistinguishable from the other
    two -- and from an issuer with no filings.
    """
    result = _MapResult(rows=len(rows))
    unknown: dict[str, None] = {}  # ordered set
    for row in rows:
        heading = str(row["section"])
        category, disposition = _section_disposition(heading)
        text, count = split_section_count(heading)
        if count is not None and category is not None:
            result.reported_counts[category.value] = count
        if disposition == "skipped":
            result.skipped += 1
            continue
        if disposition == "unknown":
            unknown.setdefault(text, None)
            continue
        document = row_to_document(row, unique_id, company_name=company_name)
        if document is None:
            result.no_href += 1
            continue
        result.documents.append(document)

    result.unknown_sections = list(unknown)
    logger.debug(
        f"Parsed {result.rows} row(s) from {source}: {len(result.documents)} mapped, "
        f"{result.skipped} skipped (revision-tracking), {result.no_href} without a download "
        f"link, {len(result.unknown_sections)} unrecognised section(s)"
    )

    if result.unknown_sections:
        listed = ", ".join(repr(h) for h in result.unknown_sections)
        if not result.documents:
            message = (
                f"{result.rows} row(s) parsed from {source} but NONE could be classified; "
                f"unrecognised section heading(s): {listed}. The page structure or its language "
                f"may have changed. This is raised rather than returned as an empty list because "
                f"an empty list is indistinguishable from an issuer with no filings."
            )
            logger.error(message)
            raise ParseError(
                message,
                url=source,
                rows_parsed=result.rows,
                unknown_sections=result.unknown_sections,
            )
        logger.warning(
            f"{len(result.unknown_sections)} unrecognised section heading(s) in {source} were "
            f"dropped: {listed}. {len(result.documents)} document(s) from the recognised sections "
            f"were kept."
        )
    return result


_CATEGORY_FOR_VIEWMORE_SLUG: dict[str, DocumentCategory] = {
    "fs-norm": DocumentCategory.FINANCIAL_STATEMENT,
    "fs-kf": DocumentCategory.KEY_FINANCIAL_RATIO,
    "fs-mda": DocumentCategory.MDA,
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
        docs = [d for group, _ in results for d in group]
        reported: dict[str, int] = {}
        for _, counts in results:
            reported.update(counts)
        logger.info(f"Listed {len(docs)} SEC document(s) for uid={unique_id}")
        return SecDocumentList(docs, reported_counts=reported)

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
        tokens = extract_aspnet_tokens(get_resp.text)
        if not tokens.get("__VIEWSTATE"):
            from settfex.exceptions import FetchError

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
    ) -> tuple[list[SecDocument], dict[str, int]]:
        """Run one search code, map rows, and (optionally) complete sections via ViewMore."""
        html, url = await self._run_search(
            fetcher, code, unique_id, company_name, date_from, date_to, lang
        )
        mapped = _map_rows(
            parse_report_tables(html), unique_id, company_name=company_name, source=url
        )
        reported = dict(mapped.reported_counts)
        inline = [d for d in mapped.documents if d.category in wanted]
        if not follow_view_more:
            return inline, reported

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
                vm = _map_rows(
                    parse_report_tables(page.text),
                    unique_id,
                    company_name=company_name,
                    source=url,
                )
                reported.update(vm.reported_counts)
                replacements[cat] = [d for d in vm.documents if d.category == cat]

        result = [d for d in inline if d.category not in replacements]
        for docs in replacements.values():
            result.extend(docs)
        return result, reported


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
