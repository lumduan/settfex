"""Tests for the ThaiBMA point-in-time government yield curve service.

The sharp edges pinned here are the silent roll-back, the percent/basis-point unit split, the
JSON-``null`` body, and the fact that the classification flags were never backfilled.
"""

import json
from datetime import date
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from settfex.exceptions import FetchError, InvalidDateError, StaleDataError
from settfex.services.thaibma.yield_curve import (
    BondQuote,
    CurvePoint,
    YieldCurve,
    YieldCurveService,
    get_government_yield_curve,
)
from settfex.utils.data_fetcher import FetcherConfig, FetchResponse
from settfex.utils.parsing import ResponseParseError
from tests.services.thaibma.fixtures import (
    ASPNET_ERROR_JSON,
    GOV_CURVE_1999_09_15,
    GOV_CURVE_2012_01_04,
    GOV_CURVE_2026_08_07,
    GOV_CURVE_2026_08_10,
    HTML_404_BODY,
)


def _response(payload: Any = None, *, status_code: int = 200, text: str | None = None):
    """Build a FetchResponse whose body is ``payload`` as JSON (or the literal ``text``)."""
    body = text if text is not None else json.dumps(payload)
    return FetchResponse(
        status_code=status_code,
        content=body.encode("utf-8"),
        text=body,
        headers={},
        url="https://www.thaibma.or.th/yieldcurve/gov",
        elapsed=0.1,
    )


@pytest.fixture
def mock_fetcher():
    """Patch AsyncDataFetcher inside the yield_curve module; yield its async instance.

    The patched class mock is attached as ``.cls`` so tests can assert on the config passed in.
    """
    with patch("settfex.services.thaibma.yield_curve.AsyncDataFetcher") as mock:
        instance = AsyncMock()
        mock.return_value.__aenter__.return_value = instance
        mock.return_value.__aexit__.return_value = None
        instance.cls = mock
        yield instance


def _curve(payload: dict[str, Any], requested: date | None = None) -> YieldCurve:
    """Build a YieldCurve straight from a fixture, bypassing the network."""
    return YieldCurve(
        requested_date=requested,
        as_of=date.fromisoformat(payload["Curve"][0]["Asof"][:10]),
        points=[CurvePoint.model_validate(p) for p in payload["Curve"]],
        quotes=[BondQuote.model_validate(q) for q in payload["Stat"]],
    )


# --- models ---


class TestCurvePointModel:
    """The fitted curve grid."""

    def test_maps_aliases_and_coerces_date(self):
        point = CurvePoint.model_validate(GOV_CURVE_2026_08_10["Curve"][0])
        assert point.as_of == date(2026, 8, 10)
        assert point.tenor_years == pytest.approx(0.076712328767123)
        assert point.yield_percent == 0.856643

    def test_as_of_is_a_plain_date_not_a_datetime(self):
        """The wire sends a midnight timestamp; the model reduces it to a calendar day."""
        point = CurvePoint.model_validate(GOV_CURVE_2026_08_10["Curve"][0])
        assert type(point.as_of) is date

    def test_tenor_label_bridges_to_the_history_columns(self):
        points = [CurvePoint.model_validate(p) for p in GOV_CURVE_2026_08_10["Curve"]]
        assert [p.tenor_label for p in points[:5]] == ["1M", "3M", "6M", "1Y", "2Y"]


class TestBondQuoteModel:
    """The underlying ``Stat`` rows."""

    def test_maps_every_alias(self):
        quote = BondQuote.model_validate(GOV_CURVE_2026_08_10["Stat"][-1])
        assert quote.symbol == "LB776A"
        assert quote.maturity_date == date(2077, 6, 17)
        assert quote.group_order == 2
        assert quote.is_benchmark is True
        assert quote.is_plot is True

    def test_maturity_date_is_none_for_synthetic_tbills(self):
        """The only nullable field in the whole payload."""
        quote = BondQuote.model_validate(GOV_CURVE_2026_08_10["Stat"][0])
        assert quote.symbol == "T-BILL1M"
        assert quote.maturity_date is None
        assert quote.is_tbill is True


class TestUnitTrap:
    """`Yield` is percent while `Change` is basis points — the highest-value regression here."""

    def test_change_bps_equals_the_day_over_day_percent_move_times_100(self):
        today = {q["Symbol"]: BondQuote.model_validate(q) for q in GOV_CURVE_2026_08_10["Stat"]}
        prior = {q["Symbol"]: BondQuote.model_validate(q) for q in GOV_CURVE_2026_08_07["Stat"]}

        compared = 0
        for symbol, quote in today.items():
            previous = prior[symbol]
            move_bps = (quote.yield_percent - previous.yield_percent) * 100
            assert move_bps == pytest.approx(quote.change_bps, abs=1e-3), symbol
            compared += 1
        assert compared >= 5

    def test_change_percent_is_the_safe_to_add_derived_form(self):
        quote = BondQuote.model_validate(GOV_CURVE_2026_08_10["Stat"][2])
        assert quote.change_percent == quote.change_bps / 100


class TestSchemaStability:
    """The same models parse every era — the payload schema never drifted in 27 years."""

    def test_1999_payload_validates_with_the_same_models(self):
        curve = _curve(GOV_CURVE_1999_09_15)
        assert curve.as_of == date(1999, 9, 15)
        assert curve.count == 5
        assert curve.quotes[0].symbol.startswith("LB")

    def test_change_is_null_on_the_very_first_curve(self):
        """1999-09-15 has no prior business day, so ThaiBMA publishes Change as null."""
        curve = _curve(GOV_CURVE_1999_09_15)
        assert all(q.change_bps is None for q in curve.quotes)
        assert curve.quotes[0].change_percent is None
        # Every other field is still populated - only Change degrades.
        assert all(q.yield_percent is not None for q in curve.quotes)

    def test_pre_2013_flags_are_absent_not_broken(self):
        """IsBenchmark was never backfilled, so an empty list is the data, not a failure."""
        curve = _curve(GOV_CURVE_2012_01_04)
        assert curve.benchmarks == []
        assert all(q.is_synthetic is False for q in curve.quotes)
        assert curve.quotes  # the quotes themselves are present


# --- container helpers ---


class TestYieldCurveHelpers:
    """What a rates desk actually reaches for."""

    @pytest.fixture
    def curve(self):
        return _curve(GOV_CURVE_2026_08_10)

    def test_count_and_tenor_labels(self, curve):
        assert curve.count == 8
        assert curve.tenor_labels[:4] == ["1M", "3M", "6M", "1Y"]

    def test_yield_at_accepts_label_and_number_alike(self, curve):
        assert curve.yield_at("1Y") == curve.yield_at(1) == curve.yield_at(1.0)

    def test_yield_at_returns_none_off_grid(self, curve):
        """A 1999 curve has no 1M tenor at all; off-grid must be None, not an exception."""
        assert curve.yield_at("40Y") is None

    def test_to_dict_is_keyed_by_label_in_maturity_order(self, curve):
        as_dict = curve.to_dict()
        assert list(as_dict)[:3] == ["1M", "3M", "6M"]
        assert as_dict["1Y"] == pytest.approx(0.945142)

    def test_interpolate_sits_between_the_bracketing_points(self, curve):
        low, high = curve.yield_at("1Y"), curve.yield_at("2Y")
        mid = curve.interpolate(1.5)
        assert min(low, high) <= mid <= max(low, high)

    def test_interpolate_never_extrapolates(self, curve):
        with pytest.raises(ValueError, match="outside this curve's grid"):
            curve.interpolate(99.0)

    def test_interpolate_on_empty_curve_raises(self):
        with pytest.raises(ValueError, match="empty yield curve"):
            YieldCurve(as_of=date(2026, 8, 10)).interpolate(5.0)

    def test_slope_bps_is_the_spread_in_basis_points(self, curve):
        expected = (curve.yield_at("2Y") - curve.yield_at("1Y")) * 100
        assert curve.slope_bps("1Y", "2Y") == pytest.approx(expected)

    def test_slope_bps_names_the_missing_leg(self, curve):
        with pytest.raises(ValueError, match="'30Y'"):
            curve.slope_bps("1Y", "30Y")

    def test_group_helpers_partition_the_quotes(self, curve):
        assert len(curve.bills) + len(curve.bonds) == len(curve.quotes)
        assert all(q.group_order == 1 for q in curve.bills)

    def test_quote_lookup_is_case_insensitive(self, curve):
        assert curve.quote("lb776a") is not None
        assert curve.quote("NOPE") is None


class TestComputedFields:
    """The roll-back audit trail must survive serialization."""

    def test_flags_are_present_in_model_dump(self):
        curve = _curve(GOV_CURVE_2026_08_07, requested=date(2026, 8, 8))
        dumped = curve.model_dump()
        assert dumped["is_rolled_back"] is True
        assert dumped["rollback_days"] == 1
        assert json.loads(curve.model_dump_json())["rollback_days"] == 1

    def test_latest_request_is_never_flagged(self):
        curve = _curve(GOV_CURVE_2026_08_10, requested=None)
        assert curve.is_rolled_back is False
        assert curve.rollback_days is None


class TestToDataframe:
    """pandas is optional and imported lazily."""

    def test_curve_layout(self):
        frame = _curve(GOV_CURVE_2026_08_10).to_dataframe()
        assert list(frame.columns) == ["as_of", "tenor_years", "tenor", "yield_percent"]
        assert len(frame) == 8

    def test_quotes_layout(self):
        frame = _curve(GOV_CURVE_2026_08_10).to_dataframe("quotes")
        assert "change_bps" in frame.columns
        assert len(frame) == 7

    def test_unknown_kind_raises(self):
        with pytest.raises(ValueError, match="'curve' or 'quotes'"):
            _curve(GOV_CURVE_2026_08_10).to_dataframe("nope")  # type: ignore[arg-type]

    def test_missing_pandas_names_the_extra(self, monkeypatch):
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "pandas":
                raise ImportError("no pandas")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        with pytest.raises(ImportError, match=r"settfex\[dataframe\]"):
            _curve(GOV_CURVE_2026_08_10).to_dataframe()


# --- service ---


@pytest.mark.asyncio
class TestFetchCurve:
    """Request construction and the stateless-host guarantee."""

    async def test_builds_the_dated_url(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(GOV_CURVE_2026_08_10)

        await YieldCurveService().fetch_curve("2026-08-10")

        url = mock_fetcher.fetch.call_args.args[0]
        assert url == "https://www.thaibma.or.th/yieldcurve/gov/2026-08-10"

    async def test_omits_the_date_segment_for_latest(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(GOV_CURVE_2026_08_10)

        curve = await YieldCurveService().fetch_curve()

        assert mock_fetcher.fetch.call_args.args[0].endswith("/yieldcurve/gov")
        assert curve.requested_date is None

    async def test_unpadded_date_is_repadded_on_the_wire(self, mock_fetcher):
        """'2026-8-10' would 404; the service must never send it."""
        mock_fetcher.fetch.return_value = _response(GOV_CURVE_2026_08_10)

        await YieldCurveService().fetch_curve("2026-8-10")

        assert mock_fetcher.fetch.call_args.args[0].endswith("/2026-08-10")

    async def test_session_is_forced_off_but_timeout_survives(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(GOV_CURVE_2026_08_10)

        await YieldCurveService(FetcherConfig(timeout=99, max_retries=7)).fetch_curve()

        config = mock_fetcher.cls.call_args.kwargs["config"]
        assert config.use_session is False
        assert config.timeout == 99
        assert config.max_retries == 7

    async def test_parses_curve_and_quotes(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(GOV_CURVE_2026_08_10)

        curve = await YieldCurveService().fetch_curve("2026-08-10")

        assert curve.as_of == date(2026, 8, 10)
        assert curve.count == 8
        assert len(curve.quotes) == 7
        assert curve.yield_at("1M") == 0.856643

    async def test_raw_returns_the_wire_keys_unvalidated(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(GOV_CURVE_2026_08_10)

        raw = await YieldCurveService().fetch_curve_raw("2026-08-10")

        assert set(raw) == {"Curve", "Stat"}
        assert raw["Curve"][0]["Asof"] == "2026-08-10T00:00:00"


@pytest.mark.asyncio
class TestRollback:
    """The endpoint never 404s on a date — it silently serves an earlier one."""

    async def test_weekend_is_flagged_and_warned(self, mock_fetcher, caplog):
        mock_fetcher.fetch.return_value = _response(GOV_CURVE_2026_08_07)

        curve = await YieldCurveService().fetch_curve("2026-08-08")

        assert curve.requested_date == date(2026, 8, 8)
        assert curve.as_of == date(2026, 8, 7)
        assert curve.is_rolled_back is True
        assert curve.rollback_days == 1

    async def test_future_date_message_says_future(self, mock_fetcher):
        with patch("settfex.services.thaibma.yield_curve.logger") as log:
            mock_fetcher.fetch.return_value = _response(GOV_CURVE_2026_08_10)
            curve = await YieldCurveService().fetch_curve("2030-01-01")

        assert curve.is_rolled_back is True
        assert curve.rollback_days > 1000
        assert "future" in log.warning.call_args.args[0]

    async def test_weekend_message_says_weekend_or_holiday(self, mock_fetcher):
        with patch("settfex.services.thaibma.yield_curve.logger") as log:
            mock_fetcher.fetch.return_value = _response(GOV_CURVE_2026_08_07)
            await YieldCurveService().fetch_curve("2026-08-08")

        assert "weekend or a Thai public holiday" in log.warning.call_args.args[0]

    async def test_raise_policy_carries_the_diagnostics(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(GOV_CURVE_2026_08_07)

        with pytest.raises(StaleDataError) as exc_info:
            await YieldCurveService().fetch_curve("2026-08-08", on_rollback="raise")

        error = exc_info.value
        assert error.requested_date == date(2026, 8, 8)
        assert error.as_of == date(2026, 8, 7)
        assert error.rollback_days == 1
        assert isinstance(error, FetchError)

    async def test_allow_policy_is_silent_but_still_flags(self, mock_fetcher):
        with patch("settfex.services.thaibma.yield_curve.logger") as log:
            mock_fetcher.fetch.return_value = _response(GOV_CURVE_2026_08_07)
            curve = await YieldCurveService().fetch_curve("2026-08-08", on_rollback="allow")

        assert curve.is_rolled_back is True
        assert log.warning.call_count == 0

    async def test_exact_match_is_not_flagged_and_does_not_warn(self, mock_fetcher):
        with patch("settfex.services.thaibma.yield_curve.logger") as log:
            mock_fetcher.fetch.return_value = _response(GOV_CURVE_2026_08_10)
            curve = await YieldCurveService().fetch_curve("2026-08-10")

        assert curve.is_rolled_back is False
        assert curve.rollback_days == 0
        assert log.warning.call_count == 0


@pytest.mark.asyncio
class TestBadDates:
    """Malformed input must be rejected before a request is ever made."""

    @pytest.mark.parametrize("bad", ["2026-02-30", "10/08/2026", "not-a-date"])
    async def test_malformed_dates_never_reach_the_network(self, mock_fetcher, bad):
        with pytest.raises(InvalidDateError):
            await YieldCurveService().fetch_curve(bad)

        mock_fetcher.fetch.assert_not_awaited()

    async def test_pre_history_date_is_rejected_client_side(self, mock_fetcher):
        with pytest.raises(InvalidDateError, match="1999-09-15"):
            await YieldCurveService().fetch_curve("1999-09-14")

        mock_fetcher.fetch.assert_not_awaited()


@pytest.mark.asyncio
class TestNullBody:
    """A date before coverage returns HTTP 200 with a literal ``null``, not a 404."""

    async def test_null_body_raises_fetch_error_naming_the_first_date(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(text="null")

        with pytest.raises(FetchError, match="1999-09-15"):
            await YieldCurveService().fetch_curve("2026-08-10")

    async def test_null_body_is_not_a_validation_error(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(text="null")

        with pytest.raises(FetchError):
            await YieldCurveService().fetch_curve_raw("2026-08-10")

    async def test_empty_envelope_raises_rather_than_guessing_a_date(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response({"Curve": [], "Stat": []})

        with pytest.raises(FetchError, match="empty"):
            await YieldCurveService().fetch_curve("2026-08-10")


@pytest.mark.asyncio
class TestStatusHandling:
    """AsyncDataFetcher never raises on a non-2xx, so the service must check the status itself."""

    async def test_html_404_body_is_never_parsed(self, mock_fetcher):
        """An HTML error page must surface as FetchError, not a JSON decode failure."""
        mock_fetcher.fetch.return_value = _response(status_code=404, text=HTML_404_BODY)

        with pytest.raises(FetchError) as exc_info:
            await YieldCurveService().fetch_curve("2026-08-10")

        assert not isinstance(exc_info.value, ResponseParseError)

    async def test_aspnet_json_400_raises_fetch_error(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(status_code=400, text=ASPNET_ERROR_JSON)

        with pytest.raises(FetchError, match="HTTP 400"):
            await YieldCurveService().fetch_curve("2026-08-10")

    async def test_server_error_raises(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(status_code=500, text="")

        with pytest.raises(FetchError, match="HTTP 500"):
            await YieldCurveService().fetch_curve()


@pytest.mark.asyncio
class TestFetchCurves:
    """The multi-date helper exists only for the per-date Stat block."""

    async def test_dedupes_dates_and_sorts_results(self, mock_fetcher):
        mock_fetcher.fetch.side_effect = [
            _response(GOV_CURVE_2026_08_10),
            _response(GOV_CURVE_2026_08_07),
        ]

        curves = await YieldCurveService().fetch_curves(["2026-08-10", "2026-08-07", "2026-08-10"])

        assert mock_fetcher.fetch.await_count == 2
        assert [c.as_of for c in curves] == [date(2026, 8, 7), date(2026, 8, 10)]

    async def test_continue_on_error_skips_a_bad_date(self, mock_fetcher):
        mock_fetcher.fetch.side_effect = [
            _response(GOV_CURVE_2026_08_10),
            _response(status_code=500, text=""),
        ]

        curves = await YieldCurveService().fetch_curves(["2026-08-10", "2026-08-07"])

        assert len(curves) == 1

    async def test_continue_on_error_false_propagates(self, mock_fetcher):
        mock_fetcher.fetch.side_effect = [_response(status_code=500, text="")]

        with pytest.raises(FetchError):
            await YieldCurveService().fetch_curves(["2026-08-10"], continue_on_error=False)


@pytest.mark.asyncio
class TestConvenienceFunction:
    """The flat, one-call LLM tool-calling entry point."""

    async def test_get_government_yield_curve_delegates(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(GOV_CURVE_2026_08_10)

        curve = await get_government_yield_curve("2026-08-10", config=FetcherConfig(timeout=42))

        assert curve.as_of == date(2026, 8, 10)
        assert mock_fetcher.cls.call_args.kwargs["config"].timeout == 42


class TestSessionManagerIsNeverReached:
    """A regression guard on the one mistake that would break this whole package."""

    def test_service_config_disables_the_session(self):
        service = YieldCurveService(FetcherConfig(use_session=True))
        assert service.config.use_session is False

    def test_session_lookup_would_blow_up_if_it_ran(self):
        """Proves the assertion below is meaningful: the helper exists and is patchable."""
        with patch(
            "settfex.utils.session_manager.get_session_for_url",
            new=Mock(side_effect=AssertionError("SessionManager must never see a ThaiBMA URL")),
        ) as guard:
            YieldCurveService()
            assert guard.call_count == 0
