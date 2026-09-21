"""Tests for the ThaiBMA availability service — what yield-curve history actually exists."""

import json
from datetime import date
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from settfex.exceptions import FetchError
from settfex.services.thaibma.availability import (
    YieldCurveAvailability,
    YieldCurveAvailabilityService,
    get_yield_curve_availability,
)
from settfex.utils.data_fetcher import FetcherConfig, FetchResponse
from settfex.utils.parsing import ResponseParseError
from tests.services.thaibma.fixtures import AVAIL, AVAILYEAR


def _response(payload: Any = None, *, status_code: int = 200, text: str | None = None):
    """Build a FetchResponse whose body is ``payload`` as JSON (or the literal ``text``)."""
    body = text if text is not None else json.dumps(payload)
    return FetchResponse(
        status_code=status_code,
        content=body.encode("utf-8"),
        text=body,
        headers={},
        url="https://www.thaibma.or.th/yieldcurve/avail",
        elapsed=0.1,
    )


def _router(*, window: Any = None, years: Any = None, window_status: int = 200):
    """A fetch side-effect dispatching between /avail and /availyear."""

    async def route(url: str, headers=None, **kwargs):
        if "availyear" in url:
            return _response(AVAILYEAR if years is None else years)
        if window_status != 200:
            return _response(status_code=window_status, text="")
        return _response(AVAIL if window is None else window)

    return route


@pytest.fixture
def mock_fetcher():
    """Patch AsyncDataFetcher inside the availability module."""
    with patch("settfex.services.thaibma.availability.AsyncDataFetcher") as mock:
        instance = AsyncMock()
        mock.return_value.__aenter__.return_value = instance
        mock.return_value.__aexit__.return_value = None
        instance.cls = mock
        yield instance


# --- model ---


class TestAvailabilityModel:
    """Window arithmetic used to clamp history requests."""

    @pytest.fixture
    def availability(self):
        return YieldCurveAvailability(
            first_date=date(1999, 9, 15), last_date=date(2026, 8, 10), years=list(AVAILYEAR)
        )

    def test_span_days(self, availability):
        assert availability.span_days == (date(2026, 8, 10) - date(1999, 9, 15)).days

    @pytest.mark.parametrize(
        "day,expected",
        [
            ("1999-09-15", True),
            ("1999-09-14", False),
            ("2026-08-10", True),
            ("2026-08-11", False),
        ],
    )
    def test_covers_is_inclusive_at_both_ends(self, availability, day, expected):
        assert availability.covers(day) is expected

    def test_covers_a_weekend_inside_the_window(self, availability):
        """The window is about coverage, not about a curve existing that exact day."""
        assert availability.covers("2026-08-08") is True

    def test_clamp_narrows_to_the_window(self, availability):
        start, end = availability.clamp(date(1990, 1, 1), date(2099, 1, 1))
        assert (start, end) == (date(1999, 9, 15), date(2026, 8, 10))

    def test_clamp_leaves_an_inner_span_alone(self, availability):
        span = (date(2020, 1, 1), date(2021, 1, 1))
        assert availability.clamp(*span) == span


# --- service ---


@pytest.mark.asyncio
class TestFetchAvailability:
    """Two tiny requests, issued concurrently."""

    async def test_parses_window_and_years(self, mock_fetcher):
        mock_fetcher.fetch.side_effect = _router()

        availability = await YieldCurveAvailabilityService().fetch_availability()

        assert availability.first_date == date(1999, 9, 15)
        assert availability.last_date == date(2026, 8, 10)
        assert availability.years[0] == 1999
        assert len(availability.years) == 28

    async def test_hits_both_endpoints(self, mock_fetcher):
        mock_fetcher.fetch.side_effect = _router()

        await YieldCurveAvailabilityService().fetch_availability()

        urls = [call.args[0] for call in mock_fetcher.fetch.call_args_list]
        assert any(url.endswith("/yieldcurve/avail") for url in urls)
        assert any(url.endswith("/yieldcurve/availyear") for url in urls)

    async def test_include_years_false_issues_one_request(self, mock_fetcher):
        mock_fetcher.fetch.side_effect = _router()

        availability = await YieldCurveAvailabilityService().fetch_availability(include_years=False)

        assert mock_fetcher.fetch.await_count == 1
        assert availability.years == []

    async def test_session_is_forced_off_but_timeout_survives(self, mock_fetcher):
        mock_fetcher.fetch.side_effect = _router()

        await YieldCurveAvailabilityService(FetcherConfig(timeout=55)).fetch_availability()

        config = mock_fetcher.cls.call_args.kwargs["config"]
        assert config.use_session is False
        assert config.timeout == 55

    @pytest.mark.parametrize("bad", [["2026-08-10T00:00:00"], [], ["a", "b", "c"], {"a": 1}])
    async def test_window_must_be_exactly_two_dates(self, mock_fetcher, bad):
        """Never index blindly into a differently-shaped body."""
        mock_fetcher.fetch.side_effect = _router(window=bad)

        with pytest.raises(ResponseParseError, match="2-element"):
            await YieldCurveAvailabilityService().fetch_availability()

    async def test_bad_status_raises(self, mock_fetcher):
        mock_fetcher.fetch.side_effect = _router(window_status=500)

        with pytest.raises(FetchError, match="HTTP 500"):
            await YieldCurveAvailabilityService().fetch_availability()

    async def test_years_are_sorted_and_junk_is_skipped(self, mock_fetcher):
        mock_fetcher.fetch.side_effect = _router(years=[2001, "2000", None, True, 1999])

        availability = await YieldCurveAvailabilityService().fetch_availability()

        assert availability.years == [1999, 2000, 2001]

    async def test_non_list_years_degrade_to_empty(self, mock_fetcher):
        mock_fetcher.fetch.side_effect = _router(years={"unexpected": True})

        availability = await YieldCurveAvailabilityService().fetch_availability()

        assert availability.years == []

    async def test_raw_returns_both_payloads(self, mock_fetcher):
        mock_fetcher.fetch.side_effect = _router()

        raw = await YieldCurveAvailabilityService().fetch_availability_raw()

        assert raw["avail"] == AVAIL
        assert raw["availyear"] == AVAILYEAR


@pytest.mark.asyncio
class TestConvenienceFunction:
    """The flat, one-call LLM tool-calling entry point."""

    async def test_delegates_and_passes_config(self, mock_fetcher):
        mock_fetcher.fetch.side_effect = _router()

        availability = await get_yield_curve_availability(config=FetcherConfig(timeout=33))

        assert availability.first_date == date(1999, 9, 15)
        assert mock_fetcher.cls.call_args.kwargs["config"].timeout == 33


class TestTheTwoHalvesFailTogether:
    """F5 — one logical answer, so a partial is never returned; both causes always survive.

    ``/avail`` gives the window and ``/availyear`` gives the years, and an availability with only
    one of them is not a usable answer: the history service clamps a requested span against
    ``years`` and reports the gap. So unlike the SEC listing legs, there is deliberately **no**
    severity ladder here and no ``missing_half`` field — the halves fail as a unit.

    What 0.24.0 changed is narrower: the bare ``gather`` raised the first cause and **discarded the
    other**, so with both endpoints down a caller saw one failure and could spend a while fixing
    one endpoint while the other was equally broken. The second cause now rides along as a PEP 678
    note — no new type, no changed signature, and ``except FetchError`` still catches it.
    """

    @staticmethod
    def _boom(*, window: BaseException | None, years: BaseException | None):
        async def route(url: str, headers=None, **kwargs):
            failure = years if "availyear" in url else window
            if failure is not None:
                raise failure
            return _response(AVAILYEAR if "availyear" in url else AVAIL)

        return route

    @pytest.mark.asyncio
    async def test_one_half_failing_fails_the_whole_answer(self) -> None:
        """No partial availability: a window with no years would clamp nothing, silently."""
        with patch("settfex.services.thaibma.availability.AsyncDataFetcher") as mock:
            instance = AsyncMock()
            instance.fetch = AsyncMock(
                side_effect=self._boom(window=None, years=FetchError("years endpoint down"))
            )
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=None)
            mock.return_value = instance
            with pytest.raises(FetchError, match="years endpoint down"):
                await YieldCurveAvailabilityService().fetch_availability()

    @pytest.mark.asyncio
    async def test_both_failing_carries_the_second_cause_as_a_note(self) -> None:
        """Re-raising one exception must not silently drop the other."""
        with patch("settfex.services.thaibma.availability.AsyncDataFetcher") as mock:
            instance = AsyncMock()
            instance.fetch = AsyncMock(
                side_effect=self._boom(
                    window=FetchError("window endpoint down"),
                    years=FetchError("years endpoint down"),
                )
            )
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=None)
            mock.return_value = instance
            with pytest.raises(FetchError) as excinfo:
                await YieldCurveAvailabilityService().fetch_availability()

        assert "window endpoint down" in str(excinfo.value), "the first half is the raised cause"
        notes = getattr(excinfo.value, "__notes__", [])
        assert len(notes) == 1, "one note for the OTHER half, never for the raised one"
        assert "years endpoint down" in notes[0]
        assert "availyear" in notes[0], "the note must name which endpoint, not just the error"

    @pytest.mark.asyncio
    async def test_it_is_still_catchable_as_fetch_error(self) -> None:
        """Deliberately not an ExceptionGroup: `except FetchError` does not catch one."""
        with patch("settfex.services.thaibma.availability.AsyncDataFetcher") as mock:
            instance = AsyncMock()
            instance.fetch = AsyncMock(
                side_effect=self._boom(window=FetchError("a"), years=ResponseParseError("b"))
            )
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=None)
            mock.return_value = instance
            with pytest.raises(FetchError) as excinfo:
                await YieldCurveAvailabilityService().fetch_availability()
        assert not isinstance(excinfo.value, BaseExceptionGroup)

    @pytest.mark.asyncio
    async def test_nothing_fires_when_both_halves_answer(self) -> None:
        """The discipline every signal in this release is held to."""
        with patch("settfex.services.thaibma.availability.AsyncDataFetcher") as mock:
            instance = AsyncMock()
            instance.fetch = AsyncMock(side_effect=self._boom(window=None, years=None))
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=None)
            mock.return_value = instance
            availability = await YieldCurveAvailabilityService().fetch_availability()
        assert availability.years and availability.first_date
