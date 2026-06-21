"""Tests for the SET stock chart quotation service and its latest-traded-price logic."""

import json
from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest

from settfex.services.set.stock.chart_quotation import (
    ChartQuotation,
    ChartQuotationService,
    Intermission,
    Quotation,
    get_chart_quotation,
    get_latest_price,
)
from settfex.services.set.stock.stock import Stock
from settfex.utils.data_fetcher import FetcherConfig, FetchResponse

# Thailand has no DST, so a fixed +07:00 offset is equivalent to Asia/Bangkok.
BKK = timezone(timedelta(hours=7))

# Realistic 1D intraday payload for JAS-W4 (a hyphenated warrant). It deliberately mixes:
#   - a leading null bucket (09:45, pre-trade carry-forward)
#   - two morning trades (09:59, 10:30)
#   - a null bucket inside the lunch intermission (13:00)
#   - an afternoon trade (14:00)
#   - a trailing future / no-trade null bucket (16:00)
SAMPLE: dict = {
    "prior": 0.21,
    "intermissions": [
        {"begin": "2026-06-19T12:30:00", "end": "2026-06-19T13:45:00"},
    ],
    "quotations": [
        {
            "datetime": "2026-06-19T09:45:00+07:00",
            "localDatetime": "2026-06-19T09:45:00",
            "price": 0.21,
            "volume": None,
            "value": None,
            "change": None,
            "percentChange": None,
        },
        {
            "datetime": "2026-06-19T09:59:00+07:00",
            "localDatetime": "2026-06-19T09:59:00",
            "price": 0.21,
            "volume": 4500,
            "value": 945.0,
            "change": 0.0,
            "percentChange": 0.0,
        },
        {
            "datetime": "2026-06-19T10:30:00+07:00",
            "localDatetime": "2026-06-19T10:30:00",
            "price": 0.22,
            "volume": 12000,
            "value": 2640.0,
            "change": 0.01,
            "percentChange": 4.76,
        },
        {
            "datetime": "2026-06-19T13:00:00+07:00",
            "localDatetime": "2026-06-19T13:00:00",
            "price": 0.22,
            "volume": None,
            "value": None,
            "change": None,
            "percentChange": None,
        },
        {
            "datetime": "2026-06-19T14:00:00+07:00",
            "localDatetime": "2026-06-19T14:00:00",
            "price": 0.23,
            "volume": 8000,
            "value": 1840.0,
            "change": 0.02,
            "percentChange": 9.52,
        },
        {
            "datetime": "2026-06-19T16:00:00+07:00",
            "localDatetime": "2026-06-19T16:00:00",
            "price": 0.23,
            "volume": None,
            "value": None,
            "change": None,
            "percentChange": None,
        },
    ],
}


def _at(hour: int, minute: int = 0) -> datetime:
    """Return an aware Asia/Bangkok instant on the sample's trading day (2026-06-19)."""
    return datetime(2026, 6, 19, hour, minute, tzinfo=BKK)


def _response(payload: dict) -> FetchResponse:
    """Build a 200 FetchResponse whose body is ``payload`` serialized as JSON."""
    body = json.dumps(payload)
    return FetchResponse(
        status_code=200,
        content=body.encode("utf-8"),
        text=body,
        headers={},
        url="https://www.set.or.th/api/set/stock/JAS-W4/chart-quotation?period=1D&accumulated=false",
        elapsed=0.1,
    )


@pytest.fixture
def mock_fetcher():
    """Patch AsyncDataFetcher inside the chart_quotation module; yield its async instance.

    The patched class mock is attached as ``.cls`` so tests can assert on the referer passed to
    ``get_set_api_headers``.
    """
    with patch("settfex.services.set.stock.chart_quotation.AsyncDataFetcher") as mock:
        fetcher_instance = AsyncMock()
        mock.return_value.__aenter__.return_value = fetcher_instance
        mock.return_value.__aexit__.return_value = None
        mock.get_set_api_headers = Mock(return_value={"Accept": "application/json"})
        fetcher_instance.cls = mock
        yield fetcher_instance


class TestModelParsing:
    """Pydantic parsing: camelCase aliases, timezone handling, nullable trade fields."""

    def test_aliases_and_structure(self):
        cq = ChartQuotation.model_validate(SAMPLE)
        assert cq.prior == 0.21
        assert len(cq.intermissions) == 1
        assert isinstance(cq.intermissions[0], Intermission)
        assert cq.intermissions[0].begin == datetime(2026, 6, 19, 12, 30)
        assert len(cq.quotations) == 6
        assert all(isinstance(q, Quotation) for q in cq.quotations)

    def test_datetime_aliases_and_timezones(self):
        cq = ChartQuotation.model_validate(SAMPLE)
        q = cq.quotations[1]
        # "datetime" -> quote_datetime (tz-aware), "localDatetime" -> local_datetime (naive)
        assert q.quote_datetime == datetime(2026, 6, 19, 9, 59, tzinfo=BKK)
        assert q.quote_datetime.tzinfo is not None
        assert q.local_datetime == datetime(2026, 6, 19, 9, 59)
        assert q.local_datetime.tzinfo is None
        # "percentChange" -> percent_change
        assert cq.quotations[2].percent_change == 4.76

    def test_null_trade_fields(self):
        cq = ChartQuotation.model_validate(SAMPLE)
        leading = cq.quotations[0]
        assert leading.volume is None
        assert leading.value is None
        assert leading.change is None
        assert leading.percent_change is None
        # price may still be carried forward on a no-trade bucket
        assert leading.price == 0.21


@pytest.mark.asyncio
class TestChartQuotationService:
    """Service I/O: fetch, raw fetch, URL/query/referer construction, error handling."""

    async def test_init_default_and_custom_config(self):
        assert ChartQuotationService().base_url == "https://www.set.or.th"
        service = ChartQuotationService(config=FetcherConfig(timeout=60, max_retries=5))
        assert service.config.timeout == 60
        assert service.config.max_retries == 5

    async def test_fetch_success(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        result = await ChartQuotationService().fetch_chart_quotation("CPALL")
        assert isinstance(result, ChartQuotation)
        assert len(result.quotations) == 6
        assert result.prior == 0.21

    async def test_fetch_url_and_default_query(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        await ChartQuotationService().fetch_chart_quotation("CPALL")
        url = mock_fetcher.fetch.call_args.args[0]
        assert "/api/set/stock/CPALL/chart-quotation" in url
        assert "period=1D" in url
        assert "accumulated=false" in url  # boolean serialized lowercase

    async def test_fetch_query_period_and_accumulated_true(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        await ChartQuotationService().fetch_chart_quotation("CPALL", period="5D", accumulated=True)
        url = mock_fetcher.fetch.call_args.args[0]
        assert "period=5D" in url
        assert "accumulated=true" in url

    async def test_fetch_referer_and_hyphen_symbol_normalization(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        # lowercase, hyphenated warrant symbol -> uppercased, hyphen preserved
        await ChartQuotationService().fetch_chart_quotation("jas-w4")
        url = mock_fetcher.fetch.call_args.args[0]
        assert "/api/set/stock/JAS-W4/chart-quotation" in url
        referer = mock_fetcher.cls.get_set_api_headers.call_args.kwargs["referer"]
        assert referer == "https://www.set.or.th/en/market/product/stock/quote/JAS-W4/price"

    async def test_fetch_empty_symbol_raises(self):
        with pytest.raises(ValueError, match="symbol cannot be empty"):
            await ChartQuotationService().fetch_chart_quotation("   ")

    async def test_fetch_http_error_raises(self, mock_fetcher):
        mock_fetcher.fetch.return_value = FetchResponse(
            status_code=403, content=b"", text="", headers={}, url="x", elapsed=0.1
        )
        with pytest.raises(Exception, match="HTTP 403"):
            await ChartQuotationService().fetch_chart_quotation("CPALL")

    async def test_fetch_raw_success(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        raw = await ChartQuotationService().fetch_chart_quotation_raw("CPALL")
        assert isinstance(raw, dict)
        assert raw["prior"] == 0.21
        assert len(raw["quotations"]) == 6

    async def test_fetch_raw_http_error_raises(self, mock_fetcher):
        mock_fetcher.fetch.return_value = FetchResponse(
            status_code=500, content=b"", text="", headers={}, url="x", elapsed=0.1
        )
        with pytest.raises(Exception, match="HTTP 500"):
            await ChartQuotationService().fetch_chart_quotation_raw("CPALL")

    async def test_fetch_raw_empty_symbol_raises(self):
        with pytest.raises(ValueError, match="symbol cannot be empty"):
            await ChartQuotationService().fetch_chart_quotation_raw("")


@pytest.mark.asyncio
class TestConvenienceFunctions:
    """Top-level get_chart_quotation and get_latest_price (returns a Quotation)."""

    async def test_get_chart_quotation(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        result = await get_chart_quotation("CPALL", period="1D")
        assert isinstance(result, ChartQuotation)
        assert result.prior == 0.21

    async def test_get_latest_price_returns_latest_traded_quotation(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        q = await get_latest_price("CPALL", as_of=_at(11, 0))
        assert isinstance(q, Quotation)
        assert q.local_datetime == datetime(2026, 6, 19, 10, 30)
        assert q.price == 0.22

    async def test_get_latest_price_none_before_open(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        assert await get_latest_price("CPALL", as_of=_at(9, 0)) is None


@pytest.mark.asyncio
class TestStockClassIntegration:
    """The unified Stock class exposes get_chart_quotation and get_latest_price."""

    async def test_stock_get_chart_quotation(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        cq = await Stock("CPALL").get_chart_quotation()
        assert isinstance(cq, ChartQuotation)
        assert len(cq.quotations) == 6

    async def test_stock_get_latest_price(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        q = await Stock("CPALL").get_latest_price(as_of=_at(11, 0))
        assert isinstance(q, Quotation)
        assert q.price == 0.22

    async def test_stock_get_latest_price_none_before_open(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        assert await Stock("CPALL").get_latest_price(as_of=_at(9, 0)) is None


class TestGetLatestQuotation:
    """Pure, I/O-free selection logic — driven entirely by injected ``as_of``."""

    @pytest.fixture
    def cq(self) -> ChartQuotation:
        return ChartQuotation.model_validate(SAMPLE)

    def test_mid_session_returns_latest_traded_minute(self, cq):
        q = cq.get_latest_quotation(_at(11, 0))
        assert q is not None
        assert q.local_datetime == datetime(2026, 6, 19, 10, 30)

    def test_between_two_trades_excludes_later_one(self, cq):
        q = cq.get_latest_quotation(_at(10, 0))
        assert q is not None
        assert q.local_datetime == datetime(2026, 6, 19, 9, 59)

    def test_exact_trade_timestamp_is_inclusive(self, cq):
        q = cq.get_latest_quotation(_at(10, 30))
        assert q is not None
        assert q.local_datetime == datetime(2026, 6, 19, 10, 30)

    def test_inside_lunch_intermission_returns_last_morning_trade(self, cq):
        # 13:00 falls in the 12:30-13:45 break; its bucket is null -> skip to 10:30
        q = cq.get_latest_quotation(_at(13, 0))
        assert q is not None
        assert q.local_datetime == datetime(2026, 6, 19, 10, 30)

    def test_pre_open_returns_none(self, cq):
        assert cq.get_latest_quotation(_at(9, 0)) is None

    def test_after_close_skips_trailing_null_bucket(self, cq):
        q = cq.get_latest_quotation(_at(23, 0))
        assert q is not None
        assert q.local_datetime == datetime(2026, 6, 19, 14, 0)

    def test_empty_quotations_returns_none(self):
        cq = ChartQuotation(prior=0.5, quotations=[])
        assert cq.get_latest_quotation(_at(11, 0)) is None

    def test_all_null_series_returns_none(self):
        cq = ChartQuotation.model_validate(
            {
                "prior": 0.5,
                "quotations": [
                    {
                        "datetime": "2026-06-19T10:00:00+07:00",
                        "localDatetime": "2026-06-19T10:00:00",
                        "price": 0.5,
                        "volume": None,
                        "value": None,
                        "change": None,
                        "percentChange": None,
                    }
                ],
            }
        )
        assert cq.get_latest_quotation(_at(11, 0)) is None

    def test_naive_as_of_treated_as_bangkok(self, cq):
        q = cq.get_latest_quotation(datetime(2026, 6, 19, 11, 0))  # naive
        assert q is not None
        assert q.local_datetime == datetime(2026, 6, 19, 10, 30)

    def test_aware_non_bangkok_as_of_is_converted(self, cq):
        # 04:00 UTC == 11:00 Asia/Bangkok -> same result as the naive 11:00 case
        utc_as_of = datetime(2026, 6, 19, 4, 0, tzinfo=UTC)
        q = cq.get_latest_quotation(utc_as_of)
        assert q is not None
        assert q.local_datetime == datetime(2026, 6, 19, 10, 30)

    def test_default_as_of_uses_now_in_bangkok(self, cq, monkeypatch):
        # Freeze "now" to 11:00 Bangkok by patching the module's datetime.now.
        import settfex.services.set.stock.chart_quotation as module

        class _FixedDatetime(datetime):
            @classmethod
            def now(cls, tz=None):  # type: ignore[override]
                return datetime(2026, 6, 19, 11, 0, tzinfo=tz)

        monkeypatch.setattr(module, "datetime", _FixedDatetime)
        q = cq.get_latest_quotation()
        assert q is not None
        assert q.local_datetime == datetime(2026, 6, 19, 10, 30)


class TestGetLatestPriceModel:
    """The model's scalar get_latest_price, including the ``prior`` fallback."""

    @pytest.fixture
    def cq(self) -> ChartQuotation:
        return ChartQuotation.model_validate(SAMPLE)

    def test_returns_latest_traded_price(self, cq):
        assert cq.get_latest_price(_at(11, 0)) == 0.22

    def test_returns_price_at_first_trade(self, cq):
        assert cq.get_latest_price(_at(10, 0)) == 0.21

    def test_falls_back_to_prior_before_open(self, cq):
        assert cq.get_latest_price(_at(9, 0)) == 0.21  # == prior

    def test_falls_back_to_prior_when_empty(self):
        cq = ChartQuotation(prior=0.33, quotations=[])
        assert cq.get_latest_price(_at(11, 0)) == 0.33

    def test_none_when_no_trade_and_no_prior(self):
        cq = ChartQuotation(prior=None, quotations=[])
        assert cq.get_latest_price(_at(11, 0)) is None

    def test_falls_back_to_prior_when_latest_trade_has_null_price(self):
        # A traded bucket (volume set) but with a null price -> get_latest_quotation still finds it,
        # but get_latest_price falls back to prior.
        cq = ChartQuotation.model_validate(
            {
                "prior": 0.9,
                "quotations": [
                    {
                        "datetime": "2026-06-19T10:00:00+07:00",
                        "localDatetime": "2026-06-19T10:00:00",
                        "price": None,
                        "volume": 100,
                        "value": 0.0,
                        "change": None,
                        "percentChange": None,
                    }
                ],
            }
        )
        assert cq.get_latest_quotation(_at(11, 0)) is not None
        assert cq.get_latest_price(_at(11, 0)) == 0.9
