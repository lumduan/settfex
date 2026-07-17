"""Tests for the network-free 'did you mean?' symbol suggestion on SymbolNotFoundError."""

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

import settfex.services.set.list as list_module
from settfex.exceptions import FetchError, SymbolNotFoundError, raise_for_status
from settfex.services.set.list import StockListService, suggest_symbol


def _stock(symbol: str) -> dict[str, Any]:
    """Minimal securitySymbols row."""
    return {
        "symbol": symbol,
        "nameTH": f"{symbol} TH",
        "nameEN": f"{symbol} EN",
        "market": "SET",
        "securityType": "S",
        "typeSequence": 1,
        "industry": "SERVICE",
        "sector": "COMM",
        "querySector": "comm",
        "isIFF": False,
        "isForeignListing": False,
        "remark": "",
    }


@pytest.fixture(autouse=True)
def _reset_symbol_cache():
    """Isolate the process-global symbol cache between tests."""
    original = list_module._KNOWN_SYMBOLS
    list_module._KNOWN_SYMBOLS = None
    yield
    list_module._KNOWN_SYMBOLS = original


# --- suggest_symbol ---------------------------------------------------------------------------


def test_suggest_symbol_returns_close_match() -> None:
    list_module._KNOWN_SYMBOLS = ["CPALL", "PTT", "KBANK", "SCB"]
    assert suggest_symbol("CPALLL") == "CPALL"
    assert suggest_symbol("cpall") == "CPALL"  # query is case-insensitive


def test_suggest_symbol_no_cache_returns_none_and_never_fetches() -> None:
    assert list_module._KNOWN_SYMBOLS is None
    # A fetch would construct AsyncDataFetcher — prove suggest_symbol does not.
    with patch("settfex.services.set.list.AsyncDataFetcher") as fetcher:
        assert suggest_symbol("CPALL") is None
    fetcher.assert_not_called()


def test_suggest_symbol_no_close_match_returns_none() -> None:
    list_module._KNOWN_SYMBOLS = ["CPALL", "PTT"]
    assert suggest_symbol("ZZZZ") is None


def test_suggest_symbol_empty_input_returns_none() -> None:
    list_module._KNOWN_SYMBOLS = ["CPALL"]
    assert suggest_symbol("") is None


# --- SymbolNotFoundError.suggestion + raise_for_status ----------------------------------------


def test_symbol_not_found_error_carries_suggestion_and_message() -> None:
    exc = SymbolNotFoundError("HTTP 404", status_code=404, symbol="CPALLL", suggestion="CPALL")
    assert exc.suggestion == "CPALL"
    assert exc.symbol == "CPALLL"
    assert exc.status_code == 404
    assert "did you mean 'CPALL'" in str(exc)
    assert isinstance(exc, FetchError)  # still catchable as FetchError / Exception


def test_symbol_not_found_error_without_suggestion_leaves_message_clean() -> None:
    exc = SymbolNotFoundError("HTTP 404", status_code=404, symbol="X")
    assert exc.suggestion is None
    assert "did you mean" not in str(exc)


def test_raise_for_status_404_warm_cache_suggests() -> None:
    list_module._KNOWN_SYMBOLS = ["CPALL", "PTT", "KBANK"]
    with pytest.raises(SymbolNotFoundError) as ei:
        raise_for_status(
            404, "Failed to fetch highlight data for CPALLL: HTTP 404", symbol="CPALLL"
        )
    assert ei.value.suggestion == "CPALL"
    assert "did you mean 'CPALL'" in str(ei.value)


def test_raise_for_status_404_cold_cache_no_suggestion() -> None:
    assert list_module._KNOWN_SYMBOLS is None
    with pytest.raises(SymbolNotFoundError) as ei:
        raise_for_status(404, "Failed to fetch data for CPALLL: HTTP 404", symbol="CPALLL")
    assert ei.value.suggestion is None


def test_raise_for_status_404_suggest_false_skips_stock_list() -> None:
    """Index lookups pass suggest=False, so an index typo is never matched against stock symbols."""
    list_module._KNOWN_SYMBOLS = ["CPALL", "PTT", "SCB", "SCC"]
    with pytest.raises(SymbolNotFoundError) as ei:
        raise_for_status(
            404, "Failed to fetch index info for SCG: HTTP 404", symbol="SCG", suggest=False
        )
    assert ei.value.suggestion is None


def test_raise_for_status_non_404_is_plain_fetch_error() -> None:
    list_module._KNOWN_SYMBOLS = ["CPALL"]
    with pytest.raises(FetchError) as ei:
        raise_for_status(500, "Failed: HTTP 500", symbol="CPALLL")
    assert not isinstance(ei.value, SymbolNotFoundError)
    assert ei.value.status_code == 500


# --- integration: a real fetch populates the cache (no separate fetch for suggestions) ---------


@pytest.mark.asyncio
async def test_fetch_stock_list_populates_cache_for_suggestions() -> None:
    payload = {"securitySymbols": [_stock("CPALL"), _stock("PTT"), _stock("KBANK")]}
    with patch("settfex.services.set.list.AsyncDataFetcher") as mock:
        inst = AsyncMock()
        mock.return_value.__aenter__.return_value = inst
        mock.return_value.__aexit__.return_value = None
        mock.get_set_api_headers = Mock(return_value={})
        inst.fetch_json.return_value = payload
        await StockListService().fetch_stock_list(include_indices=False)
    assert list_module._KNOWN_SYMBOLS == ["CPALL", "PTT", "KBANK"]
    assert suggest_symbol("CPALLL") == "CPALL"
