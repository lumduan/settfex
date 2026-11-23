"""ThaiBMA refuses automated access (0.30.1): a clear ``BlockedError``, never a bare "HTTP 403".

Since a change between 2026-11-20 18:05 and 2026-11-23 09:18 ICT, www.thaibma.or.th answers every
automated request (settfex 0.27.0 and 0.30.0 alike, from two networks) with HTTP 403 from
Cloudflare and a bilingual page: "Automated access is not permitted ... please use the ThaiBMA API
service at https://apiportal.thaibma.or.th". It is the data owner's terms. settfex does not work
around it, so the only thing to get right is saying so clearly and stopping.

The page is the real answer, captured once on 2026-11-23 09:25 ICT
(``fixtures_thaibma/automated_access_refused.html``, 2,731 bytes, sha256 f68bce9f…). Injected
at ``AsyncDataFetcher._make_request``, so the fetcher runs as in production.
"""

from __future__ import annotations

import contextlib
import hashlib
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest

from settfex.exceptions import FetchError
from settfex.services.thaibma import get_government_yield_curve, get_yield_curve_history
from settfex.services.thaibma.utils import looks_like_thaibma_refusal
from settfex.services.thaibma.yield_curve import YieldCurveService
from settfex.utils.data_fetcher import AsyncDataFetcher, FetcherConfig
from settfex.utils.parsing import BlockedError, UnexpectedPageError

PAGE = (Path(__file__).parent / "fixtures_thaibma" / "automated_access_refused.html").read_bytes()
NO_RETRY = FetcherConfig(max_retries=0)


def _refusal(url: str = "https://www.thaibma.or.th/yieldcurve/gov") -> Mock:
    response = Mock()
    response.status_code = 403
    response.content = PAGE
    response.headers = {"content-type": "text/html", "server": "cloudflare"}
    response.url = url
    return response


class TestTheDetector:
    def test_the_real_page_is_recognised(self) -> None:
        assert len(PAGE) == 2731
        assert hashlib.sha256(PAGE).hexdigest().startswith("f68bce9f392d31f5"), "byte-exact"
        assert looks_like_thaibma_refusal(PAGE)

    @pytest.mark.parametrize(
        "body",
        [
            b'{"Message":"An error has occurred."}',  # an ASP.NET error body
            b"<html><title>404</title></html>",
            b"<html>cdn-cgi/challenge-platform</html>",  # Cloudflare alone is not the refusal
        ],
        ids=["aspnet-json", "html-404", "cloudflare-only"],
    )
    def test_other_error_bodies_are_not(self, body: bytes) -> None:
        assert not looks_like_thaibma_refusal(body)

    def test_the_thai_sentence_alone_counts(self) -> None:
        thai = "<p>ไม่อนุญาตให้ดึงข้อมูลด้วยโปรแกรมอัตโนมัติ</p>".encode()
        assert looks_like_thaibma_refusal(thai)


class TestTheError:
    @pytest.mark.asyncio
    async def test_the_latest_curve_raises_a_blocked_error_that_says_why(self) -> None:
        with (
            patch.object(AsyncDataFetcher, "_make_request", return_value=_refusal()),
            pytest.raises(BlockedError) as excinfo,
        ):
            await get_government_yield_curve(config=NO_RETRY)
        exc = excinfo.value
        assert exc.status_code == 403
        assert "refuses automated access" in str(exc)
        assert "https://apiportal.thaibma.or.th" in str(exc)
        assert "retrying cannot help" in str(exc)
        for family in (UnexpectedPageError, FetchError):
            assert isinstance(exc, family), "every 0.30.0 `except FetchError` still catches it"
        assert b"Automated access is not permitted" in exc.body

    @pytest.mark.asyncio
    async def test_another_403_is_still_the_plain_fetch_error(self) -> None:
        other = _refusal()
        other.content = b"<html>forbidden</html>"
        with (
            patch.object(AsyncDataFetcher, "_make_request", return_value=other),
            pytest.raises(FetchError) as excinfo,
        ):
            await get_government_yield_curve(config=NO_RETRY)
        assert not isinstance(excinfo.value, BlockedError)


class TestTheBatchesStop:
    @pytest.mark.asyncio
    async def test_history_sends_nothing_after_the_first_refusal(self) -> None:
        calls: list[str] = []

        async def answer(self: Any, url: str, *args: Any, **kwargs: Any) -> Mock:
            calls.append(url)
            return _refusal(url)

        with (
            patch.object(AsyncDataFetcher, "_make_request", answer),
            contextlib.suppress(FetchError),  # a total loss may raise; the count is the point
        ):
            await get_yield_curve_history(
                "2020-01-01",
                "2026-06-30",
                max_concurrency=1,
                check_availability=False,
                config=NO_RETRY,
            )
        assert len(calls) == 1, f"{len(calls)} requests after the site refused the first one"

    @pytest.mark.asyncio
    async def test_fetch_curves_sends_nothing_after_the_first_refusal(self) -> None:
        calls: list[str] = []

        async def answer(self: Any, url: str, *args: Any, **kwargs: Any) -> Mock:
            calls.append(url)
            return _refusal(url)

        dates = ["2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06"]
        with (
            patch.object(AsyncDataFetcher, "_make_request", answer),
            contextlib.suppress(FetchError),
        ):
            await YieldCurveService(config=NO_RETRY).fetch_curves(dates, max_concurrency=1)
        assert len(calls) == 1, f"{len(calls)} requests after the site refused the first one"
