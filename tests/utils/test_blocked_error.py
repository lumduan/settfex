"""``BlockedError`` — a bot-protection block page is detected once, at the fetcher, and never retried.

Everything here is injected at ``AsyncDataFetcher._make_request``, one layer BELOW ``fetch()``,
because the detector runs inside ``fetch()``: the fault matrix patches ``fetch`` itself and would
skip right past it.

**The block page used here is SYNTHETIC.** It is reconstructed from the one observation, on
market.sec.or.th on 2026-09-20, whose probe normalised newlines before printing — so its whitespace
was never byte-verified and it does not meet the repo's fixture rule. The detector is built to
match: case-insensitive, whitespace-tolerant, and keyed on two pieces of vendor boilerplate rather
than on the page's bytes. The support ID below is invented. When a real block is next observed,
``exc.body`` is the byte-exact capture to commit instead.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest

from settfex.exceptions import FetchError, ParseError
from settfex.services.sec.download import DocumentDownloadService
from settfex.services.thaibma.history import YieldCurveHistoryService
from settfex.services.thaibma.yield_curve import YieldCurveService
from settfex.utils.data_fetcher import AsyncDataFetcher, FetcherConfig
from settfex.utils.parsing import (
    _MAX_BLOCK_PAGE_BYTES,
    BlockedError,
    ResponseParseError,
    looks_like_block_page,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

FAKE_SUPPORT_ID = b"1234567890123456789"

#: SYNTHETIC — see the module docstring. 242 bytes, like the observed page.
BLOCK_PAGE = (
    b"<html><head><title>Request Rejected</title></head><body>The requested URL was rejected. "
    b"Please consult with your administrator.<br><br>Your support ID is: " + FAKE_SUPPORT_ID + b""
    b"<br><br><a href='javascript:history.back();'>[Go Back]</body></html>"
)


def _curl_response(body: bytes, status: int = 200, headers: dict[str, str] | None = None) -> Mock:
    response = Mock()
    response.status_code = status
    response.content = body
    # The observed block page carried NO Content-Type header at all.
    response.headers = headers if headers is not None else {}
    response.url = "https://market.sec.or.th/public/idisc/en/FinancialReport/FS"
    return response


class TestDetectionAtTheFetcher:
    @pytest.mark.asyncio
    async def test_a_block_page_raises_on_the_first_request_and_is_not_retried(self) -> None:
        fetcher = AsyncDataFetcher(FetcherConfig(max_retries=3, use_session=False))
        with (
            patch.object(
                fetcher, "_make_request", return_value=_curl_response(BLOCK_PAGE)
            ) as request,
            pytest.raises(BlockedError) as excinfo,
        ):
            await fetcher.fetch("https://market.sec.or.th/x")
        assert request.call_count == 1, "a block page must never be retried"
        assert "after 4 attempts" not in str(excinfo.value), (
            "it must not be re-wrapped into the generic retries-exhausted FetchError"
        )

    @pytest.mark.asyncio
    async def test_binary_fetches_are_covered(self) -> None:
        """The SEC download path fetches with decode_text=False, so `text` is empty there."""
        fetcher = AsyncDataFetcher(FetcherConfig(use_session=False))
        with (
            patch.object(fetcher, "_make_request", return_value=_curl_response(BLOCK_PAGE)),
            pytest.raises(BlockedError),
        ):
            await fetcher.fetch("https://market.sec.or.th/x", decode_text=False)

    @pytest.mark.parametrize(
        ("name", "body", "status"),
        [
            ("title-only", b"<html><head><title>Request Rejected</title></head></html>", 200),
            ("support-id-only", b"<p>Your support ID is: 42</p>", 200),
            ("over-the-cap", BLOCK_PAGE + b" " * _MAX_BLOCK_PAGE_BYTES, 200),
            ("non-2xx", BLOCK_PAGE, 403),
        ],
    )
    @pytest.mark.asyncio
    async def test_what_is_not_a_block(self, name: str, body: bytes, status: int) -> None:
        """Both markers, a small body, and a 2xx — anything less is returned as it is.

        A non-2xx is left alone on purpose: its status already reports it, and every service
        raises on that status, so relabelling it here would only change the name of an error the
        caller can already see.
        """
        fetcher = AsyncDataFetcher(FetcherConfig(use_session=False))
        with patch.object(fetcher, "_make_request", return_value=_curl_response(body, status)):
            response = await fetcher.fetch("https://market.sec.or.th/x")
        assert response.status_code == status

    def test_matching_tolerates_case_and_whitespace(self) -> None:
        """The observed capture's whitespace was never verified, so the match must not rely on it."""
        variant = BLOCK_PAGE.replace(b"Request Rejected", b"request\n   REJECTED").replace(
            b"Your support ID is:", b"your  support\tid is :"
        )
        assert looks_like_block_page(variant)


class TestWhatTheExceptionCarries:
    @staticmethod
    async def _blocked(headers: dict[str, str] | None = None) -> BlockedError:
        fetcher = AsyncDataFetcher(FetcherConfig(use_session=False))
        response = _curl_response(BLOCK_PAGE, headers=headers)
        with patch.object(fetcher, "_make_request", return_value=response):
            try:
                await fetcher.fetch("https://market.sec.or.th/x")
            except BlockedError as exc:
                return exc
        raise AssertionError("no BlockedError")

    @pytest.mark.asyncio
    async def test_the_facts_of_the_block(self) -> None:
        exc = await self._blocked()
        assert exc.status_code == 200
        assert exc.content_type is None, "the observed page had no Content-Type; record that"
        assert exc.url and "market.sec.or.th" in exc.url

    @pytest.mark.asyncio
    async def test_the_support_id_is_screened_and_the_body_stays_out_of_the_message(self) -> None:
        exc = await self._blocked()
        assert FAKE_SUPPORT_ID not in exc.body, "a per-incident identifier must not be kept"
        assert b"<SCREENED>" in exc.body
        assert b"Request Rejected" in exc.body, "the rest of the page is kept for a fixture"
        assert "Request Rejected" not in str(exc)

    @pytest.mark.asyncio
    async def test_set_cookie_is_not_kept(self) -> None:
        exc = await self._blocked(headers={"Set-Cookie": "TS01=secret", "Server": "BigIP"})
        assert exc.headers == {"Server": "BigIP"}

    @pytest.mark.parametrize(
        "handler",
        [ResponseParseError, ParseError, FetchError, ValueError],
        ids=lambda h: h.__name__,
    )
    @pytest.mark.asyncio
    async def test_every_handler_that_caught_a_block_before_still_does(
        self, handler: type[Exception]
    ) -> None:
        """Additive by the policy's own rule: a strict subclass of what was raised before."""
        fetcher = AsyncDataFetcher(FetcherConfig(use_session=False))
        with (
            patch.object(fetcher, "_make_request", return_value=_curl_response(BLOCK_PAGE)),
            pytest.raises(handler),
        ):
            await fetcher.fetch("https://market.sec.or.th/x")


class TestNoCommittedFixtureLooksLikeABlock:
    def test_no_fixture_file_trips_the_detector(self) -> None:
        """A false positive here would turn a real, captured response into a BlockedError."""
        suffixes = {".html", ".htm", ".json", ".txt", ".xml"}
        scanned = [
            path
            for path in (REPO_ROOT / "tests").rglob("*")
            if path.is_file() and path.suffix.lower() in suffixes
        ]
        assert scanned, "found no fixture files to scan — the glob has stopped matching"
        tripped = [
            str(p.relative_to(REPO_ROOT)) for p in scanned if looks_like_block_page(p.read_bytes())
        ]
        assert not tripped, f"committed fixtures detected as block pages: {tripped}"


class TestBatchesStopAtTheFirstBlock:
    """Every further request to a host that is blocking us deepens the block."""

    @pytest.mark.asyncio
    async def test_download_all_requests_nothing_after_a_block(self, tmp_path: Path) -> None:
        calls = 0

        async def request(self: Any, url: str, *args: Any, **kwargs: Any) -> Mock:
            nonlocal calls
            calls += 1
            return _curl_response(BLOCK_PAGE)

        targets = [
            f"https://market.sec.or.th/public/idisc/Download?FILEID=dat/news/f{i}.zip"
            for i in range(5)
        ]
        with patch.object(AsyncDataFetcher, "_make_request", request):
            result = await DocumentDownloadService().download_all(
                targets, dest_dir=tmp_path, max_concurrency=1
            )

        assert calls == 1, f"{calls} requests were sent to a host that had already blocked us"
        assert result.requested == 5 and not result.is_complete
        assert len(result.failed) == 5
        assert {f.error_type for f in result.failed} == {"BlockedError"}
        assert sum("not requested" in f.error for f in result.failed) == 4
        assert list(tmp_path.iterdir()) == [], "a block page must never be saved as a document"

    @pytest.mark.asyncio
    async def test_a_single_download_raises_instead_of_returning_the_page(self) -> None:
        """Before 0.25.0 the page, having no Content-Type, came back as the file."""
        with (
            patch.object(
                AsyncDataFetcher, "_make_request", return_value=_curl_response(BLOCK_PAGE)
            ),
            pytest.raises(BlockedError),
        ):
            await DocumentDownloadService().download(
                "https://market.sec.or.th/public/idisc/Download?FILEID=dat/news/f.zip"
            )

    @pytest.mark.asyncio
    async def test_fetch_curves_requests_nothing_after_a_block(self) -> None:
        calls = 0

        async def request(self: Any, url: str, *args: Any, **kwargs: Any) -> Mock:
            nonlocal calls
            calls += 1
            return _curl_response(BLOCK_PAGE)

        with patch.object(AsyncDataFetcher, "_make_request", request):
            curves = await YieldCurveService().fetch_curves(
                ["2026-08-06", "2026-08-07", "2026-08-10"], max_concurrency=1
            )
        assert curves == []
        assert calls == 1

    @pytest.mark.asyncio
    async def test_history_records_unrequested_years_as_missing(self) -> None:
        calls = 0

        async def request(self: Any, url: str, *args: Any, **kwargs: Any) -> Mock:
            nonlocal calls
            calls += 1
            return _curl_response(BLOCK_PAGE)

        with patch.object(AsyncDataFetcher, "_make_request", request):
            history = await YieldCurveHistoryService().fetch_history(
                "2020-01-01", "2023-12-31", check_availability=False, max_concurrency=1
            )
        assert calls == 1
        assert history.missing_years == [2020, 2021, 2022, 2023]
