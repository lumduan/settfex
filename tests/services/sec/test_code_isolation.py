"""One failing report code must not discard the others — issue #132, and R0-1 with it.

`fetch_documents` defaults to all five categories, which collapse to three `ddlReportType` codes
run concurrently. `asyncio.gather` **without** `return_exceptions=True` propagates the first
exception before the line that collects the results is ever reached, so a total loss in the `R562`
search discarded the `FS` documents that had parsed perfectly well in the same call.

The irony the issue names is the point: 0.22.0 added `IncompleteListingError` so a caller could tell
loss from emptiness — and this `gather` threw away the evidence of what *did* parse at the moment
of raising it.

The rule adopted is the one the rest of this module already uses, for the third time:
**a partial loss reports, a total loss raises.** So:

* one code fails, others succeed  → keep their documents, record the failure, warn, return
* every code fails                → raise the first cause, unchanged in type and traceback
* something that is not a FetchError → propagate; a settfex bug must not become an accounting row

R0-1 ("incomplete exceptions carry no partial results") is answered by construction rather than by
new attributes: under this rule we only raise when nothing parsed, so there is nothing to carry.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from loguru import logger

from settfex.exceptions import FetchError, HTTPStatusError, IncompleteListingError, ParseError
from settfex.services.sec.financial_report import (
    CodeFailure,
    DocumentCategory,
    FinancialReportService,
    ListingAccounting,
    SecDocumentList,
)

from .fixtures import FORM_56_1_HTML, FORM_56_2_HTML, REPORT_PAGE_HTML, load_fixture
from .test_financial_report import _make_fetcher, _resp
from .test_listing_transport import _captured

#: Categories spanning three different report codes: FS, R561, R562.
ACROSS_CODES = ["financial_statement", "form_56_1", "form_56_2"]


def _router_for(bodies: dict[str, Any]):
    """Answer each report code's POST with `bodies[code]` — a string, or an exception to raise."""

    async def router(url, headers=None, *, method="GET", json_body=None, data=None, **kw):
        if method != "POST":
            return _resp(REPORT_PAGE_HTML)
        code = str(data.get("ctl00$CPH$ddlReportType", ""))
        outcome = bodies[code]
        if isinstance(outcome, BaseException):
            raise outcome
        if isinstance(outcome, int):
            return _resp("<html><body>error</body></html>", status=outcome)
        return _resp(outcome)

    return router


async def _list(bodies: dict[str, Any], **kwargs: Any) -> SecDocumentList:
    with patch("settfex.services.sec.financial_report.AsyncDataFetcher") as cls:
        _make_fetcher(cls, _router_for(bodies))
        return await FinancialReportService().fetch_documents(
            "uid", types=ACROSS_CODES, follow_view_more=False, **kwargs
        )


class TestOneCodeFailing:
    @pytest.mark.asyncio
    async def test_the_siblings_keep_their_documents(self) -> None:
        """The whole issue in one assertion."""
        records, sink = _captured()
        try:
            docs = await _list(
                {
                    "FS": load_fixture("en_ptt_fs_h1_2025.html"),
                    "R561": FORM_56_1_HTML,
                    "R562": 500,
                }
            )
        finally:
            logger.remove(sink)

        assert len(docs) > 0, "FS and R561 parsed; their documents must survive R562 failing"
        assert {d.category for d in docs} == {
            DocumentCategory.FINANCIAL_STATEMENT,
            DocumentCategory.FORM_56_1,
        }
        assert any("R562" in m for m in records), "the failure is logged, not only recorded"

    @pytest.mark.asyncio
    async def test_the_failure_is_named_in_the_return_value(self) -> None:
        """Data, not prose: a consumer recording "R562 failed" must not parse a message."""
        docs = await _list(
            {"FS": load_fixture("en_ptt_fs_h1_2025.html"), "R561": FORM_56_1_HTML, "R562": 503}
        )
        assert len(docs.accounting.failed_codes) == 1
        failure = docs.accounting.failed_codes[0]
        assert failure.code == "R562"
        assert failure.categories == ["form_56_2"]
        assert failure.error_type == "HTTPStatusError"
        assert failure.status_code == 503
        assert failure.url

    @pytest.mark.asyncio
    async def test_has_losses_is_true(self) -> None:
        """A search that never ran is the largest loss there is, and this is the flag people use."""
        docs = await _list(
            {"FS": load_fixture("en_ptt_fs_h1_2025.html"), "R561": FORM_56_1_HTML, "R562": 500}
        )
        assert docs.accounting.has_losses

    @pytest.mark.asyncio
    async def test_summary_and_repr_show_it(self) -> None:
        """A summary listing only what arrived reads as success when a whole search is missing."""
        docs = await _list(
            {"FS": load_fixture("en_ptt_fs_h1_2025.html"), "R561": FORM_56_1_HTML, "R562": 500}
        )
        assert "FAILED R562" in docs.summary()
        assert "form_56_2" in docs.summary()
        assert "R562" in repr(docs)

    @pytest.mark.asyncio
    async def test_a_parse_failure_is_isolated_the_same_way(self) -> None:
        """Not only transport: `ParseError` from one code is still that code's problem."""
        docs = await _list(
            {
                "FS": load_fixture("en_ptt_fs_h1_2025.html"),
                "R561": FORM_56_1_HTML,
                "R562": load_fixture("idisc_505_error_page.html"),  # 200, but not a listing
            }
        )
        assert len(docs) > 0
        assert docs.accounting.failed_codes[0].error_type == "ParseError"


class TestEveryCodeFailing:
    @pytest.mark.asyncio
    async def test_it_raises_the_first_cause_unchanged(self) -> None:
        """Nothing parsed, so there is nothing partial to return — and nothing to carry (R0-1)."""
        with pytest.raises(HTTPStatusError) as excinfo:
            await _list({"FS": 500, "R561": 502, "R562": 503})
        assert excinfo.value.status_code in (500, 502, 503)
        assert excinfo.value.report_code in ("FS", "R561", "R562")

    @pytest.mark.asyncio
    async def test_it_is_still_catchable_as_fetch_error(self) -> None:
        with pytest.raises(FetchError):
            await _list({"FS": 500, "R561": 500, "R562": 500})

    @pytest.mark.asyncio
    async def test_the_other_causes_ride_along_as_notes(self) -> None:
        """Raising one cause must not lose the other two.

        GATE B's constraint is that the caller can *always* tell which code failed and why, and
        re-raising a single exception would quietly drop the rest. PEP 678 notes carry them with
        no new type, no changed signature and no ExceptionGroup — they show up in the traceback
        and in `__notes__`, and `except FetchError` still catches it.
        """
        with pytest.raises(HTTPStatusError) as excinfo:
            await _list({"FS": 500, "R561": 502, "R562": 503})

        notes = getattr(excinfo.value, "__notes__", [])
        assert len(notes) == 2, "one note per OTHER failed code, never for the raised one"
        joined = " ".join(notes)
        assert "'R561'" in joined and "502" in joined
        assert "'R562'" in joined and "503" in joined
        assert "'FS'" not in joined, "the raised cause is not also a note about itself"

    @pytest.mark.asyncio
    async def test_first_means_first_in_code_order_not_first_to_fail(self) -> None:
        """Determinism: two identical runs must raise the same cause.

        `gather` returns results positionally, so the winner is the first failing code in
        `codes` order — not whichever request happened to lose the race. Here the LAST code fails
        instantly while the first fails only after yielding several times, so a completion-ordered
        implementation would raise R562's 503 instead of FS's 500.
        """
        import asyncio as _asyncio

        async def slow_500(url, headers=None, *, method="GET", json_body=None, data=None, **kw):
            code = str((data or {}).get("ctl00$CPH$ddlReportType", ""))
            if method != "POST":
                return _resp(REPORT_PAGE_HTML)
            if code == "FS":
                for _ in range(20):
                    await _asyncio.sleep(0)  # lose the race, repeatedly
                return _resp("<html/>", status=500)
            return _resp("<html/>", status=503 if code == "R562" else 502)

        for _ in range(3):  # a flake here would mean the order is not actually pinned
            with patch("settfex.services.sec.financial_report.AsyncDataFetcher") as cls:
                _make_fetcher(cls, slow_500)
                with pytest.raises(HTTPStatusError) as excinfo:
                    await FinancialReportService().fetch_documents(
                        "uid", types=ACROSS_CODES, follow_view_more=False
                    )
            assert excinfo.value.report_code == "FS", "first in code order, not first in time"
            assert excinfo.value.status_code == 500

    @pytest.mark.asyncio
    async def test_a_single_requested_code_behaves_as_before(self) -> None:
        """With one code, "one failed" and "all failed" are the same event — it must still raise."""
        with patch("settfex.services.sec.financial_report.AsyncDataFetcher") as cls:
            _make_fetcher(cls, _router_for({"R561": 500}))
            with pytest.raises(HTTPStatusError):
                await FinancialReportService().fetch_documents(
                    "uid", types="form_56_1", follow_view_more=False
                )


class TestNonFetchErrorsPropagate:
    @pytest.mark.asyncio
    async def test_a_bug_is_not_laundered_into_an_accounting_row(self) -> None:
        """A KeyError from settfex is a defect, not "a report code that failed".

        Recording it as one would bury it in a field most callers never read — the exact failure
        mode this whole family of fixes exists to close.
        """
        with pytest.raises(RuntimeError, match="not a fetch problem"):
            await _list(
                {
                    "FS": load_fixture("en_ptt_fs_h1_2025.html"),
                    "R561": FORM_56_1_HTML,
                    "R562": RuntimeError("not a fetch problem"),
                }
            )


class TestNothingFiresOnHealthyData:
    """The discipline every one of these signals is held to."""

    @pytest.mark.asyncio
    async def test_a_clean_three_code_fetch_records_no_failure(self) -> None:
        docs = await _list(
            {
                "FS": load_fixture("en_ptt_fs_h1_2025.html"),
                "R561": FORM_56_1_HTML,
                "R562": FORM_56_2_HTML,
            }
        )
        assert docs.accounting.failed_codes == []
        assert not docs.accounting.has_losses
        assert docs.accounting.is_balanced
        assert "FAILED" not in docs.summary()
        assert "FAILED" not in repr(docs)


class TestTheAccountingMerge:
    def test_failed_codes_survive_absorb(self) -> None:
        first = ListingAccounting()
        first.absorb(
            ListingAccounting(
                failed_codes=[CodeFailure(code="R562", error="boom", error_type="FetchError")]
            )
        )
        assert [f.code for f in first.failed_codes] == ["R562"]

    def test_the_same_failure_is_not_recorded_twice(self) -> None:
        failure = CodeFailure(code="R562", error="boom", error_type="FetchError")
        acc = ListingAccounting(failed_codes=[failure])
        acc.absorb(ListingAccounting(failed_codes=[failure]))
        assert len(acc.failed_codes) == 1


class TestIncompleteListingErrorCarriesItsSections:
    """R0-1's one real sub-claim: a field that looked answered and never was."""

    def test_unknown_sections_is_passed_through(self) -> None:
        error = IncompleteListingError(
            "x", url="u", rows_parsed=3, unknown_sections=["Some New Section"], lost_rows=3
        )
        assert error.unknown_sections == ["Some New Section"]

    def test_it_is_still_a_parse_error(self) -> None:
        assert issubclass(IncompleteListingError, ParseError)
