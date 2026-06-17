"""Tests for TFEX trading statistics service (validation + response-shape hardening)."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic import ValidationError

from settfex.services.tfex.trading_statistics import (
    TradingStatistics,
    TradingStatisticsService,
    get_trading_statistics,
)
from settfex.utils.parsing import ResponseParseError

MOCK_TRADING_STATS = {
    "symbol": "S50Z25",
    "marketTime": "2025-10-05T17:00:00+07:00",
    "lastTradingDate": "2025-12-29T16:30:00+07:00",
    "dayToMaturity": 85,
    "settlementPattern": "#,##0.0",
    "isOptions": False,
    "theoreticalPrice": 850.5,
    "priorSettlementPrice": 848.0,
    "settlementPrice": 851.2,
    "im": 9600.0,
    "mm": 6720.0,
    "hasTheoreticalPrice": True,
}


@pytest.fixture
def mock_fetcher():
    """Mock AsyncDataFetcher with an async-context-manager returning fetch_json results."""
    with patch("settfex.services.tfex.trading_statistics.AsyncDataFetcher") as mock:
        fetcher_instance = AsyncMock()
        mock.return_value.__aenter__.return_value = fetcher_instance
        mock.return_value.__aexit__.return_value = None
        mock.get_set_api_headers = Mock(return_value={"Accept": "application/json"})
        yield fetcher_instance


class TestTradingStatisticsService:
    @pytest.mark.asyncio
    async def test_fetch_success(self, mock_fetcher) -> None:
        mock_fetcher.fetch_json.return_value = MOCK_TRADING_STATS
        result = await TradingStatisticsService().fetch_trading_statistics("s50z25")
        assert isinstance(result, TradingStatistics)
        assert result.symbol == "S50Z25"
        assert result.day_to_maturity == 85
        assert result.settlement_price == 851.2

    @pytest.mark.asyncio
    async def test_fetch_missing_required_field_raises(self, mock_fetcher) -> None:
        bad = {k: v for k, v in MOCK_TRADING_STATS.items() if k != "dayToMaturity"}
        mock_fetcher.fetch_json.return_value = bad
        with pytest.raises(ValidationError):
            await TradingStatisticsService().fetch_trading_statistics("S50Z25")

    @pytest.mark.asyncio
    async def test_raw_rejects_non_dict_response(self, mock_fetcher) -> None:
        # Replaces the old `assert isinstance(data, dict)` (stripped under -O).
        mock_fetcher.fetch_json.return_value = ["unexpected", "list"]
        with pytest.raises(ResponseParseError, match="S50Z25"):
            await TradingStatisticsService().fetch_trading_statistics_raw("S50Z25")

    @pytest.mark.asyncio
    async def test_raw_success_returns_dict(self, mock_fetcher) -> None:
        mock_fetcher.fetch_json.return_value = MOCK_TRADING_STATS
        raw = await TradingStatisticsService().fetch_trading_statistics_raw("S50Z25")
        assert raw["symbol"] == "S50Z25"


class TestConvenienceFunction:
    @pytest.mark.asyncio
    async def test_get_trading_statistics(self, mock_fetcher) -> None:
        mock_fetcher.fetch_json.return_value = MOCK_TRADING_STATS
        result = await get_trading_statistics("S50Z25")
        assert isinstance(result, TradingStatistics)
        assert result.symbol == "S50Z25"
