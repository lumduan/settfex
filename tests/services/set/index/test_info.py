"""Tests for the SET market index info (quotation) service."""

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from settfex.services.set.index.info import (
    IndexInfo,
    IndexInfoListResponse,
    IndexInfoService,
    get_index_info,
    get_index_info_list,
)
from settfex.utils.data_fetcher import FetcherConfig, FetchResponse

# Thailand has no DST, so a fixed +07:00 offset is equivalent to Asia/Bangkok.
BKK = timezone(timedelta(hours=7))

# Live /api/set/index/SET50/info payload shape (values trimmed).
SAMPLE_INFO: dict[str, Any] = {
    "symbol": "SET50",
    "nameEN": "SET50",
    "nameTH": "SET50",
    "prior": 1071.84,
    "open": 1074.13,
    "high": 1081.17,
    "low": 1072.86,
    "last": 1078.25,
    "change": 6.41,
    "percentChange": 0.6,
    "volume": 1178627200,
    "value": 34883715617.84,
    "querySymbol": "SET50",
    "marketStatus": "Open2",
    "marketDateTime": "2026-07-16T14:18:29.086034922+07:00",
    "marketName": "SET",
    "industryName": "",
    "sectorName": "",
    "level": "INDEX",
}

SAMPLE_INFO_LIST: dict[str, Any] = {
    "indexIndustrySectors": [
        SAMPLE_INFO,
        {
            "symbol": "sSET",
            "nameEN": "sSET",
            "nameTH": "sSET",
            "prior": 658.2,
            "open": 660.31,
            "high": 666.15,
            "low": 660.2,
            "last": 664.65,
            "change": 6.45,
            "percentChange": 0.98,
            "volume": 380518100,
            "value": 1428656002.0,
            "querySymbol": "sSET",
            "marketStatus": "Open2",
            "marketDateTime": "2026-07-16T14:18:59.08648785+07:00",
            "marketName": "SET",
            "industryName": "",
            "sectorName": "",
            "level": "INDEX",
        },
    ]
}


def _response(payload: dict[str, Any], status_code: int = 200) -> FetchResponse:
    """Build a FetchResponse whose body is ``payload`` serialized as JSON."""
    body = json.dumps(payload)
    return FetchResponse(
        status_code=status_code,
        content=body.encode("utf-8"),
        text=body,
        headers={},
        url="https://www.set.or.th/api/set/index/SET50/info?language=en",
        elapsed=0.1,
    )


@pytest.fixture
def mock_fetcher():
    """Patch AsyncDataFetcher inside the index info module; yield its async instance."""
    with patch("settfex.services.set.index.info.AsyncDataFetcher") as mock:
        fetcher_instance = AsyncMock()
        mock.return_value.__aenter__.return_value = fetcher_instance
        mock.return_value.__aexit__.return_value = None
        mock.get_set_api_headers = Mock(return_value={"Accept": "application/json"})
        fetcher_instance.cls = mock
        yield fetcher_instance


class TestIndexInfoModel:
    """Pydantic parsing: camelCase aliases, tz-aware timestamp, nullable numerics."""

    def test_aliases_and_values(self):
        info = IndexInfo.model_validate(SAMPLE_INFO)
        assert info.symbol == "SET50"
        assert info.prior == 1071.84
        assert info.last == 1078.25
        assert info.percent_change == 0.6
        assert info.query_symbol == "SET50"
        assert info.market_status == "Open2"
        assert info.market_name == "SET"
        assert info.level == "INDEX"

    def test_market_date_time_is_tz_aware_bangkok(self):
        info = IndexInfo.model_validate(SAMPLE_INFO)
        assert info.market_date_time is not None
        assert info.market_date_time.tzinfo is not None
        assert info.market_date_time.utcoffset() == timedelta(hours=7)
        assert info.market_date_time.replace(microsecond=0) == datetime(
            2026, 7, 16, 14, 18, 29, tzinfo=BKK
        )

    def test_minimal_payload_defaults_none(self):
        info = IndexInfo.model_validate({"symbol": "SET50"})
        assert info.last is None
        assert info.percent_change is None
        assert info.market_date_time is None

    def test_empty_string_datetime_becomes_none(self):
        info = IndexInfo.model_validate({"symbol": "SET50", "marketDateTime": ""})
        assert info.market_date_time is None


@pytest.mark.asyncio
class TestIndexInfoService:
    """Single-index fetch: URL/language/referer, case preservation, error handling."""

    async def test_init_default_and_custom_config(self):
        assert IndexInfoService().base_url == "https://www.set.or.th"
        service = IndexInfoService(config=FetcherConfig(timeout=60))
        assert service.config.timeout == 60

    async def test_fetch_success(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE_INFO)
        info = await IndexInfoService().fetch_index_info("SET50")
        assert isinstance(info, IndexInfo)
        assert info.last == 1078.25
        assert info.market_status == "Open2"

    async def test_fetch_url_and_language(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE_INFO)
        await IndexInfoService().fetch_index_info("SET50", lang="th")
        url = mock_fetcher.fetch.call_args.args[0]
        assert "/api/set/index/SET50/info" in url
        assert "language=th" in url

    async def test_fetch_preserves_sset_casing_and_lowercases_referer(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE_INFO)
        await IndexInfoService().fetch_index_info(" sSET ")
        url = mock_fetcher.fetch.call_args.args[0]
        assert "/api/set/index/sSET/info" in url  # NOT uppercased to SSET
        referer = mock_fetcher.cls.get_set_api_headers.call_args.kwargs["referer"]
        assert referer == "https://www.set.or.th/en/market/index/sset/overview"

    async def test_fetch_empty_symbol_raises(self):
        with pytest.raises(ValueError, match="symbol cannot be empty"):
            await IndexInfoService().fetch_index_info("   ")

    async def test_fetch_invalid_language_raises(self):
        with pytest.raises(ValueError, match="Invalid language"):
            await IndexInfoService().fetch_index_info("SET50", lang="jp")  # type: ignore[arg-type]  # intentional: runtime-permissive language

    async def test_fetch_http_error_raises(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response({}, status_code=404)
        with pytest.raises(Exception, match="HTTP 404"):
            await IndexInfoService().fetch_index_info("NOPE")

    async def test_fetch_raw_success(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE_INFO)
        raw = await IndexInfoService().fetch_index_info_raw("SET50")
        assert isinstance(raw, dict)
        assert raw["last"] == 1078.25


@pytest.mark.asyncio
class TestIndexInfoList:
    """All-indices fetch via the info/list endpoint and its envelope unwrapping."""

    async def test_fetch_default_type_index(self, mock_fetcher):
        mock_fetcher.fetch_json.return_value = SAMPLE_INFO_LIST
        quotes = await IndexInfoService().fetch_index_info_list()
        assert len(quotes) == 2
        assert all(isinstance(q, IndexInfo) for q in quotes)
        assert quotes[1].symbol == "sSET"
        url = mock_fetcher.fetch_json.call_args.args[0]
        assert "/api/set/index/info/list" in url
        assert "type=INDEX" in url
        assert "language=en" in url

    async def test_fetch_industry_type(self, mock_fetcher):
        mock_fetcher.fetch_json.return_value = SAMPLE_INFO_LIST
        await IndexInfoService().fetch_index_info_list(index_type="INDUSTRY")
        assert "type=INDUSTRY" in mock_fetcher.fetch_json.call_args.args[0]

    async def test_fetch_uses_default_referer(self, mock_fetcher):
        mock_fetcher.fetch_json.return_value = SAMPLE_INFO_LIST
        await IndexInfoService().fetch_index_info_list()
        assert mock_fetcher.cls.get_set_api_headers.call_args.kwargs == {}

    async def test_envelope_model(self):
        response = IndexInfoListResponse.model_validate(SAMPLE_INFO_LIST)
        assert len(response.index_industry_sectors) == 2

    async def test_fetch_raw_returns_envelope_dict(self, mock_fetcher):
        mock_fetcher.fetch_json.return_value = SAMPLE_INFO_LIST
        raw = await IndexInfoService().fetch_index_info_list_raw()
        assert "indexIndustrySectors" in raw


@pytest.mark.asyncio
class TestConvenienceFunctions:
    """Top-level get_index_info and get_index_info_list."""

    async def test_get_index_info(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE_INFO)
        info = await get_index_info("SET50")
        assert isinstance(info, IndexInfo)
        assert info.symbol == "SET50"

    async def test_get_index_info_list(self, mock_fetcher):
        mock_fetcher.fetch_json.return_value = SAMPLE_INFO_LIST
        quotes = await get_index_info_list(index_type="INDEX")
        assert [q.symbol for q in quotes] == ["SET50", "sSET"]
