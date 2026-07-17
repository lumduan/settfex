"""Tests for the SET stock list service, incl. the index-membership enrichment."""

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from settfex.services.set.index.composition import IndexCompositionResponse
from settfex.services.set.index.list import IndexListResponse, IndexSymbol
from settfex.services.set.list import (
    StockListResponse,
    StockListService,
    StockSymbol,
    get_stock_list,
)
from settfex.utils.data_fetcher import FetcherConfig


def _stock(symbol: str, market: str = "SET", industry: str = "SERVICE") -> dict[str, Any]:
    """Build one realistic securitySymbols row."""
    return {
        "symbol": symbol,
        "nameTH": f"{symbol} (TH)",
        "nameEN": f"{symbol} (EN)",
        "market": market,
        "securityType": "S",
        "typeSequence": 1,
        "industry": industry,
        "sector": "COMM",
        "querySector": "comm",
        "isIFF": False,
        "isForeignListing": False,
        "remark": "",
    }


SAMPLE_STOCK_LIST: dict[str, Any] = {
    "securitySymbols": [
        _stock("CPALL"),
        _stock("AAA", industry="INDUS"),
        _stock("PTT", industry="RESOURC"),
    ]
}


def _index_entry(symbol: str, level: str = "INDEX", market: str = "SET") -> IndexSymbol:
    return IndexSymbol(
        symbol=symbol, market=market, level=level, parent_index=None, query_symbol=symbol
    )


def _composition(index_symbol: str, stock_symbols: list[str]) -> IndexCompositionResponse:
    return IndexCompositionResponse.model_validate(
        {
            "composition": {
                "symbol": index_symbol,
                "stockInfos": [{"symbol": s} for s in stock_symbols],
                "subIndices": None,
            },
            "indexInfos": [],
        }
    )


@pytest.fixture
def mock_fetcher():
    """Patch AsyncDataFetcher inside the stock list module; yield its async instance."""
    with patch("settfex.services.set.list.AsyncDataFetcher") as mock:
        fetcher_instance = AsyncMock()
        mock.return_value.__aenter__.return_value = fetcher_instance
        mock.return_value.__aexit__.return_value = None
        mock.get_set_api_headers = Mock(return_value={"Accept": "application/json"})
        fetcher_instance.fetch_json.return_value = SAMPLE_STOCK_LIST
        fetcher_instance.cls = mock
        yield fetcher_instance


@pytest.fixture
def mock_index_services():
    """Patch the index services the enrichment lazily imports.

    Default wiring: directory has SET/mai (must be excluded) + SET50 and SETESG targets;
    SET50 contains CPALL+AAA, SETESG contains CPALL only. Tests override side effects as
    needed. Yields (mock IndexListService class, mock IndexCompositionService class).
    """
    with (
        patch("settfex.services.set.index.list.IndexListService") as mock_ils,
        patch("settfex.services.set.index.composition.IndexCompositionService") as mock_ics,
    ):
        directory = IndexListResponse(
            indices=[
                _index_entry("SET"),
                _index_entry("SET50"),
                _index_entry("SETESG"),
                _index_entry("mai", market="mai"),
                _index_entry("AGRO", level="INDUSTRY"),  # non-INDEX level: never a target
            ]
        )
        mock_ils.return_value.fetch_index_list = AsyncMock(return_value=directory)
        mock_ics.return_value.fetch_composition = AsyncMock(
            side_effect=[
                _composition("SET50", ["CPALL", "AAA"]),
                _composition("SETESG", ["CPALL"]),
            ]
        )
        yield mock_ils, mock_ics


class TestStockSymbolModel:
    """Alias parsing and the new ``indices`` enrichment field."""

    def test_aliases(self):
        stock = StockSymbol.model_validate(_stock("CPALL"))
        assert stock.symbol == "CPALL"
        assert stock.name_en == "CPALL (EN)"
        assert stock.security_type == "S"
        assert stock.is_foreign_listing is False

    def test_indices_defaults_to_empty_list(self):
        stock = StockSymbol.model_validate(_stock("CPALL"))
        assert stock.indices == []

    def test_indices_accepts_explicit_value(self):
        stock = StockSymbol.model_validate({**_stock("CPALL"), "indices": ["SET50"]})
        assert stock.indices == ["SET50"]


class TestStockListResponse:
    """Count, filters (incl. the new filter_by_index), and symbol lookup."""

    @pytest.fixture
    def response(self) -> StockListResponse:
        response = StockListResponse.model_validate(SAMPLE_STOCK_LIST)
        response.security_symbols[0].indices = ["SET50", "SETESG"]  # CPALL
        response.security_symbols[1].indices = ["sSET"]  # AAA
        return response

    def test_count(self, response):
        assert response.count == 3

    def test_filter_by_market(self, response):
        assert len(response.filter_by_market("set")) == 3
        assert response.filter_by_market("mai") == []

    def test_filter_by_industry(self, response):
        assert [s.symbol for s in response.filter_by_industry("resourc")] == ["PTT"]

    def test_get_symbol_case_insensitive(self, response):
        found = response.get_symbol("cpall")
        assert found is not None
        assert found.symbol == "CPALL"
        assert response.get_symbol("NOPE") is None

    def test_filter_by_index(self, response):
        assert [s.symbol for s in response.filter_by_index("SET50")] == ["CPALL"]
        assert [s.symbol for s in response.filter_by_index("SETESG")] == ["CPALL"]

    def test_filter_by_index_case_insensitive(self, response):
        assert [s.symbol for s in response.filter_by_index("sset")] == ["AAA"]

    def test_filter_by_index_unknown_returns_empty(self, response):
        assert response.filter_by_index("SETHD") == []


@pytest.mark.asyncio
class TestStockListService:
    """Service I/O and the default-on index-membership enrichment."""

    async def test_init_default_and_custom_config(self):
        assert StockListService().base_url == "https://www.set.or.th"
        service = StockListService(config=FetcherConfig(timeout=60))
        assert service.config.timeout == 60

    async def test_fetch_url(self, mock_fetcher, mock_index_services):
        await StockListService().fetch_stock_list()
        assert "/api/set/stock/list" in mock_fetcher.fetch_json.call_args.args[0]

    async def test_enrichment_default_on_multi_composition(self, mock_fetcher, mock_index_services):
        _, mock_ics = mock_index_services
        response = await StockListService().fetch_stock_list()

        cpall = response.get_symbol("CPALL")
        aaa = response.get_symbol("AAA")
        ptt = response.get_symbol("PTT")
        assert cpall is not None and cpall.indices == ["SET50", "SETESG"]
        assert aaa is not None and aaa.indices == ["SET50"]
        assert ptt is not None and ptt.indices == []

        # Only the two sub-index targets are fetched — never SET/mai/industries
        fetch_composition = mock_ics.return_value.fetch_composition
        assert fetch_composition.await_count == 2
        requested = [c.args[0] for c in fetch_composition.await_args_list]
        assert requested == ["SET50", "SETESG"]

    async def test_enrichment_uses_query_symbol_for_fetch(self, mock_fetcher):
        # A target whose query_symbol differs from symbol must be fetched by query_symbol.
        with (
            patch("settfex.services.set.index.list.IndexListService") as mock_ils,
            patch("settfex.services.set.index.composition.IndexCompositionService") as mock_ics,
        ):
            directory = IndexListResponse(
                indices=[
                    IndexSymbol(
                        symbol="sSET",
                        market="SET",
                        level="INDEX",
                        parent_index=None,
                        query_symbol="sSET-q",
                    )
                ]
            )
            mock_ils.return_value.fetch_index_list = AsyncMock(return_value=directory)
            mock_ics.return_value.fetch_composition = AsyncMock(
                return_value=_composition("sSET", ["cpall"])
            )
            response = await StockListService().fetch_stock_list()
            assert mock_ics.return_value.fetch_composition.await_args.args == ("sSET-q",)
            # Membership maps case-insensitively and stores the canonical symbol
            cpall = response.get_symbol("CPALL")
            assert cpall is not None and cpall.indices == ["sSET"]

    async def test_include_indices_false_skips_index_services(self, mock_fetcher):
        with (
            patch("settfex.services.set.index.list.IndexListService") as mock_ils,
            patch("settfex.services.set.index.composition.IndexCompositionService") as mock_ics,
        ):
            response = await StockListService().fetch_stock_list(include_indices=False)
            mock_ils.assert_not_called()
            mock_ics.assert_not_called()
        assert all(s.indices == [] for s in response.security_symbols)
        assert mock_fetcher.fetch_json.await_count == 1

    async def test_partial_composition_failure_is_tolerated(
        self, mock_fetcher, mock_index_services
    ):
        _, mock_ics = mock_index_services
        mock_ics.return_value.fetch_composition.side_effect = [
            Exception("HTTP 403"),
            _composition("SETESG", ["CPALL"]),
        ]
        response = await StockListService().fetch_stock_list()
        cpall = response.get_symbol("CPALL")
        aaa = response.get_symbol("AAA")
        assert cpall is not None and cpall.indices == ["SETESG"]  # SET50 skipped
        assert aaa is not None and aaa.indices == []

    async def test_total_enrichment_failure_returns_unenriched_list(self, mock_fetcher):
        with patch("settfex.services.set.index.list.IndexListService") as mock_ils:
            mock_ils.return_value.fetch_index_list = AsyncMock(
                side_effect=Exception("index API down")
            )
            response = await StockListService().fetch_stock_list()
        assert response.count == 3
        assert all(s.indices == [] for s in response.security_symbols)

    async def test_fetch_raw_untouched_by_enrichment(self, mock_fetcher):
        raw = await StockListService().fetch_stock_list_raw()
        assert isinstance(raw, dict)
        assert "securitySymbols" in raw
        assert "indices" not in raw["securitySymbols"][0]


@pytest.mark.asyncio
class TestConvenienceFunctions:
    """Top-level get_stock_list passes include_indices through."""

    async def test_get_stock_list_default_enriches(self, mock_fetcher, mock_index_services):
        response = await get_stock_list()
        cpall = response.get_symbol("CPALL")
        assert cpall is not None and cpall.indices == ["SET50", "SETESG"]

    async def test_get_stock_list_opt_out(self, mock_fetcher):
        with patch("settfex.services.set.index.list.IndexListService") as mock_ils:
            response = await get_stock_list(include_indices=False)
            mock_ils.assert_not_called()
        assert response.count == 3
