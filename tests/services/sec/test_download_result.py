"""Regression tests for issue #128 P5 — `download_all` dropped its failures from the return value.

`continue_on_error` defaults to True, and a failed item used to become `None` and be filtered out.
The result was that a partial batch was shaped exactly like a complete one: "I downloaded the
filings" and "I downloaded some of the filings" returned the same thing, and the difference existed
only as a log line. `download_all` now returns a :class:`DownloadResult` — still a list of the
successes, so nothing that iterated it has to change, and now also carrying `.failed`.

The realistic failure here is the one the SEC host actually serves: a dead FILEID answered with an
HTML "file not found" page under **HTTP 200** (a soft 404), which is why `DownloadedFile` is not
simply whatever came back.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from settfex.exceptions import FetchError
from settfex.services.sec.download import (
    DocumentDownloadService,
    DownloadedFile,
    DownloadResult,
    FailedDownload,
    download_sec_documents,
)
from settfex.services.sec.financial_report import DocumentCategory, SecDocument

from .fixtures import FILE_NOT_FOUND_HTML
from .test_download import ZIP_BYTES, _dl_resp, _doc

GOOD = "https://market.sec.or.th/public/idisc/Download?FILEID=dat/news/ok.zip"
DEAD = "https://market.sec.or.th/public/idisc/Download?FILEID=dat/annual/gone.zip"


def _router(url, headers=None, *, method="GET", json_body=None, data=None, decode_text=True):
    """The real mix: one live document, one soft-404 (HTML body under HTTP 200)."""
    if "gone.zip" in url:
        return _dl_resp(FILE_NOT_FOUND_HTML.encode("utf-8"), "text/html; charset=utf-8")
    return _dl_resp(ZIP_BYTES, "application/zip", "ok.zip")


@pytest.fixture
def patched_downloads():
    from unittest.mock import AsyncMock

    with patch("settfex.services.sec.download.AsyncDataFetcher") as cls:
        instance = AsyncMock()
        instance.fetch = AsyncMock(side_effect=_router)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)
        cls.return_value = instance
        yield instance


class TestFailuresReachTheCaller:
    @pytest.mark.asyncio
    async def test_a_partial_batch_is_no_longer_shaped_like_a_complete_one(
        self, patched_downloads
    ) -> None:
        result = await DocumentDownloadService().download_all([_doc(GOOD, "ok.zip"), DEAD])
        assert len(result) == 1
        assert result.requested == 2
        assert not result.is_complete
        assert [f.target for f in result.failed] == [DEAD]

    @pytest.mark.asyncio
    async def test_the_reason_survives_not_just_the_fact(self, patched_downloads) -> None:
        """A caller has to be able to tell a dead link from a timeout without re-running it."""
        result = await DocumentDownloadService().download_all([DEAD])
        failure = result.failed[0]
        assert failure.error_type == "FetchError"
        assert "soft 404" in failure.error

    @pytest.mark.asyncio
    async def test_the_source_document_rides_along(self, patched_downloads) -> None:
        """So a retry or a report can name the filing, not just a URL."""
        document = SecDocument(
            company_name="PTT",
            unique_id="uid",
            category=DocumentCategory.FORM_56_2,
            section="Form 56-2 : Annual Reports",
            year=2025,
            file_url=DEAD,
            file_id="dat/annual/gone.zip",
        )
        result = await DocumentDownloadService().download_all([document])
        assert result.failed[0].document is document
        assert result.failed[0].document.year == 2025

    @pytest.mark.asyncio
    async def test_a_complete_batch_says_so(self, patched_downloads) -> None:
        result = await DocumentDownloadService().download_all([_doc(GOOD, "ok.zip")])
        assert result.is_complete
        assert result.failed == []
        assert result.requested == 1

    @pytest.mark.asyncio
    async def test_the_convenience_function_returns_it_too(self, patched_downloads) -> None:
        """The `get_*`-tier entry point is the one an agent calls; it must not lose the failures."""
        result = await download_sec_documents([_doc(GOOD, "ok.zip"), DEAD])
        assert isinstance(result, DownloadResult)
        assert len(result.failed) == 1


class TestBackwardCompatibility:
    """It is a list, and everything that treated it as one must keep working."""

    @pytest.mark.asyncio
    async def test_it_is_a_list(self, patched_downloads) -> None:
        result = await DocumentDownloadService().download_all([_doc(GOOD, "ok.zip"), DEAD])
        assert isinstance(result, list)
        assert isinstance(result[0], DownloadedFile)
        assert [f.filename for f in result] == ["ok.zip"]
        assert len(list(result)) == 1
        assert result[:1] == [result[0]]

    @pytest.mark.asyncio
    async def test_continue_on_error_false_still_propagates(self, patched_downloads) -> None:
        """The default stays True; the strict mode is unchanged."""
        with pytest.raises(FetchError):
            await DocumentDownloadService().download_all([DEAD], continue_on_error=False)

    @pytest.mark.asyncio
    async def test_duplicate_targets_are_still_collapsed_before_counting(
        self, patched_downloads
    ) -> None:
        """`requested` counts unique files — a statement's Company and Consolidated rows share a zip."""
        result = await DocumentDownloadService().download_all(
            [_doc(GOOD, "ok.zip"), _doc(GOOD, "ok.zip"), DEAD]
        )
        assert result.requested == 2
        assert len(result) == 1

    def test_an_empty_result_is_complete(self) -> None:
        assert DownloadResult().is_complete
        assert DownloadResult().requested == 0

    def test_requested_defaults_to_what_it_holds(self) -> None:
        failed = [FailedDownload(target=DEAD, error="boom", error_type="FetchError")]
        assert DownloadResult([], failed=failed).requested == 1
