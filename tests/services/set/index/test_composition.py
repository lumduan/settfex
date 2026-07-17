"""Tests for the SET market index composition (constituents) service."""

import json
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from settfex.services.set.index.composition import (
    BidOffer,
    IndexComposition,
    IndexCompositionResponse,
    IndexCompositionService,
    IndexConstituent,
    get_index_composition,
)
from settfex.services.set.index.info import IndexInfo
from settfex.utils.data_fetcher import FetchResponse

# Live /api/set/index/SET50/composition payload shape: one full constituent row (CPALL-like,
# with the string bid/offer prices the API really sends), one minimal row with null ladders.
SAMPLE_COMPOSITION: dict[str, Any] = {
    "composition": {
        "symbol": "SET50",
        "nameEN": "SET50",
        "nameTH": "SET50",
        "stockInfos": [
            {
                "symbol": "CPALL",
                "sign": "",
                "prior": 46.25,
                "last": 46.75,
                "open": 46.5,
                "high": 47.0,
                "low": 46.25,
                "average": 46.64,
                "floor": 32.5,
                "ceiling": 60.0,
                "change": 0.5,
                "percentChange": 1.08,
                "totalVolume": 18519650.0,
                "totalValue": 863820650.0,
                "trVolume": None,
                "trValue": None,
                "aomVolume": 18500000.0,
                "aomValue": 863000000.0,
                "bids": [{"volume": 323200.0, "price": "46.50"}],
                "offers": [{"volume": 206300.0, "price": "46.75"}],
                "marketStatus": "Open2",
                "marketDateTime": "2026-07-16T14:18:59.08648785+07:00",
                "securityType": "S",
                "tickSize": 0.25,
                "nameEN": "CP ALL PUBLIC COMPANY LIMITED",
                "nameTH": "บริษัท ซีพี ออลล์ จำกัด (มหาชน)",
                "marketName": "SET",
                "industryName": "SERVICE",
                "sectorName": "COMM",
                "isNPG": False,
                "high52Weeks": 60.0,
                "low52Weeks": 40.0,
                "par": 1.0,
                "inav": None,
                "multiplier": None,
                "exerciseRatio": "1 : 1",
                "exercisePrice": None,
                "exercisePriceUnit": "THB",
                "maturityDate": None,
                "lastTradingDate": None,
                "underlying": "",
                "isIFF": False,
                "isPFUND": False,
                "statisticsAsOf": "2026-07-15T00:00:00+07:00",
                "marketCap": 419884744750.0,
                "peRatio": 15.9,
                "pbRatio": 3.2,
                "dividendYield": 2.8,
                "nvdrNetVolume": -2927196.0,
                "listedShare": 8983101348,
                "ttm": None,
                "moneynessStatus": None,
                "moneynessPercent": None,
            },
            {
                "symbol": "ADVANC",
                "bids": None,
                "offers": None,
            },
        ],
        "subIndices": None,
    },
    "indexInfos": [
        {
            "symbol": "SET50",
            "nameEN": "SET50",
            "prior": 1071.84,
            "last": 1078.25,
            "change": 6.41,
            "percentChange": 0.6,
            "marketStatus": "Open2",
            "marketDateTime": "2026-07-16T14:18:59.08648785+07:00",
            "level": "INDEX",
        }
    ],
}

# SET industry indices (e.g. 'AGRO') return no stocks — just their sector quotes.
SAMPLE_INDUSTRY_DRILLDOWN: dict[str, Any] = {
    "composition": {
        "symbol": "AGRO",
        "nameEN": "Agro & Food Industry",
        "nameTH": "เกษตรและอุตสาหกรรมอาหาร",
        "stockInfos": [],
        "subIndices": [
            {"symbol": "AGRI", "nameEN": "Agribusiness", "last": 120.5, "level": "SECTOR"},
            {"symbol": "FOOD", "nameEN": "Food & Beverage", "last": 233.1, "level": "SECTOR"},
        ],
    },
    "indexInfos": [{"symbol": "AGRO", "last": 334.35, "level": "INDUSTRY"}],
}


def _response(payload: dict[str, Any], status_code: int = 200) -> FetchResponse:
    """Build a FetchResponse whose body is ``payload`` serialized as JSON."""
    body = json.dumps(payload)
    return FetchResponse(
        status_code=status_code,
        content=body.encode("utf-8"),
        text=body,
        headers={},
        url="https://www.set.or.th/api/set/index/SET50/composition?language=en",
        elapsed=0.1,
    )


@pytest.fixture
def mock_fetcher():
    """Patch AsyncDataFetcher inside the composition module; yield its async instance."""
    with patch("settfex.services.set.index.composition.AsyncDataFetcher") as mock:
        fetcher_instance = AsyncMock()
        mock.return_value.__aenter__.return_value = fetcher_instance
        mock.return_value.__aexit__.return_value = None
        mock.get_set_api_headers = Mock(return_value={"Accept": "application/json"})
        fetcher_instance.cls = mock
        yield fetcher_instance


class TestBidOfferModel:
    """The API sends ladder prices as strings; blanks/placeholders must become None."""

    def test_string_price_coerces_to_float(self):
        bo = BidOffer.model_validate({"volume": 323200.0, "price": "46.50"})
        assert bo.price == 46.5
        assert isinstance(bo.price, float)
        assert bo.volume == 323200.0

    def test_blank_and_placeholder_strings_become_none(self):
        assert BidOffer.model_validate({"volume": "", "price": ""}).price is None
        assert BidOffer.model_validate({"volume": "-", "price": "-"}).volume is None
        assert BidOffer.model_validate({"price": "  "}).price is None

    def test_numeric_passthrough_and_defaults(self):
        bo = BidOffer.model_validate({"price": 46.5})
        assert bo.price == 46.5
        assert bo.volume is None


class TestIndexConstituentModel:
    """Alias parsing, null-ladder handling, minimal payloads, best bid/offer shortcuts."""

    def test_full_row_aliases(self):
        row = IndexConstituent.model_validate(SAMPLE_COMPOSITION["composition"]["stockInfos"][0])
        assert row.symbol == "CPALL"
        assert row.percent_change == 1.08
        assert row.total_volume == 18519650.0
        assert row.total_value == 863820650.0
        assert row.high_52_weeks == 60.0
        assert row.pe_ratio == 15.9
        assert row.is_npg is False
        assert row.security_type == "S"
        assert row.exercise_ratio == "1 : 1"
        assert row.market_date_time is not None
        assert row.market_date_time.utcoffset() == timedelta(hours=7)

    def test_bid_price_string_coerced_inside_row(self):
        row = IndexConstituent.model_validate(SAMPLE_COMPOSITION["composition"]["stockInfos"][0])
        assert row.bids[0].price == 46.5
        assert row.offers[0].price == 46.75
        assert row.best_bid == 46.5
        assert row.best_offer == 46.75

    def test_null_ladders_become_empty_lists(self):
        row = IndexConstituent.model_validate(SAMPLE_COMPOSITION["composition"]["stockInfos"][1])
        assert row.bids == []
        assert row.offers == []
        assert row.best_bid is None
        assert row.best_offer is None

    def test_minimal_payload_defaults(self):
        row = IndexConstituent.model_validate({"symbol": "X"})
        assert row.last is None
        assert row.market_cap is None
        assert row.bids == []

    def test_empty_string_dates_become_none(self):
        row = IndexConstituent.model_validate(
            {"symbol": "X", "maturityDate": "", "statisticsAsOf": " "}
        )
        assert row.maturity_date is None
        assert row.statistics_as_of is None


class TestIndexCompositionResponse:
    """Response shortcuts and the SET-industry sector drilldown shape."""

    def test_properties(self):
        response = IndexCompositionResponse.model_validate(SAMPLE_COMPOSITION)
        assert response.count == 2
        assert response.symbols == ["CPALL", "ADVANC"]
        assert len(response.constituents) == 2
        assert response.index_info is not None
        assert response.index_info.last == 1078.25

    def test_get_constituent_case_insensitive(self):
        response = IndexCompositionResponse.model_validate(SAMPLE_COMPOSITION)
        found = response.get_constituent("cpall")
        assert found is not None
        assert found.symbol == "CPALL"
        assert response.get_constituent("NOPE") is None

    def test_industry_drilldown_shape(self):
        response = IndexCompositionResponse.model_validate(SAMPLE_INDUSTRY_DRILLDOWN)
        assert response.count == 0
        assert response.composition.sub_indices is not None
        assert len(response.composition.sub_indices) == 2
        assert all(isinstance(sub, IndexInfo) for sub in response.composition.sub_indices)
        assert response.composition.sub_indices[0].symbol == "AGRI"

    def test_null_stock_infos_becomes_empty_list(self):
        composition = IndexComposition.model_validate({"symbol": "AGRO", "stockInfos": None})
        assert composition.stock_infos == []


@pytest.mark.asyncio
class TestIndexCompositionService:
    """Service I/O: fetch, URL/referer, empty symbol, the SET/mai 404 message, raw."""

    async def test_fetch_success(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE_COMPOSITION)
        response = await IndexCompositionService().fetch_composition("SET50")
        assert isinstance(response, IndexCompositionResponse)
        assert response.count == 2
        assert response.constituents[0].bids[0].price == 46.5

    async def test_fetch_url_language_and_referer(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE_COMPOSITION)
        await IndexCompositionService().fetch_composition("SETESG", lang="th")
        url = mock_fetcher.fetch.call_args.args[0]
        assert "/api/set/index/SETESG/composition" in url
        assert "language=th" in url
        referer = mock_fetcher.cls.get_set_api_headers.call_args.kwargs["referer"]
        assert referer == "https://www.set.or.th/en/market/index/setesg/overview"

    async def test_fetch_preserves_agro_m_casing(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE_INDUSTRY_DRILLDOWN)
        await IndexCompositionService().fetch_composition("AGRO-m")
        assert "/api/set/index/AGRO-m/composition" in mock_fetcher.fetch.call_args.args[0]

    async def test_fetch_empty_symbol_raises(self):
        with pytest.raises(ValueError, match="symbol cannot be empty"):
            await IndexCompositionService().fetch_composition("")

    async def test_fetch_404_explains_whole_market_indices(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response({}, status_code=404)
        with pytest.raises(Exception, match="no composition endpoint"):
            await IndexCompositionService().fetch_composition("SET")

    async def test_fetch_other_http_error_generic_message(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response({}, status_code=500)
        with pytest.raises(Exception, match="HTTP 500"):
            await IndexCompositionService().fetch_composition("SET50")

    async def test_fetch_raw_success(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE_COMPOSITION)
        raw = await IndexCompositionService().fetch_composition_raw("SET50")
        assert isinstance(raw, dict)
        assert "composition" in raw
        assert raw["composition"]["stockInfos"][0]["bids"][0]["price"] == "46.50"


@pytest.mark.asyncio
class TestConvenienceFunctions:
    """Top-level get_index_composition."""

    async def test_get_index_composition(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE_COMPOSITION)
        response = await get_index_composition("SET50")
        assert isinstance(response, IndexCompositionResponse)
        assert response.symbols == ["CPALL", "ADVANC"]
