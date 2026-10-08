"""A non-document answer carries the answer (0.26.0) — the evidence case recorded on #135.

A downstream consumer saw four non-document HTML answers in a row and could not tell a WAF block
page (back off for days) from an upstream error page (retry the next night): settfex raised a
message-only ``FetchError`` and discarded the body. The same consumer saw sixty "file does not
exist" answers for files that all existed. Each answer is now a typed ``FetchError`` subclass that
carries the status, the headers, the first 8 KB of the body and the elapsed time.

Injected at ``AsyncDataFetcher._make_request`` — below ``fetch()`` — so the fetcher's own 2xx
block-page detector runs exactly as it does in production. The SEC error page is the real
captured fixture; the block page is SYNTHETIC (no byte-exact capture exists yet — see
``tests/utils/test_blocked_error.py``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest

from settfex.exceptions import (
    FetchError,
    HTTPStatusError,
    ParseError,
    SoftNotFoundError,
    UnexpectedPageError,
)
from settfex.services.sec.constants import SOFT_404_MARKERS, SOFT_404_WINDOW_BYTES
from settfex.services.sec.download import DocumentDownloadService
from settfex.utils.data_fetcher import AsyncDataFetcher, FetcherConfig
from settfex.utils.parsing import BlockedError, ResponseParseError, looks_like_block_page

from .fixtures import FILE_NOT_FOUND_HTML, load_fixture

URL = "https://market.sec.or.th/public/idisc/Download?FILEID=dat/news/202608/F.zip"
FAKE_SUPPORT_ID = b"1234567890123456789"
#: SYNTHETIC block page, reconstructed from the 2026-09-20 observation (support ID invented).
BLOCK_PAGE = (
    b"<html><head><title>Request Rejected</title></head><body>The requested URL was rejected. "
    b"Please consult with your administrator.<br><br>Your support ID is: " + FAKE_SUPPORT_ID + b""
    b"<br><br><a href='javascript:history.back();'>[Go Back]</body></html>"
)
#: The SEC's real HTTP 505 error page (committed fixture), here served as an HTML answer.
SEC_ERROR_PAGE = load_fixture("idisc_505_error_page.html").encode("utf-8")
GENERIC_404 = b"<html><body><h1>404 - File or directory not found.</h1></body></html>"
HTML = {"Content-Type": "text/html; charset=utf-8"}


def _answer(body: bytes, status: int = 200, headers: dict[str, str] | None = None) -> Mock:
    response = Mock()
    response.status_code = status
    response.content = body
    response.headers = dict(HTML if headers is None else headers)
    response.url = URL
    return response


async def _download(response: Mock) -> Any:
    async def answer(self: Any, url: str, *args: Any, **kwargs: Any) -> Mock:
        return response

    with patch.object(AsyncDataFetcher, "_make_request", answer):
        return await DocumentDownloadService().download(URL)


async def _raised(response: Mock) -> Exception:
    try:
        await _download(response)
    except Exception as exc:  # noqa: BLE001 - the test inspects whatever was raised
        return exc
    raise AssertionError("download() returned instead of raising")


class TestEachAnswerHasItsOwnType:
    @pytest.mark.parametrize("status", [200, 403], ids=["200-via-fetcher", "403-via-download"])
    @pytest.mark.asyncio
    async def test_a_block_page_is_blocked_error_under_any_status(self, status: int) -> None:
        """2xx: the fetcher's detector. Non-2xx: the download path, which used to raise a plain
        FetchError("…HTTP 403") and so lost the page."""
        exc = await _raised(_answer(BLOCK_PAGE, status, headers={}))
        assert type(exc) is BlockedError
        assert exc.status_code == status

    @pytest.mark.parametrize(
        ("body", "marker"),
        [(FILE_NOT_FOUND_HTML.encode("utf-8"), "sec-thai"), (GENERIC_404, "generic-not-found")],
        ids=["sec-thai", "generic"],
    )
    @pytest.mark.asyncio
    async def test_a_not_found_page_says_which_rule_matched(self, body: bytes, marker: str) -> None:
        exc = await _raised(_answer(body))
        assert type(exc) is SoftNotFoundError
        assert exc.matched_marker == marker

    @pytest.mark.asyncio
    async def test_any_other_page_is_unexpected_page_error(self) -> None:
        exc = await _raised(_answer(SEC_ERROR_PAGE))
        assert type(exc) is UnexpectedPageError

    @pytest.mark.asyncio
    async def test_an_html_error_status_keeps_its_page(self) -> None:
        exc = await _raised(_answer(SEC_ERROR_PAGE, 503))
        assert type(exc) is UnexpectedPageError
        assert exc.status_code == 503 and exc.body == SEC_ERROR_PAGE

    @pytest.mark.parametrize(
        "headers", [{"Content-Type": "text/plain"}, {}], ids=["text-plain", "no-content-type"]
    )
    @pytest.mark.asyncio
    async def test_a_non_html_error_status_stays_a_plain_fetch_error(
        self, headers: dict[str, str]
    ) -> None:
        exc = await _raised(_answer(b"Service Unavailable", 503, headers=headers))
        assert type(exc) is FetchError
        assert exc.status_code == 503

    @pytest.mark.asyncio
    async def test_an_untyped_html_error_status_is_still_recognised_as_a_page(self) -> None:
        """No Content-Type (the observed block page had none) but the body starts like a page."""
        exc = await _raised(_answer(b"  <!DOCTYPE html><html><body>busy</body></html>", 502, {}))
        assert type(exc) is UnexpectedPageError

    @pytest.mark.asyncio
    async def test_a_document_is_still_a_document_and_reports_its_time(self) -> None:
        downloaded = await _download(
            _answer(b"PK\x03\x04zip", headers={"Content-Type": "application/zip"})
        )
        assert downloaded.content == b"PK\x03\x04zip"
        assert downloaded.elapsed_seconds is not None and downloaded.elapsed_seconds >= 0


class TestNothingThatCaughtThemBeforeStopsCatchingThem:
    """Each class is a strict subclass of what 0.25.0 raised, with the same message."""

    @pytest.mark.parametrize(
        ("response", "message"),
        [
            (_answer(BLOCK_PAGE, 403, headers={}), None),
            (_answer(GENERIC_404), f"SEC reports the file does not exist (soft 404): {URL}"),
            (
                _answer(SEC_ERROR_PAGE),
                f"Unexpected HTML response (not a document) downloading {URL}",
            ),
            (_answer(SEC_ERROR_PAGE, 503), f"Failed to download {URL}: HTTP 503"),
        ],
        ids=["blocked-403", "soft-404", "unexpected-200", "unexpected-503"],
    )
    @pytest.mark.asyncio
    async def test_except_fetch_error_still_catches_and_the_message_is_unchanged(
        self, response: Mock, message: str | None
    ) -> None:
        with pytest.raises(FetchError) as excinfo:
            await _download(response)
        assert isinstance(excinfo.value, UnexpectedPageError)
        if message is not None:
            assert str(excinfo.value) == message

    @pytest.mark.parametrize("handler", [ResponseParseError, ParseError, ValueError, FetchError])
    @pytest.mark.asyncio
    async def test_blocked_error_keeps_every_0_25_family(self, handler: type[Exception]) -> None:
        with pytest.raises(handler):
            await _download(_answer(BLOCK_PAGE, 200, headers={}))

    def test_the_hierarchy(self) -> None:
        assert issubclass(SoftNotFoundError, UnexpectedPageError)
        assert issubclass(BlockedError, UnexpectedPageError)
        assert BlockedError.__mro__[1:3] == (ResponseParseError, ParseError), (
            "UnexpectedPageError must be added AFTER BlockedError's 0.25.0 bases"
        )

    def test_a_soft_404_is_deliberately_not_a_not_found_error(self) -> None:
        """NotFoundError means 'never retry'; sixty false soft-404s say that would be wrong."""
        from settfex.exceptions import NotFoundError

        assert not issubclass(SoftNotFoundError, NotFoundError)


class TestTheEvidence:
    @pytest.mark.asyncio
    async def test_the_body_is_bounded_at_8_kb(self) -> None:
        big = b"<html><body>" + b"x" * 10_000 + b"</body></html>"
        exc = await _raised(_answer(big))
        assert isinstance(exc, UnexpectedPageError)
        assert len(exc.body) == 8192 and exc.body_truncated is True

    @pytest.mark.asyncio
    async def test_a_small_body_is_kept_whole(self) -> None:
        exc = await _raised(_answer(SEC_ERROR_PAGE))
        assert isinstance(exc, UnexpectedPageError)
        assert exc.body == SEC_ERROR_PAGE and exc.body_truncated is False

    @pytest.mark.asyncio
    async def test_the_kept_body_reproduces_the_detectors_verdict(self) -> None:
        exc = await _raised(_answer(BLOCK_PAGE, 403, headers={}))
        assert isinstance(exc, BlockedError)
        assert looks_like_block_page(exc.body)

    @pytest.mark.asyncio
    async def test_credential_headers_never_ride_on_the_exception(self) -> None:
        headers = {
            "Content-Type": "text/html",
            "Set-Cookie": "TS01=secret",
            "cookie": "a=b",
            "Authorization": "Bearer x",
            "Proxy-Authorization": "Basic y",
            "Server": "BigIP",
        }
        exc = await _raised(_answer(SEC_ERROR_PAGE, headers=headers))
        assert isinstance(exc, UnexpectedPageError)
        assert exc.headers == {"Content-Type": "text/html", "Server": "BigIP"}

    @pytest.mark.asyncio
    async def test_the_answer_is_described(self) -> None:
        exc = await _raised(_answer(GENERIC_404))
        assert isinstance(exc, SoftNotFoundError)
        assert (exc.url, exc.final_url, exc.status_code) == (URL, URL, 200)
        assert exc.content_type == "text/html; charset=utf-8"
        assert exc.elapsed_seconds is not None and exc.elapsed_seconds >= 0
        assert "not found" not in str(exc).lower().split("(soft 404)")[1], "body not in message"

    @pytest.mark.asyncio
    async def test_a_support_id_is_screened(self) -> None:
        exc = await _raised(_answer(BLOCK_PAGE, 403, headers={}))
        assert isinstance(exc, BlockedError)
        assert FAKE_SUPPORT_ID not in exc.body and b"<SCREENED>" in exc.body


class TestTheSoft404RuleIsDocumented:
    def test_the_constants_name_both_rules(self) -> None:
        assert set(SOFT_404_MARKERS) == {"sec-thai", "generic-not-found"}
        assert SOFT_404_WINDOW_BYTES == 400

    @pytest.mark.asyncio
    async def test_the_window_is_the_one_applied(self) -> None:
        """'not found' just past the window is not a soft-404 — it is some other page."""
        body = b"<html>" + b" " * SOFT_404_WINDOW_BYTES + b"not found</html>"
        exc = await _raised(_answer(body))
        assert type(exc) is UnexpectedPageError


class TestJsonEndpointsAreUnchanged:
    @pytest.mark.asyncio
    async def test_a_non_2xx_block_page_on_a_json_path_is_still_http_status_error(self) -> None:
        """A non-2xx there must keep raising HTTPStatusError, which BlockedError is not."""
        fetcher = AsyncDataFetcher(FetcherConfig(use_session=False))
        with (
            patch.object(fetcher, "_make_request", return_value=_answer(BLOCK_PAGE, 403, {})),
            pytest.raises(HTTPStatusError) as excinfo,
        ):
            await fetcher.fetch_json("https://www.set.or.th/api/set/x")
        assert not isinstance(excinfo.value, BlockedError)


class TestTheBatchKeepsTheKind:
    @pytest.mark.asyncio
    async def test_failed_downloads_carry_the_type_and_the_status(self, tmp_path: Path) -> None:
        answers = {"a.zip": _answer(GENERIC_404), "b.zip": _answer(SEC_ERROR_PAGE, 503)}

        async def answer(self: Any, url: str, *args: Any, **kwargs: Any) -> Mock:
            return answers[url.rsplit("/", 1)[-1]]

        targets = [
            f"https://market.sec.or.th/public/idisc/Download?FILEID=dat/news/{n}" for n in answers
        ]
        with patch.object(AsyncDataFetcher, "_make_request", answer):
            result = await DocumentDownloadService().download_all(targets, dest_dir=tmp_path)

        kinds = {f.target.rsplit("/", 1)[-1]: (f.error_type, f.status_code) for f in result.failed}
        assert kinds == {"a.zip": ("SoftNotFoundError", 200), "b.zip": ("UnexpectedPageError", 503)}
        assert list(tmp_path.iterdir()) == [], "no page is ever saved as a document"
