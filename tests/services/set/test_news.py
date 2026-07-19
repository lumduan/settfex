"""Tests for the SET news search service."""

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from settfex.exceptions import (
    FetchError,
    InvalidDateError,
    InvalidLanguageError,
    InvalidSymbolError,
    SymbolNotFoundError,
)
from settfex.services.set.news import (
    NewsItem,
    NewsSearchResponse,
    NewsService,
    get_news,
)
from settfex.services.set.stock.stock import Stock
from settfex.utils.data_fetcher import FetcherConfig, FetchResponse
from settfex.utils.parsing import ResponseParseError

# Thailand has no DST, so a fixed +07:00 offset is equivalent to Asia/Bangkok.
BKK = timezone(timedelta(hours=7))

# Sample test data based on the actual API response (live-verified 2026-07-19).
SAMPLE: dict[str, Any] = {
    "totalCount": 3,
    "newsInfoList": [
        {
            "id": "105467000",
            "datetime": "2026-07-17T21:06:00+07:00",
            "symbol": "CPALL",
            "source": "CPALL",
            "url": (
                "https://www.set.or.th/en/market/news-and-alert/newsdetails"
                "?id=105467000&symbol=CPALL"
            ),
            "headline": "Financial Performance Quarter 2 (F45)",
            "isTodayNews": False,
            "viewClarification": None,
            "marketAlertTypeId": None,
            "percentPriceChange": None,
            "tag": "financial-statement",
            "product": "S",
            "lang": "en",
        },
        {
            "id": "105467001",
            "datetime": "2026-07-17T08:00:00+07:00",
            "symbol": "PTT",
            "source": "PTT",
            "url": (
                "https://www.set.or.th/en/market/news-and-alert/newsdetails?id=105467001&symbol=PTT"
            ),
            "headline": "Notification of the Resignation of the Chief Executive Officer",
            "isTodayNews": True,
            "viewClarification": None,
            "marketAlertTypeId": None,
            "percentPriceChange": None,
            "tag": "",
            "product": "S",
            "lang": "en",
        },
        {
            "id": "105467002",
            "datetime": "2026-07-17T17:30:00+07:00",
            "symbol": "S50U26",
            "source": "TFEX",
            "url": (
                "https://www.set.or.th/en/market/news-and-alert/newsdetails"
                "?id=105467002&symbol=S50U26"
            ),
            "headline": "TFEX Daily Settlement Price",
            "isTodayNews": False,
            "viewClarification": None,
            "marketAlertTypeId": None,
            "percentPriceChange": None,
            "tag": "set-releases",
            "product": "TFEX",
            "lang": "en",
        },
    ],
}


def _response(
    payload: dict[str, Any] | None = None,
    *,
    status_code: int = 200,
    text: str | None = None,
) -> FetchResponse:
    """Build a FetchResponse whose body is ``payload`` as JSON (or the literal ``text``)."""
    body = text if text is not None else json.dumps(payload)
    return FetchResponse(
        status_code=status_code,
        content=body.encode("utf-8"),
        text=body,
        headers={},
        url="https://www.set.or.th/api/set/news/search?sourceId=company&lang=en",
        elapsed=0.1,
    )


@pytest.fixture
def mock_fetcher():
    """Patch AsyncDataFetcher inside the news module; yield its async instance.

    The patched class mock is attached as ``.cls`` so tests can assert on the referer passed
    to ``get_set_api_headers``.
    """
    with patch("settfex.services.set.news.AsyncDataFetcher") as mock:
        fetcher_instance = AsyncMock()
        mock.return_value.__aenter__.return_value = fetcher_instance
        mock.return_value.__aexit__.return_value = None
        mock.get_set_api_headers = Mock(return_value={"Accept": "application/json"})
        fetcher_instance.cls = mock
        yield fetcher_instance


class TestModelParsing:
    """Pydantic parsing: camelCase aliases, timezone handling, null-tolerant fields."""

    def test_news_item_aliases_and_structure(self):
        """camelCase payload lands in snake_case fields via aliases."""
        response = NewsSearchResponse.model_validate(SAMPLE)
        assert response.total_count == 3
        assert len(response.news_info_list) == 3
        item = response.news_info_list[0]
        assert isinstance(item, NewsItem)
        assert item.id == "105467000"
        assert item.symbol == "CPALL"
        assert item.is_today_news is False
        assert item.tag == "financial-statement"
        assert item.product == "S"
        assert item.lang == "en"

    def test_datetime_is_tz_aware(self):
        """The publication timestamp keeps its +07:00 offset."""
        response = NewsSearchResponse.model_validate(SAMPLE)
        item = response.news_info_list[0]
        assert item.news_datetime.tzinfo is not None
        assert item.news_datetime == datetime(2026, 7, 17, 21, 6, tzinfo=BKK)

    def test_null_only_fields_tolerate_null(self):
        """viewClarification/marketAlertTypeId/percentPriceChange accept null."""
        response = NewsSearchResponse.model_validate(SAMPLE)
        item = response.news_info_list[0]
        assert item.view_clarification is None
        assert item.market_alert_type_id is None
        assert item.percent_price_change is None

    def test_null_only_fields_tolerate_future_values(self):
        """If SET starts populating the alert fields, permissive unions absorb them."""
        raw = dict(SAMPLE["newsInfoList"][0])
        raw.update({"viewClarification": True, "marketAlertTypeId": 3, "percentPriceChange": -1.5})
        item = NewsItem.model_validate(raw)
        assert item.view_clarification is True
        assert item.market_alert_type_id == 3
        assert item.percent_price_change == -1.5

        raw.update({"viewClarification": "Y", "marketAlertTypeId": "3"})
        item = NewsItem.model_validate(raw)
        assert item.view_clarification == "Y"
        assert item.market_alert_type_id == "3"

    def test_populate_by_name(self):
        """Models can be built from snake_case field names as well as aliases."""
        item = NewsItem(
            id="1",
            news_datetime=datetime(2026, 7, 17, 9, 0, tzinfo=BKK),
            symbol="CPALL",
            source="CPALL",
            url="https://www.set.or.th/x",
            headline="Test",
            is_today_news=True,
            product="S",
            lang="en",
        )
        assert item.symbol == "CPALL"
        assert item.tag == ""
        assert item.view_clarification is None

    def test_response_null_news_list_becomes_empty(self):
        """A null newsInfoList (empty result set) parses as an empty list."""
        response = NewsSearchResponse.model_validate({"totalCount": 0, "newsInfoList": None})
        assert response.count == 0
        assert response.news_info_list == []


class TestResponseHelpers:
    """Count property and filter helpers on NewsSearchResponse."""

    def test_count(self):
        response = NewsSearchResponse.model_validate(SAMPLE)
        assert response.count == 3

    def test_filter_by_symbol_case_insensitive(self):
        response = NewsSearchResponse.model_validate(SAMPLE)
        items = response.filter_by_symbol("cpall")
        assert len(items) == 1
        assert items[0].symbol == "CPALL"

    def test_filter_today(self):
        response = NewsSearchResponse.model_validate(SAMPLE)
        items = response.filter_today()
        assert len(items) == 1
        assert items[0].symbol == "PTT"

    def test_filter_by_tag_case_insensitive(self):
        response = NewsSearchResponse.model_validate(SAMPLE)
        items = response.filter_by_tag("FINANCIAL-STATEMENT")
        assert len(items) == 1
        assert items[0].symbol == "CPALL"


@pytest.mark.asyncio
class TestNewsService:
    """Service behavior: URL building, headers, normalization, error paths."""

    async def test_init_default_config(self):
        service = NewsService()
        assert service.config is not None
        assert service.base_url == "https://www.set.or.th"

    async def test_init_custom_config(self):
        config = FetcherConfig(timeout=60, max_retries=5)
        service = NewsService(config=config)
        assert service.config.timeout == 60
        assert service.config.max_retries == 5

    async def test_fetch_news_success(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        result = await NewsService().fetch_news()
        assert isinstance(result, NewsSearchResponse)
        assert result.count == 3
        assert all(isinstance(item, NewsItem) for item in result.news_info_list)

    async def test_url_default_params(self, mock_fetcher):
        """Default call queries company disclosures in English with no other filters."""
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        await NewsService().fetch_news()
        url = mock_fetcher.fetch.call_args.args[0]
        assert "/api/set/news/search?" in url
        assert "sourceId=company" in url
        assert "lang=en" in url
        assert "symbol=" not in url
        assert "fromDate" not in url
        assert "toDate" not in url
        assert "keyword" not in url

    async def test_url_with_all_filters(self, mock_fetcher):
        """All filters land on the wire; date objects are zero-padded dd/MM/yyyy."""
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        await NewsService().fetch_news(
            symbol="cpall",
            from_date=date(2026, 7, 5),
            to_date="17/07/2026",
            keyword="dividend",
        )
        url = mock_fetcher.fetch.call_args.args[0]
        assert "symbol=CPALL" in url
        assert "fromDate=05/07/2026" in url
        assert "toDate=17/07/2026" in url
        assert "keyword=dividend" in url

    async def test_url_source_id_none_omits_param(self, mock_fetcher):
        """source_id=None is the explicit all-sources switch (param omitted)."""
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        await NewsService().fetch_news(source_id=None)
        url = mock_fetcher.fetch.call_args.args[0]
        assert "sourceId" not in url

    async def test_keyword_is_url_encoded(self, mock_fetcher):
        """Free-text keywords are encoded while date slashes stay literal."""
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        await NewsService().fetch_news(keyword="cash dividend", from_date="15/07/2026")
        url = mock_fetcher.fetch.call_args.args[0]
        assert " " not in url
        assert "cash+dividend" in url
        assert "fromDate=15/07/2026" in url

    async def test_date_string_is_canonicalized(self, mock_fetcher):
        """A non-zero-padded dd/MM/yyyy string is re-formatted to the canonical form."""
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        await NewsService().fetch_news(from_date="5/7/2026")
        url = mock_fetcher.fetch.call_args.args[0]
        assert "fromDate=05/07/2026" in url

    async def test_date_accepts_datetime_object(self, mock_fetcher):
        """A datetime (subclass of date) converts to dd/MM/yyyy."""
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        await NewsService().fetch_news(from_date=datetime(2026, 7, 5, 9, 30))
        url = mock_fetcher.fetch.call_args.args[0]
        assert "fromDate=05/07/2026" in url

    async def test_referer_header(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        await NewsService().fetch_news()
        referer = mock_fetcher.cls.get_set_api_headers.call_args.kwargs["referer"]
        assert referer == "https://www.set.or.th/en/market/news-and-alert/news"

    async def test_lang_normalization(self, mock_fetcher):
        """Thai aliases normalize to lang=th on the wire."""
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        service = NewsService()
        for alias in ("th", "TH", "tha", "thai"):
            await service.fetch_news(lang=alias)  # type: ignore[arg-type]
            url = mock_fetcher.fetch.call_args.args[0]
            assert "lang=th" in url

    async def test_invalid_language_raises(self, mock_fetcher):
        with pytest.raises(InvalidLanguageError, match="Invalid language"):
            await NewsService().fetch_news(lang="fr")  # type: ignore[arg-type]
        mock_fetcher.fetch.assert_not_called()

    async def test_invalid_date_string_raises(self, mock_fetcher):
        """ISO and other malformed date strings fail eagerly, before any request."""
        with pytest.raises(InvalidDateError, match="dd/MM/yyyy"):
            await NewsService().fetch_news(from_date="2026-07-15")
        with pytest.raises(InvalidDateError, match="dd/MM/yyyy"):
            await NewsService().fetch_news(to_date="15-07-2026")
        mock_fetcher.fetch.assert_not_called()

    async def test_empty_symbol_raises(self, mock_fetcher):
        with pytest.raises(InvalidSymbolError):
            await NewsService().fetch_news(symbol="   ")
        mock_fetcher.fetch.assert_not_called()

    async def test_http_error_raises_fetch_error(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(status_code=400, text="Bad Request")
        with pytest.raises(FetchError) as exc_info:
            await NewsService().fetch_news()
        assert exc_info.value.status_code == 400

    async def test_http_404_with_symbol_raises_symbol_not_found(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(status_code=404, text="Not Found")
        with pytest.raises(SymbolNotFoundError):
            await NewsService().fetch_news(symbol="XXXX")

    async def test_json_decode_error(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(text="Invalid JSON")
        with pytest.raises(ResponseParseError, match="news"):
            await NewsService().fetch_news()


@pytest.mark.asyncio
class TestFetchRaw:
    """fetch_news_raw returns the raw dict and shares the URL builder."""

    async def test_fetch_news_raw_returns_dict(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        raw = await NewsService().fetch_news_raw()
        assert isinstance(raw, dict)
        assert raw["totalCount"] == 3
        assert "newsInfoList" in raw

    async def test_fetch_news_raw_builds_same_url(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        await NewsService().fetch_news_raw(symbol="ptt", from_date=date(2026, 7, 1))
        url = mock_fetcher.fetch.call_args.args[0]
        assert "symbol=PTT" in url
        assert "fromDate=01/07/2026" in url
        assert "sourceId=company" in url


@pytest.mark.asyncio
class TestConvenienceFunction:
    """Top-level get_news() passes arguments through."""

    async def test_get_news_passthrough(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        result = await get_news(symbol="CPALL")
        assert isinstance(result, NewsSearchResponse)
        url = mock_fetcher.fetch.call_args.args[0]
        assert "symbol=CPALL" in url

    async def test_get_news_custom_config(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        result = await get_news(config=FetcherConfig(timeout=60))
        assert isinstance(result, NewsSearchResponse)
        assert result.count == 3


@pytest.mark.asyncio
class TestStockIntegration:
    """Stock.get_news() delegates with the symbol pre-filled."""

    async def test_stock_get_news_prefills_symbol(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        stock = Stock("cpall")
        result = await stock.get_news()
        assert isinstance(result, NewsSearchResponse)
        url = mock_fetcher.fetch.call_args.args[0]
        assert "symbol=CPALL" in url
        assert "sourceId=company" in url
