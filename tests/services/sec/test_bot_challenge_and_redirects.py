"""SEC refusals and redirects a caller could not tell apart (0.28.0), from a downstream archive's reports.

1. **Akamai Bot Manager's interstitial**: since 2026-11-11 the iDisc listing GET has
   intermittently answered HTTP 200 with a challenge page (every night in a downstream archive's
   probe, not on every request by day). It reached callers as "no __VIEWSTATE token", the
   same words as a site redesign. Now it is ``BotChallengeError``, a ``BlockedError``. It is
   recognised and never solved: the refresh is not followed, the script is not run, the token is
   not sent. The page is the archive's real capture (``idisc_akamai_interstitial.html``, tokens
   redacted by that archive).
2. **An off-host 302 on the old-format download**: ``capital.sec.or.th/tmp/<id>.zip`` sometimes
   answers ``302`` to an Azure fallback host. It was followed, and the other host's 505 was
   reported under capital's name. Now the fetch does not leave the host (``OffHostRedirectError``),
   and download errors name the host that actually answered.

Injected at ``AsyncDataFetcher._make_request``, below ``fetch()``, so the fetcher's own detectors
run exactly as in production.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock, patch

import pytest

from settfex.exceptions import (
    FetchError,
    OffHostRedirectError,
    ParseError,
    UnexpectedPageError,
)
from settfex.services.sec.download import DocumentDownloadService
from settfex.services.sec.financial_report import FinancialReportService
from settfex.utils.data_fetcher import AsyncDataFetcher, FetcherConfig
from settfex.utils.parsing import (
    BlockedError,
    BotChallengeError,
    ResponseParseError,
    looks_like_block_page,
    looks_like_bot_challenge,
)

from .fixtures import load_fixture

CHALLENGE = load_fixture("idisc_akamai_interstitial.html").encode("utf-8")
#: The capture's tokens were redacted by its owner; a realistic one is put back to test screening.
FAKE_TOKEN = b"3.Ab9zQf_k2-LMNOPqrst"
LIVE_SHAPED_CHALLENGE = CHALLENGE.replace(b"REDACTED", FAKE_TOKEN)
LISTING_URL = "https://market.sec.or.th/public/idisc/th/FinancialReport/FS"
DOWNLOAD_URL = "https://market.sec.or.th/public/idisc/Download?FILEID=dat/news/202608/F.zip"
HTML = {"Content-Type": "text/html; charset=utf-8", "Set-Cookie": "ak_bmsc=SECRET; Path=/"}


def _answer(
    body: bytes, status: int = 200, headers: dict[str, str] | None = None, url: str = ""
) -> Mock:
    response = Mock()
    response.status_code = status
    response.content = body
    response.headers = dict(HTML if headers is None else headers)
    response.url = url or DOWNLOAD_URL
    return response


class TestTheDetector:
    def test_the_real_capture_is_a_challenge_and_not_the_f5_block_page(self) -> None:
        assert looks_like_bot_challenge(CHALLENGE)
        assert not looks_like_block_page(CHALLENGE)

    @pytest.mark.parametrize(
        "body",
        [
            b'<a href="/x?bm-verify=abc">a link</a>',  # one marker alone is an ordinary link
            b"<p>POST /_sec/verify is an endpoint</p>",
            b"%PDF-1.7 " + b"x" * 9000 + b"bm-verify /_sec/verify",  # over the cap: never scanned
        ],
        ids=["token-only", "path-only", "over-cap"],
    )
    def test_both_markers_and_a_small_body_are_required(self, body: bytes) -> None:
        assert not looks_like_bot_challenge(body)


class TestTheListingLeg:
    @pytest.mark.asyncio
    async def test_the_listing_get_raises_bot_challenge_not_no_viewstate(self) -> None:
        calls: list[str] = []

        async def answer(self: Any, url: str, *args: Any, **kwargs: Any) -> Mock:
            calls.append(kwargs.get("method", "GET"))
            return _answer(LIVE_SHAPED_CHALLENGE, url=url)

        with patch.object(AsyncDataFetcher, "_make_request", answer):
            async with AsyncDataFetcher(FetcherConfig(use_session=False)) as fetcher:
                with pytest.raises(BotChallengeError) as excinfo:
                    await FinancialReportService()._run_search(
                        fetcher, "FS", "0000000000", "X", "01/01/2026", "31/01/2026", "th"
                    )

        exc = excinfo.value
        assert calls == ["GET"], "recognised on the GET: the form is never posted, nothing retried"
        assert "__VIEWSTATE" not in str(exc), "the diagnosis is the challenge, not a redesign"
        assert exc.status_code == 200
        assert exc.url == LISTING_URL


class TestWhatTheErrorCarries:
    @pytest.mark.asyncio
    async def test_it_is_a_blocked_error_and_everything_older_still_catches_it(self) -> None:
        async def answer(self: Any, url: str, *args: Any, **kwargs: Any) -> Mock:
            return _answer(LIVE_SHAPED_CHALLENGE)

        with (
            patch.object(AsyncDataFetcher, "_make_request", answer),
            pytest.raises(BotChallengeError) as excinfo,
        ):
            await DocumentDownloadService().download(DOWNLOAD_URL)
        exc = excinfo.value
        for family in (BlockedError, UnexpectedPageError, ResponseParseError, ParseError,
                       FetchError, ValueError):  # fmt: skip
            assert isinstance(exc, family), family
        assert FAKE_TOKEN not in exc.body, "the bm-verify token is a session credential"
        assert exc.body.count(b"<SCREENED>") == 2
        assert b"bm-verify=[^#]*" in exc.body, "the page's own JS is left byte-exact"
        assert "Set-Cookie" not in exc.headers, "the ak_bmsc cookie never rides on an exception"

    @pytest.mark.asyncio
    async def test_no_content_type_is_no_longer_accepted_as_a_document(self) -> None:
        """The archive's AD-20 case: F5-style answers carry no Content-Type at all."""

        async def answer(self: Any, url: str, *args: Any, **kwargs: Any) -> Mock:
            return _answer(LIVE_SHAPED_CHALLENGE, headers={})

        with (
            patch.object(AsyncDataFetcher, "_make_request", answer),
            pytest.raises(BotChallengeError),
        ):
            await DocumentDownloadService().download(DOWNLOAD_URL)

    @pytest.mark.asyncio
    async def test_a_non_2xx_challenge_on_a_download_is_recognised_too(self) -> None:
        async def answer(self: Any, url: str, *args: Any, **kwargs: Any) -> Mock:
            return _answer(LIVE_SHAPED_CHALLENGE, status=403)

        with (
            patch.object(AsyncDataFetcher, "_make_request", answer),
            pytest.raises(BotChallengeError) as excinfo,
        ):
            await DocumentDownloadService().download(DOWNLOAD_URL)
        assert excinfo.value.status_code == 403


# ── 2. the old-format download does not leave capital.sec.or.th ──────────────────────────────────

CAPITAL_PAGE = load_fixture("capital_indirection_en.html").encode("utf-8")
CAPITAL_URL = (
    "http://capital.sec.or.th/webapp/corp_fin/cgi-bin/get_zip_all_public_page.php"
    "?report_type=FS&lang=E&comp_id=1517&year=2013&period=12&set_id=1245&fs_type=01"
)
AZURE = "https://secdocumentstorage.z23.web.core.windows.net"
ZIP = b"PK\x03\x04" + b"\x00" * 60


def _capital_router(tmp_answer: Mock, seen: list[tuple[str, bool]]) -> Any:
    async def answer(self: Any, url: str, *args: Any, **kwargs: Any) -> Mock:
        seen.append((url, kwargs.get("follow_redirects", True)))
        if "get_zip_all_public_page.php" in url:
            return _answer(CAPITAL_PAGE, headers={"Content-Type": "text/html"}, url=url)
        if url.startswith(AZURE):
            raise AssertionError("a request was sent to the off-host target")
        return tmp_answer if "/tmp/" in url else _answer(ZIP, headers={}, url=url)

    return answer


class TestNoOffHostRedirect:
    @pytest.mark.asyncio
    async def test_an_off_host_302_raises_before_any_request_leaves_the_host(self) -> None:
        seen: list[tuple[str, bool]] = []
        redirect = _answer(b"", status=302, headers={"Location": AZURE, "Server": "BigIP"})
        with (
            patch.object(AsyncDataFetcher, "_make_request", _capital_router(redirect, seen)),
            pytest.raises(OffHostRedirectError) as excinfo,
        ):
            await DocumentDownloadService().download(CAPITAL_URL)

        exc = excinfo.value
        assert exc.target_host == "secdocumentstorage.z23.web.core.windows.net"
        assert exc.location == AZURE
        assert exc.status_code == 302
        assert "capital.sec.or.th/tmp/" in str(exc) and exc.target_host in str(exc)
        assert isinstance(exc, UnexpectedPageError) and isinstance(exc, FetchError)
        assert seen[-1][1] is False, "the /tmp fetch must not let libcurl follow"
        assert not any(url.startswith(AZURE) for url, _ in seen)

    @pytest.mark.asyncio
    async def test_an_on_host_redirect_is_still_followed(self) -> None:
        seen: list[tuple[str, bool]] = []
        redirect = _answer(b"", status=302, headers={"Location": "/files/1517du.zip"})
        with patch.object(AsyncDataFetcher, "_make_request", _capital_router(redirect, seen)):
            result = await DocumentDownloadService().download(CAPITAL_URL)
        assert result.content == ZIP
        assert seen[-1][0] == "http://capital.sec.or.th/files/1517du.zip"


class TestTheAnsweringHostIsNamed:
    @pytest.mark.asyncio
    async def test_a_followed_redirect_is_named_in_the_error(self) -> None:
        async def answer(self: Any, url: str, *args: Any, **kwargs: Any) -> Mock:
            return _answer(b"<html>gone</html>", status=505, url=AZURE + "/")

        with (
            patch.object(AsyncDataFetcher, "_make_request", answer),
            pytest.raises(FetchError) as excinfo,
        ):
            await DocumentDownloadService().download(DOWNLOAD_URL)
        assert "(answered by secdocumentstorage.z23.web.core.windows.net)" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_the_same_host_keeps_the_old_message_exactly(self) -> None:
        async def answer(self: Any, url: str, *args: Any, **kwargs: Any) -> Mock:
            return _answer(b"<html>error</html>", status=505)

        with (
            patch.object(AsyncDataFetcher, "_make_request", answer),
            pytest.raises(FetchError) as excinfo,
        ):
            await DocumentDownloadService().download(DOWNLOAD_URL)
        assert str(excinfo.value) == f"Failed to download {DOWNLOAD_URL}: HTTP 505"


class TestFollowRedirectsOption:
    @pytest.mark.asyncio
    async def test_it_reaches_curl_cffi_as_allow_redirects(self) -> None:
        fetcher = AsyncDataFetcher(FetcherConfig(use_session=False, max_retries=0))
        with patch("settfex.utils.data_fetcher.requests.get") as get:
            get.return_value = _answer(b"x", status=302, headers={"Location": "/y"})
            await fetcher._make_request("https://x/y", headers={}, follow_redirects=False)
        assert get.call_args.kwargs["allow_redirects"] is False

    @pytest.mark.asyncio
    async def test_a_persistent_session_refuses_it(self) -> None:
        fetcher = AsyncDataFetcher(FetcherConfig(use_session=True))
        with pytest.raises(NotImplementedError):
            await fetcher._make_request("https://x/y", headers={}, follow_redirects=False)
