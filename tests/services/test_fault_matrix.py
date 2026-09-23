"""Library-wide fault-injection matrix — the harness issue #135 asks for.

Every public ``get_*`` entry point is driven against a set of injected transport faults, and the
result is checked against invariants rather than against specific exception types. The invariants
are what the caller actually depends on; the exception type is an implementation detail that may
legitimately differ per service.

**The injection rule, and it is load-bearing.** Faults are injected at
``AsyncDataFetcher.fetch`` — the lowest layer — and **never** by mocking the code under test.
Learned the hard way: an earlier sweep mocked ``fetch_json`` and produced artifacts
(``JSONDecodeError`` where settfex's real wrapper raises ``ResponseParseError``) that would have
been reported as findings. Patching only ``.fetch`` leaves every wrapper, validator, retry loop
and envelope model real, so what the matrix reports is what a caller would actually see.

**The rule this matrix exists to keep closed**, distilled from the #135 audit::

    silent  ⟺  (no HTTP status check)  AND  (the response model validates the error body)

Both halves are now checked: ``fetch_json`` raises on a non-2xx, and a response envelope whose
only field is optional is the case where the second half bites. That is why ``200+[]`` and
``200+{}`` are separate faults — they are the payloads that slip past a permissive model.

One fault is not a response at all: ``transport`` is the request never completing, raised exactly
as the real ``fetch`` raises it once its retries are spent. Until 0.25.0 every fault here was a
*response*, so no service anywhere was tested against a raised transport error at this layer —
the gap the 2026-09-23 checklist audit on #135 found in all four service rows.

Invariants asserted here:

* **I1** — a fault never yields a successful-looking result.
* **I2** — every error is in the ``FetchError`` family, so one ``except FetchError`` covers them.

I3 (partial failure recorded *and* logged), I4 (the signal survives ordinary consumer handling,
including serialization) and I5 (one logical answer fails together) are asserted in the
service-specific suites, where the partial-result shapes exist to inspect.
"""

from __future__ import annotations

import importlib
import json
from typing import Any
from unittest.mock import patch

import pytest

from settfex.exceptions import CompanyNotFoundError, FetchError
from settfex.services.sec.download import DownloadResult, FailedDownload
from settfex.services.sec.financial_report import (
    CodeFailure,
    DegradedSection,
    DocumentCategory,
    ListingAccounting,
    RowTally,
    SecDocument,
    SecDocumentList,
)
from settfex.utils.data_fetcher import AsyncDataFetcher, FetchResponse


def _resp(body: str, status: int = 200, ctype: str = "application/json") -> FetchResponse:
    return FetchResponse(
        status_code=status,
        content=body.encode("utf-8"),
        text=body,
        headers={"Content-Type": ctype},
        url="https://injected.invalid/",
        elapsed=0.0,
    )


def _transport_failure() -> FetchResponse:
    """Raise what ``AsyncDataFetcher.fetch`` raises when every attempt failed to complete.

    Mirrors ``settfex/utils/data_fetcher.py`` after its retry loop: a ``FetchError`` naming the
    attempts, chained from the transport cause. A connection reset is the cause chosen because it is
    the first WAF signal the live-probe politeness rule names.
    """
    raise FetchError(
        "Failed to fetch https://injected.invalid/ after 4 attempts"
    ) from ConnectionResetError(104, "Connection reset by peer")


#: The faults. Each is something a real origin can and does produce: a response, or no response.
FAULTS: dict[str, Any] = {
    # The request never completes. Raised from `fetch` itself, as the real one does after retries.
    "transport": _transport_failure,
    # A plain upstream failure with an HTML error page — the shape SEC's real HTTP 505 had.
    "500+html": lambda: _resp(
        "<html><body>500 Internal Server Error</body></html>", 500, "text/html"
    ),
    # An error or interstitial page served with 200, which no status check can see.
    "200+html": lambda: _resp("<html><body>Service unavailable</body></html>", 200, "text/html"),
    # The two payloads that slip past a permissive envelope model.
    "200+{}": lambda: _resp("{}", 200),
    "200+[]": lambda: _resp("[]", 200),
    # A non-2xx that still carries valid JSON — the case a JSON parser cannot catch.
    "503+json": lambda: _resp('{"message":"Service Unavailable"}', 503),
}

#: Endpoints whose payload is a bare JSON array, where ``200+[]`` is a **legitimate empty answer**
#: rather than a fault — so that one cell is asserted as a normal result instead of as an error.
#:
#: Each entry is (entry point, evidence). Classified from **live payloads on 2026-09-20**, not from
#: a blanket rule, because the expectation going in was wrong for one of them:
#:
#:   get_board_of_directors was expected to raise, on the reasoning that a listed company always
#:   has a board. True of companies — but this endpoint takes ANY symbol, and an ETF is a fund with
#:   no board. `1DIV` (ETF), `SCBSET` (unit trust) and `AAOI03` (DR) all answer HTTP 200 with an
#:   empty list. That is ~508 symbols by the stock list's own census (493 DR + 13 ETF + 2 unit
#:   trust); raising would have broken every one of them.
#:
#: The premise behind the wider worry does not hold here either: all six answer an **invalid**
#: symbol with HTTP 404 → ``SymbolNotFoundError``, so an empty list never means "bad symbol". The
#: general "invalid input must not look like empty data" class stays on #135, where
#: ``ConsensusOverallResponse`` still answers an unknown symbol with ``overall: []``.
EMPTY_IS_LEGITIMATE: dict[str, str] = {
    "get_corporate_actions": "live: JAS-W4 (warrant) and CPALL-F both return 0",
    "get_board_of_directors": "live: 1DIV (ETF), SCBSET (unit trust), AAOI03 (DR) return 0",
    "get_balance_sheet": "live: JAS-W4, GOOG80 (DR), CPALL-F return 0",
    "get_income_statement": "live: same securities as the balance sheet return 0",
    "get_cash_flow": "live: same securities as the balance sheet return 0",
    # INFERRED, not observed: every security type probed returned 3 periods, so an empty result was
    # never seen. It is not demonstrably impossible, so the current behaviour is pinned rather than
    # asserted to be correct — if it ever returns [], this is where to revisit.
    "get_trading_stats": "INFERRED — legitimate but unobserved; 3 periods for every type probed",
}

#: Cells where a **documented input error** is the correct answer, so I2's "must be a FetchError"
#: does not apply. Keyed by (entry point, fault) with the reason, so the exemption is a recorded
#: classification rather than a loosened invariant.
#:
#: ``get_sec_documents`` with ``200+[]``: the SEC company search's payload *is* a bare array, and
#: an empty one is the site answering honestly that it knows no such issuer. That is a fact about
#: the INPUT, not a fetch failure — and separating the two is the entire point of D10, since
#: returning ``[]`` for both let a backfill record a window as covered either way.
INPUT_ERROR_IS_CORRECT: dict[tuple[str, str], tuple[type[Exception], str]] = {
    ("get_sec_documents", "200+[]"): (
        CompanyNotFoundError,
        "an empty company-search array means no such issuer, which is an input error by design",
    ),
}

#: (module, entry point, positional args). Covers every module-level public ``get_*`` that can be
#: driven without a second, differently-shaped response. Excluded ones are listed below with a
#: reason — an honest gap is better than a test that proves nothing.
ENTRY_POINTS: list[tuple[str, str, tuple[Any, ...]]] = [
    # -- SET ------------------------------------------------------------------------------------
    ("settfex.services.set.list", "get_stock_list", ()),
    ("settfex.services.set.news", "get_news", ()),
    ("settfex.services.set.holiday", "get_holidays", ()),
    ("settfex.services.set.index.list", "get_index_list", ()),
    ("settfex.services.set.index.info", "get_index_info_list", ()),
    ("settfex.services.set.index.info", "get_index_info", ("SET50",)),
    ("settfex.services.set.index.composition", "get_index_composition", ("SET50",)),
    ("settfex.services.set.index.chart_quotation", "get_index_chart_quotation", ("SET50",)),
    ("settfex.services.set.stock.highlight_data", "get_highlight_data", ("CPALL",)),
    ("settfex.services.set.stock.info", "get_stock_info", ("CPALL",)),
    ("settfex.services.set.stock.profile_stock", "get_profile", ("CPALL",)),
    ("settfex.services.set.stock.profile_company", "get_company_profile", ("CPALL",)),
    ("settfex.services.set.stock.profile_dr", "get_dr_profile", ("GOOG80",)),
    ("settfex.services.set.stock.corporate_action", "get_corporate_actions", ("CPALL",)),
    ("settfex.services.set.stock.shareholder", "get_shareholder_data", ("CPALL",)),
    ("settfex.services.set.stock.nvdr_holder", "get_nvdr_holder_data", ("CPALL",)),
    ("settfex.services.set.stock.board_of_director", "get_board_of_directors", ("CPALL",)),
    ("settfex.services.set.stock.trading_stat", "get_trading_stats", ("CPALL",)),
    ("settfex.services.set.stock.price_performance", "get_price_performance", ("CPALL",)),
    ("settfex.services.set.stock.chart_quotation", "get_chart_quotation", ("CPALL",)),
    (
        "settfex.services.set.stock.latest_historical_trading",
        "get_latest_historical_trading",
        ("CPALL",),
    ),
    ("settfex.services.set.stock.financial.financial", "get_balance_sheet", ("CPALL",)),
    ("settfex.services.set.stock.financial.financial", "get_income_statement", ("CPALL",)),
    ("settfex.services.set.stock.financial.financial", "get_cash_flow", ("CPALL",)),
    ("settfex.services.set.stock.analyst_consensus", "get_analyst_consensus", ("CPALL",)),
    ("settfex.services.set.stock.analyst_consensus", "get_consensus_overall", ()),
    ("settfex.services.set.earnings_call", "get_earnings_calls", ()),
    # -- TFEX -----------------------------------------------------------------------------------
    ("settfex.services.tfex.list", "get_series_list", ()),
    ("settfex.services.tfex.trading_statistics", "get_trading_statistics", ("S50Z26",)),
    ("settfex.services.tfex.underlying_price", "get_underlying_price", ("S50Z26",)),
    # -- SEC ------------------------------------------------------------------------------------
    ("settfex.services.sec.financial_report", "get_sec_documents", ("CPALL",)),
    # -- ThaiBMA --------------------------------------------------------------------------------
    ("settfex.services.thaibma.yield_curve", "get_government_yield_curve", ()),
    ("settfex.services.thaibma.availability", "get_yield_curve_availability", ()),
]

#: Deliberately excluded, with the reason — each needs a second response of a different shape, so
#: a single injected fault would test the harness rather than the library:
#:   get_latest_price / get_index_latest_price  - chained probes (DR profile, then chart)
#:   get_dr_indicative_price                    - POSTs a foreign host (TradingView)
#:   get_all_earnings_calls, get_earnings_call_detail / _transcript, *_dataframe
#:                                              - fan-out or optional extras (pandas/tqdm)
#:   get_yield_curve_history / get_bond_yield_history
#:                                              - one request per year; covered in the ThaiBMA suite


CASES = [
    (module, name, args, fault)
    for module, name, args in ENTRY_POINTS
    for fault in FAULTS
    if not (fault == "200+[]" and name in EMPTY_IS_LEGITIMATE)
]

#: The cells narrowed out of the matrix above, asserted here instead — so the classification is a
#: documented decision with a test behind it, not a deleted row.
EMPTY_CASES = [
    (module, name, args) for module, name, args in ENTRY_POINTS if name in EMPTY_IS_LEGITIMATE
]


@pytest.mark.parametrize(
    ("module", "name", "args", "fault"),
    CASES,
    ids=[f"{name}[{fault}]" for _, name, _, fault in CASES],
)
@pytest.mark.asyncio
async def test_a_fault_never_returns_a_result(
    module: str, name: str, args: tuple[Any, ...], fault: str
) -> None:
    """I1 + I2: a fault must raise, and raise something ``except FetchError`` catches.

    I1 is the silent-loss invariant: returning *anything* for an injected fault means a caller
    cannot tell a broken upstream from an empty one — the bug behind #123, #127, #131 and #132.

    I2 is what makes I1 actionable: an error nobody can catch with the documented handler is only
    marginally better than no error. A bare ``ValidationError`` for an HTTP 503 fails this.
    """
    entry = getattr(importlib.import_module(module), name)

    async def fake_fetch(self: Any, url: str, headers: Any = None, **kwargs: Any) -> FetchResponse:
        return FAULTS[fault]()

    expected_input_error = INPUT_ERROR_IS_CORRECT.get((name, fault))

    with patch.object(AsyncDataFetcher, "fetch", fake_fetch):
        try:
            result = await entry(*args)
        except FetchError:
            assert expected_input_error is None, (
                f"{name}/{fault} is classified as an input error but raised a FetchError"
            )
            return  # I1 and I2 both satisfied
        except Exception as exc:  # noqa: BLE001 - the matrix is here to classify these
            if expected_input_error is not None:
                kind, reason = expected_input_error
                assert isinstance(exc, kind), (
                    f"{name}/{fault} should raise {kind.__name__} ({reason}), "
                    f"got {type(exc).__name__}"
                )
                return  # a documented input error, not a fault
            pytest.fail(
                f"I2: {name} raised {type(exc).__name__} for {fault}, which is not a FetchError "
                f"and so escapes the documented handler: {exc}"
            )

    pytest.fail(
        f"I1: {name} RETURNED {type(result).__name__} for {fault} instead of raising — a broken "
        f"upstream is indistinguishable from an empty result."
    )


@pytest.mark.parametrize(
    ("module", "name", "args"),
    EMPTY_CASES,
    ids=[name for _, name, _ in EMPTY_CASES],
)
@pytest.mark.asyncio
async def test_a_bare_empty_array_is_a_result_not_a_fault(
    module: str, name: str, args: tuple[Any, ...]
) -> None:
    """The narrowed cells: these endpoints' payload IS a JSON array, so ``[]`` means "none".

    Pinned rather than dropped. Each classification carries its evidence in
    :data:`EMPTY_IS_LEGITIMATE`, and `get_trading_stats` is marked INFERRED there because an empty
    result was never observed — this pins its current behaviour rather than claiming it is right.

    An empty list here is not the silent-loss bug: a fault on these endpoints arrives as a status
    or an unparseable body, both covered by the matrix above, and an invalid symbol arrives as a
    404. ``[]`` is left with exactly one meaning.
    """
    entry = getattr(importlib.import_module(module), name)

    async def fake_fetch(self: Any, url: str, headers: Any = None, **kwargs: Any) -> FetchResponse:
        return FAULTS["200+[]"]()

    with patch.object(AsyncDataFetcher, "fetch", fake_fetch):
        result = await entry(*args)

    assert result == [], f"{name}: {EMPTY_IS_LEGITIMATE[name]}"


# ==================================================================================================
# I4 — the signal survives consumer handling
#
# I1-I3 get a loss as far as the return value. I4 is the other half, and the one this release
# learned last: **a signal that reaches the return value can still be lost on the way out.** The
# #134 containers proved it — the accounting was right there on the object and six of eight
# ordinary list operations dropped it in silence.
#
# Serialization is the boundary that matters most, because function-calling results are JSON: an
# agent never sees the Python object, only what `model_dump()` produced. A field that does not
# serialize does not exist at the tool boundary.
# ==================================================================================================


def _lossy_listing() -> SecDocumentList:
    """A listing carrying every kind of loss this release can record."""
    return SecDocumentList(
        documents=[
            SecDocument(
                company_name="CP ALL PUBLIC COMPANY LIMITED",
                unique_id="0000003875",
                category=DocumentCategory.FINANCIAL_STATEMENT,
                section="Financial Statements",
                year=2025,
                file_url="https://x/a.zip",
                file_id="a.zip",
            )
        ],
        reported_counts={"financial_statement": 12},
        accounting=ListingAccounting(
            rows=3,
            by_category={"financial_statement": RowTally(rows=3, documents=1, no_link=2)},
            failed_codes=[CodeFailure(code="R562", error="boom", error_type="HTTPStatusError")],
            degraded_sections=[
                DegradedSection(category="mda", url="https://x/ViewMore/fs-mda", reason="HTTP 500")
            ],
            unknown_sections=["Some New Section"],
        ),
    )


class TestTheSignalSurvivesSerialization:
    """The tool boundary: what an agent actually receives is JSON, not the object."""

    def test_the_listing_accounting_survives_model_dump(self) -> None:
        dumped = _lossy_listing().model_dump(mode="json")
        assert dumped["accounting"]["has_losses"] is True, "the flag callers branch on"
        assert dumped["accounting"]["no_link"] == 2
        assert dumped["accounting"]["failed_codes"][0]["code"] == "R562"
        assert dumped["accounting"]["degraded_sections"][0]["category"] == "mda"
        assert dumped["reported_counts"] == {"financial_statement": 12}
        assert len(dumped["documents"]) == 1

    def test_it_survives_a_json_round_trip(self) -> None:
        """Strict JSON, then back — what crossing a process or an HTTP boundary really does."""
        restored = SecDocumentList.model_validate(json.loads(_lossy_listing().model_dump_json()))
        assert restored.accounting.has_losses
        assert restored.accounting.no_link == 2
        assert [f.code for f in restored.accounting.failed_codes] == ["R562"]
        assert len(restored) == 1 and restored[0].year == 2025

    def test_the_download_failure_report_survives_model_dump(self) -> None:
        result = DownloadResult(
            files=[],
            failed=[
                FailedDownload(
                    target="https://x/dead.zip", error="soft 404", error_type="FetchError"
                )
            ],
            requested=1,
        )
        dumped = result.model_dump(mode="json")
        assert dumped["is_complete"] is False, "a computed field, so it reaches JSON"
        assert dumped["failed"][0]["error_type"] == "FetchError"
        assert dumped["requested"] == 1

    def test_a_clean_result_serializes_as_clean(self) -> None:
        """The discipline: the signal must be absent, not merely falsy, on healthy data."""
        dumped = SecDocumentList().model_dump(mode="json")
        assert dumped["accounting"]["has_losses"] is False
        assert dumped["accounting"]["failed_codes"] == []
        assert dumped["accounting"]["degraded_sections"] == []


class TestTheSignalSurvivesListLikeHandling:
    """#134's actual failure: the operations a caller reaches for next.

    Slicing and indexing now go through the model. ``sorted()`` and ``list()`` still produce plain
    lists — iteration is kept, so they must — which is why the migration notes say to sort
    ``docs.documents`` and read the accounting off the object the call returned.
    """

    def test_slicing_keeps_the_accounting(self) -> None:
        docs = _lossy_listing()
        sliced = docs[:1]
        assert isinstance(sliced, SecDocumentList), "never a bare list again"
        assert sliced.accounting.has_losses
        assert sliced.accounting.no_link == 2

    def test_a_slice_carries_the_whole_calls_accounting_not_the_slices(self) -> None:
        """Documented, and deliberate: narrowing must not hide a loss from whoever narrowed."""
        docs = _lossy_listing()
        empty_slice = docs[0:0]
        assert len(empty_slice) == 0
        assert empty_slice.accounting.no_link == 2, "the LISTING lost 2 rows; the slice holds none"
        assert empty_slice.reported_counts == {"financial_statement": 12}

    def test_filter_keeps_it_too(self) -> None:
        narrowed = _lossy_listing().filter(category="financial_statement")
        assert narrowed.accounting.has_losses
        assert [f.code for f in narrowed.accounting.failed_codes] == ["R562"]

    def test_indexing_iteration_and_truthiness_are_unchanged(self) -> None:
        docs = _lossy_listing()
        assert len(docs) == 1 and bool(docs) is True
        assert docs[0].file_id == "a.zip"
        assert [d.file_id for d in docs] == ["a.zip"]
        assert not bool(SecDocumentList())

    def test_repr_and_summary_refuse_to_look_whole(self) -> None:
        """A REPL or a log line is a consumer too, and the one a human reads first."""
        docs = _lossy_listing()
        assert "FAILED" in repr(docs) and "R562" in repr(docs)
        assert "DEGRADED" in repr(docs)
        assert "2 row(s) lost" in repr(docs)
        assert "FAILED R562" in docs.summary()

    def test_the_type_change_is_the_one_silent_break(self) -> None:
        """Pinned so it is a known cost, not a surprise: ``isinstance`` takes the other branch."""
        assert not isinstance(_lossy_listing(), list)
        assert not isinstance(DownloadResult(), list)
