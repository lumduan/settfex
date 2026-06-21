"""Tests for the SET stock latest-historical-trading service."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest

from settfex.services.set.stock.latest_historical_trading import (
    LatestHistoricalTrading,
    LatestHistoricalTradingService,
    get_latest_historical_trading,
)
from settfex.services.set.stock.stock import Stock
from settfex.utils.data_fetcher import FetcherConfig, FetchResponse

BKK = timezone(timedelta(hours=7))

# Real API response shape for CPALL (captured from the live endpoint). `nav` / `marketIndex` /
# `marketPercentChange` come back null for ordinary stocks.
SAMPLE: dict = {
    "date": "2026-06-19T00:00:00+07:00",
    "symbol": "CPALL",
    "prior": 46.75,
    "open": 46.75,
    "high": 46.75,
    "low": 46.0,
    "average": 46.44,
    "close": 46.5,
    "change": -0.25,
    "percentChange": -0.53,
    "totalVolume": 54470359.0,
    "totalValue": 2529470234.5,
    "pe": 13.93,
    "pbv": 2.8,
    "bookValuePerShare": 16.63,
    "dividendYield": 3.55,
    "marketCap": 417714212682.0,
    "listedShare": 8983101348.0,
    "par": 1.0,
    "financialDate": "2026-03-31T00:00:00+07:00",
    "nav": None,
    "marketIndex": None,
    "marketPercentChange": None,
}


def _response(payload: dict) -> FetchResponse:
    """Build a 200 FetchResponse whose body is ``payload`` serialized as JSON."""
    body = json.dumps(payload)
    return FetchResponse(
        status_code=200,
        content=body.encode("utf-8"),
        text=body,
        headers={},
        url="https://www.set.or.th/api/set/stock/CPALL/latest-historical-trading",
        elapsed=0.1,
    )


@pytest.fixture
def mock_fetcher():
    """Patch AsyncDataFetcher in the service module; yield its async instance.

    The patched class mock is attached as ``.cls`` for referer assertions.
    """
    with patch("settfex.services.set.stock.latest_historical_trading.AsyncDataFetcher") as mock:
        fetcher_instance = AsyncMock()
        mock.return_value.__aenter__.return_value = fetcher_instance
        mock.return_value.__aexit__.return_value = None
        mock.get_set_api_headers = Mock(return_value={"Accept": "application/json"})
        fetcher_instance.cls = mock
        yield fetcher_instance


class TestModelParsing:
    """Pydantic parsing: camelCase aliases, datetimes, nullable fields."""

    def test_aliases_and_values(self):
        data = LatestHistoricalTrading.model_validate(SAMPLE)
        assert data.symbol == "CPALL"
        assert data.close == 46.5
        assert data.percent_change == -0.53  # percentChange
        assert data.total_volume == 54470359.0  # totalVolume
        assert data.total_value == 2529470234.5  # totalValue
        assert data.pe == 13.93
        assert data.pbv == 2.8
        assert data.book_value_per_share == 16.63  # bookValuePerShare
        assert data.dividend_yield == 3.55  # dividendYield
        assert data.market_cap == 417714212682.0  # marketCap
        assert data.listed_share == 8983101348.0  # listedShare

    def test_datetime_fields(self):
        data = LatestHistoricalTrading.model_validate(SAMPLE)
        assert data.date == datetime(2026, 6, 19, 0, 0, tzinfo=BKK)
        assert data.financial_date == datetime(2026, 3, 31, 0, 0, tzinfo=BKK)

    def test_nullable_fields(self):
        data = LatestHistoricalTrading.model_validate(SAMPLE)
        assert data.nav is None
        assert data.market_index is None  # marketIndex
        assert data.market_percent_change is None  # marketPercentChange


@pytest.mark.asyncio
class TestLatestHistoricalTradingService:
    """Service I/O: fetch, raw fetch, URL/referer construction, error handling."""

    async def test_init_default_and_custom_config(self):
        assert LatestHistoricalTradingService().base_url == "https://www.set.or.th"
        service = LatestHistoricalTradingService(config=FetcherConfig(timeout=60, max_retries=5))
        assert service.config.timeout == 60
        assert service.config.max_retries == 5

    async def test_fetch_success(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        result = await LatestHistoricalTradingService().fetch_latest_historical_trading("CPALL")
        assert isinstance(result, LatestHistoricalTrading)
        assert result.symbol == "CPALL"
        assert result.close == 46.5
        assert result.pe == 13.93

    async def test_fetch_url_and_referer_and_symbol_normalization(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        # lowercase input -> normalized to upper
        await LatestHistoricalTradingService().fetch_latest_historical_trading("cpall")
        url = mock_fetcher.fetch.call_args.args[0]
        assert url == "https://www.set.or.th/api/set/stock/CPALL/latest-historical-trading"
        # this service builds a Thai (/th/) referer
        referer = mock_fetcher.cls.get_set_api_headers.call_args.kwargs["referer"]
        assert referer == "https://www.set.or.th/th/market/product/stock/quote/CPALL/price"

    async def test_fetch_empty_symbol_raises(self):
        with pytest.raises(ValueError, match="symbol cannot be empty"):
            await LatestHistoricalTradingService().fetch_latest_historical_trading("   ")

    async def test_fetch_http_error_raises(self, mock_fetcher):
        mock_fetcher.fetch.return_value = FetchResponse(
            status_code=404, content=b"", text="", headers={}, url="x", elapsed=0.1
        )
        with pytest.raises(Exception, match="HTTP 404"):
            await LatestHistoricalTradingService().fetch_latest_historical_trading("CPALL")

    async def test_fetch_raw_success(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        raw = await LatestHistoricalTradingService().fetch_latest_historical_trading_raw("CPALL")
        assert isinstance(raw, dict)
        assert raw["symbol"] == "CPALL"
        assert raw["pbv"] == 2.8

    async def test_fetch_raw_http_error_raises(self, mock_fetcher):
        mock_fetcher.fetch.return_value = FetchResponse(
            status_code=500, content=b"", text="", headers={}, url="x", elapsed=0.1
        )
        with pytest.raises(Exception, match="HTTP 500"):
            await LatestHistoricalTradingService().fetch_latest_historical_trading_raw("CPALL")

    async def test_fetch_raw_empty_symbol_raises(self):
        with pytest.raises(ValueError, match="symbol cannot be empty"):
            await LatestHistoricalTradingService().fetch_latest_historical_trading_raw("")


@pytest.mark.asyncio
class TestConvenienceAndStock:
    """Top-level convenience function and the unified Stock accessor."""

    async def test_get_latest_historical_trading(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        result = await get_latest_historical_trading("CPALL")
        assert isinstance(result, LatestHistoricalTrading)
        assert result.market_cap == 417714212682.0

    async def test_stock_get_latest_historical_trading(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        result = await Stock("CPALL").get_latest_historical_trading()
        assert isinstance(result, LatestHistoricalTrading)
        assert result.close == 46.5
