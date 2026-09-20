"""Regression tests for issue #127 — the silent-loss paths 0.21.0 left open.

#123 fixed one instance of a class of bug: data lost with no signal in the return value. These
cover the rest of the class in the listing parser:

* **P1** rows dropped for want of a download link were counted and never escalated, so an
  all-``no_href`` page returned ``[]`` and raised nothing.
* **P2** the caller-facing summary logged at INFO in the same words as a success, although the
  number that contradicted it was already in scope.
* **P3** ``completeness()`` existed and nothing in the package ever called it.
* **P4** the Thai ``Receive Date`` header was unmapped, so Thai 56-1/56-2 lost their only filing
  timestamp.

The governing idea is one the corpus forced: the old single ``no_href`` counter conflated three
outcomes — a "nothing here" placeholder, a "display all results" navigation row, and a real data
row whose link is gone. Only the third is a defect, and separating them is what lets it be
escalated **without** making the 24% of live pages that truncate behind "view more" into errors.

Fixtures are the committed panel slices of real captures (see ``fixtures_sec/README.md``). Where a
case has no natural example, it is derived **in-test** from those real bytes by one mechanical edit,
which is also how ``test_wholly_unrecognised_page_raises`` works — never by inventing markup.
"""

from __future__ import annotations

import re
from typing import Any
from unittest.mock import patch

import pytest
from loguru import logger

from settfex.exceptions import FetchError, IncompleteListingError, ParseError
from settfex.services.sec.financial_report import (
    _HEADER_FIELD_MAP,
    _IGNORED_HEADERS,
    DocumentCategory,
    FinancialReportService,
    ListingAccounting,
    RowTally,
    SecDocument,
    SecDocumentList,
    _map_rows,
)
from settfex.services.sec.utils import classify_download_href, parse_report_tables

from .fixtures import FS_TRUNCATED_HTML, FS_VIEWMORE_HTML, REPORT_PAGE_HTML, load_fixture
from .test_financial_report import _make_fetcher, _resp

# Every committed listing fixture — the real-page corpus these invariants are measured against.
ALL_FIXTURES = [
    "th_ptt_fs_h1_2025.html",
    "en_ptt_fs_h1_2025.html",
    "th_mother_fs_h1_2025.html",
    "en_mother_fs_h1_2025.html",
    "th_ptt_56_1.html",
    "en_ptt_56_1.html",
    "th_ptt_56_2.html",
    "en_ptt_56_2.html",
]

# The download anchor, in both shapes IDISC serves. Removing the `href` ATTRIBUTE (not the anchor,
# the row or the URL) is the minimal edit that makes `classify_download_href` return no file_url,
# which is exactly the drop path P1 is about. Same recipe as the issue's own fixture derivation.
_DOWNLOAD_HREF = re.compile(r'\s+href="[^"]*(?:Download\?FILEID=|IPOSGetFile\.aspx)[^"]*"')


def _strip_hrefs(html: str, count: int = 0) -> str:
    """Remove the `href` attribute from the page's download anchors (all of them, or the first N)."""
    return _DOWNLOAD_HREF.sub("", html, count=count)


def _mapped(html: str, source: str = "fixture", **kwargs: Any):
    return _map_rows(
        parse_report_tables(html), "uid", company_name="ISSUER", source=source, **kwargs
    )


def _captured(level: str = "WARNING") -> tuple[list[str], Any]:
    """Collect loguru messages at ``level`` and above, replacing the default sink."""
    records: list[str] = []
    logger.remove()
    sink_id = logger.add(lambda m: records.append(m.record["message"]), level=level)
    return records, sink_id


class TestDropReasonTaxonomy:
    """The split that makes everything else possible: three outcomes, not one counter."""

    @pytest.mark.parametrize("name", ALL_FIXTURES)
    def test_no_real_page_loses_a_row(self, name: str) -> None:
        """`no_link` is the defect signal, so it must be zero on every page the site really served.

        If this ever goes non-zero for a captured page, either the site changed or the
        classification is wrong — and in both cases the number is the finding.
        """
        assert _mapped(load_fixture(name)).accounting.no_link == 0

    def test_placeholder_row_is_not_a_loss(self) -> None:
        """MOTHER's Key Financial Ratio reports 0 records and serves `ไม่พบข้อมูล`.

        That is the site saying it has nothing, which must never look like a dropped document —
        it is also exactly what a genuine "this issuer filed nothing" looks like.
        """
        accounting = _mapped(load_fixture("th_mother_fs_h1_2025.html")).accounting
        assert accounting.placeholders == 1
        assert accounting.no_link == 0
        assert accounting.by_category["key_financial_ratio"] == RowTally(rows=1, placeholders=1)

    def test_view_more_row_is_navigation_not_a_loss(self) -> None:
        """The "display all results" row has an href that is a page, not a file.

        It is how the site truncates a long section — 24% of live sections do — so counting it as
        a lost document would turn ordinary truncation into a defect.
        """
        accounting = _mapped(FS_TRUNCATED_HTML).accounting
        assert accounting.navigation == 1
        assert accounting.no_link == 0
        assert accounting.documents == 1

    @pytest.mark.parametrize("name", ALL_FIXTURES)
    def test_accounting_identity_holds(self, name: str) -> None:
        """Every row lands in exactly one bucket.

        Asserted component-wise rather than through `is_balanced` alone, so a failure says which
        side of the identity moved instead of only that the two stopped matching.
        """
        accounting = _mapped(load_fixture(name)).accounting
        for category, tally in accounting.by_category.items():
            assert tally.rows == (
                tally.documents + tally.placeholders + tally.navigation + tally.no_link
            ), category
        assert accounting.rows == (
            accounting.skipped
            + accounting.unknown_rows
            + sum(t.rows for t in accounting.by_category.values())
        )
        assert accounting.is_balanced

    @pytest.mark.parametrize("name", ALL_FIXTURES)
    def test_legacy_no_href_is_the_sum_of_the_three_reasons(self, name: str) -> None:
        """`_MapResult.no_href` keeps its old meaning so nothing that read it has to change."""
        result = _mapped(load_fixture(name))
        accounting = result.accounting
        assert result.no_href == (
            accounting.placeholders + accounting.navigation + accounting.no_link
        )


class TestThirdDownloadShape:
    """Found BY the loss accounting, on the live site, after the issue said it never had been.

    The reporting issue's corpus scan looked at 39 captured pages and found **zero** natural
    instances of a lost row, so its P1 example had to be derived. The first live run of the new
    probe found two: CPALL's 2026 Q1/Q2 Key Financial Ratio rows link through a third URL shape,
    ``/public/idisc/Views/FinancialStatementDownload?query=<blob>``, which `classify_download_href`
    did not recognise — so two real, downloadable filings were being dropped in silence. The URL
    answers `application/zip` with the actual PDFs inside (verified live, 134 KB).

    The blob is opaque: no path, no extension, so there is nothing to derive a `file_kind` from.
    """

    URL = (
        "https://market.sec.or.th/public/idisc/Views/FinancialStatementDownload"
        "?query=GSDdpphMAUrdyKpAaZSrzewJvvZPnzr5NL0bvRh%2fekk%3d"
    )

    def test_it_is_recognised_as_a_download(self) -> None:
        url, file_id, file_kind = classify_download_href(self.URL)
        assert url == self.URL
        assert file_id == "fsdl:GSDdpphMAUrdyKpAaZSrzewJvvZPnzr5NL0bvRh/ekk="
        assert file_kind is None, "an opaque query blob states no file type"

    def test_a_row_using_it_becomes_a_document(self) -> None:
        """The live shape, spliced into a real fixture row in place of its own anchor."""
        html = load_fixture("en_ptt_fs_h1_2025.html")
        original = re.search(r'href="[^"]*IPOSGetFile[^"]*"', html)
        assert original, "fixture must contain an IPOS-hosted row to rewrite"
        html = html.replace(original.group(0), f'href="{self.URL}"', 1)

        result = _mapped(html, source="third-shape")
        assert result.accounting.no_link == 0
        rewritten = [d for d in result.documents if (d.file_id or "").startswith("fsdl:")]
        assert len(rewritten) == 1
        assert rewritten[0].file_kind is None

    def test_the_synthetic_id_is_not_sliced_like_a_path(self) -> None:
        """`fsdl:`/`ipos:` ids are not paths; a real FILEID never contains a colon."""
        from settfex.services.sec.download import _fallback_filename

        document = SecDocument(
            company_name="X",
            unique_id="uid",
            category=DocumentCategory.KEY_FINANCIAL_RATIO,
            section="Key Financial Ratio",
            file_url=self.URL,
            file_id="fsdl:AAA/BBB=",
        )
        assert _fallback_filename(self.URL, document) != "BBB="
        document.file_id = "dat/news/202605/0737FIN.zip"
        assert _fallback_filename(self.URL, document) == "0737FIN.zip"


class TestTotalLossRaises:
    """P1: a page that reports records and yields none must not return an empty list."""

    def test_all_rows_losing_their_link_raises(self) -> None:
        """Derived in-test from the real Thai page: the 10 download anchors lose their `href`.

        Nothing else changes — the section headings, their record-count markers and every cell
        value are the fixture's own bytes, so the page still reports 10 records across 3 sections.
        """
        html = _strip_hrefs(load_fixture("th_ptt_fs_h1_2025.html"))
        rows = parse_report_tables(html)
        assert rows, "the stripped page must still contain data rows"

        with pytest.raises(IncompleteListingError) as excinfo:
            _mapped(html, source="stripped")
        error = excinfo.value
        assert error.lost_rows == 10
        assert error.rows_parsed == len(rows)
        assert error.reported == {"financial_statement": 6, "key_financial_ratio": 2, "mda": 2}
        assert "financial_statement (6 of 6)" in str(error)

    def test_it_is_catchable_as_parse_error_and_fetch_error(self) -> None:
        """Deliberate: callers already wrapping SEC calls in `except FetchError` keep working."""
        assert issubclass(IncompleteListingError, ParseError)
        assert issubclass(IncompleteListingError, FetchError)

    def test_partial_loss_warns_and_keeps_what_it_has(self) -> None:
        """The severity ladder: a partial result is usable once the loss is named.

        Raising here would turn one bad row in a long listing into no listing at all — and unlike
        a total loss, a partial one is visible in the return value.
        """
        html = _strip_hrefs(load_fixture("th_ptt_fs_h1_2025.html"), count=1)
        records, sink = _captured()
        try:
            result = _mapped(html, source="one-stripped")
        finally:
            logger.remove(sink)
        assert len(result.documents) == 9
        assert result.accounting.no_link == 1
        assert result.accounting.has_losses
        assert any("carried no download link" in m for m in records)

    def test_loss_outside_the_requested_categories_does_not_raise(self) -> None:
        """A single "FS" search returns three sections; a caller may have asked for one.

        Reporting a loss in a section that was filtered out on request is the same noise PR #125
        removed from `completeness()`, and here it would be an outright exception.
        """
        html = load_fixture("th_ptt_fs_h1_2025.html")
        # Strip only the MD&A rows' links by stripping every anchor on the page, then ask for a
        # category whose rows are unaffected... instead, assert the scoping directly: strip all,
        # request nothing that lost rows.
        stripped = _strip_hrefs(html)
        with pytest.raises(IncompleteListingError):
            _mapped(stripped, wanted=None)
        result = _mapped(stripped, wanted={DocumentCategory.FORM_56_1})
        assert result.documents == []
        assert result.accounting.no_link == 10, "still accounted for, just not escalated"

    def test_revision_only_page_still_returns_quietly(self) -> None:
        """Rows skipped by design are not a loss — the case that must stay silent."""
        html = (
            '<div class="card card-table"><div class="card-heading">'
            "งบการเงินที่อยู่ระหว่างการแก้ไข (จำนวนรายการที่พบ 0 รายการ)</div>"
            "<table><tbody><tr><th>ชื่อ</th><th>รายละเอียด</th></tr>"
            "<tr><td>ไม่พบข้อมูล</td><td></td></tr></tbody></table></div>"
        )
        result = _mapped(html)
        assert result.documents == []
        assert result.accounting.skipped == 1
        assert not result.accounting.has_losses


class TestColumnCoverage:
    """P-adjacent: the gap that hid P4 for a release was an unread column nobody reported."""

    @pytest.mark.parametrize("name", ALL_FIXTURES)
    def test_every_real_page_is_fully_covered(self, name: str) -> None:
        """The ignore-list plus the field map account for every header the corpus serves.

        This is what keeps the check quiet enough to be worth having: it fires on nothing today,
        so the first thing it ever names will be a real change.
        """
        assert _mapped(load_fixture(name)).accounting.unmapped_headers == []

    def test_a_new_column_is_named_but_does_not_raise(self) -> None:
        """An unmodelled column is "the site has more than we model", not lost data.

        Raising would turn a cosmetic site change into a total outage, so it is reported instead —
        in the return value, which is the whole point of this issue.
        """
        html = load_fixture("en_ptt_56_1.html").replace(
            '<th class="RgCol_Center" scope="col">Receive Date</th>',
            '<th class="RgCol_Center" scope="col">Filing Agent</th>',
        )
        records, sink = _captured()
        try:
            result = _mapped(html, source="new-column")
        finally:
            logger.remove(sink)
        assert result.accounting.unmapped_headers == ["Filing Agent"]
        assert len(result.documents) == 6, "the documents themselves are unaffected"
        assert all(d.receive_date is None for d in result.documents), "its value is dropped"
        assert any("map to no field" in m for m in records)

    def test_ignore_list_and_field_map_do_not_overlap(self) -> None:
        """A header cannot be both mapped and ignored; that would be two answers to one question."""
        assert not (_IGNORED_HEADERS & set(_HEADER_FIELD_MAP))

    def test_revision_section_headers_are_not_on_the_ignore_list(self) -> None:
        """They are unmapped and never reported, because their rows are skipped before any cell
        is read. Listing them would make the ignore-list look broader than it is."""
        for header in ("order date", "company name", "reviewed financial statement", "ชื่อบริษัท"):
            assert header not in _IGNORED_HEADERS


class TestCountMarker:
    """D4: a section with no record-count marker cannot be cross-checked, and must say so."""

    @pytest.mark.parametrize("name", ALL_FIXTURES)
    def test_every_real_section_carries_a_marker(self, name: str) -> None:
        assert _mapped(load_fixture(name)).accounting.unverifiable_sections == []

    def test_a_section_without_a_marker_is_flagged_not_assumed_complete(self) -> None:
        html = load_fixture("en_ptt_56_2.html").replace(" ( 7 record(s) found)", "")
        records, sink = _captured()
        try:
            result = _mapped(html, source="no-marker")
        finally:
            logger.remove(sink)
        assert result.accounting.unverifiable_sections == ["Form 56-2 : Annual Reports"]
        assert result.reported_counts == {}
        assert any("no record-count marker" in m for m in records)


class TestAccountingTravels:
    """The accounting has to reach the caller, or none of the above is visible."""

    def test_filter_carries_it(self) -> None:
        """Otherwise the cross-check evaporates exactly when someone narrows the result."""
        result = _mapped(load_fixture("th_ptt_fs_h1_2025.html"))
        docs = SecDocumentList(
            result.documents,
            reported_counts=result.reported_counts,
            accounting=result.accounting,
        )
        narrowed = docs.filter(category=DocumentCategory.FINANCIAL_STATEMENT)
        assert narrowed.accounting is docs.accounting

    def test_default_is_an_empty_accounting_not_none(self) -> None:
        """A caller should never have to guard the attribute before reading it."""
        empty = SecDocumentList()
        assert empty.accounting.rows == 0
        assert not empty.accounting.has_losses

    def test_it_survives_model_dump(self) -> None:
        """Computed totals must reach Parquet/JSON, not be recomputed by every consumer."""
        dumped = _mapped(load_fixture("th_ptt_fs_h1_2025.html")).accounting.model_dump(mode="json")
        assert dumped["documents"] == 10
        assert dumped["no_link"] == 0
        assert dumped["is_balanced"] is True
        assert dumped["by_category"]["mda"]["documents"] == 2


class TestAccountingMerge:
    """`absorb` and `supersede` are where the identity can genuinely break."""

    def test_absorb_sums_disjoint_searches(self) -> None:
        first = ListingAccounting(rows=3, by_category={"form_56_1": RowTally(rows=3, documents=3)})
        second = ListingAccounting(
            rows=8, skipped=1, by_category={"financial_statement": RowTally(rows=7, documents=7)}
        )
        first.absorb(second)
        assert first.rows == 11
        assert first.documents == 10
        assert first.is_balanced

    def test_supersede_replaces_rather_than_adds(self) -> None:
        """The ViewMore page REPLACES the truncated inline rows; adding both double-counts them."""
        inline = ListingAccounting(
            rows=2,
            by_category={"financial_statement": RowTally(rows=2, documents=1, navigation=1)},
        )
        complete = ListingAccounting(
            rows=3, by_category={"financial_statement": RowTally(rows=3, documents=3)}
        )
        inline.supersede("financial_statement", complete)
        assert inline.rows == 3
        assert inline.documents == 3
        assert inline.is_balanced

    def test_merge_unions_the_diagnostic_names(self) -> None:
        first = ListingAccounting(unmapped_headers=["A"], unknown_sections=["X"])
        first.absorb(ListingAccounting(unmapped_headers=["A", "B"], unverifiable_sections=["S"]))
        assert first.unmapped_headers == ["A", "B"]
        assert first.unknown_sections == ["X"]
        assert first.unverifiable_sections == ["S"]


class TestSummaryLine:
    """P2 + P3: the summary is derived from the accounting, and completeness() finally has a caller."""

    @staticmethod
    async def _list(html: str, *, follow_view_more: bool = False, **kwargs: Any) -> Any:
        async def router(
            url, headers=None, *, method="GET", json_body=None, data=None, decode_text=True
        ):
            if "ViewMore" in url:
                return _resp(FS_VIEWMORE_HTML)
            return _resp(html if method == "POST" else REPORT_PAGE_HTML)

        with patch("settfex.services.sec.financial_report.AsyncDataFetcher") as cls:
            _make_fetcher(cls, router)
            return await FinancialReportService().fetch_documents(
                "uid", follow_view_more=follow_view_more, **kwargs
            )

    #: The three categories a single "FS" search returns, so the mock answers exactly one search.
    FS_CATEGORIES = ["financial_statement", "key_financial_ratio", "mda"]

    @pytest.mark.asyncio
    async def test_complete_listing_logs_the_sites_number_too(self) -> None:
        """`Listed 10` and `Listed 0` used to be the same sentence; now the claim is checkable."""
        records, sink = _captured("INFO")
        try:
            docs = await self._list(
                load_fixture("th_ptt_fs_h1_2025.html"), lang="th", types=self.FS_CATEGORIES
            )
        finally:
            logger.remove(sink)
        assert len(docs) == 10
        assert docs.completeness() == {
            "financial_statement": (6, 6),
            "key_financial_ratio": (2, 2),
            "mda": (2, 2),
        }
        assert any("the site reports 10" in m for m in records)

    @pytest.mark.asyncio
    async def test_expected_truncation_stays_at_info(self) -> None:
        """With follow_view_more=False a shortfall is what the caller asked for.

        Warning about it would train people to ignore warnings, which is how the real one gets
        missed.
        """
        records, sink = _captured()
        try:
            docs = await self._list(FS_TRUNCATED_HTML, types="financial_statement")
        finally:
            logger.remove(sink)
        assert docs.completeness() == {"financial_statement": (1, 3)}
        assert records == []

    @pytest.mark.asyncio
    async def test_residual_shortfall_after_view_more_warns(self) -> None:
        """Following "display all results" should return the section in full.

        If it still falls short, nothing is left to explain the gap — the one shortfall worth a
        warning.
        """
        short_view_more = FS_VIEWMORE_HTML.replace("( 3 record(s) found)", "( 9 record(s) found)")

        async def router(
            url, headers=None, *, method="GET", json_body=None, data=None, decode_text=True
        ):
            if "ViewMore" in url:
                return _resp(short_view_more)
            return _resp(FS_TRUNCATED_HTML if method == "POST" else REPORT_PAGE_HTML)

        records, sink = _captured()
        try:
            with patch("settfex.services.sec.financial_report.AsyncDataFetcher") as cls:
                _make_fetcher(cls, router)
                docs = await FinancialReportService().fetch_documents(
                    "uid", types="financial_statement", follow_view_more=True
                )
        finally:
            logger.remove(sink)
        assert docs.completeness() == {"financial_statement": (3, 9)}
        assert any("even after following" in m for m in records)

    @pytest.mark.asyncio
    async def test_a_lossy_parse_warns_rather_than_reporting_success(self) -> None:
        """The P2 shape itself: documents were lost and the summary must not read like success."""
        html = _strip_hrefs(load_fixture("th_ptt_fs_h1_2025.html"), count=1)
        records, sink = _captured()
        try:
            docs = await self._list(html, lang="th", types=self.FS_CATEGORIES)
        finally:
            logger.remove(sink)
        assert docs.accounting.no_link == 1
        assert any("the parse was not clean" in m for m in records)

    @pytest.mark.asyncio
    async def test_view_more_accounting_is_replaced_not_doubled(self) -> None:
        records, sink = _captured()
        try:
            docs = await self._list(
                FS_TRUNCATED_HTML, types="financial_statement", follow_view_more=True
            )
        finally:
            logger.remove(sink)
        assert len(docs) == 3
        assert docs.accounting.by_category["financial_statement"] == RowTally(rows=3, documents=3)
        assert docs.accounting.is_balanced
        assert records == []


class TestThaiReceiveDate:
    """P4: the Thai 56-1/56-2 `Receive Date` column was unmapped, so the date was dropped."""

    PAIRS = [("th_ptt_56_1.html", "en_ptt_56_1.html"), ("th_ptt_56_2.html", "en_ptt_56_2.html")]

    @staticmethod
    def _by_year(name: str) -> dict[int, Any]:
        return {
            d.year: d.receive_date
            for d in _mapped(load_fixture(name)).documents
            if d.year is not None
        }

    @pytest.mark.parametrize(("th_name", "en_name"), PAIRS)
    def test_both_languages_agree_on_the_filing_date(self, th_name: str, en_name: str) -> None:
        """Compared per (form, year), never by count.

        The Thai and English 56-1 captures are from different windows — 3 records against 6 — so
        the two pages describe an overlapping, not an identical, set of filings.
        """
        thai, english = self._by_year(th_name), self._by_year(en_name)
        shared = set(thai) & set(english)
        assert shared, "the two captures must overlap to be comparable at all"
        for year in shared:
            assert thai[year] == english[year], year
            assert thai[year] is not None

    def test_the_thai_page_really_states_the_buddhist_era_year(self) -> None:
        """Otherwise this could pass with no era conversion happening at all."""
        assert "12/03/2569" in load_fixture("th_ptt_56_1.html")
        assert self._by_year("th_ptt_56_1.html")[2025].isoformat() == "2026-03-12"

    def test_the_column_is_not_confused_with_the_plain_date_header(self) -> None:
        """`วันที่` already maps to `as_of`; `วันที่ได้รับข้อมูล` must not collide with it."""
        assert _HEADER_FIELD_MAP["วันที่"] == "as_of"
        assert _HEADER_FIELD_MAP["วันที่ได้รับข้อมูล"] == "receive_date"
        for document in _mapped(load_fixture("th_ptt_56_2.html")).documents:
            assert document.as_of is None, "56-2 rows have no As Of column"
            assert document.receive_date is not None
