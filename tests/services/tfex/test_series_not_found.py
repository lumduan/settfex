"""An unknown TFEX series raises SeriesNotFoundError (0.27.0), and nothing that caught it before stops.

Live-probed 2026-11-03: ``ZZZZ99`` answered HTTP 404 on both per-series endpoints, which reached
callers as a plain ``HTTPStatusError(404)``. The SET stock endpoints raise ``SymbolNotFoundError``,
so ``except NotFoundError`` caught a bad stock symbol and silently missed every bad TFEX series. A
downstream consumer nearly shipped exactly that catch.

The new class is a strict subclass of ``HTTPStatusError`` that keeps ``status_code``, ``url`` and
``symbol``, so this is additive under the deprecation policy. These tests pin both halves: the new
catch works, and every old catch still works.
"""

from collections.abc import Awaitable, Callable, Iterator
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from settfex.exceptions import FetchError, HTTPStatusError, NotFoundError, SeriesNotFoundError
from settfex.services.tfex.list import TFEXSeriesListService
from settfex.services.tfex.trading_statistics import (
    TradingStatisticsService,
    get_trading_statistics,
)
from settfex.services.tfex.underlying_price import (
    TFEXUnderlyingPriceService,
    get_underlying_price,
)

URL = "https://www.set.or.th/api/set/tfex/series/ZZZZ99/x"


def _http_error(status: int) -> HTTPStatusError:
    """What AsyncDataFetcher.fetch_json raises for a non-2xx answer."""
    return HTTPStatusError(f"Request failed: HTTP {status} for {URL}.", status_code=status, url=URL)


def _patched(module: str) -> Iterator[AsyncMock]:
    with patch(f"settfex.services.tfex.{module}.AsyncDataFetcher") as mock:
        fetcher = AsyncMock()
        mock.return_value.__aenter__.return_value = fetcher
        mock.return_value.__aexit__.return_value = None
        mock.get_set_api_headers = Mock(return_value={"Accept": "application/json"})
        yield fetcher


CALLS: list[tuple[str, str, Callable[[str], Awaitable[Any]]]] = [
    (
        "trading_statistics",
        "fetch_trading_statistics",
        lambda s: TradingStatisticsService().fetch_trading_statistics(s),
    ),
    (
        "trading_statistics",
        "fetch_trading_statistics_raw",
        lambda s: TradingStatisticsService().fetch_trading_statistics_raw(s),
    ),
    ("trading_statistics", "get_trading_statistics", lambda s: get_trading_statistics(s)),
    (
        "underlying_price",
        "TFEXUnderlyingPriceService.get_underlying_price",
        lambda s: TFEXUnderlyingPriceService().get_underlying_price(s),
    ),
    (
        "underlying_price",
        "get_underlying_price_raw",
        lambda s: TFEXUnderlyingPriceService().get_underlying_price_raw(s),
    ),
    ("underlying_price", "get_underlying_price", lambda s: get_underlying_price(s)),
]
IDS = [name for _, name, _ in CALLS]


@pytest.mark.asyncio
@pytest.mark.parametrize(("module", "name", "call"), CALLS, ids=IDS)
async def test_a_404_is_a_series_not_found_error(
    module: str, name: str, call: Callable[[str], Awaitable[Any]]
) -> None:
    for fetcher in _patched(module):
        boom = _http_error(404)
        fetcher.fetch_json.side_effect = boom
        with pytest.raises(SeriesNotFoundError) as excinfo:
            await call("zzzz99")

    exc = excinfo.value
    assert exc.status_code == 404
    assert exc.symbol == "ZZZZ99", "the normalized symbol rides on the error"
    assert exc.url == URL
    assert exc.__cause__ is boom, "the transport error stays reachable"
    assert "ZZZZ99" in str(exc)


@pytest.mark.asyncio
@pytest.mark.parametrize(("module", "name", "call"), CALLS, ids=IDS)
async def test_every_catch_written_against_0_26_still_catches_it(
    module: str, name: str, call: Callable[[str], Awaitable[Any]]
) -> None:
    """Additive, not a change: HTTPStatusError and FetchError handlers keep working."""
    for fetcher in _patched(module):
        fetcher.fetch_json.side_effect = _http_error(404)
        with pytest.raises(HTTPStatusError) as excinfo:
            await call("ZZZZ99")
    assert isinstance(excinfo.value, FetchError)
    assert isinstance(excinfo.value, NotFoundError), "and the new do-not-retry catch works too"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 403, 429, 500, 503])
@pytest.mark.parametrize(("module", "name", "call"), CALLS, ids=IDS)
async def test_any_other_status_stays_a_plain_http_status_error(
    module: str, name: str, call: Callable[[str], Awaitable[Any]], status: int
) -> None:
    """Only a 404 means "unknown series"; a 503 must stay retryable, never a NotFoundError."""
    for fetcher in _patched(module):
        boom = _http_error(status)
        fetcher.fetch_json.side_effect = boom
        with pytest.raises(HTTPStatusError) as excinfo:
            await call("S50Z26")
    assert excinfo.value is boom
    assert not isinstance(excinfo.value, NotFoundError)


@pytest.mark.asyncio
async def test_the_series_list_404_is_not_an_unknown_series() -> None:
    """The list endpoint takes no symbol, so its 404 means a wrong route and stays generic."""
    for fetcher in _patched("list"):
        boom = _http_error(404)
        fetcher.fetch_json.side_effect = boom
        with pytest.raises(HTTPStatusError) as excinfo:
            await TFEXSeriesListService().fetch_series_list()
    assert excinfo.value is boom
    assert not isinstance(excinfo.value, SeriesNotFoundError)
