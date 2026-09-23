"""``_is_listed_symbol`` — tells an unknown symbol from a listed-but-unserved one (0.25.0).

The original function is imported here at module load, before ``tests/conftest.py``'s autouse
guard replaces the module attribute, so these tests exercise the real thing while every other test
in the suite gets the network-free stand-in. The stock-list request itself is always faked.
"""

from __future__ import annotations

import asyncio
import weakref
from typing import Any

import pytest

import settfex.services.set.list as list_module
from settfex.exceptions import FetchError
from settfex.services.set.list import StockListService
from settfex.services.set.list import _is_listed_symbol as is_listed_symbol


@pytest.fixture(autouse=True)
def _fresh_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(list_module, "_KNOWN_SYMBOLS", None)
    monkeypatch.setattr(list_module, "_LISTING_LOADS", weakref.WeakKeyDictionary())


def _fake_load(monkeypatch: pytest.MonkeyPatch, symbols: list[str] | None) -> list[dict[str, Any]]:
    """Replace the stock-list request; record each call. ``None`` makes the load fail."""
    calls: list[dict[str, Any]] = []

    async def fetch_stock_list(self: StockListService, include_indices: bool = True) -> None:
        calls.append({"include_indices": include_indices, "config": self.config})
        await asyncio.sleep(0)  # let concurrent lookups interleave, as a real request would
        if symbols is None:
            raise FetchError("stock list unavailable", status_code=503)
        monkeypatch.setattr(list_module, "_KNOWN_SYMBOLS", list(symbols))

    monkeypatch.setattr(StockListService, "fetch_stock_list", fetch_stock_list)
    return calls


@pytest.mark.asyncio
class TestIsListedSymbol:
    async def test_an_already_loaded_list_is_used_without_a_request(self, monkeypatch) -> None:
        monkeypatch.setattr(list_module, "_KNOWN_SYMBOLS", ["CPALL", "PTT"])
        calls = _fake_load(monkeypatch, ["unused"])
        assert await is_listed_symbol("cpall") is True
        assert await is_listed_symbol("CPALLL") is False
        assert calls == []

    async def test_the_list_is_loaded_once_even_under_concurrency(self, monkeypatch) -> None:
        calls = _fake_load(monkeypatch, ["CPALL", "PTT"])
        answers = await asyncio.gather(*(is_listed_symbol(s) for s in ["CPALL", "X", "PTT"] * 3))
        assert answers == [True, False, True] * 3
        assert len(calls) == 1, f"{len(calls)} stock-list requests for one lookup batch"

    async def test_the_load_is_one_minimal_request(self, monkeypatch) -> None:
        """A side lookup: no index enrichment (~10 requests), no retry ladder."""
        calls = _fake_load(monkeypatch, ["CPALL"])
        await is_listed_symbol("CPALL")
        [call] = calls
        assert call["include_indices"] is False
        assert call["config"].max_retries == 0

    async def test_a_failed_load_answers_unknowable_and_is_not_retried(self, monkeypatch) -> None:
        calls = _fake_load(monkeypatch, None)
        assert await is_listed_symbol("CPALL") is None
        assert await is_listed_symbol("PTT") is None
        assert len(calls) == 1, "a broken list endpoint must not cost a request per lookup"

    @pytest.mark.parametrize("symbol", ["CPALL-R", "CPALL-F"])
    async def test_a_line_of_a_listed_company_is_listed(self, monkeypatch, symbol: str) -> None:
        monkeypatch.setattr(list_module, "_KNOWN_SYMBOLS", ["CPALL"])
        assert await is_listed_symbol(symbol) is True

    async def test_a_blank_symbol_is_unknowable_without_a_request(self, monkeypatch) -> None:
        calls = _fake_load(monkeypatch, ["CPALL"])
        assert await is_listed_symbol("   ") is None
        assert calls == []
