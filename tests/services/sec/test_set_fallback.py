"""SET's copy as the fallback for an SEC download, and cookie NAMES on page errors (0.29.0).

1. **The SET fallback.** SET's ``weblink.set.or.th`` serves the same files at the same path as
   SEC's ``Download?FILEID=<path>``. They were byte-identical in every live comparison made on
   2026-11-19/20 (``dat/news/`` statements and an MD&A pdf, a ``dat/f56/`` One Report). On
   2026-11-19 at 21:44 ICT SEC answered a known-good file with its "file not found" page; SET's
   copy, fetched at 22:07, was the same bytes SEC had served at 20:00. So when SEC's answer fails,
   a download now fetches SET's copy once, and says so (``source``, ``fallback_reason``).
2. **Cookie names.** The cookie NAME (F5's ``TS01…`` against Akamai's ``ak_bmsc``) was what told
   the hosts' layers apart, and settfex dropped ``Set-Cookie`` entirely. Page errors now carry
   ``set_cookie_names``; the values are credentials and are still never kept.

Injected at ``AsyncDataFetcher._make_request``, so the fetcher's own detectors run as in
production.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest

from settfex.exceptions import FetchError, SoftNotFoundError, UnexpectedPageError
from settfex.services.sec import SecCompany
from settfex.services.sec.download import (
    DocumentDownloadService,
    _set_weblink_url,
    download_sec_document,
)
from settfex.utils.data_fetcher import AsyncDataFetcher, FetcherConfig
from settfex.utils.parsing import BlockedError, BotChallengeError, set_cookie_names

from .fixtures import load_fixture

SEC = "https://market.sec.or.th/public/idisc/Download?FILEID="
SET = "https://weblink.set.or.th/"
STATEMENT = "dat/news/202608/0646FIN130820261551150876T.zip"
ZIP = b"PK\x03\x04" + b"\x00" * 120
#: The shape of SEC's 118-byte answer on 2026-11-19 21:44 (its "file not found" page).
NOT_FOUND = (
    "<html><body>ไม่พบไฟล์ที่ระบุ <a href='javascript:history.back()'>ย้อนกลับ</a></body></html>".encode()
)
CHALLENGE = load_fixture("idisc_akamai_interstitial.html").encode("utf-8")
#: Two Set-Cookie headers as curl_cffi's dict() joins them: an Expires date contains ", " too.
JOINED_COOKIES = (
    "TS01a5e5b3=SECRET1; Path=/; Expires=Thu, 20 Nov 2026 10:00:00 GMT, "
    "ak_bmsc=SECRET2; Domain=.sec.or.th; Path=/; HttpOnly"
)
NO_RETRY = FetcherConfig(max_retries=0, use_session=False)


def _answer(body: bytes, status: int = 200, ctype: str = "", url: str = "", **extra: str) -> Mock:
    response = Mock()
    response.status_code = status
    response.content = body
    response.headers = {"content-type": ctype, **extra} if ctype else dict(extra)
    response.url = url
    return response


def _router(sec: Mock | Exception, set_: Mock | Exception, seen: list[tuple[str, Any]]) -> Any:
    async def answer(self: Any, url: str, *args: Any, **kwargs: Any) -> Mock:
        headers = args[0] if args else kwargs.get("headers") or {}
        seen.append((url, headers.get("Referer")))
        chosen = set_ if url.startswith(SET) else sec
        if isinstance(chosen, Exception):
            raise chosen
        chosen.url = url
        return chosen

    return answer


class TestWhichFilesHaveASetCopy:
    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            (SEC + STATEMENT, SET + STATEMENT),
            (SEC + "dat/f56/0646ONE120320262211000257T.zip", SET + "dat/f56/0646ONE120320262211000257T.zip"),
            (SEC + "dat%2Fnews%2F202611%2Fx.zip", SET + "dat/news/202611/x.zip"),
            ("https://market.sec.or.th/public/idisc/download?fileid=dat/news/a.pdf", SET + "dat/news/a.pdf"),
        ],
        ids=["statement", "one-report", "url-encoded", "case-insensitive"],
    )  # fmt: skip
    def test_verified_prefixes_map_to_the_same_path_on_set(self, url: str, expected: str) -> None:
        assert _set_weblink_url(url) == expected

    @pytest.mark.parametrize(
        "url",
        [
            SEC + "dat/annual/0646ONE120320262211000257T.zip",  # unverified on SET
            SEC + "dat/news/../../etc/passwd",
            "https://market.sec.or.th/ipos/Common/IPOSGetFile.aspx?id=123",
            "https://market.sec.or.th/public/idisc/Views/FinancialStatementDownload?query=abc",
            "https://market.sec.or.th/public/idisc/views/viewdoc?TransId=1&FileSeq=1",
            "http://capital.sec.or.th/webapp/corp_fin/cgi-bin/get_zip_all_public_page.php?x=1",
            "https://example.com/public/idisc/Download?FILEID=" + STATEMENT,
            SEC,
        ],
        ids=["annual", "traversal", "ipos", "fsdl", "viewdoc", "capital", "other-host", "empty"],
    )
    def test_everything_else_has_none(self, url: str) -> None:
        assert _set_weblink_url(url) is None


class TestTheFallback:
    @pytest.mark.asyncio
    async def test_a_sec_not_found_is_answered_from_set_and_says_so(self) -> None:
        seen: list[tuple[str, Any]] = []
        sec = _answer(NOT_FOUND, ctype="text/html; charset=utf-8", **{"set-cookie": JOINED_COOKIES})
        set_ = _answer(ZIP, ctype="application/zip")
        with patch.object(AsyncDataFetcher, "_make_request", _router(sec, set_, seen)):
            dl = await DocumentDownloadService(NO_RETRY).download(SEC + STATEMENT)

        assert dl.content == ZIP
        assert dl.source == "set_weblink"
        assert dl.file_url == SET + STATEMENT, "file_url is where the bytes came from"
        assert dl.requested_url == SEC + STATEMENT
        assert dl.fallback_reason is not None
        assert dl.fallback_reason.startswith("SoftNotFoundError: ")
        assert [u for u, _ in seen] == [SEC + STATEMENT, SET + STATEMENT], "SEC once, SET once"
        assert seen[1][1] == "https://www.set.or.th/", "SET is asked with SET's own referer"

    @pytest.mark.asyncio
    async def test_a_file_sec_serves_says_sec(self) -> None:
        seen: list[tuple[str, Any]] = []
        with patch.object(
            AsyncDataFetcher,
            "_make_request",
            _router(_answer(ZIP, ctype="application/zip"), AssertionError("SET asked"), seen),
        ):
            dl = await DocumentDownloadService(NO_RETRY).download(SEC + STATEMENT)
        assert (dl.source, dl.fallback_reason) == ("sec", None)
        assert dl.requested_url == dl.file_url == SEC + STATEMENT
        assert len(seen) == 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("sec", "reason"),
        [
            (_answer(CHALLENGE, ctype="text/html"), "BotChallengeError"),
            (_answer(b"<html>busy</html>", status=503, ctype="text/html"), "UnexpectedPageError"),
            (_answer(b"", status=505), "FetchError"),
            (ConnectionError("reset by peer"), "FetchError"),
        ],
        ids=["challenge", "error-page", "bare-5xx", "transport"],
    )
    async def test_any_sec_failure_falls_back(self, sec: Mock | Exception, reason: str) -> None:
        seen: list[tuple[str, Any]] = []
        set_ = _answer(ZIP, ctype="application/zip")
        with patch.object(AsyncDataFetcher, "_make_request", _router(sec, set_, seen)):
            dl = await DocumentDownloadService(NO_RETRY).download(SEC + STATEMENT)
        assert dl.source == "set_weblink"
        assert dl.fallback_reason is not None and dl.fallback_reason.startswith(f"{reason}: ")

    @pytest.mark.asyncio
    async def test_when_set_has_no_file_either_secs_error_is_raised_with_the_set_answer(
        self,
    ) -> None:
        seen: list[tuple[str, Any]] = []
        sec = _answer(NOT_FOUND, ctype="text/html; charset=utf-8")
        set_ = _answer(b"", status=404)
        with (
            patch.object(AsyncDataFetcher, "_make_request", _router(sec, set_, seen)),
            pytest.raises(SoftNotFoundError) as excinfo,
        ):
            await DocumentDownloadService(NO_RETRY).download(SEC + STATEMENT)
        notes = " ".join(getattr(excinfo.value, "__notes__", []))
        assert SET + STATEMENT in notes
        assert "HTTP 404: SET has no file at this path either" in notes
        assert excinfo.value.url == SEC + STATEMENT, "the raised error is SEC's"

    @pytest.mark.asyncio
    async def test_a_page_from_set_is_never_returned_as_the_file(self) -> None:
        sec = _answer(NOT_FOUND, ctype="text/html; charset=utf-8")
        set_ = _answer(b"<html>Incapsula incident</html>", ctype="text/html")
        with (
            patch.object(AsyncDataFetcher, "_make_request", _router(sec, set_, [])),
            pytest.raises(SoftNotFoundError) as excinfo,
        ):
            await DocumentDownloadService(NO_RETRY).download(SEC + STATEMENT)
        assert "UnexpectedPageError" in " ".join(excinfo.value.__notes__)

    @pytest.mark.asyncio
    async def test_set_fallback_false_asks_sec_only(self) -> None:
        seen: list[tuple[str, Any]] = []
        sec = _answer(NOT_FOUND, ctype="text/html; charset=utf-8")
        with (
            patch.object(
                AsyncDataFetcher, "_make_request", _router(sec, AssertionError("SET"), seen)
            ),
            pytest.raises(SoftNotFoundError),
        ):
            await download_sec_document(SEC + STATEMENT, config=NO_RETRY, set_fallback=False)
        assert len(seen) == 1

    @pytest.mark.asyncio
    async def test_a_path_set_does_not_carry_asks_sec_only(self) -> None:
        seen: list[tuple[str, Any]] = []
        sec = _answer(NOT_FOUND, ctype="text/html; charset=utf-8")
        with (
            patch.object(
                AsyncDataFetcher, "_make_request", _router(sec, AssertionError("SET"), seen)
            ),
            pytest.raises(SoftNotFoundError),
        ):
            await DocumentDownloadService(NO_RETRY).download(SEC + "dat/annual/x.zip")
        assert len(seen) == 1


class TestTheBatch:
    @pytest.mark.asyncio
    async def test_after_sec_blocks_the_batch_asks_only_set(self, tmp_path: Path) -> None:
        sec_calls: list[str] = []
        set_calls: list[str] = []

        async def answer(self: Any, url: str, *args: Any, **kwargs: Any) -> Mock:
            if url.startswith(SET):
                set_calls.append(url)
                return _answer(ZIP, ctype="application/zip", url=url)
            sec_calls.append(url)
            return _answer(CHALLENGE, ctype="text/html", url=url)

        targets = [f"{SEC}dat/news/202611/f{i}.zip" for i in range(4)] + [f"{SEC}dat/annual/a.zip"]
        with patch.object(AsyncDataFetcher, "_make_request", answer):
            result = await DocumentDownloadService(NO_RETRY).download_all(
                targets, dest_dir=tmp_path, max_concurrency=1
            )

        assert len(sec_calls) == 1, "nothing more goes to SEC after its first block"
        assert len(set_calls) == 4
        assert len(result) == 4 and all(f.source == "set_weblink" for f in result)
        assert all(f.fallback_reason for f in result)
        [failed] = result.failed
        assert failed.target.endswith("dat/annual/a.zip"), "no SET copy: recorded, not requested"
        assert "not requested" in failed.error and failed.error_type == "BotChallengeError"
        assert sorted(p.name for p in tmp_path.iterdir()) == [f"f{i}.zip" for i in range(4)]

    @pytest.mark.asyncio
    async def test_set_fallback_false_keeps_the_0_28_batch(self) -> None:
        calls: list[str] = []

        async def answer(self: Any, url: str, *args: Any, **kwargs: Any) -> Mock:
            calls.append(url)
            return _answer(CHALLENGE, ctype="text/html", url=url)

        targets = [f"{SEC}dat/news/202611/f{i}.zip" for i in range(3)]
        with patch.object(AsyncDataFetcher, "_make_request", answer):
            result = await DocumentDownloadService(NO_RETRY, set_fallback=False).download_all(
                targets, max_concurrency=1
            )
        assert len(calls) == 1 and len(result.failed) == 3 and len(result) == 0


class TestCookieNames:
    @pytest.mark.parametrize(
        ("headers", "names"),
        [
            ({"set-cookie": JOINED_COOKIES}, ["TS01a5e5b3", "ak_bmsc"]),
            ({"Set-Cookie": "ak_bmsc=SECRET; Path=/"}, ["ak_bmsc"]),
            ({"set-cookie": "a=1; Expires=Wed, 21-Oct-2015 07:28:00 GMT, b=2, a=3"}, ["a", "b"]),
            ({"content-type": "text/html"}, []),
        ],
        ids=["joined-with-expires", "single", "repeat-and-old-date", "none"],
    )
    def test_names_in_order_without_repeats(
        self, headers: dict[str, str], names: list[str]
    ) -> None:
        assert set_cookie_names(headers) == names

    @pytest.mark.asyncio
    async def test_a_page_error_carries_the_names_and_never_a_value(self) -> None:
        sec = _answer(NOT_FOUND, ctype="text/html; charset=utf-8", **{"set-cookie": JOINED_COOKIES})
        with (
            patch.object(AsyncDataFetcher, "_make_request", _router(sec, AssertionError(), [])),
            pytest.raises(SoftNotFoundError) as excinfo,
        ):
            await DocumentDownloadService(NO_RETRY, set_fallback=False).download(SEC + STATEMENT)
        exc = excinfo.value
        assert exc.set_cookie_names == ["TS01a5e5b3", "ak_bmsc"]
        rendered = f"{exc} {exc!r} {exc.headers} {exc.body!r} {exc.set_cookie_names}"
        assert "SECRET" not in rendered, "a cookie value must never ride on an exception"
        assert "set-cookie" not in {k.lower() for k in exc.headers}

    @pytest.mark.asyncio
    async def test_the_fetchers_block_errors_carry_them_too(self) -> None:
        response = _answer(CHALLENGE, ctype="text/html", **{"set-cookie": "ak_bmsc=SECRET; Path=/"})
        response.url = SEC + STATEMENT
        with (
            patch.object(AsyncDataFetcher, "_make_request", return_value=response),
            pytest.raises(BotChallengeError) as excinfo,
        ):
            async with AsyncDataFetcher(NO_RETRY) as fetcher:
                await fetcher.fetch(SEC + STATEMENT)
        assert excinfo.value.set_cookie_names == ["ak_bmsc"]
        assert isinstance(excinfo.value, BlockedError)

    def test_a_bare_error_has_an_empty_list(self) -> None:
        for exc in (UnexpectedPageError("x"), BlockedError("x"), SoftNotFoundError("x")):
            assert exc.set_cookie_names == []
        assert isinstance(SoftNotFoundError("x"), FetchError)


class TestTheFacadeHonoursTheSwitch:
    """0.29.0 shipped `set_fallback` on the service and both functions, but not on `SecCompany`,
    so `SecCompany.download*` always fell back with no way to turn it off (fixed in 0.29.1)."""

    def test_default_is_on_and_false_reaches_the_service(self) -> None:
        assert SecCompany("CPALL").download_service.set_fallback is True
        assert SecCompany("CPALL", set_fallback=False).download_service.set_fallback is False

    @pytest.mark.asyncio
    async def test_facade_download_with_false_asks_sec_only(self) -> None:
        seen: list[tuple[str, Any]] = []
        sec = _answer(NOT_FOUND, ctype="text/html; charset=utf-8")
        facade = SecCompany("CPALL", config=NO_RETRY, set_fallback=False)
        with (
            patch.object(
                AsyncDataFetcher, "_make_request", _router(sec, AssertionError("SET"), seen)
            ),
            pytest.raises(SoftNotFoundError),
        ):
            await facade.download(SEC + STATEMENT)
        assert len(seen) == 1
