"""Tests for the ThaiBMA shared helpers — date normalization, tenor labels, stateless config."""

from datetime import date, datetime

import pytest

from settfex.exceptions import InvalidDateError
from settfex.services.thaibma.utils import (
    build_thaibma_headers,
    format_curve_date,
    normalize_curve_date,
    normalize_year,
    parse_tenor,
    sort_tenor_columns,
    stateless_config,
    tenor_label,
)
from settfex.utils.data_fetcher import FetcherConfig

# --- date normalization ---


class TestNormalizeCurveDate:
    """The client-side guard that makes ThaiBMA's malformed-date traps unreachable."""

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("2026-08-10", date(2026, 8, 10)),
            ("2026-08-10T00:00:00", date(2026, 8, 10)),
            ("  2026-08-10  ", date(2026, 8, 10)),
            (date(2026, 8, 10), date(2026, 8, 10)),
            (datetime(2026, 8, 10, 15, 30), date(2026, 8, 10)),
        ],
    )
    def test_accepts_supported_forms(self, value, expected):
        """Dates, datetimes and ISO strings all reduce to a plain calendar day."""
        assert normalize_curve_date(value) == expected

    def test_unpadded_string_is_accepted_and_repadded(self):
        """'2026-8-10' would 404 on the wire, so it is normalized rather than rejected."""
        assert format_curve_date(normalize_curve_date("2026-8-10")) == "2026-08-10"

    def test_accepts_iso_basic_format(self):
        """'20260810' is valid ISO 8601 basic form and normalizes to the padded wire format."""
        assert format_curve_date(normalize_curve_date("20260810")) == "2026-08-10"

    @pytest.mark.parametrize(
        "value",
        ["2026-02-30", "2026-13-01", "10/08/2026", "not-a-date", ""],
    )
    def test_rejects_malformed_and_impossible_dates(self, value):
        """An impossible date must never reach the API, which answers it with the LATEST curve."""
        with pytest.raises(InvalidDateError):
            normalize_curve_date(value)

    def test_rejects_wrong_type(self):
        """A non-date argument raises rather than being coerced into a URL."""
        with pytest.raises(InvalidDateError, match="date, datetime or"):
            normalize_curve_date(20260810)  # type: ignore[arg-type]

    def test_format_is_always_zero_padded(self):
        """The wire format is strict about padding; formatting guarantees it."""
        assert format_curve_date(date(1999, 9, 5)) == "1999-09-05"


class TestNormalizeYear:
    """Client-side typo guard on the per-year history endpoints."""

    def test_accepts_in_range(self):
        assert normalize_year(2026) == 2026

    @pytest.mark.parametrize("bad", [1998, 2101])
    def test_rejects_out_of_range(self, bad):
        with pytest.raises(ValueError, match="out of range"):
            normalize_year(bad)

    def test_rejects_bool(self):
        """bool is an int subclass; True must not be formatted into a URL as '1'."""
        with pytest.raises(ValueError, match="must be an integer"):
            normalize_year(True)  # type: ignore[arg-type]


# --- tenor labels: the bridge between the float grid and the history columns ---


class TestTenorLabels:
    """The mapping is exact and verified against live data, not a day-count approximation."""

    @pytest.mark.parametrize(
        "tenor_years,label",
        [
            (0.076712328767123, "1M"),
            (0.249315068493151, "3M"),
            (0.498630136986301, "6M"),
            (1.0, "1Y"),
            (10.0, "10Y"),
            (50.0, "50Y"),
        ],
    )
    def test_tenor_label_round_trip(self, tenor_years, label):
        """Every grid X maps to its history column label, and back to the same tenor."""
        assert tenor_label(tenor_years) == label
        assert parse_tenor(label) == pytest.approx(tenor_years, abs=1e-9)

    def test_parse_tenor_is_case_insensitive(self):
        assert parse_tenor("10y") == 10.0

    def test_parse_tenor_rejects_unknown(self):
        with pytest.raises(ValueError, match="Unrecognized ThaiBMA tenor"):
            parse_tenor("1W")

    def test_sort_is_by_maturity_not_lexicographic(self):
        """Plain sorted() puts '10Y' before '2Y'; maturity order must not."""
        labels = ["10Y", "2Y", "1M", "6M", "1Y", "3M"]
        assert sort_tenor_columns(labels) == ["1M", "3M", "6M", "1Y", "2Y", "10Y"]
        assert sorted(labels) != sort_tenor_columns(labels)

    def test_unknown_labels_sort_last_without_raising(self):
        """A new ThaiBMA column must not break an entire history pull."""
        assert sort_tenor_columns(["5Y", "MYSTERY", "1Y"]) == ["1Y", "5Y", "MYSTERY"]


# --- fetcher configuration ---


class TestStatelessConfig:
    """use_session must be forced off without discarding the caller's settings."""

    def test_disables_session_and_preserves_everything_else(self):
        config = FetcherConfig(timeout=99, max_retries=7, retry_delay=2.5, rate_limit_delay=0.5)

        result = stateless_config(config)

        assert result.use_session is False
        assert result.timeout == 99
        assert result.max_retries == 7
        assert result.retry_delay == 2.5
        assert result.rate_limit_delay == 0.5

    def test_none_yields_defaults_with_session_off(self):
        assert stateless_config(None).use_session is False

    def test_does_not_mutate_the_caller_config(self):
        """The caller's object must survive being handed to a service."""
        config = FetcherConfig(use_session=True)
        stateless_config(config)
        assert config.use_session is True


class TestHeaders:
    """The host needs no bot-detection posture, so the headers stay minimal and honest."""

    def test_requests_json_without_inventing_a_referer(self):
        headers = build_thaibma_headers()
        assert "application/json" in headers["Accept"]
        assert "Referer" not in headers
        assert "Cookie" not in headers
