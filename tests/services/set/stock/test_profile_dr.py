"""Tests for the DR profile service (expression parsing, model, service, Stock wiring)."""

import json
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from settfex.exceptions import (
    FetchError,
    InvalidSymbolError,
    SymbolNotFoundError,
    register_symbol_suggester,
)
from settfex.services.set.asset_type import AssetType
from settfex.services.set.list import suggest_symbol
from settfex.services.set.stock.profile_dr import (
    DrProfile,
    DrProfileService,
    get_dr_profile,
    parse_indicative_price_expression,
)
from settfex.services.set.stock.stock import Stock
from settfex.utils.data_fetcher import FetchResponse

# Live-captured payload of GET /api/set/dr/GOOG80/profile?lang=en (2026-08-03).
SAMPLE_DR_PROFILE: dict[str, Any] = {
    "symbol": "GOOG80",
    "name": "Depositary Receipt on GOOG Issued by KTB",
    "market": "SET",
    "issuer": "KTB",
    "issuerName": "KRUNG THAI BANK PUBLIC COMPANY LIMITED",
    "url": "https://krungthai.com",
    "address": "35 SUKHUMVIT ROAD, KHLONG TOEI NUA, WATTANA Bangkok 10110",
    "telephone": "0-2255-2222",
    "fax": "0-2255-9391-6",
    "securityType": "X",
    "securityTypeName": "Depositary Receipts",
    "status": "Listed",
    "firstTradeDate": "2023-06-21T00:00:00+07:00",
    "conversionRatio": "2,000 : 1",
    "ipo": 2.18,
    "par": None,
    "listedShare": 6000000000,
    "currency": "THB",
    "isin": "TH0150120903",
    "drType": "Depositary Receipt Representing Interest from Underlying Foreign Securities",
    "offeringType": "Direct Listing",
    "underlying": "GOOG",
    "underlyingName": "ALPHABET INC. (GOOG)",
    "underlyingClassName": "Foreign Common Stock",
    "underlyingExchange": "The Nasdaq Global Select Market",
    "underlyingUrl": "https://www.nasdaq.com/market-activity/stocks/goog",
    "fractionalTrade": False,
    "outstandingShare": 791482000.0,
    "outstandingDate": "2026-07-31T00:00:00+07:00",
    "listingDetail": None,
    "memorandumUrl": "https://weblink.set.or.th/dat/security/00117657E.pdf",
    "tradingSession": "Day & Night Session",
    "indicativePriceSymbol": "NASDAQ:GOOG*FX_IDC:USDTHB/2000.0",
    "indicativePriceUrl": (
        "https://th.tradingview.com/chart/?symbol=NASDAQ%3AGOOG*FX_IDC%3AUSDTHB%2F2000.0"
    ),
}

# HERMES80-style: indicativePriceSymbol null, but the URL still carries the expression
# (also live-observed for BYDCOM80 and NDX01).
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
        url="https://www.set.or.th/api/set/dr/GOOG80/profile?lang=en",
        elapsed=0.1,
    )


@pytest.fixture
def mock_fetcher():
    """Patch AsyncDataFetcher inside the profile_dr module; yield its async instance."""
    with patch("settfex.services.set.stock.profile_dr.AsyncDataFetcher") as mock:
        fetcher_instance = AsyncMock()
        mock.return_value.__aenter__.return_value = fetcher_instance
        mock.return_value.__aexit__.return_value = None
        mock.get_set_api_headers = Mock(return_value={"Accept": "application/json"})
        fetcher_instance.cls = mock
        yield fetcher_instance


class TestExpressionParsing:
    """parse_indicative_price_expression against observed and defensive grammar."""

    def test_two_leg_nasdaq_with_ratio(self):
        expr = parse_indicative_price_expression("NASDAQ:GOOG*FX_IDC:USDTHB/2000.0")
        assert expr.tickers == ["NASDAQ:GOOG", "FX_IDC:USDTHB"]
        assert expr.ratio == 2000.0
        assert expr.expression == "NASDAQ:GOOG*FX_IDC:USDTHB/2000.0"

    def test_numeric_hkex_ticker(self):
        expr = parse_indicative_price_expression("HKEX:1211*FX_IDC:HKDTHB/1000.0")
        assert expr.tickers == ["HKEX:1211", "FX_IDC:HKDTHB"]
        assert expr.ratio == 1000.0

    def test_no_ratio_defaults_to_one(self):
        expr = parse_indicative_price_expression("NASDAQ:GOOG*FX_IDC:USDTHB")
        assert expr.tickers == ["NASDAQ:GOOG", "FX_IDC:USDTHB"]
        assert expr.ratio == 1.0

    def test_single_leg(self):
        expr = parse_indicative_price_expression("NASDAQ:GOOG")
        assert expr.tickers == ["NASDAQ:GOOG"]
        assert expr.ratio == 1.0

    def test_three_legs(self):
        expr = parse_indicative_price_expression("A:X*B:Y*C:Z/5.0")
        assert expr.tickers == ["A:X", "B:Y", "C:Z"]
        assert expr.ratio == 5.0

    def test_whitespace_tolerated(self):
        expr = parse_indicative_price_expression("  NASDAQ:GOOG * FX_IDC:USDTHB / 2000.0  ")
        assert expr.tickers == ["NASDAQ:GOOG", "FX_IDC:USDTHB"]
        assert expr.ratio == 2000.0

    def test_empty_raises_value_error(self):
        with pytest.raises(ValueError, match="empty"):
            parse_indicative_price_expression("   ")

    def test_bad_ratio_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid ratio"):
            parse_indicative_price_expression("NASDAQ:GOOG/abc")

    def test_zero_or_negative_ratio_raises(self):
        with pytest.raises(ValueError, match="Non-positive ratio"):
            parse_indicative_price_expression("NASDAQ:GOOG/0")
        with pytest.raises(ValueError, match="Non-positive ratio"):
            parse_indicative_price_expression("NASDAQ:GOOG/-2.0")


class TestDrProfileModel:
    """DrProfile aliases and derived properties."""

    def test_full_payload_aliases(self):
        profile = DrProfile.model_validate(SAMPLE_DR_PROFILE)
        assert profile.symbol == "GOOG80"
        assert profile.issuer_name == "KRUNG THAI BANK PUBLIC COMPANY LIMITED"
        assert profile.security_type == "X"
        assert profile.underlying == "GOOG"
        assert profile.underlying_exchange == "The Nasdaq Global Select Market"
        assert profile.fractional_trade is False
        assert profile.trading_session == "Day & Night Session"
        assert profile.indicative_price_symbol == "NASDAQ:GOOG*FX_IDC:USDTHB/2000.0"

    def test_conversion_ratio_kept_verbatim(self):
        profile = DrProfile.model_validate(SAMPLE_DR_PROFILE)
        assert profile.conversion_ratio == "2,000 : 1"

    def test_indicative_expression_from_symbol_field(self):
        profile = DrProfile.model_validate(SAMPLE_DR_PROFILE)
        expr = profile.indicative_expression
        assert expr is not None
        assert expr.tickers == ["NASDAQ:GOOG", "FX_IDC:USDTHB"]
        assert expr.ratio == 2000.0

    def test_indicative_expression_recovered_from_url_when_symbol_null(self):
        profile = DrProfile.model_validate(SAMPLE_DR_PROFILE_NULL_EXPR)
        expr = profile.indicative_expression
        assert expr is not None
        # %3A / %2F in the URL must decode back to ':' and '/'
        assert expr.tickers == ["EURONEXT:RMS", "FX_IDC:EURTHB"]
        assert expr.ratio == 10000.0

    def test_indicative_expression_none_when_both_unusable(self):
        payload = {
            **SAMPLE_DR_PROFILE,
            "indicativePriceSymbol": None,
            "indicativePriceUrl": None,
        }
        profile = DrProfile.model_validate(payload)
        assert profile.indicative_expression is None

    def test_indicative_expression_none_on_unparseable(self):
        payload = {
            **SAMPLE_DR_PROFILE,
            "indicativePriceSymbol": "NASDAQ:GOOG/abc",
            "indicativePriceUrl": None,
        }
        profile = DrProfile.model_validate(payload)
        assert profile.indicative_expression is None  # logged, never raises

    def test_tradingview_url_property(self):
        profile = DrProfile.model_validate(SAMPLE_DR_PROFILE)
        assert profile.tradingview_url == SAMPLE_DR_PROFILE["indicativePriceUrl"]

    def test_asset_type_is_dr(self):
        profile = DrProfile.model_validate(SAMPLE_DR_PROFILE)
        assert profile.asset_type is AssetType.DEPOSITARY_RECEIPT

    def test_minimal_payload_tolerates_missing_keys(self):
        profile = DrProfile.model_validate({"symbol": "GOOG80"})
        assert profile.symbol == "GOOG80"
        assert profile.indicative_price_url is None
        assert profile.indicative_expression is None
        assert profile.asset_type is AssetType.UNKNOWN


@pytest.mark.asyncio
class TestDrProfileService:
    """Service I/O against the mocked fetcher."""

    async def test_fetch_success(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE_DR_PROFILE)
        profile = await DrProfileService().fetch_dr_profile("GOOG80")
        assert profile.symbol == "GOOG80"
        assert profile.underlying == "GOOG"

    async def test_fetch_url_and_lang_param(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE_DR_PROFILE)
        await DrProfileService().fetch_dr_profile("GOOG80", lang="th")
        url = mock_fetcher.fetch.call_args[0][0]
        assert url == "https://www.set.or.th/api/set/dr/GOOG80/profile?lang=th"

    async def test_fetch_referer_is_dr_quote_page(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE_DR_PROFILE)
        await DrProfileService().fetch_dr_profile("GOOG80")
        referer = mock_fetcher.cls.get_set_api_headers.call_args.kwargs["referer"]
        assert referer == "https://www.set.or.th/en/market/product/dr/quote/GOOG80/price"

    async def test_symbol_normalization(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE_DR_PROFILE)
        await DrProfileService().fetch_dr_profile("  goog80  ")
        url = mock_fetcher.fetch.call_args[0][0]
        assert "/api/set/dr/GOOG80/profile" in url

    async def test_empty_symbol_raises_invalid_symbol(self, mock_fetcher):
        with pytest.raises(InvalidSymbolError):
            await DrProfileService().fetch_dr_profile("   ")
        mock_fetcher.fetch.assert_not_called()

    async def test_404_raises_symbol_not_found_without_suggestion(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response({"message": "Invalid DR"}, status_code=404)
        # Even with a suggester registered, the DR 404 must NOT suggest — the endpoint 404s
        # for perfectly valid non-DR symbols ("did you mean 'CPALL'?" for CPALL is nonsense).
        register_symbol_suggester(lambda symbol: "CPALL")
        try:
            with pytest.raises(SymbolNotFoundError) as excinfo:
                await DrProfileService().fetch_dr_profile("CPALL")
        finally:
            register_symbol_suggester(suggest_symbol)  # restore the real suggester
        assert excinfo.value.status_code == 404
        assert excinfo.value.suggestion is None
        assert "not a DR" in str(excinfo.value)

    async def test_other_http_error_raises_fetch_error(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(text="oops", status_code=500)
        with pytest.raises(FetchError) as excinfo:
            await DrProfileService().fetch_dr_profile("GOOG80")
        assert excinfo.value.status_code == 500

    async def test_fetch_raw_success(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE_DR_PROFILE)
        raw = await DrProfileService().fetch_dr_profile_raw("GOOG80")
        assert raw["indicativePriceSymbol"] == "NASDAQ:GOOG*FX_IDC:USDTHB/2000.0"

    async def test_fetch_raw_404_raises_symbol_not_found(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response({"message": "Invalid DR"}, status_code=404)
        with pytest.raises(SymbolNotFoundError):
            await DrProfileService().fetch_dr_profile_raw("CPALL")


@pytest.mark.asyncio
class TestConvenienceFunction:
    async def test_get_dr_profile(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE_DR_PROFILE)
        profile = await get_dr_profile("GOOG80")
        assert isinstance(profile, DrProfile)
        assert profile.symbol == "GOOG80"


@pytest.mark.asyncio
class TestStockIntegration:
    """Stock.get_dr_profile caching and Stock.get_tradingview_url."""

    async def test_stock_get_dr_profile_cached_single_fetch(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE_DR_PROFILE)
        stock = Stock("GOOG80")
        first = await stock.get_dr_profile()
        second = await stock.get_dr_profile()
        assert first is second
        assert mock_fetcher.fetch.call_count == 1
        assert stock._is_dr is True

    async def test_stock_get_dr_profile_refresh_refetches(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE_DR_PROFILE)
        stock = Stock("GOOG80")
        await stock.get_dr_profile()
        await stock.get_dr_profile(refresh=True)
        assert mock_fetcher.fetch.call_count == 2

    async def test_stock_get_dr_profile_caches_per_language(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE_DR_PROFILE)
        stock = Stock("GOOG80")
        await stock.get_dr_profile(lang="en")
        await stock.get_dr_profile(lang="th")
        await stock.get_dr_profile(lang="en")
        assert mock_fetcher.fetch.call_count == 2

    async def test_stock_get_tradingview_url(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE_DR_PROFILE)
        url = await Stock("GOOG80").get_tradingview_url()
        assert url == SAMPLE_DR_PROFILE["indicativePriceUrl"]

    async def test_stock_get_tradingview_url_none_for_non_dr(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response({"message": "Invalid DR"}, status_code=404)
        stock = Stock("CPALL")
        assert await stock.get_tradingview_url() is None
        assert stock._is_dr is False
