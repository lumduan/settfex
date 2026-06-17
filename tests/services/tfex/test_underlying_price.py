"""Tests for TFEX underlying price service (validation + response-shape hardening)."""

from collections.abc import Iterator
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic import ValidationError

from settfex.services.tfex.underlying_price import (
    TFEXUnderlyingPriceService,
    UnderlyingPrice,
    get_underlying_price,
)
from settfex.utils.data_fetcher import AsyncDataFetcher
from settfex.utils.parsing import ResponseParseError

# Real live response shape captured for series S50M26C880 (underlying = SET50 index).
MOCK_UNDERLYING_PRICE = {
    "symbol": "SET50",
    "sign": "",
    "prior": 1027.83,
    "high": 1029.4,
    "low": 1020.16,
    "last": 1028.46,
    "change": 0.63,
    "percentChange": 0.06,
    "totalVolume": 1874003100.0,
    "totalValue": 45186543947.0,
    "marketStatus": "Closed",
    "marketTime": "2026-06-17T20:42:45.165793313+07:00",
    "underlyingType": "I",
    "statisticsAsOf": "2026-06-17T00:00:00+07:00",
    "pe": 15.39,
    "pbv": 1.53,
}


@pytest.fixture
def mock_fetcher() -> Iterator[AsyncMock]:
    """Mock AsyncDataFetcher with an async-context-manager returning fetch_json results."""
    with patch("settfex.services.tfex.underlying_price.AsyncDataFetcher") as mock:
        fetcher_instance = AsyncMock()
        mock.return_value.__aenter__.return_value = fetcher_instance
        mock.return_value.__aexit__.return_value = None
        mock.get_set_api_headers = Mock(return_value={"Accept": "application/json"})
        yield fetcher_instance


class TestTFEXUnderlyingPriceService:
    def test_init_uses_default_config(self) -> None:
        service = TFEXUnderlyingPriceService()
        assert service.base_url == "https://www.tfex.co.th"
        assert service.config is not None

    @pytest.mark.asyncio
    async def test_fetch_success(self, mock_fetcher: AsyncMock) -> None:
        mock_fetcher.fetch_json.return_value = MOCK_UNDERLYING_PRICE
        result = await TFEXUnderlyingPriceService().get_underlying_price("s50m26c880")
        assert isinstance(result, UnderlyingPrice)
        assert result.symbol == "SET50"
        assert result.last == 1028.46
        assert result.change == 0.63
        assert result.percent_change == 0.06
        assert result.total_volume == 1874003100.0
        assert result.market_status == "Closed"
        assert result.underlying_type == "I"
        assert result.pe == 15.39
        assert result.pbv == 1.53
        # tz-offset ISO strings parse into aware datetimes
        assert result.market_time.year == 2026
        assert result.market_time.utcoffset() is not None
        assert result.statistics_as_of.tzinfo is not None

    @pytest.mark.asyncio
    async def test_fetch_normalizes_symbol_in_url(self, mock_fetcher: AsyncMock) -> None:
        mock_fetcher.fetch_json.return_value = MOCK_UNDERLYING_PRICE
        await TFEXUnderlyingPriceService().get_underlying_price("  s50m26c880  ")
        called_url = mock_fetcher.fetch_json.call_args[0][0]
        assert called_url.endswith("/api/set/tfex/series/S50M26C880/underlying-price")

    @pytest.mark.asyncio
    async def test_fetch_missing_required_field_raises(self, mock_fetcher: AsyncMock) -> None:
        bad = {k: v for k, v in MOCK_UNDERLYING_PRICE.items() if k != "marketStatus"}
        mock_fetcher.fetch_json.return_value = bad
        with pytest.raises(ValidationError):
            await TFEXUnderlyingPriceService().get_underlying_price("S50M26C880")

    @pytest.mark.asyncio
    async def test_fetch_nullable_financial_fields_accept_none(
        self, mock_fetcher: AsyncMock
    ) -> None:
        payload = {**MOCK_UNDERLYING_PRICE, "pe": None, "pbv": None, "last": None}
        mock_fetcher.fetch_json.return_value = payload
        result = await TFEXUnderlyingPriceService().get_underlying_price("S50M26C880")
        assert result.pe is None
        assert result.pbv is None
        assert result.last is None

    @pytest.mark.asyncio
    async def test_fetch_rejects_non_finite_financial_field(self) -> None:
        """The audit's headline guarantee: NaN/Infinity in a financial field is rejected.

        decode_json (used by fetch_json) rejects the non-finite JSON literal, so a malformed
        price can never reach the model. We drive the real decode path here instead of the
        AsyncDataFetcher mock so the guard is genuinely exercised.
        """
        body = (
            '{"symbol":"SET50","sign":"","prior":1027.83,"high":1029.4,"low":1020.16,'
            '"last":NaN,"change":0.63,"percentChange":0.06,"totalVolume":1874003100.0,'
            '"totalValue":45186543947.0,"marketStatus":"Closed",'
            '"marketTime":"2026-06-17T20:42:45.165793313+07:00","underlyingType":"I",'
            '"statisticsAsOf":"2026-06-17T00:00:00+07:00","pe":15.39,"pbv":1.53}'
        )
        fake_response = Mock()
        fake_response.text = body
        with (
            patch.object(AsyncDataFetcher, "fetch", AsyncMock(return_value=fake_response)),
            pytest.raises(ResponseParseError, match="non-finite"),
        ):
            await TFEXUnderlyingPriceService().get_underlying_price("S50M26C880")

    @pytest.mark.asyncio
    async def test_raw_rejects_non_dict_response(self, mock_fetcher: AsyncMock) -> None:
        # Replaces the old `assert isinstance(data, dict)` (stripped under -O).
        mock_fetcher.fetch_json.return_value = ["unexpected", "list"]
        with pytest.raises(ResponseParseError, match="S50M26C880"):
            await TFEXUnderlyingPriceService().get_underlying_price_raw("S50M26C880")

    @pytest.mark.asyncio
    async def test_raw_success_returns_dict(self, mock_fetcher: AsyncMock) -> None:
        mock_fetcher.fetch_json.return_value = MOCK_UNDERLYING_PRICE
        raw = await TFEXUnderlyingPriceService().get_underlying_price_raw("S50M26C880")
        assert raw["symbol"] == "SET50"


class TestConvenienceFunction:
    @pytest.mark.asyncio
    async def test_get_underlying_price(self, mock_fetcher: AsyncMock) -> None:
        mock_fetcher.fetch_json.return_value = MOCK_UNDERLYING_PRICE
        result = await get_underlying_price("S50M26C880")
        assert isinstance(result, UnderlyingPrice)
        assert result.symbol == "SET50"
        assert result.last == 1028.46
