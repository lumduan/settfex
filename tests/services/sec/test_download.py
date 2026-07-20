"""Tests for the SEC document download service (mocked bytes; soft-404 handling)."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from settfex.exceptions import FetchError
from settfex.services.sec.download import (
    DocumentDownloadService,
    DownloadedFile,
    _filename_from_disposition,
)
from settfex.services.sec.financial_report import DocumentCategory, SecDocument
from settfex.utils.data_fetcher import FetchResponse
from tests.services.sec.fixtures import FILE_NOT_FOUND_HTML

ZIP_BYTES = b"PK\x03\x04\x14\x00\x00\x08" + b"\x00" * 32


def _dl_resp(content: bytes, ctype: str, disposition: str | None = None, status: int = 200):
    headers = {"Content-Type": ctype}
    if disposition is not None:
        headers["Content-Disposition"] = disposition
    return FetchResponse(
        status_code=status, content=content, text="", headers=headers,
        url="https://market.sec.or.th/public/idisc/Download?FILEID=dat/news/x.zip", elapsed=0.01,
    )


def _doc(file_url: str, file_id: str) -> SecDocument:
    return SecDocument(
        company_name="CP ALL", unique_id="0000003875",
        category=DocumentCategory.FINANCIAL_STATEMENT, section="Financial Statements",
        file_url=file_url, file_id=file_id, file_kind="zip",
    )


def _patch_download(router):
    cls = patch("settfex.services.sec.download.AsyncDataFetcher").start()
    instance = AsyncMock()
    instance.fetch = AsyncMock(side_effect=router)
    instance.__aenter__ = AsyncMock(return_value=instance)
    instance.__aexit__ = AsyncMock(return_value=None)
    cls.return_value = instance
    return cls, instance


class TestFilenameFromDisposition:
    def test_bare_idisc_filename(self) -> None:
        assert _filename_from_disposition("0737FIN.zip", "fallback") == "0737FIN.zip"

    def test_attachment_filename(self) -> None:
        assert _filename_from_disposition("Attachment; Filename=ALL_1_V10.zip", "fb") == (
            "ALL_1_V10.zip"
        )

    def test_fallback_when_absent(self) -> None:
        assert _filename_from_disposition("", "fallback.zip") == "fallback.zip"


class TestDownloadedFileSave:
    def test_save_to_directory(self, tmp_path: Path) -> None:
        f = DownloadedFile(filename="a.zip", content=b"xyz", size=3, file_url="u")
        out = f.save(tmp_path)
        assert out == tmp_path / "a.zip"
        assert out.read_bytes() == b"xyz"

    def test_save_to_explicit_path(self, tmp_path: Path) -> None:
        f = DownloadedFile(filename="a.zip", content=b"xyz", size=3, file_url="u")
        target = tmp_path / "nested" / "custom.zip"
        out = f.save(target)
        assert out == target and out.exists()


class TestResolveUrl:
    def test_secdocument(self) -> None:
        doc = _doc("https://market.sec.or.th/dl", "dat/x.zip")
        assert DocumentDownloadService._resolve_url(doc) == (doc.file_url, doc)

    def test_http_string(self) -> None:
        url, doc = DocumentDownloadService._resolve_url("https://x/y.zip")
        assert url == "https://x/y.zip" and doc is None

    def test_bare_fileid(self) -> None:
        url, doc = DocumentDownloadService._resolve_url("dat/news/x.zip")
        assert url.endswith("Download?FILEID=dat/news/x.zip") and doc is None


class TestDownload:
    @pytest.mark.asyncio
    async def test_success_returns_bytes_and_filename(self) -> None:
        async def router(url, headers=None, *, method="GET", json_body=None, data=None,
                         decode_text=True):
            return _dl_resp(ZIP_BYTES, "application/zip", "myfile.zip")

        _patch_download(router)
        try:
            svc = DocumentDownloadService()
            dl = await svc.download("dat/news/x.zip")
        finally:
            patch.stopall()
        assert dl.filename == "myfile.zip"
        assert dl.content == ZIP_BYTES and dl.size == len(ZIP_BYTES)
        assert dl.content_type.startswith("application/zip")

    @pytest.mark.asyncio
    async def test_soft_404_raises(self) -> None:
        async def router(url, headers=None, *, method="GET", json_body=None, data=None,
                         decode_text=True):
            return _dl_resp(FILE_NOT_FOUND_HTML.encode("utf-8"), "text/html; charset=utf-8")

        _patch_download(router)
        try:
            svc = DocumentDownloadService()
            with pytest.raises(FetchError, match="soft 404"):
                await svc.download("dat/annual/dead.zip")
        finally:
            patch.stopall()

    @pytest.mark.asyncio
    async def test_http_error_raises(self) -> None:
        async def router(url, headers=None, *, method="GET", json_body=None, data=None,
                         decode_text=True):
            return _dl_resp(b"", "text/html", status=500)

        _patch_download(router)
        try:
            svc = DocumentDownloadService()
            with pytest.raises(FetchError, match="HTTP 500"):
                await svc.download("dat/news/x.zip")
        finally:
            patch.stopall()

    @pytest.mark.asyncio
    async def test_unexpected_html_raises(self) -> None:
        async def router(url, headers=None, *, method="GET", json_body=None, data=None,
                         decode_text=True):
            return _dl_resp(b"<html>login</html>", "text/html")

        _patch_download(router)
        try:
            svc = DocumentDownloadService()
            with pytest.raises(FetchError, match="not a document"):
                await svc.download("dat/news/x.zip")
        finally:
            patch.stopall()


class TestDownloadAll:
    @pytest.mark.asyncio
    async def test_batch_saves_and_skips_failures(self, tmp_path: Path) -> None:
        good = _doc("https://market.sec.or.th/public/idisc/Download?FILEID=ok.zip", "ok.zip")
        bad = _doc("https://market.sec.or.th/public/idisc/Download?FILEID=dead.zip", "dead.zip")

        async def router(url, headers=None, *, method="GET", json_body=None, data=None,
                         decode_text=True):
            if "dead.zip" in url:
                return _dl_resp(FILE_NOT_FOUND_HTML.encode("utf-8"), "text/html")
            return _dl_resp(ZIP_BYTES, "application/zip", "ok.zip")

        _patch_download(router)
        try:
            svc = DocumentDownloadService()
            got = await svc.download_all([good, bad], dest_dir=tmp_path, continue_on_error=True)
        finally:
            patch.stopall()
        assert len(got) == 1  # bad one skipped
        assert (tmp_path / "ok.zip").exists()

    @pytest.mark.asyncio
    async def test_continue_on_error_false_propagates(self) -> None:
        bad = _doc("https://market.sec.or.th/public/idisc/Download?FILEID=dead.zip", "dead.zip")

        async def router(url, headers=None, *, method="GET", json_body=None, data=None,
                         decode_text=True):
            return _dl_resp(FILE_NOT_FOUND_HTML.encode("utf-8"), "text/html")

        _patch_download(router)
        try:
            svc = DocumentDownloadService()
            with pytest.raises(FetchError):
                await svc.download_all([bad], continue_on_error=False)
        finally:
            patch.stopall()
