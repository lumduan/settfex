"""Tests for SEC financial-report models, the row->document mapper, and the listing service."""

from datetime import date

import pytest

from settfex.exceptions import InvalidDateError
from settfex.services.sec.company import CompanyMatch
from settfex.services.sec.financial_report import (
    DocumentCategory,
    FinancialReportService,
    SecDocument,
    SecDocumentList,
    _format_sec_date,
    _normalize_categories,
    category_for_section,
    get_sec_documents,
    row_to_document,
)
from settfex.services.sec.utils import ReportRow, parse_report_tables
from settfex.utils.data_fetcher import FetchResponse
from tests.services.sec.fixtures import (
    FORM_56_1_HTML,
    FORM_56_2_HTML,
    FS_SEARCH_HTML,
    FS_TRUNCATED_HTML,
    FS_VIEWMORE_HTML,
    REPORT_PAGE_HTML,
)


def _resp(text: str, *, status: int = 200) -> FetchResponse:
    return FetchResponse(
        status_code=status,
        content=text.encode("utf-8"),
        text=text,
        headers={},
        url="https://market.sec.or.th/",
        elapsed=0.01,
    )


def _make_fetcher(mock_cls, router):
    """Wire a patched AsyncDataFetcher class mock so .fetch() dispatches through ``router``."""
    from unittest.mock import AsyncMock

    instance = AsyncMock()
    instance.fetch.side_effect = router
    mock_cls.return_value.__aenter__.return_value = instance
    mock_cls.return_value.__aexit__.return_value = None
    return instance


class TestCategoryForSection:
    def test_maps_known_sections(self) -> None:
        assert category_for_section("Finanacial Statements ( 5 record(s) found)") == (
            DocumentCategory.FINANCIAL_STATEMENT
        )
        assert category_for_section("Key Financial Ratio ( 1 )") == (
            DocumentCategory.KEY_FINANCIAL_RATIO
        )
        assert category_for_section("Management's Discussion and Analysis ( 2 )") == (
            DocumentCategory.MDA
        )
        assert category_for_section("Form 56-1 : Annual Registration Statements") == (
            DocumentCategory.FORM_56_1
        )
        assert category_for_section("Form 56-2 : Annual Reports") == DocumentCategory.FORM_56_2

    def test_skips_revision_sections(self) -> None:
        assert category_for_section("The Financial Statements which need to be revised") is None
        assert category_for_section("SEC has ordered to amend Finanacial Statements") is None


class TestRowToDocument:
    def test_financial_statement_row(self) -> None:
        rows = parse_report_tables(FS_SEARCH_HTML)
        fs = next(
            d
            for r in rows
            if (d := row_to_document(r, "0000003875"))
            and d.category == DocumentCategory.FINANCIAL_STATEMENT
        )
        assert fs.year == 2026 and fs.statement_type == "Company" and fs.period == "Q1"
        assert fs.status == "Reviewed" and fs.as_of == date(2026, 3, 31)
        assert fs.file_kind == "zip" and fs.file_id == "dat/news/202605/0737FIN.zip"

    def test_mda_row_uses_company_fallback_and_title(self) -> None:
        rows = parse_report_tables(FS_SEARCH_HTML)
        mda = next(
            d
            for r in rows
            if (d := row_to_document(r, "0000003875", company_name="CP ALL"))
            and d.category == DocumentCategory.MDA
        )
        assert mda.company_name == "CP ALL"  # MD&A rows have no Name column -> fallback
        assert mda.title and "Discussion" in mda.title
        assert mda.file_kind == "pdf"

    def test_ipos_row_maps_file_id(self) -> None:
        rows = parse_report_tables(FS_SEARCH_HTML)
        ipos = next(
            d
            for r in rows
            if (d := row_to_document(r, "u")) and d.file_id and d.file_id.startswith("ipos:")
        )
        assert ipos.file_id == "ipos:726416"

    def test_data_not_found_row_returns_none(self) -> None:
        row = ReportRow(
            section="Finanacial Statements ( 0 record(s) found)",
            headers=["Name", "Year"],
            cells=["Data not found"],
            href=None,
        )
        assert row_to_document(row, "u") is None


class TestNormalizeCategories:
    def test_none_returns_all(self) -> None:
        assert set(_normalize_categories(None)) == set(DocumentCategory)

    def test_string_and_enum_and_dedup(self) -> None:
        out = _normalize_categories(["financial_statement", DocumentCategory.FINANCIAL_STATEMENT])
        assert out == [DocumentCategory.FINANCIAL_STATEMENT]

    def test_single_value(self) -> None:
        assert _normalize_categories("form_56_1") == [DocumentCategory.FORM_56_1]


class TestFormatSecDate:
    def test_date_object(self) -> None:
        assert _format_sec_date(date(2025, 12, 31), "from_date") == "31/12/2025"

    def test_valid_string_passthrough(self) -> None:
        assert _format_sec_date("01/06/2026", "from_date") == "01/06/2026"

    def test_none_is_empty(self) -> None:
        assert _format_sec_date(None, "from_date") == ""

    def test_iso_string_raises(self) -> None:
        with pytest.raises(InvalidDateError):
            _format_sec_date("2026-06-01", "from_date")


class TestFinancialReportService:
    @pytest.mark.asyncio
    async def test_fetch_documents_filters_to_requested_category(self, monkeypatch) -> None:
        from unittest.mock import patch

        async def router(
            url, headers=None, *, method="GET", json_body=None, data=None, decode_text=True
        ):
            if method == "POST":
                return _resp(FS_SEARCH_HTML)
            return _resp(REPORT_PAGE_HTML)

        with patch("settfex.services.sec.financial_report.AsyncDataFetcher") as cls:
            _make_fetcher(cls, router)
            svc = FinancialReportService()
            docs = await svc.fetch_documents(
                "0000003875", types="financial_statement", follow_view_more=False
            )
        assert {d.category for d in docs} == {DocumentCategory.FINANCIAL_STATEMENT}
        assert len(docs) == 2

    @pytest.mark.asyncio
    async def test_fetch_documents_all_categories_from_fs(self) -> None:
        from unittest.mock import patch

        async def router(
            url, headers=None, *, method="GET", json_body=None, data=None, decode_text=True
        ):
            if method == "POST":
                return _resp(FS_SEARCH_HTML)
            return _resp(REPORT_PAGE_HTML)

        with patch("settfex.services.sec.financial_report.AsyncDataFetcher") as cls:
            _make_fetcher(cls, router)
            svc = FinancialReportService()
            docs = await svc.fetch_documents(
                "u",
                types=["financial_statement", "key_financial_ratio", "mda"],
                follow_view_more=False,
            )
        cats = {d.category for d in docs}
        assert cats == {
            DocumentCategory.FINANCIAL_STATEMENT,
            DocumentCategory.KEY_FINANCIAL_RATIO,
            DocumentCategory.MDA,
        }

    @pytest.mark.asyncio
    async def test_view_more_completes_truncated_section(self) -> None:
        from unittest.mock import patch

        async def router(
            url, headers=None, *, method="GET", json_body=None, data=None, decode_text=True
        ):
            if "ViewMore" in url:
                return _resp(FS_VIEWMORE_HTML)
            if method == "POST":
                return _resp(FS_TRUNCATED_HTML)
            return _resp(REPORT_PAGE_HTML)

        with patch("settfex.services.sec.financial_report.AsyncDataFetcher") as cls:
            _make_fetcher(cls, router)
            svc = FinancialReportService()
            full = await svc.fetch_documents(
                "u", types="financial_statement", follow_view_more=True
            )
            trunc = await svc.fetch_documents(
                "u", types="financial_statement", follow_view_more=False
            )
        assert len(full) == 3  # ViewMore replaces the single truncated inline row
        assert len(trunc) == 1
        assert all("full_" in d.file_id for d in full)

    @pytest.mark.asyncio
    async def test_missing_viewstate_raises(self) -> None:
        from unittest.mock import patch

        from settfex.exceptions import FetchError

        async def router(
            url, headers=None, *, method="GET", json_body=None, data=None, decode_text=True
        ):
            return _resp("<html>blocked</html>")  # no tokens

        with patch("settfex.services.sec.financial_report.AsyncDataFetcher") as cls:
            _make_fetcher(cls, router)
            svc = FinancialReportService()
            with pytest.raises(FetchError, match="VIEWSTATE"):
                await svc.fetch_documents("u", types="form_56_1")

    @pytest.mark.asyncio
    async def test_multiple_codes_for_mixed_categories(self) -> None:
        from unittest.mock import patch

        async def router(
            url, headers=None, *, method="GET", json_body=None, data=None, decode_text=True
        ):
            if method == "POST":
                code = data["ctl00$CPH$ddlReportType"]
                return _resp({"R561": FORM_56_1_HTML, "R562": FORM_56_2_HTML}[code])
            return _resp(REPORT_PAGE_HTML)

        with patch("settfex.services.sec.financial_report.AsyncDataFetcher") as cls:
            _make_fetcher(cls, router)
            svc = FinancialReportService()
            docs = await svc.fetch_documents(
                "u", types=["form_56_1", "form_56_2"], follow_view_more=False
            )
        assert {d.category for d in docs} == {
            DocumentCategory.FORM_56_1,
            DocumentCategory.FORM_56_2,
        }


class TestGetSecDocuments:
    @pytest.mark.asyncio
    async def test_resolves_then_lists(self) -> None:
        from unittest.mock import AsyncMock, patch

        async def router(
            url, headers=None, *, method="GET", json_body=None, data=None, decode_text=True
        ):
            if method == "POST":
                return _resp(FORM_56_1_HTML)
            return _resp(REPORT_PAGE_HTML)

        with (
            patch(
                "settfex.services.sec.financial_report.resolve_company",
                new=AsyncMock(
                    return_value=CompanyMatch(Text="CP ALL", Value="0000003875", Flag=True)
                ),
            ),
            patch("settfex.services.sec.financial_report.AsyncDataFetcher") as cls,
        ):
            _make_fetcher(cls, router)
            docs = await get_sec_documents("CPALL", types="form_56_1", follow_view_more=False)
        assert isinstance(docs, SecDocumentList)  # helpers available on the result
        assert len(docs) == 2 and docs[0].category == DocumentCategory.FORM_56_1

    @pytest.mark.asyncio
    async def test_unresolved_company_returns_empty(self) -> None:
        from unittest.mock import AsyncMock, patch

        with patch(
            "settfex.services.sec.financial_report.resolve_company",
            new=AsyncMock(return_value=None),
        ):
            docs = await get_sec_documents("NOPE")
        assert docs == [] and isinstance(docs, SecDocumentList)


def _doc(category: DocumentCategory, year: int | None, *, section: str = "S") -> SecDocument:
    """Minimal SecDocument for SecDocumentList tests."""
    return SecDocument(
        company_name="CP ALL",
        unique_id="0000003875",
        category=category,
        section=section,
        year=year,
        file_url=f"https://x/{category.value}_{year}.zip",
        file_id=f"{category.value}_{year}.zip",
        file_kind="zip",
    )


class TestSecDocumentList:
    def _sample(self) -> SecDocumentList:
        return SecDocumentList(
            [
                _doc(DocumentCategory.FINANCIAL_STATEMENT, 2026),
                _doc(DocumentCategory.FINANCIAL_STATEMENT, 2025),
                _doc(DocumentCategory.FINANCIAL_STATEMENT, 2025),  # duplicate year
                _doc(DocumentCategory.FORM_56_1, 2024),
                _doc(DocumentCategory.FORM_56_1, 2023),
                _doc(DocumentCategory.MDA, None),  # MD&A rows have no reporting year
            ]
        )

    def test_is_a_list(self) -> None:
        docs = self._sample()
        assert isinstance(docs, list) and len(docs) == 6

    def test_categories_in_enum_order(self) -> None:
        assert self._sample().categories() == [
            DocumentCategory.FINANCIAL_STATEMENT,
            DocumentCategory.FORM_56_1,
            DocumentCategory.MDA,
        ]

    def test_available_years_all_sorted_desc_unique_no_none(self) -> None:
        assert self._sample().available_years() == [2026, 2025, 2024, 2023]

    def test_available_years_by_category_enum_or_str(self) -> None:
        docs = self._sample()
        assert docs.available_years(DocumentCategory.FINANCIAL_STATEMENT) == [2026, 2025]
        assert docs.available_years("form_56_1") == [2024, 2023]
        assert docs.available_years("mda") == []  # no year column

    def test_years_by_category(self) -> None:
        assert self._sample().years_by_category() == {
            "financial_statement": [2026, 2025],
            "form_56_1": [2024, 2023],
            "mda": [],
        }

    def test_filter_by_category_returns_sec_document_list(self) -> None:
        sub = self._sample().filter(category="form_56_1")
        assert isinstance(sub, SecDocumentList) and len(sub) == 2
        assert {d.category for d in sub} == {DocumentCategory.FORM_56_1}

    def test_filter_by_year(self) -> None:
        assert len(self._sample().filter(year=2025)) == 2

    def test_filter_by_category_and_year(self) -> None:
        sub = self._sample().filter(category=DocumentCategory.FINANCIAL_STATEMENT, year=2026)
        assert len(sub) == 1

    def test_summary_lists_years_per_category(self) -> None:
        text = self._sample().summary()
        assert "financial_statement : 2026, 2025" in text
        assert "form_56_1" in text and "2024, 2023" in text
        assert "mda" in text and " : -" in text

    def test_empty_summary(self) -> None:
        assert SecDocumentList().summary() == "(no documents)"
