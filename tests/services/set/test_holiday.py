"""Tests for the SET market holiday calendar service.

All HTTP is mocked (the suite runs offline). Fixtures are the real payloads captured live from
``/api/cms/v1/holidays/year/2026`` on 2026-07-27, including the trailing ``" *"`` footnote marker
that must survive parsing verbatim.
"""

import json
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from settfex.exceptions import FetchError, InvalidLanguageError
from settfex.services.set.holiday import (
    BANGKOK_TZ,
    MAX_YEAR,
    MIN_YEAR,
    Holiday,
    HolidayCalendar,
    HolidayService,
    get_holidays,
)
from settfex.utils.data_fetcher import FetcherConfig, FetchResponse
from settfex.utils.parsing import ResponseParseError

# Thailand has no DST, so a fixed +07:00 offset is equivalent to Asia/Bangkok.
BKK = timezone(timedelta(hours=7))

# --- real payloads, captured live 2026-07-27 -------------------------------------------------

# Full English payload for 2026 (20 entries, ascending, no duplicates).
SAMPLE_EN: list[dict[str, Any]] = [
    {"date": "2026-01-01T00:00:00+07:00", "description": "New Year's Day"},
    {"date": "2026-01-02T00:00:00+07:00", "description": "Additional special holiday"},
    {"date": "2026-03-03T00:00:00+07:00", "description": "Makha Bucha Day"},
    {"date": "2026-04-06T00:00:00+07:00", "description": "Chakri Memorial Day"},
    {"date": "2026-04-13T00:00:00+07:00", "description": "Songkran Festival"},
    {"date": "2026-04-14T00:00:00+07:00", "description": "Songkran Festival"},
    {"date": "2026-04-15T00:00:00+07:00", "description": "Songkran Festival"},
    {"date": "2026-05-01T00:00:00+07:00", "description": "National Labor Day"},
    {"date": "2026-05-04T00:00:00+07:00", "description": "Coronation Day"},
    {
        "date": "2026-06-01T00:00:00+07:00",
        "description": "Substitution for Visakha Bucha Day (Sunday 31st May 2026)",
    },
    {
        "date": "2026-06-03T00:00:00+07:00",
        "description": "H.M. Queen Suthida Bajrasudhabimalalakshana's Birthday",
    },
    {
        "date": "2026-07-28T00:00:00+07:00",
        "description": "H.M. King Maha Vajiralongkorn Phra Vajiraklaochaoyuhua's Birthday",
    },
    {"date": "2026-07-29T00:00:00+07:00", "description": "Asarnha Bucha Day"},
    {
        "date": "2026-08-12T00:00:00+07:00",
        "description": "H.M. Queen Sirikit The Queen Mother's Birthday / Mother's Day",
    },
    {
        "date": "2026-10-13T00:00:00+07:00",
        "description": "H.M. King Bhumibol Adulyadej the Great Memorial Day",
    },
    # The trailing " *" is a SET footnote marker and must never be stripped.
    {"date": "2026-10-16T00:00:00+07:00", "description": "Additional special holiday *"},
    {
        "date": "2026-10-23T00:00:00+07:00",
        "description": "H.M. King Chulalongkorn the Great Memorial Day",
    },
    {
        "date": "2026-12-07T00:00:00+07:00",
        "description": (
            "Substitution for H.M. King Bhumibol Adulyadej the Great's Birthday / National Day / "
            "Father's Day (Saturday 5th December 2026)"
        ),
    },
    {"date": "2026-12-10T00:00:00+07:00", "description": "Constitution Day"},
    {"date": "2026-12-31T00:00:00+07:00", "description": "New Year's Eve"},
]

# Thai payload subset - same dates and ordering as SAMPLE_EN. Note the parenthetical notes use
# Buddhist-era years (2569 = 2026) and the " *" marker appears in Thai too.
SAMPLE_TH: list[dict[str, Any]] = [
    {"date": "2026-01-01T00:00:00+07:00", "description": "วันขึ้นปีใหม่"},
    {"date": "2026-01-02T00:00:00+07:00", "description": "วันหยุดทำการเพิ่มเติมเป็นกรณีพิเศษ"},
    {"date": "2026-03-03T00:00:00+07:00", "description": "วันมาฆบูชา"},
    {
        "date": "2026-06-01T00:00:00+07:00",
        "description": "ชดเชยวันวิสาขบูชา (วันอาทิตย์ที่ 31 พฤษภาคม 2569)",
    },
    {"date": "2026-10-16T00:00:00+07:00", "description": "วันหยุดทำการเพิ่มเติมเป็นกรณีพิเศษ *"},
    {"date": "2026-12-31T00:00:00+07:00", "description": "วันสิ้นปี"},
]


def _response(
    payload: Any = None,
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
        url="https://www.set.or.th/api/cms/v1/holidays/year/2026?lang=en",
        elapsed=0.1,
    )


def _calendar(payload: list[dict[str, Any]] | None = None, year: int = 2026) -> HolidayCalendar:
    """Build a HolidayCalendar directly from a payload, without going through the service."""
    holidays = [
        Holiday.model_validate(item) for item in (payload if payload is not None else SAMPLE_EN)
    ]
    return HolidayCalendar(year=year, lang="en", holidays=holidays)


@pytest.fixture
def mock_fetcher():
    """Patch AsyncDataFetcher inside the holiday module; yield its async instance.

    The patched class mock is attached as ``.cls`` so tests can assert on the header helper.
    """
    with patch("settfex.services.set.holiday.AsyncDataFetcher") as mock:
        fetcher_instance = AsyncMock()
        mock.return_value.__aenter__.return_value = fetcher_instance
        mock.return_value.__aexit__.return_value = None
        mock.get_set_api_headers = Mock(return_value={"Accept": "application/json"})
        fetcher_instance.cls = mock
        yield fetcher_instance


@pytest.fixture
def no_sleep():
    """Neutralize the retry backoff so retry tests run instantly."""
    with patch("settfex.services.set.holiday.asyncio.sleep", new=AsyncMock()) as sleeper:
        yield sleeper


# --- models -----------------------------------------------------------------------------------


class TestHolidayModel:
    """Tests for the Holiday Pydantic model."""

    def test_alias_and_timezone(self):
        """The API's `date` key lands in holiday_date as an aware +07:00 datetime."""
        holiday = Holiday.model_validate(SAMPLE_EN[0])
        assert holiday.holiday_date == datetime(2026, 1, 1, 0, 0, tzinfo=BKK)
        assert holiday.holiday_date.utcoffset() == timedelta(hours=7)
        assert holiday.description == "New Year's Day"

    def test_footnote_marker_preserved_verbatim(self):
        """The trailing ' *' footnote marker must survive parsing untouched."""
        holiday = Holiday.model_validate(SAMPLE_EN[15])
        assert holiday.description == "Additional special holiday *"
        assert holiday.description.endswith(" *")

    def test_thai_footnote_marker_preserved(self):
        """Same guard for the Thai payload."""
        holiday = Holiday.model_validate(SAMPLE_TH[4])
        assert holiday.description.endswith(" *")
        assert "วันหยุดทำการเพิ่มเติมเป็นกรณีพิเศษ" in holiday.description

    def test_populate_by_name(self):
        """The model accepts the snake_case field name as well as the API alias."""
        holiday = Holiday(
            holiday_date=datetime(2026, 1, 1, tzinfo=BKK), description="New Year's Day"
        )
        assert holiday.holiday_date.year == 2026

    def test_round_trips_to_api_alias(self):
        """Dumping by alias reproduces the API's key name."""
        holiday = Holiday.model_validate(SAMPLE_EN[0])
        assert "date" in holiday.model_dump(by_alias=True)


class TestHolidayCalendar:
    """Tests for the HolidayCalendar container and its query helpers."""

    def test_count_and_dates(self):
        """count reflects the payload; dates are plain ascending calendar days."""
        calendar = _calendar()
        assert calendar.count == 20
        assert calendar.dates[0] == date(2026, 1, 1)
        assert calendar.dates[-1] == date(2026, 12, 31)
        assert calendar.dates == sorted(calendar.dates)

    def test_is_holiday(self):
        """A published holiday is recognized; an ordinary trading day is not."""
        calendar = _calendar()
        assert calendar.is_holiday(date(2026, 1, 1)) is True
        assert calendar.is_holiday(date(2026, 1, 5)) is False

    def test_is_holiday_returns_false_for_weekend(self):
        """Weekends are absent from the payload - this is the documented sharp edge."""
        calendar = _calendar()
        saturday = date(2026, 1, 3)
        assert saturday.weekday() == 5
        assert calendar.is_holiday(saturday) is False

    def test_is_holiday_accepts_naive_datetime(self):
        """A naive datetime is treated as Bangkok-local."""
        calendar = _calendar()
        assert calendar.is_holiday(datetime(2026, 1, 1, 15, 30)) is True

    def test_is_holiday_converts_aware_datetime(self):
        """An aware datetime is converted to the Bangkok calendar day before matching."""
        calendar = _calendar()
        # 2025-12-31 18:00 UTC is 2026-01-01 01:00 in Bangkok.
        moment = datetime(2025, 12, 31, 18, 0, tzinfo=UTC)
        assert calendar.is_holiday(moment) is True

    def test_get_holiday(self):
        """get_holiday returns the matching entry, or None."""
        calendar = _calendar()
        holiday = calendar.get_holiday(date(2026, 4, 13))
        assert holiday is not None
        assert holiday.description == "Songkran Festival"
        assert calendar.get_holiday(date(2026, 4, 16)) is None

    def test_filter_by_month(self):
        """Songkran gives April four entries (6th, 13th, 14th, 15th)."""
        calendar = _calendar()
        april = calendar.filter_by_month(4)
        assert len(april) == 4
        assert all(h.holiday_date.month == 4 for h in april)

    def test_filter_by_month_rejects_out_of_range(self):
        """An impossible month is a caller error, not an empty result."""
        calendar = _calendar()
        with pytest.raises(ValueError, match="between 1 and 12"):
            calendar.filter_by_month(13)

    def test_next_holiday(self):
        """next_holiday is exclusive of the given day."""
        calendar = _calendar()
        upcoming = calendar.next_holiday(date(2026, 1, 1))
        assert upcoming is not None
        assert upcoming.holiday_date.date() == date(2026, 1, 2)

    def test_next_holiday_returns_none_past_year_end(self):
        """The calendar only covers its own year."""
        calendar = _calendar()
        assert calendar.next_holiday(date(2026, 12, 31)) is None

    def test_next_holiday_is_order_independent(self):
        """Correct even if the API stops returning sorted data."""
        shuffled = list(reversed(SAMPLE_EN))
        calendar = _calendar(shuffled)
        upcoming = calendar.next_holiday(date(2026, 1, 1))
        assert upcoming is not None
        assert upcoming.holiday_date.date() == date(2026, 1, 2)

    def test_empty_calendar(self):
        """An empty holiday list is valid and answers everything negatively."""
        calendar = HolidayCalendar(year=2026, lang="en", holidays=[])
        assert calendar.count == 0
        assert calendar.dates == []
        assert calendar.is_holiday(date(2026, 1, 1)) is False
        assert calendar.next_holiday(date(2026, 1, 1)) is None


# --- service ----------------------------------------------------------------------------------


@pytest.mark.asyncio
class TestHolidayService:
    """Tests for HolidayService."""

    async def test_init_default_config(self):
        """Default config keeps use_session=True (this host is behind Incapsula)."""
        service = HolidayService()
        assert service.config.use_session is True
        assert service.base_url == "https://www.set.or.th"

    async def test_init_custom_config(self):
        """A caller-supplied config is honored."""
        config = FetcherConfig(max_retries=6, retry_delay=2.0)
        service = HolidayService(config=config)
        assert service.config.max_retries == 6

    async def test_fetch_holidays_success(self, mock_fetcher):
        """A successful fetch parses into a HolidayCalendar."""
        mock_fetcher.fetch.return_value = _response(SAMPLE_EN)

        calendar = await HolidayService().fetch_holidays(2026)

        assert isinstance(calendar, HolidayCalendar)
        assert calendar.year == 2026
        assert calendar.lang == "en"
        assert calendar.count == 20
        assert calendar.holidays[0].description == "New Year's Day"

    async def test_fetch_holidays_builds_expected_url(self, mock_fetcher):
        """URL uses the /api/cms/v1/ prefix and ?lang= (not ?language=)."""
        mock_fetcher.fetch.return_value = _response(SAMPLE_EN)

        await HolidayService().fetch_holidays(2026, lang="th")

        url = mock_fetcher.fetch.call_args.args[0]
        assert url == "https://www.set.or.th/api/cms/v1/holidays/year/2026?lang=th"
        assert "language=" not in url

    async def test_fetch_holidays_uses_set_api_headers(self, mock_fetcher):
        """Market-level services call the header helper with no arguments."""
        mock_fetcher.fetch.return_value = _response(SAMPLE_EN)

        await HolidayService().fetch_holidays(2026)

        mock_fetcher.cls.get_set_api_headers.assert_called_once_with()

    async def test_language_normalization(self, mock_fetcher):
        """Language aliases are normalized before hitting the wire."""
        mock_fetcher.fetch.return_value = _response(SAMPLE_TH)

        calendar = await HolidayService().fetch_holidays(2026, lang="thai")  # type: ignore[arg-type]

        assert calendar.lang == "th"
        assert mock_fetcher.fetch.call_args.args[0].endswith("?lang=th")

    async def test_invalid_language(self, mock_fetcher):
        """An unrecognized language is rejected before any request is made."""
        with pytest.raises(InvalidLanguageError):
            await HolidayService().fetch_holidays(2026, lang="de")  # type: ignore[arg-type]
        mock_fetcher.fetch.assert_not_called()

    async def test_year_defaults_to_current_bangkok_year(self, mock_fetcher):
        """Omitting the year resolves it from Asia/Bangkok, never system-local time."""
        mock_fetcher.fetch.return_value = _response(SAMPLE_EN)

        await HolidayService().fetch_holidays()

        expected = datetime.now(BANGKOK_TZ).year
        assert f"/holidays/year/{expected}?" in mock_fetcher.fetch.call_args.args[0]

    async def test_normalize_year_resolves_none(self):
        """_normalize_year(None) matches the Bangkok clock."""
        assert HolidayService._normalize_year(None) == datetime.now(BANGKOK_TZ).year

    @pytest.mark.parametrize("bad_year", [MIN_YEAR - 1, MAX_YEAR + 1, 0, -2026])
    async def test_year_out_of_range(self, bad_year, mock_fetcher):
        """Out-of-range years are a typo guard and never reach the network."""
        with pytest.raises(ValueError, match="out of range"):
            await HolidayService().fetch_holidays(bad_year)
        mock_fetcher.fetch.assert_not_called()

    @pytest.mark.parametrize("bad_year", [True, False, "2026", 2026.0])
    async def test_year_must_be_int(self, bad_year, mock_fetcher):
        """Non-int years (including bools, which are ints in Python) are rejected."""
        with pytest.raises(ValueError, match="must be an integer"):
            await HolidayService().fetch_holidays(bad_year)
        mock_fetcher.fetch.assert_not_called()

    async def test_fetch_holidays_raw(self, mock_fetcher):
        """The raw tier returns the untouched list of dicts."""
        mock_fetcher.fetch.return_value = _response(SAMPLE_EN)

        data = await HolidayService().fetch_holidays_raw(2026)

        assert isinstance(data, list)
        assert data[0] == {"date": "2026-01-01T00:00:00+07:00", "description": "New Year's Day"}

    async def test_empty_list_response(self, mock_fetcher):
        """An empty array is a valid, empty calendar - not an error."""
        mock_fetcher.fetch.return_value = _response([])

        calendar = await HolidayService().fetch_holidays(2026)

        assert calendar.count == 0


@pytest.mark.asyncio
class TestRetryBehaviour:
    """The endpoint returns a bare 401 transiently, so the service retries."""

    async def test_retries_transient_401_then_succeeds(self, mock_fetcher, no_sleep):
        """A 401 followed by a 200 yields data rather than an exception."""
        mock_fetcher.fetch.side_effect = [
            _response(status_code=401, text=""),
            _response(status_code=401, text=""),
            _response(SAMPLE_EN),
        ]
        service = HolidayService(FetcherConfig(max_retries=3, retry_delay=0.1))

        calendar = await service.fetch_holidays(2026)

        assert calendar.count == 20
        assert mock_fetcher.fetch.call_count == 3
        assert no_sleep.await_count == 2

    async def test_backoff_is_exponential(self, mock_fetcher, no_sleep):
        """Successive retries wait retry_delay * 2**attempt."""
        mock_fetcher.fetch.side_effect = [
            _response(status_code=401, text=""),
            _response(status_code=401, text=""),
            _response(SAMPLE_EN),
        ]
        service = HolidayService(FetcherConfig(max_retries=3, retry_delay=1.0))

        await service.fetch_holidays(2026)

        assert [call.args[0] for call in no_sleep.await_args_list] == [1.0, 2.0]

    async def test_retries_exhausted_raises_fetch_error(self, mock_fetcher, no_sleep):
        """Persistent 401s surface as FetchError carrying the status code."""
        mock_fetcher.fetch.return_value = _response(status_code=401, text="")
        service = HolidayService(FetcherConfig(max_retries=2, retry_delay=0.1))

        with pytest.raises(FetchError) as exc_info:
            await service.fetch_holidays(2026)

        assert exc_info.value.status_code == 401
        assert mock_fetcher.fetch.call_count == 3
        # 401 is the endpoint's only failure code, so the message must name both causes.
        message = str(exc_info.value)
        assert "only the current year is available" in message
        assert "retry later" in message

    async def test_non_retryable_status_raises_immediately(self, mock_fetcher, no_sleep):
        """A 500 is not retried - it fails on the first attempt."""
        mock_fetcher.fetch.return_value = _response(status_code=500, text="")
        service = HolidayService(FetcherConfig(max_retries=3, retry_delay=0.1))

        with pytest.raises(FetchError) as exc_info:
            await service.fetch_holidays(2026)

        assert exc_info.value.status_code == 500
        assert mock_fetcher.fetch.call_count == 1
        no_sleep.assert_not_awaited()
        # The 401-specific hint must not be attached to unrelated statuses.
        assert "current year" not in str(exc_info.value)

    async def test_no_retry_when_max_retries_is_zero(self, mock_fetcher, no_sleep):
        """max_retries=0 means exactly one attempt."""
        mock_fetcher.fetch.return_value = _response(status_code=401, text="")
        service = HolidayService(FetcherConfig(max_retries=0))

        with pytest.raises(FetchError):
            await service.fetch_holidays(2026)

        assert mock_fetcher.fetch.call_count == 1
        no_sleep.assert_not_awaited()


@pytest.mark.asyncio
class TestParseErrors:
    """Malformed payloads surface as ResponseParseError."""

    async def test_invalid_json(self, mock_fetcher):
        """A non-JSON body is a parse error, not a crash."""
        mock_fetcher.fetch.return_value = _response(text="<html>nope</html>")

        with pytest.raises(ResponseParseError, match="2026"):
            await HolidayService().fetch_holidays(2026)

    async def test_non_list_payload(self, mock_fetcher):
        """A dict where an array was expected is rejected by validate_list_or_raise."""
        mock_fetcher.fetch.return_value = _response({"holidays": []})

        with pytest.raises(ResponseParseError, match="Expected a JSON array"):
            await HolidayService().fetch_holidays(2026)


# --- convenience function ---------------------------------------------------------------------


@pytest.mark.asyncio
class TestConvenienceFunction:
    """Tests for the get_holidays convenience function."""

    async def test_get_holidays(self, mock_fetcher):
        """The one-liner returns the same HolidayCalendar."""
        mock_fetcher.fetch.return_value = _response(SAMPLE_EN)

        calendar = await get_holidays(2026)

        assert isinstance(calendar, HolidayCalendar)
        assert calendar.count == 20

    async def test_get_holidays_thai(self, mock_fetcher):
        """Thai descriptions survive the round trip."""
        mock_fetcher.fetch.return_value = _response(SAMPLE_TH)

        calendar = await get_holidays(2026, lang="th")

        assert calendar.lang == "th"
        assert calendar.holidays[0].description == "วันขึ้นปีใหม่"

    async def test_get_holidays_honors_config(self, mock_fetcher):
        """A custom config reaches the underlying fetcher."""
        mock_fetcher.fetch.return_value = _response(SAMPLE_EN)
        config = FetcherConfig(timeout=99)

        await get_holidays(2026, config=config)

        assert mock_fetcher.cls.call_args.kwargs["config"].timeout == 99
