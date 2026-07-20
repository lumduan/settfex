"""SEC financial-report document models and the HTML-row → model mapper.

The listing service (added on top of this module) replays the SEC search and turns each parsed
result-table row into a :class:`SecDocument`. Models + mapping live here; the service that does
the HTTP orchestration is appended below (see ``FinancialReportService``).
"""

from __future__ import annotations

import asyncio
import re
from datetime import date, datetime
from enum import Enum
from html import unescape
from urllib.parse import urljoin

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from settfex.exceptions import InvalidDateError
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
    parse_int,
    parse_report_tables,
)
from settfex.services.set.stock.utils import Language, normalize_language
from settfex.utils.data_fetcher import AsyncDataFetcher, FetcherConfig


class DocumentCategory(str, Enum):
    """The five disclosure-document categories exposed by the SEC IDISC search."""

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


_COUNT_SUFFIX = re.compile(r"\s*\(\s*[\d,]+\s*record\(s\)\s*found\s*\)\s*$", re.IGNORECASE)


def _clean_section(heading: str) -> str:
    """Strip the '( N record(s) found )' suffix from a section heading."""
    return _COUNT_SUFFIX.sub("", heading).strip()


def category_for_section(heading: str) -> DocumentCategory | None:
    """
    Classify a result-section heading into a DocumentCategory (or None to skip).

    Skips the revision-tracking sections ("… need to be revised", "… ordered to amend").
    Tolerant of the site's "Finanacial" misspelling.
    """
    lower = heading.lower()
    if "56-1" in lower:
        return DocumentCategory.FORM_56_1
    if "56-2" in lower:
        return DocumentCategory.FORM_56_2
    if "revis" in lower or "amend" in lower or "order" in lower:
        return None  # status-tracking sections, not downloadable disclosures
    if "key financial ratio" in lower:
        return DocumentCategory.KEY_FINANCIAL_RATIO
    if "discussion and analysis" in lower or "md&a" in lower:
        return DocumentCategory.MDA
    if "finan" in lower and "statement" in lower:
        return DocumentCategory.FINANCIAL_STATEMENT
    return None


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
        year=parse_int(values.get("year")),
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
    ) -> list[SecDocument]:
        """
        List documents for a resolved ``unique_id`` (10-digit SEC uniqueIDReference).

        Args:
            unique_id: The issuer's SEC uniqueIDReference (see ``resolve_company``).
            company_name: Issuer name used as a fallback for rows lacking a Name cell (MD&A).
            types: One or more :class:`DocumentCategory` (or their string values); None = all 5.
            from_date / to_date: Window bounds — ``date``/``datetime`` or dd/mm/yyyy string.
            lang: 'en' or 'th'.
            follow_view_more: Follow ViewMore pages so truncated sections are returned in full.

        Returns:
            List of :class:`SecDocument` for the requested categories.
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
                        fetcher, code, unique_id, company_name, date_from, date_to,
                        lang, follow_view_more, wanted,
                    )
                    for code in codes
                )
            )
        docs = [d for group in results for d in group]
        logger.info(f"Listed {len(docs)} SEC document(s) for uid={unique_id}")
        return docs

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
            html = await self._run_search(
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
    ) -> str:
        """GET fresh tokens then POST the search form; return the result HTML."""
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
        return post_resp.text

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
    ) -> list[SecDocument]:
        """Run one search code, map rows, and (optionally) complete sections via ViewMore."""
        html = await self._run_search(
            fetcher, code, unique_id, company_name, date_from, date_to, lang
        )
        inline = [
            d
            for r in parse_report_tables(html)
            if (d := row_to_document(r, unique_id, company_name=company_name))
            and d.category in wanted
        ]
        if not follow_view_more:
            return inline

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
                *(fetcher.fetch(url, headers=build_sec_headers(referer=SEC_REFERER))
                  for _, url in vm_targets)
            )
            for (cat, _), page in zip(vm_targets, pages, strict=True):
                replacements[cat] = [
                    d
                    for r in parse_report_tables(page.text)
                    if (d := row_to_document(r, unique_id, company_name=company_name))
                    and d.category == cat
                ]

        result = [d for d in inline if d.category not in replacements]
        for docs in replacements.values():
            result.extend(docs)
        return result


async def get_sec_documents(
    query: str,
    *,
    types: list[DocumentCategory | str] | DocumentCategory | str | None = None,
    from_date: date | str | None = None,
    to_date: date | str | None = None,
    lang: Language = "en",
    follow_view_more: bool = True,
    config: FetcherConfig | None = None,
) -> list[SecDocument]:
    """
    Convenience: resolve a symbol/name and list its SEC disclosure documents (all 5 categories
    by default). This is the flat, one-call entry point (LLM tool-calling friendly).

    Args:
        query: Symbol or company name (e.g. "CPALL").
        types: One or more :class:`DocumentCategory` (or string values); None = all.
        from_date / to_date: Window bounds — ``date``/``datetime`` or dd/mm/yyyy string.
        lang: 'en' or 'th'.
        follow_view_more: Follow ViewMore pages for complete large sections.
        config: Optional fetcher configuration.

    Returns:
        List of :class:`SecDocument` (empty if the company cannot be resolved).
    """
    company = await resolve_company(query, lang, config=config)
    if company is None:
        logger.warning(f"No SEC company matched query={query!r}; returning no documents")
        return []
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
