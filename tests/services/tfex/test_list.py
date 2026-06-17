"""Tests for TFEX series list service (validation + response-shape hardening)."""

from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from settfex.services.tfex.list import (
    TFEXSeriesListResponse,
    TFEXSeriesListService,
    get_series_list,
)
from settfex.utils.parsing import ResponseParseError

MOCK_SERIES = {
    "symbol": "S50Z25",
    "instrumentId": "SET50_FC",
    "instrumentName": "SET50 Futures",
    "marketListId": "TXI_F",
    "marketListName": "Equity Index Futures",
    "firstTradingDate": "2024-01-02T00:00:00+07:00",
    "lastTradingDate": "2025-12-29T16:30:00+07:00",
    "contractMonth": "12/2025",
    "optionsType": "",
    "strikePrice": None,
    "hasNightSession": True,
    "underlying": "SET50",
    "active": True,
}
MOCK_SERIES_LIST = {"series": [MOCK_SERIES]}


@pytest.fixture
def mock_fetcher():
    with patch("settfex.services.tfex.list.AsyncDataFetcher") as mock:
        fetcher_instance = AsyncMock()
        mock.return_value.__aenter__.return_value = fetcher_instance
        mock.return_value.__aexit__.return_value = None
        yield fetcher_instance


class TestSeriesListService:
    @pytest.mark.asyncio
    async def test_fetch_success(self, mock_fetcher) -> None:
        mock_fetcher.fetch_json.return_value = MOCK_SERIES_LIST
        result = await TFEXSeriesListService().fetch_series_list()
        assert isinstance(result, TFEXSeriesListResponse)
        assert result.count == 1
        assert result.series[0].symbol == "S50Z25"
        assert result.get_futures()[0].symbol == "S50Z25"

    @pytest.mark.asyncio
    async def test_fetch_invalid_series_item_raises(self, mock_fetcher) -> None:
        bad_series = {k: v for k, v in MOCK_SERIES.items() if k != "symbol"}
        mock_fetcher.fetch_json.return_value = {"series": [bad_series]}
        with pytest.raises(ValidationError):
            await TFEXSeriesListService().fetch_series_list()

    @pytest.mark.asyncio
    async def test_raw_rejects_non_dict_response(self, mock_fetcher) -> None:
        # Replaces the old `assert isinstance(data, dict)` (stripped under -O).
        mock_fetcher.fetch_json.return_value = ["unexpected", "list"]
        with pytest.raises(ResponseParseError, match="series-list"):
            await TFEXSeriesListService().fetch_series_list_raw()


class TestConvenienceFunction:
    @pytest.mark.asyncio
    async def test_get_series_list(self, mock_fetcher) -> None:
        mock_fetcher.fetch_json.return_value = MOCK_SERIES_LIST
        result = await get_series_list()
        assert isinstance(result, TFEXSeriesListResponse)
        assert result.count == 1
