"""Tests for the unified ThaiBMA facade — lazy service construction and delegation."""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from settfex.services.thaibma import ThaiBMA
from settfex.services.thaibma.history import HistoryKind
from settfex.utils.data_fetcher import FetcherConfig

pytestmark = pytest.mark.asyncio


class TestLazyServices:
    """Services are constructed on first use and then cached."""

    async def test_services_are_created_once_and_reused(self):
        facade = ThaiBMA()

        assert facade._curve_service is None
        first = facade.curve_service
        assert first is facade.curve_service
        assert facade.history_service is facade.history_service
        assert facade.availability_service is facade.availability_service

    async def test_config_reaches_every_service_with_session_disabled(self):
        facade = ThaiBMA(FetcherConfig(timeout=88, max_retries=5))

        for service in (
            facade.curve_service,
            facade.history_service,
            facade.availability_service,
        ):
            assert service.config.timeout == 88
            assert service.config.max_retries == 5
            assert service.config.use_session is False


class TestDelegation:
    """Every facade method forwards to the service that owns the endpoint."""

    async def test_get_yield_curve_forwards_date_and_policy(self):
        facade = ThaiBMA()
        with patch.object(facade.curve_service, "fetch_curve", new=AsyncMock()) as fetch:
            await facade.get_yield_curve("2026-08-10", on_rollback="raise")

        fetch.assert_awaited_once_with("2026-08-10", on_rollback="raise")

    async def test_get_yield_curve_defaults_to_latest_and_warn(self):
        facade = ThaiBMA()
        with patch.object(facade.curve_service, "fetch_curve", new=AsyncMock()) as fetch:
            await facade.get_yield_curve()

        fetch.assert_awaited_once_with(None, on_rollback="warn")

    async def test_get_history_defaults_to_the_tenor_matrix(self):
        facade = ThaiBMA()
        with patch.object(facade.history_service, "fetch_history", new=AsyncMock()) as fetch:
            await facade.get_history("2026-01-01", date(2026, 8, 10))

        assert fetch.await_args.kwargs["kind"] is HistoryKind.TENOR
        assert fetch.await_args.args == ("2026-01-01", date(2026, 8, 10))

    async def test_get_bond_history_selects_the_bond_matrix(self):
        facade = ThaiBMA()
        with patch.object(facade.history_service, "fetch_history", new=AsyncMock()) as fetch:
            await facade.get_bond_history("2026-01-01")

        assert fetch.await_args.kwargs["kind"] is HistoryKind.BOND

    async def test_get_history_forwards_tuning_options(self):
        facade = ThaiBMA()
        with patch.object(facade.history_service, "fetch_history", new=AsyncMock()) as fetch:
            await facade.get_history(max_concurrency=2, check_availability=False, progress=True)

        kwargs = fetch.await_args.kwargs
        assert kwargs["max_concurrency"] == 2
        assert kwargs["check_availability"] is False
        assert kwargs["progress"] is True

    async def test_get_availability_forwards_include_years(self):
        facade = ThaiBMA()
        with patch.object(
            facade.availability_service, "fetch_availability", new=AsyncMock()
        ) as fetch:
            await facade.get_availability(include_years=False)

        fetch.assert_awaited_once_with(include_years=False)
