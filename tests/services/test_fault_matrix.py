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

Invariants asserted here:

* **I1** — a fault never yields a successful-looking result.
* **I2** — every error is in the ``FetchError`` family, so one ``except FetchError`` covers them.

I3 (partial failure recorded *and* logged), I4 (the signal survives ordinary consumer handling,
including serialization) and I5 (one logical answer fails together) are asserted in the
service-specific suites, where the partial-result shapes exist to inspect.
"""

from __future__ import annotations

import importlib
from typing import Any
from unittest.mock import patch

import pytest

from settfex.exceptions import FetchError
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


#: The faults. Each is a response a real origin can and does produce.
FAULTS: dict[str, Any] = {
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


def _ids() -> list[str]:
    return [f"{name}[{fault}]" for _, name, _ in ENTRY_POINTS for fault in FAULTS]


CASES = [(module, name, args, fault) for module, name, args in ENTRY_POINTS for fault in FAULTS]


@pytest.mark.parametrize(("module", "name", "args", "fault"), CASES, ids=_ids())
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

    with patch.object(AsyncDataFetcher, "fetch", fake_fetch):
        try:
            result = await entry(*args)
        except FetchError:
            return  # I1 and I2 both satisfied
        except Exception as exc:  # noqa: BLE001 - the matrix is here to classify these
            pytest.fail(
                f"I2: {name} raised {type(exc).__name__} for {fault}, which is not a FetchError "
                f"and so escapes the documented handler: {exc}"
            )

    pytest.fail(
        f"I1: {name} RETURNED {type(result).__name__} for {fault} instead of raising — a broken "
        f"upstream is indistinguishable from an empty result."
    )
