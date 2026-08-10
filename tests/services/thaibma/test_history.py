"""Tests for the ThaiBMA bulk-year yield history service.

The sharp edges pinned here are the per-year dynamic columns, the absent-versus-null distinction,
the silent empty-list response for an unserved year, and the fact that one request covers a year.
"""

import json
from datetime import date
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from settfex.exceptions import FetchError
from settfex.services.thaibma.history import (
    HistoryKind,
    HistoryRow,
    YieldCurveHistory,
    YieldCurveHistoryService,
    build_column_union,
    get_bond_yield_history,
    get_yield_curve_history,
)
from settfex.utils.data_fetcher import FetcherConfig, FetchResponse
from settfex.utils.parsing import ResponseParseError
from tests.services.thaibma.fixtures import (
    AVAIL,
    AVAILYEAR,
    GETBYYEAR_2026,
    INTPTTM_1999,
    INTPTTM_2005,
    INTPTTM_2026,
)


def _response(payload: Any = None, *, status_code: int = 200, text: str | None = None):
    """Build a FetchResponse whose body is ``payload`` as JSON (or the literal ``text``)."""
    body = text if text is not None else json.dumps(payload)
    return FetchResponse(
        status_code=status_code,
        content=body.encode("utf-8"),
        text=body,
        headers={},
        url="https://www.thaibma.or.th/yieldcurve/getintpttm",
        elapsed=0.1,
    )


def _router(by_year: dict[int, Any], *, avail: bool = True):
    """A fetch side-effect dispatching on the ?year= query and the availability endpoints."""

    async def route(url: str, headers=None, **kwargs):
        if "availyear" in url:
            return _response(AVAILYEAR if avail else [])
        if url.endswith("/avail"):
            return _response(AVAIL)
        year = int(url.rsplit("year=", 1)[1])
        payload = by_year.get(year, [])
        if isinstance(payload, FetchResponse):
            return payload
        return _response(payload)

    return route


@pytest.fixture
def mock_fetcher():
    """Patch AsyncDataFetcher inside the history module; yield its async instance."""
    with patch("settfex.services.thaibma.history.AsyncDataFetcher") as mock:
        instance = AsyncMock()
        mock.return_value.__aenter__.return_value = instance
        mock.return_value.__aexit__.return_value = None
        instance.cls = mock
        # The history service constructs the availability service, which patches separately.
        with patch("settfex.services.thaibma.availability.AsyncDataFetcher") as avail_mock:
            avail_mock.return_value.__aenter__.return_value = instance
            avail_mock.return_value.__aexit__.return_value = None
            yield instance


# --- models ---


class TestHistoryRow:
    """One business day of a wide matrix with dynamic columns."""

    def test_splits_asof_from_the_dynamic_columns(self):
        row = HistoryRow.model_validate(INTPTTM_2026[0])
        assert row.as_of == date(2026, 1, 5)
        assert "asof" not in row.values
        assert row.get("1M") == pytest.approx(1.08869)

    def test_lowercase_asof_alias(self):
        """The history payload uses lowercase 'asof', unlike the point-in-time 'Asof'."""
        row = HistoryRow.model_validate({"asof": "2026-08-10T00:00:00", "10Y": 2.06})
        assert row.as_of == date(2026, 8, 10)

    def test_null_is_preserved_not_coerced_or_dropped(self):
        row = HistoryRow.model_validate({"asof": "2026-08-10T00:00:00", "51Y": None})
        assert row.get("51Y") is None
        assert row.has("51Y") is True

    def test_has_distinguishes_absent_from_null(self):
        """The distinction a wide DataFrame flattens away."""
        row = HistoryRow.model_validate({"asof": "2026-08-10T00:00:00", "51Y": None})
        assert row.has("51Y") is True and row.get("51Y") is None
        assert row.has("1M") is False and row.get("1M") is None

    def test_accepts_an_already_shaped_dict(self):
        row = HistoryRow.model_validate({"as_of": date(2026, 8, 10), "values": {"10Y": 2.0}})
        assert row.get("10Y") == 2.0


class TestDynamicColumns:
    """Column sets differ by era — fixed Pydantic fields would be impossible."""

    def test_1999_has_no_subyear_tenors(self):
        rows = [HistoryRow.model_validate(r) for r in INTPTTM_1999]
        columns = build_column_union(rows, HistoryKind.TENOR)
        assert "1M" not in columns
        assert columns[0] == "1Y"
        assert len(columns) == 14

    def test_2026_carries_subyear_tenors(self):
        rows = [HistoryRow.model_validate(r) for r in INTPTTM_2026]
        columns = build_column_union(rows, HistoryKind.TENOR)
        assert columns[:3] == ["1M", "3M", "6M"]

    def test_tenor_union_is_maturity_ordered_not_lexicographic(self):
        rows = [HistoryRow.model_validate(r) for r in INTPTTM_1999 + INTPTTM_2026]
        columns = build_column_union(rows, HistoryKind.TENOR)
        assert columns[:4] == ["1M", "3M", "6M", "1Y"]
        assert columns.index("2Y") < columns.index("10Y")

    def test_bond_union_keeps_first_seen_order(self):
        rows = [HistoryRow.model_validate(r) for r in GETBYYEAR_2026]
        columns = build_column_union(rows, HistoryKind.BOND)
        assert columns[0] == "T-BILL1M"
        assert columns == list(dict.fromkeys(columns))


class TestYearDrift:
    """Merging eras must line rows up without inventing data."""

    @pytest.fixture
    def merged(self):
        rows = sorted(
            (HistoryRow.model_validate(r) for r in INTPTTM_1999 + INTPTTM_2005 + INTPTTM_2026),
            key=lambda r: r.as_of,
        )
        return YieldCurveHistory(
            kind=HistoryKind.TENOR, rows=rows, columns=build_column_union(rows, HistoryKind.TENOR)
        )

    def test_columns_by_year_exposes_the_drift(self, merged):
        """Each year reports its own column set, so a drift is inspectable rather than hidden.

        (The fixtures are column-trimmed for readability, so this asserts that the sets *differ*
        and how, not their live sizes - 14 in 1999 rising to 54 in 2026.)
        """
        by_year = merged.columns_by_year()

        assert len(by_year[1999]) == 14
        assert by_year[1999] != by_year[2026]
        assert "1M" in by_year[2026] and "1M" not in by_year[1999]
        # Every year's columns are drawn from the union, in the union's canonical order.
        for columns in by_year.values():
            assert set(columns) <= set(merged.columns)
            assert columns == [name for name in merged.columns if name in set(columns)]

    def test_a_1999_row_lacks_columns_a_2026_row_has(self, merged):
        row_1999 = next(r for r in merged.rows if r.as_of.year == 1999)
        row_2026 = next(r for r in merged.rows if r.as_of.year == 2026)
        assert row_1999.has("1M") is False
        assert row_2026.has("1M") is True

    def test_coverage_counts_non_null_observations(self, merged):
        coverage = merged.coverage()
        assert set(coverage) == set(merged.columns)
        assert coverage["1Y"] == sum(1 for r in merged.rows if r.get("1Y") is not None)


class TestContainerHelpers:
    """Slicing, series extraction and the deliberate absence of roll-back."""

    @pytest.fixture
    def history(self):
        rows = sorted((HistoryRow.model_validate(r) for r in INTPTTM_2026), key=lambda r: r.as_of)
        return YieldCurveHistory(
            kind=HistoryKind.TENOR,
            rows=rows,
            columns=build_column_union(rows, HistoryKind.TENOR),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 8, 10),
        )

    def test_count_dates_and_latest(self, history):
        assert history.count == len(history.rows)
        assert history.dates == sorted(history.dates)
        assert history.latest is history.rows[-1]

    def test_latest_of_empty_history_is_none(self):
        assert YieldCurveHistory(kind=HistoryKind.TENOR).latest is None

    def test_series_dropna_toggles_null_days(self, history):
        with_nulls = history.series("1M", dropna=False)
        assert len(with_nulls) == history.count
        assert all(value is not None for _, value in history.series("1M"))

    def test_row_for_never_rolls_back(self, history):
        """Unlike the endpoint, the container is honest about which days exist."""
        assert history.row_for(history.dates[0]) is not None
        assert history.row_for("2026-08-09") is None  # a Sunday

    def test_slice_recomputes_columns_and_bounds(self, history):
        narrowed = history.slice(history.dates[-1], history.dates[-1])
        assert narrowed.count == 1
        assert narrowed.start_date == history.dates[-1]
        assert set(narrowed.columns) <= set(history.columns)

    def test_to_long_skips_nulls(self, history):
        triples = history.to_long()
        assert all(value is not None for _, _, value in triples)


class TestToDataframe:
    """pandas is optional and imported lazily."""

    @pytest.fixture
    def history(self):
        rows = sorted(
            (HistoryRow.model_validate(r) for r in INTPTTM_1999 + INTPTTM_2026),
            key=lambda r: r.as_of,
        )
        return YieldCurveHistory(
            kind=HistoryKind.TENOR, rows=rows, columns=build_column_union(rows, HistoryKind.TENOR)
        )

    def test_wide_is_rectangular_across_eras(self, history):
        frame = history.to_dataframe()
        assert frame.shape == (history.count, len(history.columns))
        assert frame.index.name == "as_of"

    def test_wide_fills_absent_columns_with_nan(self, history):
        frame = history.to_dataframe()
        row_1999 = frame.loc[[d for d in history.dates if d.year == 1999][0]]
        assert row_1999["1M"] != row_1999["1M"]  # NaN

    def test_long_layout(self, history):
        frame = history.to_dataframe(layout="long")
        assert list(frame.columns) == ["as_of", "column", "value"]
        assert len(frame) == len(history.to_long())

    def test_unknown_layout_raises(self, history):
        with pytest.raises(ValueError, match="'wide' or 'long'"):
            history.to_dataframe(layout="tall")

    def test_missing_pandas_names_the_extra(self, history, monkeypatch):
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "pandas":
                raise ImportError("no pandas")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        with pytest.raises(ImportError, match=r"settfex\[dataframe\]"):
            history.to_dataframe()


# --- service ---


@pytest.mark.asyncio
class TestFetchYear:
    """A single year, one request."""

    async def test_builds_the_tenor_url(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(INTPTTM_2026)

        await YieldCurveHistoryService().fetch_year(2026)

        url = mock_fetcher.fetch.call_args.args[0]
        assert url == "https://www.thaibma.or.th/yieldcurve/getintpttm?year=2026"

    async def test_builds_the_bond_url(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(GETBYYEAR_2026)

        history = await YieldCurveHistoryService().fetch_year(2026, kind="bond")

        assert mock_fetcher.fetch.call_args.args[0].endswith("/getbyyear?year=2026")
        assert history.kind is HistoryKind.BOND

    async def test_session_is_forced_off_but_timeout_survives(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(INTPTTM_2026)

        await YieldCurveHistoryService(FetcherConfig(timeout=77)).fetch_year(2026)

        config = mock_fetcher.cls.call_args.kwargs["config"]
        assert config.use_session is False
        assert config.timeout == 77

    async def test_empty_year_is_not_an_error(self, mock_fetcher):
        """An unserved year returns HTTP 200 with []."""
        mock_fetcher.fetch.return_value = _response([])

        history = await YieldCurveHistoryService().fetch_year(2026)

        assert history.count == 0
        assert history.columns == []

    async def test_non_array_payload_raises(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response({"unexpected": True})

        with pytest.raises(ResponseParseError, match="Expected a JSON array"):
            await YieldCurveHistoryService().fetch_year(2026)

    async def test_bad_status_raises(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(status_code=400, text="")

        with pytest.raises(FetchError, match="HTTP 400"):
            await YieldCurveHistoryService().fetch_year(2026)

    async def test_unknown_kind_never_reaches_the_network(self, mock_fetcher):
        with pytest.raises(ValueError, match="Unknown history kind"):
            await YieldCurveHistoryService().fetch_year(2026, kind="zero")

        mock_fetcher.fetch.assert_not_awaited()

    async def test_raw_keeps_the_wire_keys(self, mock_fetcher):
        mock_fetcher.fetch.return_value = _response(INTPTTM_2026)

        raw = await YieldCurveHistoryService().fetch_year_raw(2026)

        assert "asof" in raw[0]


@pytest.mark.asyncio
class TestYearFanout:
    """A span maps onto whole-year requests, not per-day ones."""

    async def test_only_the_needed_years_are_requested(self, mock_fetcher):
        mock_fetcher.fetch.side_effect = _router({2005: INTPTTM_2005, 2026: INTPTTM_2026})

        await YieldCurveHistoryService().fetch_history("2005-06-01", "2026-08-10")

        years = sorted(
            int(call.args[0].rsplit("year=", 1)[1])
            for call in mock_fetcher.fetch.call_args_list
            if "year=" in call.args[0]
        )
        assert years == list(range(2005, 2027))

    async def test_rows_are_sliced_to_the_requested_span(self, mock_fetcher):
        mock_fetcher.fetch.side_effect = _router({2026: INTPTTM_2026})

        history = await YieldCurveHistoryService().fetch_history("2026-08-01", "2026-08-31")

        assert history.count >= 1
        assert all(date(2026, 8, 1) <= d <= date(2026, 8, 31) for d in history.dates)

    async def test_default_span_is_year_to_date_not_the_whole_record(self, mock_fetcher):
        """A bare call must not silently trigger a 28-request full-history pull."""
        mock_fetcher.fetch.side_effect = _router({2026: INTPTTM_2026})

        history = await YieldCurveHistoryService().fetch_history(end_date="2026-08-10")

        assert history.start_date == date(2026, 1, 1)
        year_calls = [c for c in mock_fetcher.fetch.call_args_list if "year=" in c.args[0]]
        assert len(year_calls) == 1

    async def test_inverted_span_raises_before_fetching(self, mock_fetcher):
        with pytest.raises(ValueError, match="is after end_date"):
            await YieldCurveHistoryService().fetch_history("2026-08-10", "2026-01-01")

        mock_fetcher.fetch.assert_not_awaited()


@pytest.mark.asyncio
class TestAvailabilityClamping:
    """An unserved year returns [] silently, so the span is clamped and the gap reported."""

    async def test_out_of_range_years_are_dropped_and_recorded(self, mock_fetcher):
        mock_fetcher.fetch.side_effect = _router({1999: INTPTTM_1999})

        history = await YieldCurveHistoryService().fetch_history("1995-01-01", "1999-12-31")

        assert history.unavailable_years == [1995, 1996, 1997, 1998]
        year_calls = [c for c in mock_fetcher.fetch.call_args_list if "year=" in c.args[0]]
        assert len(year_calls) == 1

    async def test_opting_out_requests_every_year(self, mock_fetcher):
        mock_fetcher.fetch.side_effect = _router({1999: INTPTTM_1999})

        history = await YieldCurveHistoryService().fetch_history(
            "1995-01-01", "1999-12-31", check_availability=False
        )

        year_calls = [c for c in mock_fetcher.fetch.call_args_list if "year=" in c.args[0]]
        assert len(year_calls) == 5
        assert history.unavailable_years == []

    async def test_empty_availability_falls_back_to_requesting_everything(self, mock_fetcher):
        mock_fetcher.fetch.side_effect = _router({2026: INTPTTM_2026}, avail=False)

        history = await YieldCurveHistoryService().fetch_history("2026-01-01", "2026-08-10")

        assert history.unavailable_years == []
        assert history.count >= 1


@pytest.mark.asyncio
class TestContinueOnError:
    """Any hole in the result must be attributable, never silent."""

    async def test_failed_year_is_recorded_in_missing_years(self, mock_fetcher):
        mock_fetcher.fetch.side_effect = _router(
            {2025: _response(status_code=500, text=""), 2026: INTPTTM_2026}
        )

        history = await YieldCurveHistoryService().fetch_history("2025-01-01", "2026-08-10")

        assert history.missing_years == [2025]
        assert history.count >= 1

    async def test_continue_on_error_false_propagates(self, mock_fetcher):
        mock_fetcher.fetch.side_effect = _router({2026: _response(status_code=500, text="")})

        with pytest.raises(FetchError):
            await YieldCurveHistoryService().fetch_history(
                "2026-01-01", "2026-08-10", continue_on_error=False
            )


@pytest.mark.asyncio
class TestConvenienceFunctions:
    """The flat, one-call LLM tool-calling entry points."""

    async def test_tenor_history_uses_getintpttm(self, mock_fetcher):
        mock_fetcher.fetch.side_effect = _router({2026: INTPTTM_2026})

        history = await get_yield_curve_history("2026-01-01", "2026-08-10")

        assert history.kind is HistoryKind.TENOR
        assert any("getintpttm" in c.args[0] for c in mock_fetcher.fetch.call_args_list)

    async def test_bond_history_uses_getbyyear(self, mock_fetcher):
        mock_fetcher.fetch.side_effect = _router({2026: GETBYYEAR_2026})

        history = await get_bond_yield_history("2026-01-01", "2026-08-10")

        assert history.kind is HistoryKind.BOND
        assert any("getbyyear" in c.args[0] for c in mock_fetcher.fetch.call_args_list)
        assert "T-BILL1M" in history.columns
