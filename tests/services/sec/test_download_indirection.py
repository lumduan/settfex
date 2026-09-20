"""The old-format download shape is an indirection, not a file — issue #133.

`capital.sec.or.th/…/get_zip_all_public_page.php` carries PTT's 2011/2013 filings. Recognising the
URL (see `TestOtherDownloadShapes`) is necessary but not sufficient: the URL answers **HTTP 200 with
a 2 KB HTML page whose entire body is a JavaScript redirect** to a server-minted zip. Downloading it
without following that redirect would hand the caller the 2 KB page as if it were the document.

Three properties of the target constrain the code, and each has a test here:

1. **It is minted per request.** The same filing yielded `/tmp/0653XP.zip`, `/tmp/0653sD.zip` and
   `/tmp/0653V1.zip` across three captures, so it is resolved at download time and never stored on
   the listing.
2. **It is per-language.** The Thai request yields a different archive for the same filing.
3. **The container bytes are not an identity.** Re-minting the same filing produced a different
   container sha256 while every member payload stayed byte-identical — 12 bytes of 334,498 differ,
   the Info-ZIP pack timestamp (the reporter's U-14e verdict, **MEMBER-STABLE**). That is a
   documentation obligation rather than a code one, and it is stated in the service docs.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from settfex.exceptions import FetchError, ParseError
from settfex.services.sec.download import (
    DocumentDownloadService,
    _capital_redirect_target,
)
from settfex.services.sec.financial_report import DocumentCategory, SecDocument
from settfex.utils.data_fetcher import FetchResponse

from .fixtures import load_fixture

CAPFIN = (
    "http://capital.sec.or.th/webapp/corp_fin/cgi-bin/get_zip_all_public_page.php"
    "?report_type=FS&lang=E&comp_id=0653&year=2013&period=12&set_id=0646&fs_type=03"
)
MINTED = "http://capital.sec.or.th/tmp/0653XP.zip"
ZIP_BYTES = b"PK\x03\x04\x14\x00\x00\x08" + b"\x00" * 64


def _resp(content: bytes, ctype: str, status: int = 200, url: str = CAPFIN) -> FetchResponse:
    return FetchResponse(
        status_code=status,
        content=content,
        text="",
        headers={"Content-Type": ctype},
        url=url,
        elapsed=0.01,
    )


def _indirection() -> bytes:
    """The real captured page, as bytes — it is TIS-620, not UTF-8."""
    return load_fixture("capital_indirection_en.html").encode("utf-8")


def _document(url: str = CAPFIN) -> SecDocument:
    return SecDocument(
        company_name="PTT PUBLIC COMPANY LIMITED",
        unique_id="uid",
        category=DocumentCategory.FINANCIAL_STATEMENT,
        section="Financial Statements",
        year=2013,
        file_url=url,
        file_id="capfin:0653-2013-12-E",
    )


class TestRedirectParsing:
    """Strict, and strict in two parts so the host check is not dead code."""

    def test_the_real_page_resolves(self) -> None:
        assert _capital_redirect_target(_indirection(), CAPFIN) == MINTED

    def test_a_body_with_no_redirect_raises(self) -> None:
        """Never return the HTML page as if it were the document."""
        with pytest.raises(ParseError):
            _capital_redirect_target(b"<html><body>nothing here</body></html>", CAPFIN)

    def test_an_off_host_target_is_refused(self) -> None:
        """Live, not decorative: the pattern accepts absolute URLs so this branch can fire."""
        body = b"<script>document.location = 'http://evil.test/tmp/x.zip';</script>"
        with pytest.raises(FetchError) as excinfo:
            _capital_redirect_target(body, CAPFIN)
        assert "off-host" in str(excinfo.value)

    def test_a_same_host_absolute_target_is_followed(self) -> None:
        body = b"<script>document.location = 'http://capital.sec.or.th/tmp/ok.zip';</script>"
        assert _capital_redirect_target(body, CAPFIN) == "http://capital.sec.or.th/tmp/ok.zip"

    def test_a_non_zip_target_raises(self) -> None:
        with pytest.raises(ParseError):
            _capital_redirect_target(b"<script>document.location='/tmp/x.exe';</script>", CAPFIN)


class TestDownloadFollowsTheIndirection:
    @staticmethod
    def _patch(responses: list[FetchResponse]):
        cls = patch("settfex.services.sec.download.AsyncDataFetcher").start()
        instance = AsyncMock()
        instance.fetch = AsyncMock(side_effect=responses)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)
        cls.return_value = instance
        return cls, instance

    @pytest.mark.asyncio
    async def test_it_costs_one_extra_request_and_returns_the_zip(self) -> None:
        cls, instance = self._patch(
            [
                _resp(_indirection(), "text/html; charset=TIS-620"),
                _resp(ZIP_BYTES, "application/zip", url=MINTED),
            ]
        )
        try:
            dl = await DocumentDownloadService().download(_document())
        finally:
            patch.stopall()

        assert dl.content == ZIP_BYTES
        assert dl.content_type == "application/zip"
        assert instance.fetch.await_count == 2, "the indirection costs exactly one extra request"
        assert instance.fetch.await_args_list[1].args[0] == MINTED

    @pytest.mark.asyncio
    async def test_the_html_page_is_never_returned_as_the_document(self) -> None:
        """Without the resolver this would have hit the "Unexpected HTML response" guard.

        That guard was already correct — it refused the page — but it refused it as an *error*,
        so the filing stayed unreachable rather than being fetched.
        """
        self._patch([_resp(b"<html><body>no script here</body></html>", "text/html")])
        try:
            with pytest.raises(ParseError):
                await DocumentDownloadService().download(_document())
        finally:
            patch.stopall()

    @pytest.mark.asyncio
    async def test_a_failing_mint_surfaces_as_a_fetch_error(self) -> None:
        self._patch(
            [
                _resp(_indirection(), "text/html; charset=TIS-620"),
                _resp(b"", "text/html", status=500, url=MINTED),
            ]
        )
        try:
            with pytest.raises(FetchError) as excinfo:
                await DocumentDownloadService().download(_document())
        finally:
            patch.stopall()
        assert excinfo.value.status_code == 500

    @pytest.mark.asyncio
    async def test_other_hosts_are_untouched(self) -> None:
        """The resolver must fire for this one shape and nothing else."""
        idisc = "https://market.sec.or.th/public/idisc/Download?FILEID=dat/news/x.zip"
        _, instance = self._patch([_resp(ZIP_BYTES, "application/zip", url=idisc)])
        try:
            dl = await DocumentDownloadService().download(idisc)
        finally:
            patch.stopall()
        assert dl.size == len(ZIP_BYTES)
        assert instance.fetch.await_count == 1, "no extra request for the ordinary shapes"

    @pytest.mark.asyncio
    async def test_the_minted_target_is_not_written_back_to_the_document(self) -> None:
        """It is single-use. Caching it on the listing would hand out a stale URL."""
        document = _document()
        self._patch(
            [
                _resp(_indirection(), "text/html; charset=TIS-620"),
                _resp(ZIP_BYTES, "application/zip", url=MINTED),
            ]
        )
        try:
            dl = await DocumentDownloadService().download(document)
        finally:
            patch.stopall()
        assert document.file_url == CAPFIN, "the document keeps the stable indirection URL"
        assert dl.document is document
