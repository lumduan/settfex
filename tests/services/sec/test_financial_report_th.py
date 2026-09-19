"""Regression tests for issue #123 — Thai SEC listings parsed to zero rows, silently.

`fetch_documents(lang="th")` returned an empty list for issuers with filings, because section
headings were classified by English substring probes only. No exception, no warning: an empty list
is also the correct answer for an issuer that filed nothing, so a caller could not tell the two
apart.

The fixtures here are real captured response bodies, sliced verbatim from the bytes the server
sent — see `fixtures_sec/README.md` for provenance and hashes. The governing invariant is
language-independent and is the one the issue's own reproduction script asserts: **the same query
in two languages returns the same page structure, so it must parse to the same documents.**

Note what is deliberately NOT asserted: that the two languages return the same `file_url`. They do
not, and that is the site's behaviour, not a defect — see TestLanguageSpecificDownloads.
"""

from __future__ import annotations

import pytest

from settfex.exceptions import ParseError
from settfex.services.sec.financial_report import (
    DocumentCategory,
    FinancialReportService,
    SecDocumentList,
    _map_rows,
    _section_disposition,
    category_for_section,
)
from settfex.services.sec.utils import (
    parse_report_tables,
    parse_year,
    split_section_count,
)

from .fixtures import load_fixture
from .test_financial_report import _make_fetcher, _resp

PAIRS = [
    ("th_ptt_fs_h1_2025.html", "en_ptt_fs_h1_2025.html"),
    ("th_mother_fs_h1_2025.html", "en_mother_fs_h1_2025.html"),
]

# Fields that must be identical in both languages: structural, or normalised out of the page's
# language (the year and date are Buddhist-era on the Thai page and convert to the same C.E.
# value). The rest -- company_name, status, statement_type, period, section -- are the page's own
# words and differ by design.
LANGUAGE_INDEPENDENT = ("category", "year", "as_of", "receive_date", "file_kind")


# The listing service passes the resolved issuer name as a fallback, because MD&A rows have no
# Name column of their own (their headers are Date/Time/Heading/Link). Mirror that here.
ISSUER = "RESOLVED ISSUER NAME"


def _documents(name: str):
    return _map_rows(
        parse_report_tables(load_fixture(name)), "uid", company_name=ISSUER, source=name
    )


class TestThaiListingParity:
    """The bug itself: Thai pages must yield the same documents as their English twins."""

    @pytest.mark.parametrize(("th_name", "en_name"), PAIRS)
    def test_same_document_count(self, th_name: str, en_name: str) -> None:
        th, en = _documents(th_name), _documents(en_name)
        assert th.rows == en.rows, "the two pages must have the same structure to compare at all"
        assert len(th.documents) == len(en.documents)
        assert len(th.documents) > 0, "a fixture with no documents cannot detect this regression"

    @pytest.mark.parametrize(("th_name", "en_name"), PAIRS)
    def test_language_independent_fields_match(self, th_name: str, en_name: str) -> None:
        for thai, english in zip(
            _documents(th_name).documents, _documents(en_name).documents, strict=True
        ):
            for field in LANGUAGE_INDEPENDENT:
                assert getattr(thai, field) == getattr(english, field), field

    @pytest.mark.parametrize(("th_name", "en_name"), PAIRS)
    def test_metadata_is_populated_not_just_present(self, th_name: str, en_name: str) -> None:
        """The second barrier behind the bug: a row could survive with every field None.

        Classifying the section was only half of it — the header map was English-only too, so a
        Thai row that got past the first check became a SecDocument with no year, no period and
        no date. Counting documents alone would not notice.
        """
        for thai in _documents(th_name).documents:
            assert thai.company_name
            if thai.category is DocumentCategory.MDA:
                # No Name column in this section — the resolved issuer name fills it, and the
                # Thai 'หัวข้อข่าว' header supplies the title.
                assert thai.company_name == ISSUER
                assert thai.title
                assert thai.as_of is not None, "from the Thai 'วันที่' header"
            else:
                assert thai.company_name != ISSUER, "a real Thai name from the 'ชื่อ' cell"
            if thai.category is DocumentCategory.FINANCIAL_STATEMENT:
                assert thai.year is not None
                assert thai.period is not None
                assert thai.status is not None
                assert thai.as_of is not None

    def test_key_financial_ratio_reorders_its_columns(self) -> None:
        """KFR moves Year from column 2 to 5 and puts Business Type where Status is.

        Matching on the header NAME rather than the column index is what makes that a non-event;
        a positional map would silently write the year into `status`.
        """
        kfr = [
            d
            for d in _documents("th_ptt_fs_h1_2025.html").documents
            if d.category is DocumentCategory.KEY_FINANCIAL_RATIO
        ]
        assert kfr, "fixture must contain Key Financial Ratio rows"
        for document in kfr:
            assert document.year is not None
            assert document.business_type, "KFR carries Business Type where FS carries Status"
            assert document.status is None, "KFR has no Status column"


class TestSectionDisposition:
    """Classification, and the ordering trap that Thai makes sharper than English."""

    def test_revision_section_is_skipped_not_misfiled(self) -> None:
        """`งบการเงินที่อยู่ระหว่างการแก้ไข` CONTAINS `งบการเงิน` as a prefix.

        Probing for the financial-statement heading before the skip tokens would file every
        amended-statement section under FINANCIAL_STATEMENT — quietly turning revision-tracking
        rows into ordinary filings.
        """
        for heading in (
            "งบการเงินที่อยู่ระหว่างการแก้ไข",
            "งบการเงินที่สำนักงานแจ้งให้แก้ไข",
            "งบการเงินที่อยู่ระหว่างการแก้ไข (จำนวนรายการที่พบ 0 รายการ)",
        ):
            category, disposition = _section_disposition(heading)
            assert disposition == "skipped", heading
            assert category is None, heading

    @pytest.mark.parametrize(
        ("heading", "expected"),
        [
            ("งบการเงิน", DocumentCategory.FINANCIAL_STATEMENT),
            ("งบการเงิน (จำนวนรายการที่พบ 27 รายการ)", DocumentCategory.FINANCIAL_STATEMENT),
            (
                "รายงานอัตราส่วนที่มีนัยสำคัญทางการเงิน/ข้อมูลทางการเงินที่สำคัญ/ข้อกำหนดด้านการเงิน",
                DocumentCategory.KEY_FINANCIAL_RATIO,
            ),
            ("คำอธิบายและวิเคราะห์ของฝ่ายจัดการ", DocumentCategory.MDA),
            ("แบบ 56-1 One Report", DocumentCategory.FORM_56_1),
            # English must keep working byte-for-byte, misspelling included.
            ("Finanacial Statements ( 27 record(s) found)", DocumentCategory.FINANCIAL_STATEMENT),
            ("Key Financial Ratio", DocumentCategory.KEY_FINANCIAL_RATIO),
        ],
    )
    def test_headings_classify(self, heading: str, expected: DocumentCategory) -> None:
        assert category_for_section(heading) is expected
        assert _section_disposition(heading)[1] == "mapped"

    def test_unrecognised_heading_is_unknown_not_skipped(self) -> None:
        """The distinction that did not exist before: a defect must not look like a policy."""
        category, disposition = _section_disposition("Some Entirely New Section")
        assert category is None
        assert disposition == "unknown"


class TestFailLoud:
    """A page whose rows all vanish must say so, instead of returning an empty list."""

    def test_wholly_unrecognised_page_raises(self) -> None:
        """Derived from the real Thai page by renaming only its section headings."""
        html = load_fixture("th_ptt_fs_h1_2025.html")
        for heading in ("งบการเงิน", "รายงานอัตราส่วน", "คำอธิบายและวิเคราะห์", "แก้ไข"):
            html = html.replace(heading, "XYZZY")
        rows = parse_report_tables(html)
        assert rows, "the renamed page must still contain data rows"

        with pytest.raises(ParseError) as excinfo:
            _map_rows(rows, "uid", company_name=None, source="renamed")
        assert excinfo.value.rows_parsed == len(rows)
        assert excinfo.value.unknown_sections
        assert isinstance(excinfo.value, Exception)

    def test_parse_error_is_catchable_as_fetch_error(self) -> None:
        """Deliberate: callers already wrapping SEC calls in `except FetchError` keep working."""
        from settfex.exceptions import FetchError

        assert issubclass(ParseError, FetchError)

    def test_section_present_but_empty_does_not_raise(self) -> None:
        """MOTHER's Key Financial Ratio section has a heading and header row but no data rows.

        That is a genuine absence of filings, and the single most important thing NOT to raise on
        — it is what an empty result legitimately looks like.
        """
        result = _documents("th_mother_fs_h1_2025.html")
        assert result.reported_counts["key_financial_ratio"] == 0
        assert not [
            d for d in result.documents if d.category is DocumentCategory.KEY_FINANCIAL_RATIO
        ]
        assert result.unknown_sections == []

    def test_rows_dropped_only_by_design_do_not_raise(self) -> None:
        """Every row skipped on purpose, zero documents, no unrecognised heading -> no error."""
        html = (
            '<div class="card card-table"><div class="card-heading">'
            "งบการเงินที่อยู่ระหว่างการแก้ไข (จำนวนรายการที่พบ 0 รายการ)</div>"
            "<table><tbody><tr><th>ชื่อ</th><th>รายละเอียด</th></tr>"
            "<tr><td>ไม่พบข้อมูล</td><td></td></tr></tbody></table></div>"
        )
        result = _map_rows(parse_report_tables(html), "uid", company_name=None, source="x")
        assert result.documents == []
        assert result.skipped == 1
        assert result.unknown_sections == []


class TestBuddhistEra:
    """Masked by the bug, and unmasked by fixing it: Thai pages state years as 2568."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [("2568", 2025), ("2569", 2026), ("๒๕๖๘", 2025), ("2025", 2025), (None, None)],
    )
    def test_parse_year_converts(self, raw: str | None, expected: int | None) -> None:
        assert parse_year(raw) == expected

    def test_year_is_christian_era_in_the_model(self) -> None:
        """The Thai fixture says 2568; the document must not."""
        assert "2568" in load_fixture("th_ptt_fs_h1_2025.html")
        years = {d.year for d in _documents("th_ptt_fs_h1_2025.html").documents if d.year}
        assert years and all(2000 < y < 2100 for y in years), years

    def test_parse_int_is_left_alone(self) -> None:
        """A +543 rule hidden inside something named `parse_int` would trap the next caller."""
        from settfex.services.sec.utils import parse_int

        assert parse_int("2568") == 2568


class TestReportedCounts:
    """The cross-check that caught this bug, which settfex used to delete."""

    @pytest.mark.parametrize(("th_name", "en_name"), PAIRS)
    def test_counts_match_across_languages(self, th_name: str, en_name: str) -> None:
        assert _documents(th_name).reported_counts == _documents(en_name).reported_counts

    def test_counts_are_parsed_in_both_marker_forms(self) -> None:
        assert split_section_count("Finanacial Statements ( 27 record(s) found)") == (
            "Finanacial Statements",
            27,
        )
        assert split_section_count("งบการเงิน (จำนวนรายการที่พบ 27 รายการ)") == ("งบการเงิน", 27)
        assert split_section_count("งบการเงิน") == ("งบการเงิน", None)

    def test_counts_survive_filter(self) -> None:
        """Otherwise the cross-check evaporates exactly when someone narrows the result."""
        docs = SecDocumentList(
            _documents("th_ptt_fs_h1_2025.html").documents,
            reported_counts=_documents("th_ptt_fs_h1_2025.html").reported_counts,
        )
        narrowed = docs.filter(category=DocumentCategory.FINANCIAL_STATEMENT)
        assert narrowed.reported_counts == {"financial_statement": 6}
        kept, reported = narrowed.completeness()["financial_statement"]
        assert kept == len(narrowed)
        assert reported == 6

    def test_completeness_reports_holdings_against_the_sites_number(self) -> None:
        result = _documents("th_ptt_fs_h1_2025.html")
        docs = SecDocumentList(result.documents, reported_counts=result.reported_counts)
        assert docs.completeness()["mda"] == (2, 2)


class TestLanguageSpecificDownloads:
    """`lang` selects the document language too, not just the page's — pinned so it is not "fixed".

    The Thai and English listings link to DIFFERENT files for the same filing: the news-hosted
    zip/pdf artifacts come in a Thai and an English edition (the FILEID stems differ, and the
    generated-at timestamps inside them differ by seconds). IPOS-hosted rows are shared.

    An archiver that switches to lang="th" therefore downloads different artifacts — which is the
    point of switching, but it means a cross-language `file_url` equality assertion is wrong.
    """

    def test_mda_links_differ_by_language(self) -> None:
        th = [
            d
            for d in _documents("th_ptt_fs_h1_2025.html").documents
            if d.category is DocumentCategory.MDA
        ]
        en = [
            d
            for d in _documents("en_ptt_fs_h1_2025.html").documents
            if d.category is DocumentCategory.MDA
        ]
        assert th and len(th) == len(en)
        assert all(a.file_url != b.file_url for a, b in zip(th, en, strict=True))
        assert all(a.file_kind == b.file_kind == "pdf" for a, b in zip(th, en, strict=True))

    def test_ipos_hosted_links_are_shared(self) -> None:
        th = {
            d.file_id for d in _documents("th_ptt_fs_h1_2025.html").documents if d.file_kind is None
        }
        en = {
            d.file_id for d in _documents("en_ptt_fs_h1_2025.html").documents if d.file_kind is None
        }
        assert th and th == en


class TestRequestedCategoriesOnly:
    """`completeness()` must not report a shortfall for a section nobody asked for."""

    @pytest.mark.asyncio
    async def test_counts_cover_only_the_requested_categories(self) -> None:
        """A single "FS" search returns three sections; asking for one must report one.

        Found on the live site: querying only financial statements still surfaced
        `key_financial_ratio: (0, 2)` and `mda: (0, 2)` — sections that were filtered out on
        request, reported as if two documents had gone missing. Pure noise in the one primitive
        meant to make a real shortfall visible.
        """
        from unittest.mock import patch

        from .fixtures import REPORT_PAGE_HTML

        async def router(
            url, headers=None, *, method="GET", json_body=None, data=None, decode_text=True
        ):
            return _resp(
                load_fixture("th_ptt_fs_h1_2025.html") if method == "POST" else REPORT_PAGE_HTML
            )

        with patch("settfex.services.sec.financial_report.AsyncDataFetcher") as cls:
            _make_fetcher(cls, router)
            docs = await FinancialReportService().fetch_documents(
                "uid", types="financial_statement", lang="th", follow_view_more=False
            )

        assert set(docs.reported_counts) == {"financial_statement"}
        assert docs.completeness() == {"financial_statement": (6, 6)}
