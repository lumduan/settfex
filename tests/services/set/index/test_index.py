"""Tests for the unified SetIndex facade class."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest

from settfex.services.set.index.composition import IndexCompositionResponse, IndexConstituent
from settfex.services.set.index.index import SetIndex
from settfex.services.set.index.info import IndexInfo
from settfex.services.set.stock.chart_quotation import ChartQuotation, Quotation
from settfex.utils.data_fetcher import FetcherConfig, FetchResponse

BKK = timezone(timedelta(hours=7))

SAMPLE_INFO: dict = {
    "symbol": "SET50",
    "last": 1078.25,
    "change": 6.41,
    "percentChange": 0.6,
    "marketStatus": "Open2",
    "level": "INDEX",
}

SAMPLE_COMPOSITION: dict = {
    "composition": {
        "symbol": "SET50",
        "stockInfos": [
            {"symbol": "CPALL", "last": 46.75},
            {"symbol": "PTT", "last": 38.5},
        ],
        "subIndices": None,
    },
    "indexInfos": [SAMPLE_INFO],
}

SAMPLE_CHART: dict = {
    "prior": 1071.84,
    "intermissions": [],
    "quotations": [
        {
            "datetime": "2026-07-16T10:30:00+07:00",
            "localDatetime": "2026-07-16T10:30:00",
            "price": 1078.25,
            "volume": 98000,
            "value": 2800000.0,
            "change": 6.41,
            "percentChange": 0.6,
        },
    ],
}


def _response(payload: dict) -> FetchResponse:
    body = json.dumps(payload)
    return FetchResponse(
        status_code=200, content=body.encode("utf-8"), text=body, headers={}, url="x", elapsed=0.1
    )


def _patch_fetcher(module: str, payload: dict):
    """Context manager patching AsyncDataFetcher in ``module`` to return ``payload``."""
    patcher = patch(f"settfex.services.set.index.{module}.AsyncDataFetcher")
    mock = patcher.start()
    fetcher_instance = AsyncMock()
    mock.return_value.__aenter__.return_value = fetcher_instance
    mock.return_value.__aexit__.return_value = None
    mock.get_set_api_headers = Mock(return_value={"Accept": "application/json"})
    fetcher_instance.fetch.return_value = _response(payload)
    return patcher, fetcher_instance


class TestSetIndexInit:
    """Symbol normalization (strip, no uppercase), repr/str, lazy service creation."""

    def test_symbol_stripped_but_casing_preserved(self):
        assert SetIndex(" sSET ").symbol == "sSET"
        assert SetIndex("SET50").symbol == "SET50"
        assert SetIndex("AGRO-m").symbol == "AGRO-m"

    def test_repr_and_str(self):
        index = SetIndex("SET50")
        assert repr(index) == "SetIndex(symbol='SET50')"
        assert str(index) == "SET50"

    def test_config_passthrough(self):
        config = FetcherConfig(timeout=60)
        index = SetIndex("SET50", config=config)
        assert index.config is config
        assert index.info_service.config is config

    def test_services_are_lazy_and_cached(self):
        index = SetIndex("SET50")
        assert index._info_service is None
        assert index._composition_service is None
        assert index._chart_quotation_service is None
        assert index.info_service is index.info_service
        assert index.composition_service is index.composition_service
        assert index.chart_quotation_service is index.chart_quotation_service


@pytest.mark.asyncio
class TestSetIndexIntegration:
    """Facade methods delegate to the underlying services."""

    async def test_get_info(self):
        patcher, fetcher = _patch_fetcher("info", SAMPLE_INFO)
        try:
            info = await SetIndex("SET50").get_info()
            assert isinstance(info, IndexInfo)
            assert info.last == 1078.25
            assert "/api/set/index/SET50/info" in fetcher.fetch.call_args.args[0]
        finally:
            patcher.stop()

    async def test_get_composition_and_constituents(self):
        patcher, _ = _patch_fetcher("composition", SAMPLE_COMPOSITION)
        try:
            index = SetIndex("SET50")
            composition = await index.get_composition()
            assert isinstance(composition, IndexCompositionResponse)
            assert composition.count == 2

            constituents = await index.get_constituents()
            assert all(isinstance(c, IndexConstituent) for c in constituents)
            assert [c.symbol for c in constituents] == ["CPALL", "PTT"]
        finally:
            patcher.stop()

    async def test_get_chart_quotation_and_latest_price(self):
        patcher, _ = _patch_fetcher("chart_quotation", SAMPLE_CHART)
        try:
            index = SetIndex("SET50")
            chart = await index.get_chart_quotation()
            assert isinstance(chart, ChartQuotation)
            assert chart.prior == 1071.84

            q = await index.get_latest_price(as_of=datetime(2026, 7, 16, 11, 0, tzinfo=BKK))
            assert isinstance(q, Quotation)
            assert q.price == 1078.25

            pre_open = await index.get_latest_price(as_of=datetime(2026, 7, 16, 9, 0, tzinfo=BKK))
            assert pre_open is None
        finally:
            patcher.stop()
