"""Tests for SessionManager, focused on warmup concurrency correctness."""

import asyncio
from unittest.mock import Mock, patch

import pytest

from settfex.utils.session_manager import SessionManager


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Ensure a clean singleton registry around every test."""
    SessionManager.reset_instance()
    yield
    SessionManager.reset_instance()


def _make_fake_session(counter: dict[str, int]) -> Mock:
    """A fake curl_cffi session whose .get() records warmup calls."""

    def fake_get(*_args: object, **_kwargs: object) -> Mock:
        counter["warmups"] += 1
        resp = Mock()
        resp.status_code = 200
        resp.cookies = {"incap_ses": "abc"}
        return resp

    session = Mock()
    session.get = fake_get
    return session


class TestEnsureInitializedConcurrency:
    """ensure_initialized() must warm up at most once, even under a cold-start stampede."""

    @pytest.mark.asyncio
    async def test_concurrent_cold_start_warms_once(self) -> None:
        counter = {"warmups": 0}
        manager = SessionManager(browser="chrome120", enable_cache=False, warmup_site="set")

        with patch(
            "settfex.utils.session_manager.requests.Session",
            return_value=_make_fake_session(counter),
        ):
            # Fire many concurrent initializations at a cold instance.
            await asyncio.gather(*[manager.ensure_initialized() for _ in range(25)])

        # Without the per-instance lock this would be 25 warmup round-trips.
        assert counter["warmups"] == 1
        assert manager._initialized is True

    @pytest.mark.asyncio
    async def test_single_call_warms_once(self) -> None:
        counter = {"warmups": 0}
        manager = SessionManager(browser="chrome120", enable_cache=False, warmup_site="set")

        with patch(
            "settfex.utils.session_manager.requests.Session",
            return_value=_make_fake_session(counter),
        ):
            await manager.ensure_initialized()
            # A second sequential call is already initialized and must not re-warm.
            await manager.ensure_initialized()

        assert counter["warmups"] == 1


class TestGetInstance:
    """Singleton behavior."""

    @pytest.mark.asyncio
    async def test_get_instance_is_singleton_per_site(self) -> None:
        a = await SessionManager.get_instance(warmup_site="set")
        b = await SessionManager.get_instance(warmup_site="set")
        c = await SessionManager.get_instance(warmup_site="tfex")
        assert a is b
        assert a is not c
