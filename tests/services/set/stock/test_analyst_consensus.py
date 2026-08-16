"""Tests for the SET analyst consensus (IAA) service."""

import json
import sys
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from settfex.exceptions import FetchError, InvalidLanguageError, InvalidSymbolError
from settfex.services.set.stock import Stock
from settfex.services.set.stock.analyst_consensus import (
    AnalystConsensus,
    AnalystConsensusRow,
    AnalystConsensusService,
    ConsensusOverallResponse,
    ConsensusStatistic,
    get_analyst_consensus,
    get_analyst_consensus_dataframes,
    get_consensus_overall,
)
from settfex.utils.data_fetcher import FetcherConfig, FetchResponse
from settfex.utils.parsing import ResponseParseError

# Live-captured payload for GULF (2026-08-16), trimmed to two broker rows. The four aggregate
# rows carry null identity fields; the broker rows carry a research PDF on lastResearchURL.
SAMPLE_CONSENSUS: dict[str, Any] = {
    "currentYear": "2026",
    "nextYear": "2027",
    "targetPriceYear": "2026",
    "average": {
        "id": None,
        "symbol": None,
        "brokerName": None,
        "brokerURL": None,
        "analystName": None,
        "currentYearEps": 2.421474375,
        "nextYearEps": 2.633318666666667,
        "currentYearNetProfit": 36074.269918125,
        "nextYearNetProfit": 39177.85466733333,
        "currentYearPe": 26.999511486436052,
        "nextYearPe": 24.73991076063725,
        "currentYearPbv": 2.7790181605621163,
        "nextYearPbv": 2.6575886014269505,
        "currentYearDiv": 2.2074441025641027,
        "nextYearDiv": 2.515557142857143,
        "targetPrice": 78.75,
        "targetPriceChange": 7.25,
        "targetPricePercentChange": 10.679361811631496,
        "recommend": None,
        "recommendType": None,
        "lastUpdateDate": None,
        "lastResearchURL": None,
        "fullResearchURL": None,
        "lastResearchId": None,
        "fullResearchId": None,
    },
    "median": {
        "id": None,
        "symbol": None,
        "brokerName": None,
        "analystName": None,
        "currentYearEps": 2.475,
        "targetPrice": 78.5,
        "targetPriceChange": 7.25,
        "targetPricePercentChange": 10.679361811631496,
    },
    # high/low deliberately mix in the real-world nulls: settrade nulls individual forecasts a
    # broker did not publish, and each aggregate column is computed independently.
    "high": {
        "currentYearEps": 2.67449,
        "nextYearPe": 27.083333333333336,
        "targetPrice": 91.0,
        "targetPriceChange": 12.0,
        "targetPricePercentChange": 17.91044776119403,
    },
    "low": {
        "currentYearEps": 2.02,
        "nextYearPe": None,
        "targetPrice": 72.0,
        "targetPriceChange": 2.5,
        "targetPricePercentChange": 3.4482758620689653,
    },
    "consensuses": [
        {
            "id": 350186,
            "symbol": "GULF",
            "brokerName": "ASPS",
            "brokerURL": "http://www.asiaplus.co.th",
            "analystName": "Tanya Udom",
            "currentYearEps": 2.5584,
            "nextYearEps": 2.74596,
            "currentYearNetProfit": 38222.00821,
            "nextYearNetProfit": 41024.12762,
            "currentYearPe": 25.406504065040654,
            "nextYearPe": 23.671138691022445,
            "currentYearPbv": 2.6957900468943046,
            "nextYearPbv": 2.5509012726642672,
            "currentYearDiv": 2.6568,
            "nextYearDiv": 2.851569230769231,
            "targetPrice": 80.0,
            "targetPriceChange": 0.0,
            "targetPricePercentChange": 0.0,
            "recommend": "Buy",
            "recommendType": "B",
            "lastUpdateDate": "2026-08-13T13:44:12+07:00",
            "lastResearchURL": (
                "https://portal.settrade.com/brokerpage/AnalystConsensus/Research/"
                "ASPS_GULF_350186.pdf"
            ),
            "fullResearchURL": None,
            "lastResearchId": 350186,
            "fullResearchId": None,
        },
        {
            # A real shape observed on CPALL: several numerics null, and no research PDF.
            "id": 349749,
            "symbol": "GULF",
            "brokerName": "BLS",
            "brokerURL": "http://www.bualuang.co.th",
            "analystName": "Panjapon Taensricharoen",
            "currentYearEps": 2.54,
            "nextYearEps": 2.64,
            "currentYearNetProfit": 37961.66,
            "nextYearNetProfit": 39512.59,
            "currentYearPe": 25.590551181102363,
            "nextYearPe": None,
            "currentYearPbv": 2.81507145950628,
            "nextYearPbv": None,
            "currentYearDiv": 2.9538461538461536,
            "nextYearDiv": None,
            "targetPrice": 82.0,
            "targetPriceChange": None,
            "targetPricePercentChange": None,
            "recommend": "Outperform Market",
            "recommendType": "B",
            "lastUpdateDate": "2026-08-11T15:29:00+07:00",
            "lastResearchURL": None,
            "fullResearchURL": None,
            "lastResearchId": None,
            "fullResearchId": None,
        },
    ],
}

# Live-captured for TCC (2026-08-16): no broker covers it, so settrade returns an empty
# `consensuses` list AND zero-fills every aggregate row rather than nulling them.
_ZERO_ROW: dict[str, Any] = {
    "id": None,
    "symbol": None,
    "brokerName": None,
    "brokerURL": None,
    "analystName": None,
    "currentYearEps": 0.0,
    "nextYearEps": 0.0,
    "currentYearNetProfit": 0.0,
    "nextYearNetProfit": 0.0,
    "currentYearPe": 0.0,
    "nextYearPe": 0.0,
    "currentYearPbv": 0.0,
    "nextYearPbv": 0.0,
    "currentYearDiv": 0.0,
    "nextYearDiv": 0.0,
    "targetPrice": 0.0,
    "targetPriceChange": 0.0,
    "targetPricePercentChange": 0.0,
    "recommend": None,
    "recommendType": None,
    "lastUpdateDate": None,
    "lastResearchURL": None,
    "fullResearchURL": None,
    "lastResearchId": None,
    "fullResearchId": None,
}
SAMPLE_NO_COVERAGE: dict[str, Any] = {
    "currentYear": "2026",
    "nextYear": "2027",
    "targetPriceYear": "2026",
    "average": dict(_ZERO_ROW),
    "median": dict(_ZERO_ROW),
    "high": dict(_ZERO_ROW),
    "low": dict(_ZERO_ROW),
    "consensuses": [],
}

# Live-captured summary for GULF (2026-08-16).
SAMPLE_OVERALL: dict[str, Any] = {
    "marketTime": "2026-08-15T03:20:05.697719332+07:00",
    "overall": [
        {
            "symbol": "GULF",
            "lastPrice": 64.5,
            "totalCoverage": 16,
            "buy": 16,
            "hold": 0,
            "sell": 0,
            "recommendType": "buy",
            "medianTargetPrice": 78.5,
            "averageTargetPrice": 78.75,
            "bullish": 100.0,
            "bearish": 0.0,
        }
    ],
}

# What settrade returns for a symbol it does not know: HTTP 200 with an empty list.
SAMPLE_OVERALL_EMPTY: dict[str, Any] = {
    "marketTime": "2026-08-15T03:20:05.697719332+07:00",
    "overall": [],
}

# What the table endpoint returns for an uncovered symbol - HTTP 500, not 404.
SAMPLE_ERROR_500: dict[str, Any] = {
    "timestamp": "2026-08-16T05:21:12.584+00:00",
    "status": 500,
    "error": "Internal Server Error",
    "path": "/api/consensus/stock/NOTASYMBOL123/consensus",
}


def _response(payload: Any, *, status_code: int = 200, text: str | None = None) -> FetchResponse:
    """Build a real FetchResponse (never a Mock) around a JSON payload."""
    body = text if text is not None else json.dumps(payload)
    return FetchResponse(
        status_code=status_code,
        content=body.encode("utf-8"),
        text=body,
        headers={"Content-Type": "application/json"},
        url="https://www.settrade.com/api/set-fund/consensus/stock/GULF/consensus",
        elapsed=0.1,
    )


@pytest.fixture
def mock_fetcher():
    """Patch AsyncDataFetcher in the service module; yield its async instance.

    The patched class mock is attached as ``.cls`` so tests can assert on the referer.
    """
    with patch("settfex.services.set.stock.analyst_consensus.AsyncDataFetcher") as mock:
        fetcher_instance = AsyncMock()
        mock.return_value.__aenter__.return_value = fetcher_instance
        mock.return_value.__aexit__.return_value = None
        mock.get_set_api_headers = Mock(return_value={"Accept": "application/json"})
        fetcher_instance.cls = mock
        yield fetcher_instance


class TestModelParsing:
    """Model parsing: aliases, nullability, statistic labels and derived properties."""

    def test_parses_full_payload(self) -> None:
        data = AnalystConsensus.model_validate({**SAMPLE_CONSENSUS, "symbol": "GULF"})
        assert data.symbol == "GULF"
        assert data.count == 2
        assert data.has_coverage is True
        assert data.current_year == 2026
        assert data.next_year == 2027
        assert data.target_price_year == 2026

    def test_camel_case_aliases_map(self) -> None:
        data = AnalystConsensus.model_validate({**SAMPLE_CONSENSUS, "symbol": "GULF"})
        row = data.consensuses[0]
        assert row.broker_name == "ASPS"
        assert row.broker_url == "http://www.asiaplus.co.th"
        assert row.analyst_name == "Tanya Udom"
        assert row.current_year_net_profit == pytest.approx(38222.00821)
        assert row.last_research_url is not None
        assert row.last_research_url.endswith("ASPS_GULF_350186.pdf")
        assert row.last_research_id == 350186

    def test_last_update_date_is_timezone_aware(self) -> None:
        data = AnalystConsensus.model_validate({**SAMPLE_CONSENSUS, "symbol": "GULF"})
        updated = data.consensuses[0].last_update_date
        assert isinstance(updated, datetime)
        assert updated.tzinfo is not None
        assert updated.utcoffset() is not None
        assert updated.utcoffset().total_seconds() == 7 * 3600  # type: ignore[union-attr]

    def test_every_numeric_field_is_nullable(self) -> None:
        """Real CPALL rows null individual forecasts; a non-optional float would blow up."""
        data = AnalystConsensus.model_validate({**SAMPLE_CONSENSUS, "symbol": "GULF"})
        row = data.consensuses[1]
        assert row.next_year_pe is None
        assert row.next_year_pbv is None
        assert row.next_year_div is None
        assert row.target_price_change is None
        assert row.target_price_percent_change is None
        assert row.target_price == 82.0

    def test_statistic_rows_are_labelled_and_typed(self) -> None:
        data = AnalystConsensus.model_validate({**SAMPLE_CONSENSUS, "symbol": "GULF"})
        assert isinstance(data.average, ConsensusStatistic)
        assert data.average.statistic == "average"
        assert data.median.statistic == "median"  # type: ignore[union-attr]
        assert data.high.statistic == "high"  # type: ignore[union-attr]
        assert data.low.statistic == "low"  # type: ignore[union-attr]
        assert [row.statistic for row in data.statistics] == ["average", "median", "high", "low"]

    def test_statistic_rows_have_null_identity_fields(self) -> None:
        data = AnalystConsensus.model_validate({**SAMPLE_CONSENSUS, "symbol": "GULF"})
        assert data.average.broker_name is None  # type: ignore[union-attr]
        assert data.average.analyst_name is None  # type: ignore[union-attr]
        assert data.average.recommend is None  # type: ignore[union-attr]
        assert data.average.last_update_date is None  # type: ignore[union-attr]

    def test_years_are_coerced_from_strings(self) -> None:
        data = AnalystConsensus.model_validate({**SAMPLE_CONSENSUS, "symbol": "GULF"})
        assert isinstance(data.current_year, int)

    def test_unparseable_year_becomes_none_not_an_error(self) -> None:
        """A cosmetic label must never fail a whole fetch of financial data."""
        payload = {**SAMPLE_CONSENSUS, "symbol": "GULF", "currentYear": "N/A"}
        data = AnalystConsensus.model_validate(payload)
        assert data.current_year is None
        assert data.count == 2

    def test_research_url_prefers_last_then_full(self) -> None:
        row = AnalystConsensusRow.model_validate(
            {"lastResearchURL": None, "fullResearchURL": "http://x/full.pdf"}
        )
        assert row.research_url == "http://x/full.pdf"
        assert row.has_research is True

        bare = AnalystConsensusRow.model_validate({"brokerName": "CGSI"})
        assert bare.research_url is None
        assert bare.has_research is False

    def test_recommend_group_maps_known_codes_only(self) -> None:
        assert AnalystConsensusRow.model_validate({"recommendType": "B"}).recommend_group == "buy"
        assert AnalystConsensusRow.model_validate({"recommendType": "h"}).recommend_group == "hold"
        assert AnalystConsensusRow.model_validate({"recommendType": "S"}).recommend_group == "sell"
        assert AnalystConsensusRow.model_validate({"recommendType": "Z"}).recommend_group is None
        assert AnalystConsensusRow.model_validate({}).recommend_group is None

    def test_helper_properties(self) -> None:
        data = AnalystConsensus.model_validate({**SAMPLE_CONSENSUS, "symbol": "GULF"})
        assert data.broker_names == ["ASPS", "BLS"]
        assert len(data.with_research) == 1
        assert data.research_urls[0][0] == "ASPS"
        assert data.latest_update == datetime.fromisoformat("2026-08-13T13:44:12+07:00")
        assert data.brokers is data.consensuses

    def test_broker_lookup_is_case_insensitive(self) -> None:
        data = AnalystConsensus.model_validate({**SAMPLE_CONSENSUS, "symbol": "GULF"})
        assert data.broker("asps") is not None
        assert data.broker("  BLS  ") is not None
        assert data.broker("NOSUCH") is None

    def test_no_coverage_payload_zero_fills_instead_of_nulling(self) -> None:
        """The sharpest footgun: 0.0 aggregates that look like real estimates."""
        data = AnalystConsensus.model_validate({**SAMPLE_NO_COVERAGE, "symbol": "TCC"})
        assert data.has_coverage is False
        assert data.count == 0
        assert data.average.target_price == 0.0  # type: ignore[union-attr]

    def test_has_coverage_survives_model_dump(self) -> None:
        """It is a computed field so the warning rides along into Parquet/JSON."""
        data = AnalystConsensus.model_validate({**SAMPLE_NO_COVERAGE, "symbol": "TCC"})
        assert data.model_dump()["has_coverage"] is False

    def test_overall_response_parsing(self) -> None:
        response = ConsensusOverallResponse.model_validate(SAMPLE_OVERALL)
        assert response.count == 1
        row = response.get("gulf")
        assert row is not None
        assert row.total_coverage == 16
        assert row.buy == 16
        assert row.hold == 0
        assert row.bullish == 100.0
        assert row.median_target_price == 78.5
        assert response.market_time is not None
        assert response.market_time.tzinfo is not None

    def test_overall_empty_is_not_an_error(self) -> None:
        response = ConsensusOverallResponse.model_validate(SAMPLE_OVERALL_EMPTY)
        assert response.count == 0
        assert response.get("GULF") is None


class TestDataFrames:
    """The two DataFrame views: broker rows and aggregate rows."""

    @staticmethod
    def _data() -> AnalystConsensus:
        return AnalystConsensus.model_validate({**SAMPLE_CONSENSUS, "symbol": "GULF"})

    def test_brokers_dataframe_default_columns(self) -> None:
        df = self._data().to_dataframe()
        assert list(df.columns) == [
            "broker_name",
            "analyst_name",
            "recommend",
            "recommend_type",
            "target_price",
            "target_price_change",
            "target_price_percent_change",
            "current_year_eps",
            "next_year_eps",
            "current_year_net_profit",
            "next_year_net_profit",
            "current_year_pe",
            "next_year_pe",
            "current_year_pbv",
            "next_year_pbv",
            "current_year_div",
            "next_year_div",
            "last_update_date",
            "research_url",
        ]
        assert len(df) == 2
        assert df.iloc[0]["broker_name"] == "ASPS"
        assert df.iloc[0]["research_url"].endswith("ASPS_GULF_350186.pdf")
        assert df.iloc[1]["research_url"] is None

    def test_stats_dataframe_has_four_labelled_rows(self) -> None:
        df = self._data().stats_to_dataframe()
        assert list(df["statistic"]) == ["average", "median", "high", "low"]
        assert df.columns[0] == "statistic"
        assert len(df) == 4
        assert df.set_index("statistic").loc["high", "target_price"] == 91.0

    def test_stats_dataframe_excludes_identity_columns_by_default(self) -> None:
        df = self._data().stats_to_dataframe()
        for column in ("broker_name", "analyst_name", "recommend", "research_url"):
            assert column not in df.columns

    def test_stats_dataframe_can_still_select_identity_columns(self) -> None:
        df = self._data().stats_to_dataframe(columns=["statistic", "broker_name"])
        assert list(df.columns) == ["statistic", "broker_name"]
        assert df["broker_name"].isna().all()

    def test_dataframe_attrs_carry_year_labels(self) -> None:
        """Column names stay year-agnostic, so the years ride along as metadata."""
        for df in (self._data().to_dataframe(), self._data().stats_to_dataframe()):
            assert df.attrs["symbol"] == "GULF"
            assert df.attrs["current_year"] == 2026
            assert df.attrs["next_year"] == 2027
            assert df.attrs["has_coverage"] is True

    def test_column_selection_and_ordering(self) -> None:
        df = self._data().to_dataframe(columns=["target_price", "broker_name"])
        assert list(df.columns) == ["target_price", "broker_name"]

    def test_unknown_column_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown DataFrame column"):
            self._data().to_dataframe(columns=["broker_name", "nope"])
        with pytest.raises(ValueError, match="Unknown DataFrame column"):
            self._data().stats_to_dataframe(columns=["nope"])

    def test_empty_but_typed_when_no_coverage(self) -> None:
        data = AnalystConsensus.model_validate({**SAMPLE_NO_COVERAGE, "symbol": "TCC"})
        df = data.to_dataframe()
        assert len(df) == 0
        assert "broker_name" in df.columns
        # The aggregates are still four rows - of settrade's zero-fill, flagged by has_coverage.
        assert len(data.stats_to_dataframe()) == 4
        assert data.stats_to_dataframe().attrs["has_coverage"] is False

    def test_overall_dataframe(self) -> None:
        df = ConsensusOverallResponse.model_validate(SAMPLE_OVERALL).to_dataframe()
        assert list(df.columns)[:4] == ["symbol", "last_price", "total_coverage", "buy"]
        assert df.iloc[0]["symbol"] == "GULF"
        assert df.attrs["market_time"] is not None

    def test_missing_pandas_raises_helpful_import_error(self, monkeypatch) -> None:
        monkeypatch.setitem(sys.modules, "pandas", None)
        with pytest.raises(ImportError, match=r"settfex\[dataframe\]"):
            self._data().to_dataframe()
        with pytest.raises(ImportError, match="stats_to_dataframe"):
            self._data().stats_to_dataframe()


@pytest.mark.asyncio
class TestAnalystConsensusService:
    """Service behaviour: URLs, headers, normalization and error mapping."""

    async def test_fetch_success(self, mock_fetcher) -> None:
        mock_fetcher.fetch.return_value = _response(SAMPLE_CONSENSUS)
        data = await AnalystConsensusService().fetch_analyst_consensus("GULF")
        assert data.symbol == "GULF"
        assert data.count == 2

    async def test_url_and_symbol_normalization(self, mock_fetcher) -> None:
        mock_fetcher.fetch.return_value = _response(SAMPLE_CONSENSUS)
        await AnalystConsensusService().fetch_analyst_consensus("  gulf  ")
        url = mock_fetcher.fetch.call_args.args[0]
        assert url == ("https://www.settrade.com/api/set-fund/consensus/stock/GULF/consensus")

    async def test_referer_is_a_settrade_url(self, mock_fetcher) -> None:
        """Load-bearing bot-protection invariant: a missing/foreign Referer is a 403."""
        mock_fetcher.fetch.return_value = _response(SAMPLE_CONSENSUS)
        await AnalystConsensusService().fetch_analyst_consensus("gulf")
        referer = mock_fetcher.cls.get_set_api_headers.call_args.kwargs["referer"]
        assert referer.startswith("https://www.settrade.com/")
        assert "GULF" in referer

    async def test_empty_symbol_raises(self, mock_fetcher) -> None:
        with pytest.raises(InvalidSymbolError, match="symbol cannot be empty"):
            await AnalystConsensusService().fetch_analyst_consensus("   ")
        mock_fetcher.fetch.assert_not_called()

    async def test_http_500_is_fetch_error_not_symbol_not_found(self, mock_fetcher) -> None:
        """500 means "no consensus record" - and it fires for VALID symbols like ABICO,
        so a SymbolNotFoundError (and its "did you mean 'ABICO'?" suggester) would be absurd.
        """
        mock_fetcher.fetch.return_value = _response(SAMPLE_ERROR_500, status_code=500)
        with pytest.raises(FetchError, match="No analyst consensus") as excinfo:
            await AnalystConsensusService().fetch_analyst_consensus("ABICO")
        assert excinfo.value.status_code == 500
        assert excinfo.value.symbol == "ABICO"
        assert type(excinfo.value) is FetchError

    async def test_http_403_mentions_bot_protection(self, mock_fetcher) -> None:
        mock_fetcher.fetch.return_value = _response(None, status_code=403, text="<html>")
        with pytest.raises(FetchError, match="bot protection") as excinfo:
            await AnalystConsensusService().fetch_analyst_consensus("GULF")
        assert excinfo.value.status_code == 403

    async def test_other_http_error(self, mock_fetcher) -> None:
        mock_fetcher.fetch.return_value = _response(None, status_code=502, text="bad gateway")
        with pytest.raises(FetchError) as excinfo:
            await AnalystConsensusService().fetch_analyst_consensus("GULF")
        assert excinfo.value.status_code == 502

    async def test_non_json_body_raises_parse_error(self, mock_fetcher) -> None:
        mock_fetcher.fetch.return_value = _response(None, text="<html>not json</html>")
        with pytest.raises(ResponseParseError):
            await AnalystConsensusService().fetch_analyst_consensus("GULF")

    async def test_json_array_body_raises_parse_error(self, mock_fetcher) -> None:
        mock_fetcher.fetch.return_value = _response([1, 2, 3])
        with pytest.raises(ResponseParseError, match="Expected a JSON object"):
            await AnalystConsensusService().fetch_analyst_consensus("GULF")

    async def test_no_coverage_parses_and_flags(self, mock_fetcher) -> None:
        mock_fetcher.fetch.return_value = _response(SAMPLE_NO_COVERAGE)
        data = await AnalystConsensusService().fetch_analyst_consensus("TCC")
        assert data.has_coverage is False
        assert data.count == 0

    async def test_raw_returns_payload_verbatim(self, mock_fetcher) -> None:
        mock_fetcher.fetch.return_value = _response(SAMPLE_CONSENSUS)
        raw = await AnalystConsensusService().fetch_analyst_consensus_raw("gulf")
        assert raw == SAMPLE_CONSENSUS
        assert "symbol" not in raw  # no injected symbol on the raw path
        assert "has_coverage" not in raw

    async def test_raw_rejects_empty_symbol(self, mock_fetcher) -> None:
        with pytest.raises(InvalidSymbolError):
            await AnalystConsensusService().fetch_analyst_consensus_raw("")

    async def test_config_is_used(self) -> None:
        config = FetcherConfig(timeout=60)
        assert AnalystConsensusService(config=config).config is config
        assert AnalystConsensusService().base_url == "https://www.settrade.com"


@pytest.mark.asyncio
class TestOverall:
    """The buy/hold/sell summary endpoint, including the whole-market variant."""

    async def test_with_symbol(self, mock_fetcher) -> None:
        mock_fetcher.fetch.return_value = _response(SAMPLE_OVERALL)
        response = await AnalystConsensusService().fetch_overall("gulf")
        assert response.count == 1
        url = mock_fetcher.fetch.call_args.args[0]
        assert url.endswith("/api/set-fund/consensus/stock/overall?lang=en&symbol=GULF")

    async def test_language_is_propagated_and_normalized(self, mock_fetcher) -> None:
        mock_fetcher.fetch.return_value = _response(SAMPLE_OVERALL)
        await AnalystConsensusService().fetch_overall("GULF", lang="thai")  # type: ignore[arg-type]
        assert "lang=th" in mock_fetcher.fetch.call_args.args[0]

    async def test_invalid_language_raises(self, mock_fetcher) -> None:
        with pytest.raises(InvalidLanguageError):
            await AnalystConsensusService().fetch_overall("GULF", lang="klingon")  # type: ignore[arg-type]
        mock_fetcher.fetch.assert_not_called()

    async def test_whole_market_omits_the_symbol_param(self, mock_fetcher) -> None:
        mock_fetcher.fetch.return_value = _response(SAMPLE_OVERALL)
        await AnalystConsensusService().fetch_overall()
        url = mock_fetcher.fetch.call_args.args[0]
        assert url.endswith("/overall?lang=en")
        assert "symbol=" not in url

    async def test_unknown_symbol_returns_zero_rows_not_an_error(self, mock_fetcher) -> None:
        mock_fetcher.fetch.return_value = _response(SAMPLE_OVERALL_EMPTY)
        response = await AnalystConsensusService().fetch_overall("NOSUCH")
        assert response.count == 0
        assert response.get("NOSUCH") is None

    async def test_blank_symbol_raises(self, mock_fetcher) -> None:
        with pytest.raises(InvalidSymbolError):
            await AnalystConsensusService().fetch_overall("  ")

    async def test_raw_variant(self, mock_fetcher) -> None:
        mock_fetcher.fetch.return_value = _response(SAMPLE_OVERALL_EMPTY)
        raw = await AnalystConsensusService().fetch_overall_raw("NOSUCH")
        assert raw == SAMPLE_OVERALL_EMPTY


@pytest.mark.asyncio
class TestConvenienceAndStock:
    """The module-level get_*() tier and the unified Stock accessors."""

    async def test_get_analyst_consensus(self, mock_fetcher) -> None:
        mock_fetcher.fetch.return_value = _response(SAMPLE_CONSENSUS)
        data = await get_analyst_consensus("gulf")
        assert data.symbol == "GULF"
        assert data.count == 2

    async def test_get_consensus_overall(self, mock_fetcher) -> None:
        mock_fetcher.fetch.return_value = _response(SAMPLE_OVERALL)
        response = await get_consensus_overall("GULF")
        assert response.count == 1

    async def test_get_analyst_consensus_dataframes_order(self, mock_fetcher) -> None:
        mock_fetcher.fetch.return_value = _response(SAMPLE_CONSENSUS)
        stats_df, brokers_df = await get_analyst_consensus_dataframes("GULF")
        assert list(stats_df["statistic"]) == ["average", "median", "high", "low"]
        assert list(brokers_df["broker_name"]) == ["ASPS", "BLS"]

    async def test_stock_accessor(self, mock_fetcher) -> None:
        mock_fetcher.fetch.return_value = _response(SAMPLE_CONSENSUS)
        data = await Stock("gulf").get_analyst_consensus()
        assert data.symbol == "GULF"

    async def test_stock_accessor_caches_and_refreshes(self, mock_fetcher) -> None:
        mock_fetcher.fetch.return_value = _response(SAMPLE_CONSENSUS)
        stock = Stock("GULF")
        first = await stock.get_analyst_consensus()
        second = await stock.get_analyst_consensus()
        assert first is second
        assert mock_fetcher.fetch.call_count == 1

        await stock.get_analyst_consensus(refresh=True)
        assert mock_fetcher.fetch.call_count == 2

    async def test_stock_overall_accessor_is_not_cached(self, mock_fetcher) -> None:
        """It carries a live last_price, so it must refetch every time."""
        mock_fetcher.fetch.return_value = _response(SAMPLE_OVERALL)
        stock = Stock("GULF")
        await stock.get_consensus_overall()
        await stock.get_consensus_overall()
        assert mock_fetcher.fetch.call_count == 2

    async def test_stock_service_property_is_lazy_and_passes_config(self) -> None:
        config = FetcherConfig(timeout=45)
        stock = Stock("GULF", config=config)
        assert stock._analyst_consensus_service is None
        service = stock.analyst_consensus_service
        assert service.config is config
        assert stock.analyst_consensus_service is service
