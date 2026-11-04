"""Tests for SessionManager, focused on warmup concurrency correctness."""

import asyncio
import time
from typing import Any
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

    @pytest.mark.parametrize(
        ("url", "expected_site"),
        [
            # 0.26.3: matched on the HOSTNAME, never on a substring of the whole URL.
            ("https://evil.example/?next=www.settrade.com", "set"),
            ("https://settrade.com.evil.example/api", "set"),
            ("https://notsettrade.com/api", "set"),
            ("https://api.settrade.com/x", "settrade"),
            ("https://www.tfex.co.th:443/api/set/tfex/series/list", "tfex"),
            ("not a url", "set"),
        ],
    )
    @pytest.mark.asyncio
    async def test_matching_is_on_the_hostname_not_a_substring(
        self, url: str, expected_site: str
    ) -> None:
        from settfex.utils.session_manager import get_session_for_url

        with patch(
            "settfex.utils.session_manager.get_shared_session", new_callable=AsyncMock
        ) as mock_shared:
            await get_session_for_url(url)

        assert mock_shared.call_args.kwargs["warmup_site"] == expected_site


# ── 0.26.3: cached cookies keep the domain they were issued for ─────────────────────────────────

# The jar a real SET warm-up produced (live, 2026-11-02): one host-only cookie and two Incapsula
# cookies on the registrable domain. Values are placeholders.
#
# Expiries are RELATIVE TO NOW, keeping the lifetimes the live jar showed: charlot ~1 day,
# visid_incap ~1 year, incap_ses a session cookie. They were first written as the captured
# absolute timestamps, so the fixture expired with the real cookie (charlot at 2026-11-03 20:42
# ICT): an expired cookie is dropped from the jar, and the leak test went red on main the next
# day with no code change. A fixture that copies a live expiry is a time bomb.
_NOW = int(time.time())
_LIVE_SHAPED_JAR = [
    ("charlot", "c" * 36, "www.set.or.th", False, _NOW + 86_400),
    ("visid_incap_2046605", "v" * 64, ".set.or.th", True, _NOW + 365 * 86_400),
    ("incap_ses_297_2046605", "s" * 56, ".set.or.th", True, None),
]


def _jar_session(rows: list[tuple[str, str, str, bool, int | None]]) -> Any:
    from http.cookiejar import Cookie

    from curl_cffi import requests as cr

    session = cr.Session()
    for name, value, domain, specified, expires in rows:
        session.cookies.jar.set_cookie(
            Cookie(
                0,
                name,
                value,
                None,
                False,
                domain,
                specified,
                domain.startswith("."),
                "/",
                True,
                False,
                expires,
                expires is None,
                None,
                None,
                {},
            )
        )
    return session


@pytest.fixture
def make_manager(tmp_path: Any) -> Any:
    """SessionManagers sharing one private cache dir; caches and sessions closed on teardown."""
    from settfex.utils.session_cache import SessionCache

    made: list[tuple[SessionManager, SessionCache]] = []

    def _make(site: str = "set") -> SessionManager:
        manager = SessionManager(warmup_site=site, cache_dir=tmp_path)
        cache = SessionCache(cache_dir=tmp_path)
        manager._get_cache = AsyncMock(return_value=cache)  # type: ignore[method-assign]
        made.append((manager, cache))
        return manager

    yield _make
    for manager, cache in made:
        manager.close()
        cache.close()


class TestCookieDomainsSurviveTheCache:
    """A restored session sends each cookie only to the host it was issued for."""

    @pytest.mark.asyncio
    async def test_round_trip_keeps_domain_flags_path_and_expiry(self, make_manager: Any) -> None:
        writer = make_manager()
        writer._session = _jar_session(_LIVE_SHAPED_JAR)
        await writer._save_to_cache()

        reader = make_manager()
        assert await reader._try_load_from_cache() is True
        assert reader._session is not None
        got = {c.name: c for c in reader._session.cookies.jar}
        for name, value, domain, specified, expires in _LIVE_SHAPED_JAR:
            assert got[name].value == value
            assert got[name].domain == domain
            assert got[name].domain_specified is specified
            assert got[name].path == "/"
            assert got[name].expires == expires

    @pytest.mark.asyncio
    async def test_the_legacy_name_value_entry_is_a_miss(self, make_manager: Any) -> None:
        """0.26.1/0.26.2 cached name -> value only; restoring that would be domain-less."""
        manager = make_manager()
        cache = await manager._get_cache()
        cache.set(manager._cache_key, {"cookies": {"incap_ses_297_2046605": "x"}})

        assert await manager._try_load_from_cache() is False
        assert manager._session is None

    @pytest.mark.parametrize(
        "bad",
        [
            {"name": "a", "value": "b", "domain": ""},  # domain-less
            {"name": "a", "value": "b", "domain": ".evil.example"},  # off-site
            {"name": "a", "value": "b", "domain": "set.or.th.evil.example"},
            {"name": "", "value": "b", "domain": ".set.or.th"},
            {"name": "a", "value": 1, "domain": ".set.or.th"},
            {"name": "a", "value": "b", "domain": ".set.or.th", "expires": "soon"},
            "not-a-dict",
        ],
    )
    @pytest.mark.asyncio
    async def test_a_malformed_or_off_site_cookie_is_a_miss(
        self, make_manager: Any, bad: Any
    ) -> None:
        manager = make_manager()
        cache = await manager._get_cache()
        good = {"name": "ok", "value": "v", "domain": ".set.or.th", "domain_specified": True}
        cache.set(manager._cache_key, {"cookie_jar": [good, bad], "cookies": {"ok": "v"}})

        assert await manager._try_load_from_cache() is False
        assert manager._session is None

    @pytest.mark.asyncio
    async def test_the_save_keeps_the_legacy_map_for_older_readers(self, make_manager: Any) -> None:
        writer = make_manager()
        writer._session = _jar_session(_LIVE_SHAPED_JAR)
        await writer._save_to_cache()

        cache = await writer._get_cache()
        entry = cache.get(writer._cache_key)
        assert entry is not None
        assert set(entry["cookies"]) == {row[0] for row in _LIVE_SHAPED_JAR}
        assert len(entry["cookie_jar"]) == len(_LIVE_SHAPED_JAR)


class TestARestoredSessionDoesNotLeakItsCookies:
    """Loopback only. Two names resolve to 127.0.0.1 through CURLOPT_RESOLVE, so no DNS and no
    external traffic. Before 0.26.3 the cookies were restored WITHOUT a domain, and curl_cffi
    binds such a cookie to the host of the first request that carries it, wherever that goes."""

    @pytest.mark.asyncio
    async def test_first_request_to_a_foreign_host_carries_no_cookie(
        self, make_manager: Any
    ) -> None:
        import http.server
        import threading

        from curl_cffi import CurlOpt

        seen: dict[str, list[str | None]] = {}

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_args: object) -> None:
                pass

            def do_GET(self) -> None:  # noqa: N802 - http.server's naming
                host = (self.headers.get("Host") or "").split(":")[0]
                seen.setdefault(host, []).append(self.headers.get("Cookie"))
                self.send_response(200)
                self.end_headers()

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        port = server.server_address[1]
        try:
            writer = make_manager()
            writer._session = _jar_session(_LIVE_SHAPED_JAR)
            await writer._save_to_cache()

            reader = make_manager()
            assert await reader._try_load_from_cache() is True
            assert reader._session is not None
            reader._session.curl_options = {
                CurlOpt.RESOLVE: [
                    f"attacker.example:{port}:127.0.0.1",
                    f"www.set.or.th:{port}:127.0.0.1",
                ]
            }
            # The FIRST request after the restore goes to a foreign host ...
            reader._session.get(f"http://attacker.example:{port}/", timeout=5)
            # ... and the cookies still reach their own host afterwards.
            reader._session.get(f"http://www.set.or.th:{port}/", timeout=5)
        finally:
            server.shutdown()
            server.server_close()

        assert seen["attacker.example"] == [None], "a restored cookie reached a foreign host"
        sent = seen["www.set.or.th"][0] or ""
        assert {"charlot", "visid_incap_2046605", "incap_ses_297_2046605"} <= {
            part.split("=")[0].strip() for part in sent.split(";")
        }
