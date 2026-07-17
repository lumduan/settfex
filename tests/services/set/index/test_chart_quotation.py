"""Tests for the SET market index chart quotation service (reuses the stock models)."""

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from settfex.services.set.index.chart_quotation import (
    IndexChartQuotationService,
    get_index_chart_quotation,
    get_index_latest_price,
)
from settfex.services.set.stock.chart_quotation import ChartQuotation, Quotation
from settfex.utils.data_fetcher import FetchResponse

# Thailand has no DST, so a fixed +07:00 offset is equivalent to Asia/Bangkok.
BKK = timezone(timedelta(hours=7))

# Trimmed 1D index series: pre-open null bucket, two traded minutes, trailing null bucket.
SAMPLE_CHART: dict[str, Any] = {
    "prior": 1071.84,
    "intermissions": [
        {"begin": "2026-07-16T12:30:00", "end": "2026-07-16T13:45:00"},
    ],
    "quotations": [
        {
            "datetime": "2026-07-16T09:45:00+07:00",
            "localDatetime": "2026-07-16T09:45:00",
            "price": 1071.84,
            "volume": None,
            "value": None,
            "change": None,
            "percentChange": None,
        },
        {
            "datetime": "2026-07-16T10:00:00+07:00",
            "localDatetime": "2026-07-16T10:00:00",
            "price": 1074.13,
            "volume": 120000,
            "value": 3500000.0,
            "change": 2.29,
            "percentChange": 0.21,
        },
        {
            "datetime": "2026-07-16T10:30:00+07:00",
            "localDatetime": "2026-07-16T10:30:00",
            "price": 1078.25,
            "volume": 98000,
            "value": 2800000.0,
            "change": 6.41,
            "percentChange": 0.6,
        },
        {
            "datetime": "2026-07-16T16:00:00+07:00",
            "localDatetime": "2026-07-16T16:00:00",
            "price": 1078.25,
            "volume": None,
            "value": None,
            "change": None,
            "percentChange": None,
        },
    ],
}


def _at(hour: int, minute: int = 0) -> datetime:
    """Return an aware Asia/Bangkok instant on the sample's trading day (2026-07-16)."""
    return datetime(2026, 7, 16, hour, minute, tzinfo=BKK)


def _response(payload: dict[str, Any], status_code: int = 200) -> FetchResponse:
    """Build a FetchResponse whose body is ``payload`` serialized as JSON."""
    body = json.dumps(payload)
    return FetchResponse(
        status_code=status_code,
        content=body.encode("utf-8"),
        text=body,
        headers={},
        url="https://www.set.or.th/api/set/index/SET50/chart-quotation?period=1D",
        elapsed=0.1,
    )


@pytest.fixture
def mock_fetcher():
    """Patch AsyncDataFetcher inside the index chart_quotation module."""
    with patch("settfex.services.set.index.chart_quotation.AsyncDataFetcher") as mock:
        fetcher_instance = AsyncMock()
        mock.return_value.__aenter__.return_value = fetcher_instance
        mock.return_value.__aexit__.return_value = None
        mock.get_set_api_headers = Mock(return_value={"Accept": "application/json"})
        fetcher_instance.cls = mock
        yield fetcher_instance


@pytest.mark.asyncio
class TestIndexChartQuotationService:
    """Service I/O: reuses the stock ChartQuotation model over the index endpoint."""

    async def test_fetch_returns_stock_chart_quotation_model(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE_CHART)
        result = await IndexChartQuotationService().fetch_chart_quotation("SET50")
        assert isinstance(result, ChartQuotation)
        assert result.prior == 1071.84
        assert len(result.quotations) == 4

    async def test_fetch_url_and_default_query(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE_CHART)
        await IndexChartQuotationService().fetch_chart_quotation("SET50")
        url = mock_fetcher.fetch.call_args.args[0]
        assert "/api/set/index/SET50/chart-quotation" in url
        assert "period=1D" in url
        assert "accumulated=false" in url

    async def test_fetch_preserves_sset_casing_and_referer(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE_CHART)
        await IndexChartQuotationService().fetch_chart_quotation("sSET", period="5D")
        url = mock_fetcher.fetch.call_args.args[0]
        assert "/api/set/index/sSET/chart-quotation" in url
        assert "period=5D" in url
        referer = mock_fetcher.cls.get_set_api_headers.call_args.kwargs["referer"]
        assert referer == "https://www.set.or.th/en/market/index/sset/overview"

    async def test_fetch_empty_symbol_raises(self):
        with pytest.raises(ValueError, match="symbol cannot be empty"):
            await IndexChartQuotationService().fetch_chart_quotation("  ")

    async def test_fetch_http_error_raises(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response({}, status_code=403)
        with pytest.raises(Exception, match="HTTP 403"):
            await IndexChartQuotationService().fetch_chart_quotation("SET50")

    async def test_fetch_raw_success(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE_CHART)
        raw = await IndexChartQuotationService().fetch_chart_quotation_raw("SET50")
        assert isinstance(raw, dict)
        assert raw["prior"] == 1071.84


@pytest.mark.asyncio
class TestConvenienceFunctions:
    """Top-level get_index_chart_quotation and get_index_latest_price."""

    async def test_get_index_chart_quotation(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE_CHART)
        result = await get_index_chart_quotation("SET50")
        assert isinstance(result, ChartQuotation)
        assert result.prior == 1071.84

    async def test_get_index_latest_price_returns_latest_traded(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE_CHART)
        q = await get_index_latest_price("SET50", as_of=_at(11, 0))
        assert isinstance(q, Quotation)
        assert q.price == 1078.25
        assert q.local_datetime == datetime(2026, 7, 16, 10, 30)

    async def test_get_index_latest_price_none_before_open(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE_CHART)
        assert await get_index_latest_price("SET50", as_of=_at(9, 0)) is None
