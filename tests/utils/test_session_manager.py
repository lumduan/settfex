"""Tests for SessionManager, focused on warmup concurrency correctness."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

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

    @pytest.mark.asyncio
    async def test_settrade_is_its_own_instance_and_cache_key(self) -> None:
        settrade = await SessionManager.get_instance(warmup_site="settrade")
        set_ = await SessionManager.get_instance(warmup_site="set")
        assert settrade is not set_
        assert settrade._cache_key == "settrade_session_chrome120"
        assert set_._cache_key == "set_session_chrome120"

    @pytest.mark.asyncio
    async def test_reset_set_does_not_reset_settrade(self) -> None:
        """Regression: instance keys are "<site>_<browser>", and "settrade_chrome120"
        starts with "set" - a prefix match would silently close the Settrade session too.
        """
        await SessionManager.get_instance(warmup_site="set")
        await SessionManager.get_instance(warmup_site="settrade")
        assert set(SessionManager._instances) == {"set_chrome120", "settrade_chrome120"}

        SessionManager.reset_instance("set")
        assert set(SessionManager._instances) == {"settrade_chrome120"}


class TestWarmupUrls:
    """Each site warms its own host - Incapsula cookies are per-domain."""

    @pytest.mark.parametrize(
        ("warmup_site", "expected_host"),
        [
            ("set", "https://www.set.or.th/"),
            ("tfex", "https://www.tfex.co.th/"),
            ("settrade", "https://www.settrade.com/"),
            ("unknown-site", "https://www.set.or.th/"),  # falls back to SET, as before
        ],
    )
    @pytest.mark.asyncio
    async def test_warmup_visits_the_right_host(self, warmup_site: str, expected_host: str) -> None:
        visited: list[str] = []

        def fake_get(url: str, *_args: object, **_kwargs: object) -> Mock:
            visited.append(url)
            resp = Mock()
            resp.status_code = 200
            resp.cookies = {"incap_ses": "abc"}
            return resp

        session = Mock()
        session.get = fake_get
        manager = SessionManager(enable_cache=False, warmup_site=warmup_site)
        with patch("settfex.utils.session_manager.requests.Session", return_value=session):
            await manager.ensure_initialized()

        assert visited and visited[0].startswith(expected_host)


class TestGetSessionForUrl:
    """A settrade.com URL must never fall through to the SET warmup (cookies are per-domain)."""

    @pytest.mark.parametrize(
        ("url", "expected_site"),
        [
            ("https://www.set.or.th/api/set/stock/CPALL/highlight-data", "set"),
            ("https://www.tfex.co.th/api/set/tfex/series/list", "tfex"),
            ("https://www.settrade.com/api/set-fund/consensus/stock/GULF/consensus", "settrade"),
            ("https://WWW.SETTRADE.COM/api/set-fund/consensus/stock/overall", "settrade"),
            ("https://example.com/whatever", "set"),
        ],
    )
    @pytest.mark.asyncio
    async def test_warmup_site_is_detected_from_the_host(
        self, url: str, expected_site: str
    ) -> None:
        from settfex.utils.session_manager import get_session_for_url

        with patch(
            "settfex.utils.session_manager.get_shared_session", new_callable=AsyncMock
        ) as mock_shared:
            await get_session_for_url(url)

        assert mock_shared.call_args.kwargs["warmup_site"] == expected_site
