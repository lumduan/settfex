"""Tests for the SET stock info service (live quote block + trading signs)."""

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from settfex.exceptions import FetchError, InvalidSymbolError, SymbolNotFoundError
from settfex.services.set.asset_type import AssetType
from settfex.services.set.stock.info import (
    Inav,
    StockInfo,
    StockInfoService,
    get_stock_info,
    parse_signs,
)
from settfex.services.set.stock.stock import Stock
from settfex.utils.data_fetcher import FetcherConfig, FetchResponse

BKK = timezone(timedelta(hours=7))

# Real CPALL payload (captured live 2026-09-19). Untagged security: sign is "" and every
# derivative/fund field is null.
SAMPLE: dict[str, Any] = {
    "symbol": "CPALL",
    "sign": "",
    "prior": 45.25,
    "last": 45.0,
    "open": 45.25,
    "high": 45.5,
    "low": 44.75,
    "average": 44.97793,
    "floor": 31.75,
    "ceiling": 58.75,
    "change": -0.25,
    "percentChange": -0.552486,
    "totalVolume": 25258498.0,
    "totalValue": 1136075329.5,
    "trVolume": None,
    "trValue": None,
    "aomVolume": 25245800.0,
    "aomValue": 1135503850.0,
    "bids": [{"volume": 4362900.0, "price": "44.75"}],
    "offers": [{"volume": 6649300.0, "price": "45.00"}],
    "marketStatus": "Closed",
    # 9 fractional digits: SET serves nanosecond precision here, unlike every other endpoint.
    "marketDateTime": "2026-09-19T03:20:11.783886192+07:00",
    "securityType": "S",
    "tickSize": 0.25,
    "nameEN": "CP ALL PUBLIC COMPANY LIMITED",
    "nameTH": "บริษัท ซีพี ออลล์ จำกัด (มหาชน)",
    "marketName": "SET",
    "industryName": "SERVICE",
    "sectorName": "COMM",
    "isNPG": False,
    "high52Weeks": 54.5,
    "low52Weeks": 40.5,
    "par": 1.0,
    "inav": None,
    "multiplier": None,
    "exerciseRatio": "1 : 1",
    "exercisePrice": None,
    "exercisePriceUnit": "THB",
    "maturityDate": None,
    "lastTradingDate": None,
    "underlying": "",
    "isIFF": False,
    "isPFUND": False,
    "statisticsAsOf": "2026-09-18T00:00:00+07:00",
    "marketCap": 404239560660.0,
    "peRatio": 13.16,
    "pbRatio": 2.84,
    "dividendYield": 3.67,
    "nvdrNetVolume": -3522179.0,
    "listedShare": 8983101348,
    "ttm": None,
    "moneynessStatus": None,
    "moneynessPercent": None,
}

# Real GRAND payload (live 2026-09-19): four simultaneous signs, halted book, null prices.
SUSPENDED: dict[str, Any] = {
    **SAMPLE,
    "symbol": "GRAND",
    "sign": "SP, CB, CS, CC",
    "last": None,
    "open": None,
    "high": None,
    "low": None,
    "average": None,
    "change": None,
    "percentChange": None,
    "totalVolume": None,
    "totalValue": None,
    "aomVolume": None,
    "aomValue": None,
    "bids": [],
    "offers": [],
    "marketStatus": "Suspend",
    "nameEN": "GRANDE ASSET HOTELS AND PROPERTY PUBLIC COMPANY LIMITED",
}

# Real AAV13C2610A payload (live 2026-09-19): a DW carries exercise terms and moneyness.
DERIVATIVE_WARRANT: dict[str, Any] = {
    **SAMPLE,
    "symbol": "AAV13C2610A",
    "securityType": "V",
    "industryName": "",
    "sectorName": "",
    "par": None,
    "multiplier": 2.7777777777777777,
    "exerciseRatio": "0.36 : 1",
    "exercisePrice": 1.45,
    "maturityDate": "2026-10-07T00:00:00+07:00",
    "lastTradingDate": "2026-10-02T00:00:00+07:00",
    "underlying": "AAV",
    "ttm": 12,
    "moneynessStatus": "OTM",
    "moneynessPercent": 41.0,
}

# Real 1DIV payload (live 2026-09-19): only ETFs populate the nested inav object.
ETF: dict[str, Any] = {
    **SAMPLE,
    "symbol": "1DIV",
    "securityType": "L",
    "inav": {"inav": 14.4522, "change": 0.0637, "percentChange": 0.44},
    "multiplier": 1.0,
    "exerciseRatio": None,
    "exercisePriceUnit": "Point",
    "underlying": "SETHD",
}


def _response(payload: dict[str, Any], status_code: int = 200) -> FetchResponse:
    """Build a FetchResponse whose body is ``payload`` serialized as JSON."""
    body = json.dumps(payload)
    return FetchResponse(
        status_code=status_code,
        content=body.encode("utf-8"),
        text=body,
        headers={},
        url="https://www.set.or.th/api/set/stock/CPALL/info",
        elapsed=0.1,
    )


@pytest.fixture
def mock_fetcher():
    """Patch AsyncDataFetcher in the service module; yield its async instance.

    The patched class mock is attached as ``.cls`` for referer assertions.
    """
    with patch("settfex.services.set.stock.info.AsyncDataFetcher") as mock:
        fetcher_instance = AsyncMock()
        mock.return_value.__aenter__.return_value = fetcher_instance
        mock.return_value.__aexit__.return_value = None
        mock.get_set_api_headers = Mock(return_value={"Accept": "application/json"})
        fetcher_instance.cls = mock
        yield fetcher_instance


class TestParseSigns:
    """The comma-separated sign string is the one field with no other home in the package."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("SP, CB, CS, CC", ["SP", "CB", "CS", "CC"]),
            ("SP", ["SP"]),
            ("SP,NC", ["SP", "NC"]),  # no space after the comma
            ("  sp , nc  ", ["SP", "NC"]),  # padded and lowercase
            ("SP, , NC", ["SP", "NC"]),  # empty segment dropped
            ("", []),
            ("   ", []),
            (None, []),
        ],
    )
    def test_parse_signs(self, raw, expected):
        assert parse_signs(raw) == expected


class TestModelParsing:
    """Pydantic parsing: camelCase aliases, datetimes, nested blocks, computed fields."""

    def test_aliases_and_values(self):
        info = StockInfo.model_validate(SAMPLE)
        assert info.symbol == "CPALL"
        assert info.last == 45.0
        assert info.percent_change == -0.552486  # percentChange
        assert info.total_volume == 25258498.0  # totalVolume
        assert info.aom_value == 1135503850.0  # aomValue
        assert info.market_status == "Closed"  # marketStatus
        assert info.tick_size == 0.25  # tickSize
        assert info.name_en == "CP ALL PUBLIC COMPANY LIMITED"  # nameEN
        assert info.high_52_weeks == 54.5  # high52Weeks
        assert info.market_cap == 404239560660.0  # marketCap
        assert info.pe_ratio == 13.16  # peRatio
        assert info.nvdr_net_volume == -3522179.0  # nvdrNetVolume
        assert info.is_npg is False  # isNPG
        assert info.is_pfund is False  # isPFUND

    def test_nanosecond_timestamp_is_truncated_not_rejected(self):
        """SET sends 9 fractional digits here; datetime holds 6, so it must truncate."""
        info = StockInfo.model_validate(SAMPLE)
        assert info.market_date_time == datetime(2026, 9, 19, 3, 20, 11, 783886, tzinfo=BKK)
        assert info.statistics_as_of == datetime(2026, 9, 18, tzinfo=BKK)

    def test_bid_offer_string_prices_are_coerced(self):
        """The API sends ladder prices as strings ("44.75"), volumes as numbers."""
        info = StockInfo.model_validate(SAMPLE)
        assert info.bids[0].price == 44.75
        assert info.bids[0].volume == 4362900.0
        assert info.offers[0].price == 45.00
        assert info.best_bid == 44.75
        assert info.best_offer == 45.00

    def test_empty_book_gives_none_best_prices(self):
        info = StockInfo.model_validate(SUSPENDED)
        assert info.bids == []
        assert info.offers == []
        assert info.best_bid is None
        assert info.best_offer is None

    def test_nullable_fields(self):
        info = StockInfo.model_validate(SAMPLE)
        assert info.tr_volume is None  # trVolume
        assert info.inav is None
        assert info.maturity_date is None  # maturityDate
        assert info.ttm is None
        assert info.moneyness_status is None  # moneynessStatus

    def test_exercise_ratio_kept_verbatim(self):
        """Ratios arrive as display strings ('3,000 : 1'); never reformat them."""
        assert StockInfo.model_validate(SAMPLE).exercise_ratio == "1 : 1"
        assert StockInfo.model_validate(DERIVATIVE_WARRANT).exercise_ratio == "0.36 : 1"
        assert StockInfo.model_validate(
            {**SAMPLE, "exerciseRatio": "3,000 : 1"}
        ).exercise_ratio == ("3,000 : 1")

    def test_derivative_warrant_fields(self):
        info = StockInfo.model_validate(DERIVATIVE_WARRANT)
        assert info.exercise_price == 1.45  # exercisePrice
        assert info.exercise_price_unit == "THB"  # exercisePriceUnit
        assert info.maturity_date == datetime(2026, 10, 7, tzinfo=BKK)
        assert info.last_trading_date == datetime(2026, 10, 2, tzinfo=BKK)
        assert info.ttm == 12
        assert info.moneyness_status == "OTM"
        assert info.moneyness_percent == 41.0
        assert info.underlying == "AAV"

    def test_etf_inav_block(self):
        info = StockInfo.model_validate(ETF)
        assert isinstance(info.inav, Inav)
        assert info.inav.inav == 14.4522
        assert info.inav.change == 0.0637
        assert info.inav.percent_change == 0.44  # percentChange
        assert info.exercise_ratio is None

    def test_populate_by_name(self):
        """Field names work as well as aliases (populate_by_name)."""
        info = StockInfo(symbol="CPALL", percent_change=1.5, market_status="Open2")
        assert info.percent_change == 1.5
        assert info.market_status == "Open2"


class TestSignHelpers:
    """signs / has_sign / is_suspended, and why is_suspended is not market_status."""

    def test_signs_and_is_suspended(self):
        info = StockInfo.model_validate(SUSPENDED)
        assert info.signs == ["SP", "CB", "CS", "CC"]
        assert info.is_suspended is True

    def test_untagged_security(self):
        info = StockInfo.model_validate(SAMPLE)
        assert info.signs == []
        assert info.is_suspended is False
        assert info.has_sign("SP") is False

    def test_has_sign_is_case_insensitive_and_exact(self):
        info = StockInfo.model_validate(SUSPENDED)
        assert info.has_sign("sp") is True
        assert info.has_sign(" CB ") is True
        assert info.has_sign("NC") is False
        # 'S' is a prefix of 'SP' but not a sign this symbol carries
        assert info.has_sign("S") is False

    def test_is_suspended_reads_the_sign_not_the_market_status(self):
        """market_status says 'Closed' after hours for every symbol; only the sign is per-symbol."""
        closed_but_suspended = StockInfo.model_validate(
            {**SAMPLE, "sign": "SP", "marketStatus": "Closed"}
        )
        assert closed_but_suspended.is_suspended is True

        halted_status_no_sign = StockInfo.model_validate(
            {**SAMPLE, "sign": "", "marketStatus": "Suspend"}
        )
        assert halted_status_no_sign.is_suspended is False

    def test_computed_fields_survive_model_dump(self):
        """signs/is_suspended are computed fields so a Parquet/JSON dump keeps the parsed form."""
        dumped = StockInfo.model_validate(SUSPENDED).model_dump(mode="json")
        assert dumped["signs"] == ["SP", "CB", "CS", "CC"]
        assert dumped["is_suspended"] is True
        json.dumps(dumped)  # must stay strict-JSON serializable

    @pytest.mark.parametrize(
        ("security_type", "expected"),
        [
            ("S", AssetType.STOCK),
            ("V", AssetType.DERIVATIVE_WARRANT),
            ("X", AssetType.DEPOSITARY_RECEIPT),
            ("L", AssetType.ETF),
            ("ZZ", AssetType.UNKNOWN),
            (None, AssetType.UNKNOWN),
        ],
    )
    def test_asset_type(self, security_type, expected):
        info = StockInfo.model_validate({**SAMPLE, "securityType": security_type})
        assert info.asset_type is expected


@pytest.mark.asyncio
class TestStockInfoService:
    """Service I/O: fetch, raw fetch, URL/referer construction, error handling."""

    async def test_init_default_and_custom_config(self):
        assert StockInfoService().base_url == "https://www.set.or.th"
        service = StockInfoService(config=FetcherConfig(timeout=60, max_retries=5))
        assert service.config.timeout == 60
        assert service.config.max_retries == 5

    async def test_fetch_success(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SUSPENDED)
        result = await StockInfoService().fetch_stock_info("GRAND")
        assert isinstance(result, StockInfo)
        assert result.signs == ["SP", "CB", "CS", "CC"]
        assert result.is_suspended is True

    async def test_fetch_url_and_referer_and_symbol_normalization(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        await StockInfoService().fetch_stock_info("cpall")
        url = mock_fetcher.fetch.call_args.args[0]
        assert url == "https://www.set.or.th/api/set/stock/CPALL/info"
        referer = mock_fetcher.cls.get_set_api_headers.call_args.kwargs["referer"]
        assert referer == "https://www.set.or.th/en/market/product/stock/quote/CPALL/price"

    async def test_hyphenated_symbol_is_not_mangled(self, mock_fetcher):
        """Warrants and foreign shares carry hyphens ('A5-W5', '2S-F')."""
        mock_fetcher.fetch.return_value = _response({**SAMPLE, "symbol": "A5-W5"})
        await StockInfoService().fetch_stock_info("a5-w5")
        assert mock_fetcher.fetch.call_args.args[0].endswith("/api/set/stock/A5-W5/info")

    async def test_fetch_sends_no_language_param(self, mock_fetcher):
        """The endpoint has no language dimension — en and th payloads are identical."""
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        await StockInfoService().fetch_stock_info("CPALL")
        url = mock_fetcher.fetch.call_args.args[0]
        assert "lang" not in url and "?" not in url

    async def test_fetch_empty_symbol_raises(self):
        with pytest.raises(InvalidSymbolError, match="symbol cannot be empty"):
            await StockInfoService().fetch_stock_info("   ")

    async def test_fetch_404_raises_symbol_not_found(self, mock_fetcher):
        """An unknown symbol answers 404 {"message": "Invalid Stock Name"}."""
        mock_fetcher.fetch.return_value = _response({"message": "Invalid Stock Name"}, 404)
        with pytest.raises(SymbolNotFoundError, match="HTTP 404"):
            await StockInfoService().fetch_stock_info("NOTREAL")

    async def test_fetch_500_raises_fetch_error(self, mock_fetcher):
        mock_fetcher.fetch.return_value = FetchResponse(
            status_code=500, content=b"", text="", headers={}, url="x", elapsed=0.1
        )
        with pytest.raises(FetchError, match="HTTP 500"):
            await StockInfoService().fetch_stock_info("CPALL")

    async def test_fetch_raw_success(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        raw = await StockInfoService().fetch_stock_info_raw("CPALL")
        assert isinstance(raw, dict)
        assert raw["sign"] == ""
        assert raw["bids"] == [{"volume": 4362900.0, "price": "44.75"}]

    async def test_fetch_raw_empty_symbol_raises(self):
        with pytest.raises(InvalidSymbolError, match="symbol cannot be empty"):
            await StockInfoService().fetch_stock_info_raw("")

    async def test_fetch_raw_http_error_raises(self, mock_fetcher):
        mock_fetcher.fetch.return_value = FetchResponse(
            status_code=503, content=b"", text="", headers={}, url="x", elapsed=0.1
        )
        with pytest.raises(FetchError, match="HTTP 503"):
            await StockInfoService().fetch_stock_info_raw("CPALL")


@pytest.mark.asyncio
class TestConvenienceAndStock:
    """Top-level convenience function and the unified Stock accessors."""

    async def test_get_stock_info(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        result = await get_stock_info("CPALL")
        assert isinstance(result, StockInfo)
        assert result.market_cap == 404239560660.0

    async def test_get_stock_info_with_config(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        result = await get_stock_info("CPALL", config=FetcherConfig(timeout=5))
        assert result.symbol == "CPALL"

    async def test_stock_get_info(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SUSPENDED)
        result = await Stock("GRAND").get_info()
        assert isinstance(result, StockInfo)
        assert result.market_status == "Suspend"

    async def test_stock_get_signs_and_is_suspended(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(SUSPENDED)
        stock = Stock("grand")
        assert await stock.get_signs() == ["SP", "CB", "CS", "CC"]
        assert await stock.is_suspended() is True

    async def test_stock_info_service_is_reused(self, mock_fetcher):
        """The lazy property caches the service instance, like every other Stock accessor."""
        stock = Stock("CPALL")
        assert stock.info_service is stock.info_service

    async def test_stock_get_info_is_not_cached(self, mock_fetcher):
        """Live trading state must refetch — unlike get_asset_type/get_dr_profile."""
        mock_fetcher.fetch.return_value = _response(SAMPLE)
        stock = Stock("CPALL")
        await stock.get_info()
        await stock.get_info()
        assert mock_fetcher.fetch.call_count == 2
