"""Transport-layer contract for the SEC listing path — issue #131, and the seed of #135's harness.

#123 and #127 closed silent losses in the **parse**. This one is a layer below: the listing path
read ``response.text`` without ever looking at the status, so an error page parsed to zero rows and
came back as an empty list with ``has_losses == False`` — indistinguishable from an issuer that
genuinely filed nothing, and worse than a parse bug because it is *intermittent*: the same query
succeeds an hour later, so nothing in the result or the logs marks the gap. For a backfill the
window is then recorded as covered.

settfex already had the answer everywhere else — ``raise_for_status`` at ~25 call sites across SET
and ThaiBMA, and an explicit check in ``download.py``. ``financial_report.py`` was the one module
that did neither.

Two rules, because one status code cannot see everything:

* **non-2xx → ``FetchError``.** The evidenced case: a real HTTP 505 from the listing host, captured
  2026-09-20 and committed as ``idisc_505_error_page.html``.
* **2xx body that is not a listing page → ``ParseError``.** An error or interstitial page served
  with HTTP 200, which no status check can see.

The second rule is the one that must not over-fire, so it is the weakest rule that separates the
two populations — see ``_LISTING_MARKERS``. The decisive case is the *genuinely empty* listing:
that must keep returning ``[]`` quietly, because it is the true answer for an issuer with no
filings, and mistaking it for an error would invert the whole point of the fix.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from loguru import logger

from settfex.exceptions import FetchError, ParseError
from settfex.services.sec.financial_report import (
    DocumentCategory,
    FinancialReportService,
    _require_listing_page,
    _require_ok,
)
from settfex.utils.data_fetcher import FetchResponse

from .fixtures import (
    FS_SEARCH_HTML,
    FS_TRUNCATED_HTML,
    FS_VIEWMORE_HTML,
    REPORT_PAGE_HTML,
    load_fixture,
)
from .test_financial_report import _make_fetcher, _resp

FS_CATEGORIES = ["financial_statement", "key_financial_ratio", "mda"]

# Every body the listing path can legitimately be asked to parse. None may trip the content rule.
LEGITIMATE_LISTING_BODIES = [
    "th_ptt_fs_h1_2025.html",
    "en_ptt_fs_h1_2025.html",
    "th_mother_fs_h1_2025.html",  # a genuinely EMPTY section — the case that must not raise
    "en_mother_fs_h1_2025.html",
    "th_ptt_56_1.html",
    "en_ptt_56_1.html",
    "th_ptt_56_2.html",
    "en_ptt_56_2.html",
]


def _fail_resp(status: int, body: str = "<html><body>error</body></html>") -> FetchResponse:
    return _resp(body, status=status)


def _captured(level: str = "WARNING") -> tuple[list[str], Any]:
    """Collect loguru messages at ``level`` and above, replacing the default sink."""
    records: list[str] = []
    logger.remove()
    # settfex is disabled by default since 0.24.2 (#146), so a sink alone captures
    # nothing from it. Capturing settfex's own records is an explicit opt-in.
    logger.enable("settfex")
    sink_id = logger.add(lambda m: records.append(m.record["message"]), level=level)
    return records, sink_id


async def _list_with(router, **kwargs: Any):
    with patch("settfex.services.sec.financial_report.AsyncDataFetcher") as cls:
        _make_fetcher(cls, router)
        return await FinancialReportService().fetch_documents("uid", **kwargs)


class TestNonSuccessStatus:
    """A non-2xx response must never be parsed as if it were a listing."""

    @pytest.mark.parametrize("status", [400, 404, 429, 500, 502, 503, 505])
    @pytest.mark.asyncio
    async def test_failing_post_raises_rather_than_returning_empty(self, status: int) -> None:
        """The POST result is the leg that was silently unguarded."""

        async def router(url, headers=None, *, method="GET", json_body=None, data=None, **kw):
            if method == "POST":
                return _fail_resp(status)
            return _resp(REPORT_PAGE_HTML)

        with pytest.raises(FetchError) as excinfo:
            await _list_with(router, types=FS_CATEGORIES, follow_view_more=False)
        assert excinfo.value.status_code == status
        assert str(status) in str(excinfo.value)
        assert "FS" in str(excinfo.value), "the message must name the report code"

    @pytest.mark.parametrize("status", [404, 500, 503])
    @pytest.mark.asyncio
    async def test_failing_get_reports_the_status_not_a_guess(self, status: int) -> None:
        """This leg was already guarded *by accident*, and said the wrong thing about why.

        An error page carries no ``__VIEWSTATE``, so the token check fired and reported "the page
        structure may have changed" for what was really an HTTP 500. The status is read first now,
        so the diagnosis matches the cause.
        """

        async def router(url, headers=None, *, method="GET", json_body=None, data=None, **kw):
            return _fail_resp(status)

        with pytest.raises(FetchError) as excinfo:
            await _list_with(router, types=FS_CATEGORIES, follow_view_more=False)
        assert excinfo.value.status_code == status
        assert "__VIEWSTATE" not in str(excinfo.value)

    @pytest.mark.parametrize(
        ("status", "body"),
        [(503, None), (500, None), (200, "<html><body>maintenance</body></html>")],
        ids=["503", "500", "200-but-not-a-listing"],
    )
    @pytest.mark.asyncio
    async def test_an_unusable_view_more_page_degrades_instead_of_raising(
        self, status: int, body: str | None
    ) -> None:
        """A ViewMore page REPLACES its section's inline rows, so a broken one used to delete them.

        On 0.22.0 the replacement was applied unconditionally: a failing page parsed to zero rows,
        superseded the tally, and the whole section vanished — inline rows included — in silence.
        This is a **partial** loss, though: the truncated inline rows are a real answer, the one
        `follow_view_more=False` returns. So they are kept, warned about, and the shortfall shows
        through `completeness()`. Raising here would cost the caller the entire listing over one
        section, which is #132's complaint in miniature.

        Not hypothetical: the live Thai `fs-kf` page answered 500 on every attempt on 2026-09-20.
        """
        records, sink = _captured()
        try:

            async def router(url, headers=None, *, method="GET", json_body=None, data=None, **kw):
                if "ViewMore" in url:
                    return _resp(body or "", status=status)
                return _resp(FS_TRUNCATED_HTML if method == "POST" else REPORT_PAGE_HTML)

            docs = await _list_with(router, types="financial_statement", follow_view_more=True)
        finally:
            logger.remove(sink)

        assert len(docs) == 1, "the truncated inline row survives"
        assert docs.completeness() == {"financial_statement": (1, 3)}, "the shortfall is visible"
        assert any("display all results" in m for m in records)

    @pytest.mark.parametrize("status", [200, 201, 204])
    def test_success_statuses_pass(self, status: int) -> None:
        _require_ok(status, "http://x", "FS")


class TestErrorPageServedWith200:
    """The half a status check cannot see."""

    def test_the_real_505_body_is_rejected_by_content(self) -> None:
        """The captured body, served with a 200 to isolate the content rule from the status rule."""
        with pytest.raises(ParseError):
            _require_listing_page(load_fixture("idisc_505_error_page.html"), "http://x", "FS")

    def test_an_indirection_page_is_not_a_listing_either(self) -> None:
        with pytest.raises(ParseError):
            _require_listing_page(load_fixture("capital_indirection_en.html"), "http://x", "FS")

    @pytest.mark.asyncio
    async def test_it_raises_through_the_public_entry_point(self) -> None:
        """What the issue actually reported: `[]` with `has_losses == False`, from `get_*`."""

        async def router(url, headers=None, *, method="GET", json_body=None, data=None, **kw):
            if method == "POST":
                return _resp(load_fixture("idisc_505_error_page.html"))  # HTTP 200
            return _resp(REPORT_PAGE_HTML)

        with pytest.raises(ParseError):
            await _list_with(router, types=FS_CATEGORIES, follow_view_more=False)

    @pytest.mark.parametrize("name", LEGITIMATE_LISTING_BODIES)
    def test_no_real_listing_body_trips_the_rule(self, name: str) -> None:
        """Including MOTHER, whose Key Financial Ratio section is genuinely empty."""
        _require_listing_page(load_fixture(name), "http://x", "FS")

    @pytest.mark.parametrize(
        "body", [FS_SEARCH_HTML, FS_TRUNCATED_HTML, FS_VIEWMORE_HTML], ids=["search", "trunc", "vm"]
    )
    def test_no_listing_test_constant_trips_the_rule(self, body: str) -> None:
        """`FS_VIEWMORE_HTML` is why the rule does not key on the result-panel id.

        The real ViewMore capture carries `ctl00_CPH_pnlControl`; this trimmed constant does not.
        A panel-id rule would call a legitimate page an error.
        """
        _require_listing_page(body, "http://x", "FS")


class TestEmptyResultStillMeansEmpty:
    """The property the fix must not break, stated on its own."""

    @pytest.mark.asyncio
    async def test_a_section_reporting_zero_returns_quietly(self) -> None:
        async def router(url, headers=None, *, method="GET", json_body=None, data=None, **kw):
            if method == "POST":
                return _resp(load_fixture("th_mother_fs_h1_2025.html"))
            return _resp(REPORT_PAGE_HTML)

        docs = await _list_with(
            router, types="key_financial_ratio", lang="th", follow_view_more=False
        )
        assert list(docs) == []
        assert docs.reported_counts == {"key_financial_ratio": 0}
        assert not docs.accounting.has_losses, "an empty section is not a loss"

    @pytest.mark.asyncio
    async def test_a_full_listing_is_unaffected(self) -> None:
        async def router(url, headers=None, *, method="GET", json_body=None, data=None, **kw):
            if method == "POST":
                return _resp(load_fixture("th_ptt_fs_h1_2025.html"))
            return _resp(REPORT_PAGE_HTML)

        docs = await _list_with(router, types=FS_CATEGORIES, lang="th", follow_view_more=False)
        assert len(docs) == 10
        assert docs.accounting.is_balanced
        assert not docs.accounting.has_losses


class TestZeroRowsIsNotAnEmptyListing:
    """Defence in depth, one layer below the transport.

    A body can pass the content rule (it has a table) and still parse to no rows at all. Within
    this package that cannot be a real listing: every captured page carries at least the
    placeholder row an empty section serves. Returning `[]` there would be the same silent loss,
    so `_map_rows` refuses it.
    """

    def test_no_rows_raises(self) -> None:
        from settfex.services.sec.financial_report import _map_rows

        with pytest.raises(ParseError) as excinfo:
            _map_rows([], "uid", company_name=None, source="empty")
        assert excinfo.value.rows_parsed == 0

    def test_one_placeholder_row_does_not(self) -> None:
        """The real shape of "this issuer filed nothing" — a heading and a placeholder row."""
        from settfex.services.sec.financial_report import _map_rows
        from settfex.services.sec.utils import parse_report_tables

        html = (
            '<div class="card card-table"><div class="card-heading">'
            "Key Financial Ratio ( 0 record(s) found)</div>"
            "<table><tbody><tr><th>Name</th><th>Details</th></tr>"
            "<tr><td>Data not found</td><td></td></tr></tbody></table></div>"
        )
        result = _map_rows(parse_report_tables(html), "uid", company_name=None, source="x")
        assert result.documents == []
        assert result.accounting.placeholders == 1
        assert not result.accounting.has_losses


class TestExceptionsStayCatchable:
    """Existing handlers must keep working — this is why the fix is a patch, not new API."""

    def test_the_listing_raises_only_documented_types(self) -> None:
        assert issubclass(ParseError, FetchError)

    @pytest.mark.parametrize(
        ("fixture_name", "status"),
        [(None, 500), ("idisc_505_error_page.html", 200)],
        ids=["status-rule", "content-rule"],
    )
    @pytest.mark.asyncio
    async def test_except_fetcherror_catches_both_rules(
        self, fixture_name: str | None, status: int
    ) -> None:
        """Both new rules are `FetchError` subclasses, so one existing handler covers both."""
        body = REPORT_PAGE_HTML if fixture_name is None else load_fixture(fixture_name)

        async def router(url, headers=None, *, method="GET", json_body=None, data=None, **kw):
            if method == "POST":
                return _resp(body, status=status)
            return _resp(REPORT_PAGE_HTML)

        with pytest.raises(FetchError):
            await _list_with(router, types=FS_CATEGORIES, follow_view_more=False)

    @pytest.mark.asyncio
    async def test_the_categories_requested_do_not_change_the_rule(self) -> None:
        """A 56-1 search is a different report code and gets the same guard."""

        async def router(url, headers=None, *, method="GET", json_body=None, data=None, **kw):
            if method == "POST":
                return _fail_resp(500)
            return _resp(REPORT_PAGE_HTML)

        with pytest.raises(FetchError) as excinfo:
            await _list_with(router, types=DocumentCategory.FORM_56_1, follow_view_more=False)
        assert "R561" in str(excinfo.value)
