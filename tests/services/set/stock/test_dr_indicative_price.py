"""Tests for the DR indicative price service (TradingView scan, math, Stock auto-switch)."""

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from settfex.exceptions import FetchError
from settfex.services.set.asset_type import AssetType
from settfex.services.set.stock.chart_quotation import BANGKOK_TZ, Quotation
from settfex.services.set.stock.dr_indicative_price import (
    DrIndicativePrice,
    DrIndicativePriceService,
    DrIndicativeQuotation,
    TradingViewQuote,
    get_dr_indicative_price,
)
from settfex.services.set.stock.profile_dr import DrProfile
from settfex.services.set.stock.stock import Stock
from settfex.utils.data_fetcher import FetcherConfig, FetchResponse

# Live-captured POST /global/scan response for GOOG80's two legs (2026-08-03).
SAMPLE_SCAN: dict[str, Any] = {
    "totalCount": 2,
    "data": [
        {
            "s": "NASDAQ:GOOG",
            "d": ["GOOG", 356.65, 6.8838408055622065, "USD", "delayed_streaming_900"],
        },
        {
            "s": "FX_IDC:USDTHB",
            "d": ["USDTHB", 33.33, -0.17969451931716762, "THB", "streaming"],
        },
    ],
}

# Live-captured GET /api/set/dr/GOOG80/profile payload (2026-08-03), trimmed to the fields
# the indicative flow touches (the full payload is exercised in test_profile_dr.py).
SAMPLE_DR_PROFILE: dict[str, Any] = {
    "symbol": "GOOG80",
    "securityType": "X",
    "securityTypeName": "Depositary Receipts",
    "conversionRatio": "2,000 : 1",
    "underlying": "GOOG",
    "indicativePriceSymbol": "NASDAQ:GOOG*FX_IDC:USDTHB/2000.0",
    "indicativePriceUrl": (
        "https://th.tradingview.com/chart/?symbol=NASDAQ%3AGOOG*FX_IDC%3AUSDTHB%2F2000.0"
    ),
}

SAMPLE_DR_PROFILE_NULL_EXPR: dict[str, Any] = {
    **SAMPLE_DR_PROFILE,
    "symbol": "HERMES80",
    "underlying": "RMS",
    "conversionRatio": "10,000 : 1",
    "indicativePriceSymbol": None,
    "indicativePriceUrl": (
        "https://th.tradingview.com/chart/?symbol=EURONEXT%3ARMS*FX_IDC%3AEURTHB%2F10000.0"
    ),
}

# Chart-quotation payload for fallback-path tests; timestamps are safely in the past so the
# "now in Bangkok" cutoff always includes the traded bucket.
SAMPLE_CHART: dict[str, Any] = {
    "prior": 5.75,
    "intermissions": [],
    "quotations": [
        {
            "datetime": "2026-01-05T10:00:00+07:00",
            "localDatetime": "2026-01-05T10:00:00",
            "price": 5.70,
            "volume": 100.0,
            "value": 570.0,
            "change": -0.05,
            "percentChange": -0.87,
        }
    ],
}

# Minimal-but-complete StockProfile payload for get_asset_type tests.
SAMPLE_STOCK_PROFILE: dict[str, Any] = {
    "symbol": "GOOG80",
    "name": "Depositary Receipt on GOOG Issued by KTB",
    "market": "SET",
    "industry": "",
    "industryName": "",
    "sector": "",
    "sectorName": "",
    "securityType": "X",
    "securityTypeName": "Depositary Receipts",
    "status": "Listed",
    "listedDate": None,
    "firstTradeDate": None,
    "lastTradeDate": None,
    "maturityDate": None,
    "fiscalYearEnd": None,
    "fiscalYearEndDisplay": None,
    "accountForm": None,
    "par": None,
    "currency": "THB",
    "listedShare": None,
    "ipo": None,
    "isinLocal": None,
    "isinForeign": None,
    "isinNVDR": None,
    "percentFreeFloat": None,
    "foreignLimitAsOf": None,
    "percentForeignRoom": None,
    "percentForeignLimit": None,
    "foreignAvailable": None,
    "underlying": None,
    "exercisePrice": None,
    "exerciseRatio": None,
    "reservedShare": None,
    "convertedShare": None,
    "lastExerciseDate": None,
    "issuedShare": None,
}


def _response(
    payload: Any = None, *, status_code: int = 200, text: str | None = None
) -> FetchResponse:
    """Build a FetchResponse whose body is ``payload`` as JSON (or the literal ``text``)."""
    body = text if text is not None else json.dumps(payload)
    return FetchResponse(
        status_code=status_code,
        content=body.encode("utf-8"),
        text=body,
        headers={},
        url="https://scanner.tradingview.com/global/scan",
        elapsed=0.1,
    )


def _patched_fetcher(module: str):
    """Context manager patching AsyncDataFetcher inside ``module``; yields the instance."""
    patcher = patch(f"{module}.AsyncDataFetcher")
    mock = patcher.start()
    fetcher_instance = AsyncMock()
    mock.return_value.__aenter__.return_value = fetcher_instance
    mock.return_value.__aexit__.return_value = None
    mock.get_set_api_headers = Mock(return_value={"Accept": "application/json"})
    fetcher_instance.cls = mock
    return patcher, fetcher_instance


@pytest.fixture
def mock_tv_fetcher():
    """Fetcher inside dr_indicative_price (the TradingView leg)."""
    patcher, instance = _patched_fetcher("settfex.services.set.stock.dr_indicative_price")
    yield instance
    patcher.stop()


@pytest.fixture
def mock_dr_profile_fetcher():
    """Fetcher inside profile_dr (the SET DR-profile leg)."""
    patcher, instance = _patched_fetcher("settfex.services.set.stock.profile_dr")
    yield instance
    patcher.stop()


@pytest.fixture
def mock_chart_fetcher():
    """Fetcher inside chart_quotation (the SET fallback path)."""
    patcher, instance = _patched_fetcher("settfex.services.set.stock.chart_quotation")
    yield instance
    patcher.stop()


@pytest.fixture
def mock_stock_profile_fetcher():
    """Fetcher inside profile_stock (get_asset_type)."""
    patcher, instance = _patched_fetcher("settfex.services.set.stock.profile_stock")
    yield instance
    patcher.stop()


def _dr_profile(payload: dict[str, Any] | None = None) -> DrProfile:
    return DrProfile.model_validate(payload or SAMPLE_DR_PROFILE)


@pytest.mark.asyncio
class TestTradingViewScan:
    """fetch_quotes / fetch_quotes_raw wire behavior."""

    async def test_posts_single_batch_request_with_exact_body(self, mock_tv_fetcher):
        mock_tv_fetcher.fetch.return_value = _response(SAMPLE_SCAN)
        await DrIndicativePriceService().fetch_quotes(["NASDAQ:GOOG", "FX_IDC:USDTHB"])
        assert mock_tv_fetcher.fetch.call_count == 1
        call = mock_tv_fetcher.fetch.call_args
        assert call.args[0] == "https://scanner.tradingview.com/global/scan"
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["json_body"] == {
            "symbols": {"tickers": ["NASDAQ:GOOG", "FX_IDC:USDTHB"]},
            "columns": ["name", "close", "change", "currency", "update_mode"],
        }

    async def test_config_is_stateless_for_tradingview_only(self):
        service = DrIndicativePriceService(config=FetcherConfig(timeout=60))
        # TradingView leg: session off, custom settings preserved.
        assert service.tv_config.use_session is False
        assert service.tv_config.timeout == 60
        # SET-host leg (DR profile) keeps the caller's config untouched.
        assert service.config is not None
        assert service.config.use_session is True

    async def test_parses_rows_into_quotes(self, mock_tv_fetcher):
        mock_tv_fetcher.fetch.return_value = _response(SAMPLE_SCAN)
        quotes = await DrIndicativePriceService().fetch_quotes(["NASDAQ:GOOG", "FX_IDC:USDTHB"])
        goog = quotes["NASDAQ:GOOG"]
        assert goog.name == "GOOG"
        assert goog.close == 356.65
        assert goog.currency == "USD"
        assert goog.update_mode == "delayed_streaming_900"
        assert quotes["FX_IDC:USDTHB"].close == 33.33

    async def test_short_d_array_pads_none(self, mock_tv_fetcher):
        mock_tv_fetcher.fetch.return_value = _response(
            {"totalCount": 1, "data": [{"s": "NASDAQ:GOOG", "d": ["GOOG", 356.65]}]}
        )
        quotes = await DrIndicativePriceService().fetch_quotes(["NASDAQ:GOOG"])
        goog = quotes["NASDAQ:GOOG"]
        assert goog.close == 356.65
        assert goog.change is None
        assert goog.currency is None
        assert goog.update_mode is None

    async def test_non_2xx_raises_fetch_error(self, mock_tv_fetcher):
        mock_tv_fetcher.fetch.return_value = _response(text="slow down", status_code=429)
        with pytest.raises(FetchError) as excinfo:
            await DrIndicativePriceService().fetch_quotes(["NASDAQ:GOOG"])
        assert excinfo.value.status_code == 429

    async def test_missing_ticker_raises_fetch_error(self, mock_tv_fetcher):
        # TradingView answers unknown tickers with HTTP 200 and the row simply missing.
        mock_tv_fetcher.fetch.return_value = _response(
            {"totalCount": 1, "data": [SAMPLE_SCAN["data"][0]]}
        )
        with pytest.raises(FetchError, match="no data for ticker"):
            await DrIndicativePriceService().fetch_quotes(["NASDAQ:GOOG", "FX_IDC:USDTHB"])

    async def test_duplicate_tickers_deduped_in_request(self, mock_tv_fetcher):
        mock_tv_fetcher.fetch.return_value = _response(
            {"totalCount": 1, "data": [SAMPLE_SCAN["data"][0]]}
        )
        await DrIndicativePriceService().fetch_quotes(["NASDAQ:GOOG", "NASDAQ:GOOG"])
        body = mock_tv_fetcher.fetch.call_args.kwargs["json_body"]
        assert body["symbols"]["tickers"] == ["NASDAQ:GOOG"]

    async def test_empty_tickers_raises_value_error(self, mock_tv_fetcher):
        with pytest.raises(ValueError, match="empty"):
            await DrIndicativePriceService().fetch_quotes([])
        mock_tv_fetcher.fetch.assert_not_called()

    async def test_fetch_quotes_raw(self, mock_tv_fetcher):
        mock_tv_fetcher.fetch.return_value = _response(SAMPLE_SCAN)
        raw = await DrIndicativePriceService().fetch_quotes_raw(["NASDAQ:GOOG"])
        assert raw["totalCount"] == 2
        assert raw["data"][0]["s"] == "NASDAQ:GOOG"


@pytest.mark.asyncio
class TestIndicativeComputation:
    """fetch_indicative_price math and the DrIndicativePrice model helpers."""

    async def test_verified_math_goog80(self, mock_tv_fetcher):
        mock_tv_fetcher.fetch.return_value = _response(SAMPLE_SCAN)
        price = await DrIndicativePriceService().fetch_indicative_price(
            "GOOG80", profile=_dr_profile()
        )
        assert price.indicative_price == pytest.approx(356.65 * 33.33 / 2000.0)
        assert price.ratio == 2000.0
        assert price.expression == "NASDAQ:GOOG*FX_IDC:USDTHB/2000.0"
        assert price.tradingview_url == SAMPLE_DR_PROFILE["indicativePriceUrl"]
        assert [leg.ticker for leg in price.legs] == ["NASDAQ:GOOG", "FX_IDC:USDTHB"]

    async def test_single_leg_ratio_one(self, mock_tv_fetcher):
        mock_tv_fetcher.fetch.return_value = _response(
            {"totalCount": 1, "data": [SAMPLE_SCAN["data"][0]]}
        )
        profile = _dr_profile(
            {
                **SAMPLE_DR_PROFILE,
                "indicativePriceSymbol": "NASDAQ:GOOG",
                "indicativePriceUrl": None,
            }
        )
        price = await DrIndicativePriceService().fetch_indicative_price("GOOG80", profile=profile)
        assert price.indicative_price == pytest.approx(356.65)
        assert price.ratio == 1.0

    async def test_null_close_raises_fetch_error(self, mock_tv_fetcher):
        scan = {
            "totalCount": 2,
            "data": [
                SAMPLE_SCAN["data"][0],
                {"s": "FX_IDC:USDTHB", "d": ["USDTHB", None, None, "THB", "streaming"]},
            ],
        }
        mock_tv_fetcher.fetch.return_value = _response(scan)
        with pytest.raises(FetchError, match="null close.*FX_IDC:USDTHB"):
            await DrIndicativePriceService().fetch_indicative_price("GOOG80", profile=_dr_profile())

    async def test_as_of_is_aware_bangkok(self, mock_tv_fetcher):
        mock_tv_fetcher.fetch.return_value = _response(SAMPLE_SCAN)
        price = await DrIndicativePriceService().fetch_indicative_price(
            "GOOG80", profile=_dr_profile()
        )
        assert price.as_of.tzinfo is not None
        assert price.as_of.utcoffset() == timedelta(hours=7)

    async def test_underlying_fx_and_delay_helpers(self, mock_tv_fetcher):
        mock_tv_fetcher.fetch.return_value = _response(SAMPLE_SCAN)
        price = await DrIndicativePriceService().fetch_indicative_price(
            "GOOG80", profile=_dr_profile()
        )
        assert price.underlying is not None
        assert price.underlying.ticker == "NASDAQ:GOOG"
        assert price.fx is not None
        assert price.fx.ticker == "FX_IDC:USDTHB"
        assert price.is_delayed is True  # the NASDAQ leg is delayed_streaming_900

    def test_is_delayed_false_when_all_streaming(self):
        price = DrIndicativePrice(
            symbol="X01",
            indicative_price=1.0,
            ratio=1.0,
            expression="FX_IDC:USDTHB",
            legs=[TradingViewQuote(ticker="FX_IDC:USDTHB", update_mode="streaming")],
            as_of=datetime.now(BANGKOK_TZ),
        )
        assert price.is_delayed is False

    async def test_to_quotation_shape(self, mock_tv_fetcher):
        mock_tv_fetcher.fetch.return_value = _response(SAMPLE_SCAN)
        price = await DrIndicativePriceService().fetch_indicative_price(
            "GOOG80", profile=_dr_profile()
        )
        quotation = price.to_quotation()
        assert isinstance(quotation, Quotation)
        assert isinstance(quotation, DrIndicativeQuotation)
        assert quotation.price == price.indicative_price
        assert quotation.volume is None
        assert quotation.value is None
        assert quotation.change is None
        assert quotation.percent_change is None
        assert quotation.quote_datetime == price.as_of
        assert quotation.local_datetime.tzinfo is None
        assert quotation.local_datetime == price.as_of.replace(tzinfo=None)
        assert quotation.indicative is price

    async def test_no_expression_raises_fetch_error(self, mock_tv_fetcher):
        profile = _dr_profile(
            {**SAMPLE_DR_PROFILE, "indicativePriceSymbol": None, "indicativePriceUrl": None}
        )
        with pytest.raises(FetchError, match="No usable indicative price expression"):
            await DrIndicativePriceService().fetch_indicative_price("GOOG80", profile=profile)
        mock_tv_fetcher.fetch.assert_not_called()

    async def test_url_fallback_expression_used(self, mock_tv_fetcher):
        scan = {
            "totalCount": 2,
            "data": [
                {"s": "EURONEXT:RMS", "d": ["RMS", 1531.5, -1.2, "EUR", "delayed_streaming_900"]},
                {"s": "FX_IDC:EURTHB", "d": ["EURTHB", 38.0, 0.1, "THB", "streaming"]},
            ],
        }
        mock_tv_fetcher.fetch.return_value = _response(scan)
        price = await DrIndicativePriceService().fetch_indicative_price(
            "HERMES80", profile=_dr_profile(SAMPLE_DR_PROFILE_NULL_EXPR)
        )
        body = mock_tv_fetcher.fetch.call_args.kwargs["json_body"]
        assert body["symbols"]["tickers"] == ["EURONEXT:RMS", "FX_IDC:EURTHB"]
        assert price.indicative_price == pytest.approx(1531.5 * 38.0 / 10000.0)

    async def test_end_to_end_profile_then_scan(self, mock_tv_fetcher, mock_dr_profile_fetcher):
        mock_dr_profile_fetcher.fetch.return_value = _response(SAMPLE_DR_PROFILE)
        mock_tv_fetcher.fetch.return_value = _response(SAMPLE_SCAN)
        price = await get_dr_indicative_price("GOOG80")
        assert price.indicative_price == pytest.approx(356.65 * 33.33 / 2000.0)
        assert mock_dr_profile_fetcher.fetch.call_count == 1
        assert mock_tv_fetcher.fetch.call_count == 1

    async def test_prefetched_profile_skips_profile_fetch(
        self, mock_tv_fetcher, mock_dr_profile_fetcher
    ):
        mock_tv_fetcher.fetch.return_value = _response(SAMPLE_SCAN)
        await DrIndicativePriceService().fetch_indicative_price("GOOG80", profile=_dr_profile())
        mock_dr_profile_fetcher.fetch.assert_not_called()


@pytest.mark.asyncio
class TestStockLatestPriceAutoSwitch:
    """Stock.get_latest_price DR behavior + get_asset_type/get_indicative_price wiring."""

    async def test_stock_get_asset_type_fetches_once_and_caches(self, mock_stock_profile_fetcher):
        mock_stock_profile_fetcher.fetch.return_value = _response(SAMPLE_STOCK_PROFILE)
        stock = Stock("GOOG80")
        assert await stock.get_asset_type() is AssetType.DEPOSITARY_RECEIPT
        assert await stock.get_asset_type() is AssetType.DEPOSITARY_RECEIPT
        assert mock_stock_profile_fetcher.fetch.call_count == 1

    async def test_stock_get_indicative_price(self, mock_tv_fetcher, mock_dr_profile_fetcher):
        mock_dr_profile_fetcher.fetch.return_value = _response(SAMPLE_DR_PROFILE)
        mock_tv_fetcher.fetch.return_value = _response(SAMPLE_SCAN)
        price = await Stock("GOOG80").get_indicative_price()
        assert price.indicative_price == pytest.approx(356.65 * 33.33 / 2000.0)

    async def test_dr_uses_indicative_and_skips_chart(
        self, mock_tv_fetcher, mock_dr_profile_fetcher, mock_chart_fetcher
    ):
        mock_dr_profile_fetcher.fetch.return_value = _response(SAMPLE_DR_PROFILE)
        mock_tv_fetcher.fetch.return_value = _response(SAMPLE_SCAN)
        quotation = await Stock("GOOG80").get_latest_price()
        assert isinstance(quotation, DrIndicativeQuotation)
        assert quotation.price == pytest.approx(356.65 * 33.33 / 2000.0)
        mock_chart_fetcher.fetch.assert_not_called()

    async def test_dr_falls_back_to_chart_on_tv_http_error(
        self, mock_tv_fetcher, mock_dr_profile_fetcher, mock_chart_fetcher
    ):
        mock_dr_profile_fetcher.fetch.return_value = _response(SAMPLE_DR_PROFILE)
        mock_tv_fetcher.fetch.return_value = _response(text="down", status_code=503)
        mock_chart_fetcher.fetch.return_value = _response(SAMPLE_CHART)
        quotation = await Stock("GOOG80").get_latest_price()
        assert quotation is not None
        assert not isinstance(quotation, DrIndicativeQuotation)
        assert quotation.price == 5.70

    async def test_dr_falls_back_when_no_expression(
        self, mock_tv_fetcher, mock_dr_profile_fetcher, mock_chart_fetcher
    ):
        payload = {
            **SAMPLE_DR_PROFILE,
            "indicativePriceSymbol": None,
            "indicativePriceUrl": None,
        }
        mock_dr_profile_fetcher.fetch.return_value = _response(payload)
        mock_chart_fetcher.fetch.return_value = _response(SAMPLE_CHART)
        quotation = await Stock("GOOG80").get_latest_price()
        assert quotation is not None
        assert quotation.price == 5.70
        mock_tv_fetcher.fetch.assert_not_called()

    async def test_non_dr_goes_straight_to_chart_and_caches_probe(
        self, mock_tv_fetcher, mock_dr_profile_fetcher, mock_chart_fetcher
    ):
        mock_dr_profile_fetcher.fetch.return_value = _response(
            {"message": "Invalid DR"}, status_code=404
        )
        mock_chart_fetcher.fetch.return_value = _response(SAMPLE_CHART)
        stock = Stock("CPALL")
        first = await stock.get_latest_price()
        second = await stock.get_latest_price()
        assert first is not None and second is not None
        assert first.price == 5.70
        assert stock._is_dr is False
        # The DR probe ran exactly once; the second call skipped it via the cache.
        assert mock_dr_profile_fetcher.fetch.call_count == 1
        assert mock_chart_fetcher.fetch.call_count == 2
        mock_tv_fetcher.fetch.assert_not_called()

    async def test_explicit_as_of_skips_indicative(
        self, mock_tv_fetcher, mock_dr_profile_fetcher, mock_chart_fetcher
    ):
        mock_chart_fetcher.fetch.return_value = _response(SAMPLE_CHART)
        as_of = datetime(2026, 1, 5, 12, 0, tzinfo=timezone(timedelta(hours=7)))
        quotation = await Stock("GOOG80").get_latest_price(as_of=as_of)
        assert quotation is not None
        assert quotation.price == 5.70
        mock_dr_profile_fetcher.fetch.assert_not_called()
        mock_tv_fetcher.fetch.assert_not_called()

    async def test_prefer_flag_false_forces_chart_for_dr(
        self, mock_tv_fetcher, mock_dr_profile_fetcher, mock_chart_fetcher
    ):
        mock_chart_fetcher.fetch.return_value = _response(SAMPLE_CHART)
        quotation = await Stock("GOOG80").get_latest_price(prefer_dr_indicative=False)
        assert quotation is not None
        assert quotation.price == 5.70
        mock_dr_profile_fetcher.fetch.assert_not_called()
        mock_tv_fetcher.fetch.assert_not_called()

    async def test_dr_falls_back_when_profile_fetch_breaks(
        self, mock_tv_fetcher, mock_dr_profile_fetcher, mock_chart_fetcher
    ):
        mock_dr_profile_fetcher.fetch.return_value = _response(text="oops", status_code=500)
        mock_chart_fetcher.fetch.return_value = _response(SAMPLE_CHART)
        stock = Stock("GOOG80")
        quotation = await stock.get_latest_price()
        assert quotation is not None
        assert quotation.price == 5.70
        # Transient failure must NOT cache DR-ness either way.
        assert stock._is_dr is None
        mock_tv_fetcher.fetch.assert_not_called()
