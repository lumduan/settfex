"""Tests for the SEC document download service (mocked bytes; soft-404 handling)."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from settfex.exceptions import FetchError
from settfex.services.sec.download import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DocumentDownloadService,
    DownloadedFile,
    _filename_from_disposition,
)
from settfex.services.sec.financial_report import DocumentCategory, SecDocument
from settfex.utils.data_fetcher import FetcherConfig, FetchResponse
from tests.services.sec.fixtures import FILE_NOT_FOUND_HTML

ZIP_BYTES = b"PK\x03\x04\x14\x00\x00\x08" + b"\x00" * 32


def _dl_resp(content: bytes, ctype: str, disposition: str | None = None, status: int = 200):
    headers = {"Content-Type": ctype}
    if disposition is not None:
        headers["Content-Disposition"] = disposition
    return FetchResponse(
        status_code=status,
        content=content,
        text="",
        headers=headers,
        url="https://market.sec.or.th/public/idisc/Download?FILEID=dat/news/x.zip",
        elapsed=0.01,
    )


def _doc(file_url: str, file_id: str) -> SecDocument:
    return SecDocument(
        company_name="CP ALL",
        unique_id="0000003875",
        category=DocumentCategory.FINANCIAL_STATEMENT,
        section="Financial Statements",
        file_url=file_url,
        file_id=file_id,
        file_kind="zip",
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
        async def router(
            url, headers=None, *, method="GET", json_body=None, data=None, decode_text=True
        ):
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
        async def router(
            url, headers=None, *, method="GET", json_body=None, data=None, decode_text=True
        ):
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
        async def router(
            url, headers=None, *, method="GET", json_body=None, data=None, decode_text=True
        ):
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
        async def router(
            url, headers=None, *, method="GET", json_body=None, data=None, decode_text=True
        ):
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

        async def router(
            url, headers=None, *, method="GET", json_body=None, data=None, decode_text=True
        ):
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

        async def router(
            url, headers=None, *, method="GET", json_body=None, data=None, decode_text=True
        ):
            return _dl_resp(FILE_NOT_FOUND_HTML.encode("utf-8"), "text/html")

        _patch_download(router)
        try:
            svc = DocumentDownloadService()
            with pytest.raises(FetchError):
                await svc.download_all([bad], continue_on_error=False)
        finally:
            patch.stopall()


class TestTimeoutConfig:
    def test_default_download_timeout_is_180(self) -> None:
        svc = DocumentDownloadService()
        assert svc.config.timeout == DEFAULT_DOWNLOAD_TIMEOUT == 180
        assert svc.config.use_session is False

    def test_timeout_param_overrides(self) -> None:
        assert DocumentDownloadService(timeout=250).config.timeout == 250

    def test_passed_config_timeout_is_honored(self) -> None:
        svc = DocumentDownloadService(config=FetcherConfig(timeout=45))
        assert svc.config.timeout == 45  # explicit config respected (no 180 default)

    def test_timeout_param_wins_over_config(self) -> None:
        svc = DocumentDownloadService(config=FetcherConfig(timeout=45), timeout=300)
        assert svc.config.timeout == 300


class TestDedupeAndMemory:
    @pytest.mark.asyncio
    async def test_download_all_dedupes_by_url(self) -> None:
        # Company + Consolidated rows share one zip -> same file_url.
        url = "https://market.sec.or.th/public/idisc/Download?FILEID=dat/news/shared.zip"
        company = _doc(url, "dat/news/shared.zip")
        consolidated = _doc(url, "dat/news/shared.zip")

        async def router(
            url, headers=None, *, method="GET", json_body=None, data=None, decode_text=True
        ):
            return _dl_resp(ZIP_BYTES, "application/zip", "shared.zip")

        _, instance = _patch_download(router)
        try:
            svc = DocumentDownloadService()
            got = await svc.download_all([company, consolidated])
        finally:
            patch.stopall()
        assert len(got) == 1  # one result per unique URL
        assert instance.fetch.await_count == 1  # downloaded once, not twice

    @pytest.mark.asyncio
    async def test_keep_bytes_default_drops_content_when_saving(self, tmp_path: Path) -> None:
        doc = _doc("https://market.sec.or.th/public/idisc/Download?FILEID=a.zip", "a.zip")

        async def router(
            url, headers=None, *, method="GET", json_body=None, data=None, decode_text=True
        ):
            return _dl_resp(ZIP_BYTES, "application/zip", "a.zip")

        _patch_download(router)
        try:
            svc = DocumentDownloadService()
            got = await svc.download_all([doc], dest_dir=tmp_path)
        finally:
            patch.stopall()
        dl = got[0]
        assert dl.content == b""  # bytes dropped to save memory
        assert dl.size == len(ZIP_BYTES)  # real size still reported
        assert dl.path == tmp_path / "a.zip" and dl.path.exists()  # on disk + path recorded

    @pytest.mark.asyncio
    async def test_keep_bytes_true_retains_content(self, tmp_path: Path) -> None:
        doc = _doc("https://market.sec.or.th/public/idisc/Download?FILEID=a.zip", "a.zip")

        async def router(
            url, headers=None, *, method="GET", json_body=None, data=None, decode_text=True
        ):
            return _dl_resp(ZIP_BYTES, "application/zip", "a.zip")

        _patch_download(router)
        try:
            svc = DocumentDownloadService()
            got = await svc.download_all([doc], dest_dir=tmp_path, keep_bytes=True)
        finally:
            patch.stopall()
        assert got[0].content == ZIP_BYTES  # retained despite saving

    @pytest.mark.asyncio
    async def test_no_dest_dir_keeps_bytes_by_default(self) -> None:
        doc = _doc("https://market.sec.or.th/public/idisc/Download?FILEID=a.zip", "a.zip")

        async def router(
            url, headers=None, *, method="GET", json_body=None, data=None, decode_text=True
        ):
            return _dl_resp(ZIP_BYTES, "application/zip", "a.zip")

        _patch_download(router)
        try:
            svc = DocumentDownloadService()
            got = await svc.download_all([doc])  # no dest_dir -> must keep bytes
        finally:
            patch.stopall()
        assert got[0].content == ZIP_BYTES and got[0].path is None

    @pytest.mark.asyncio
    async def test_single_download_records_path_and_keeps_bytes(self, tmp_path: Path) -> None:
        from settfex.services.sec.download import download_sec_document

        doc = _doc("https://market.sec.or.th/public/idisc/Download?FILEID=a.zip", "a.zip")

        async def router(
            url, headers=None, *, method="GET", json_body=None, data=None, decode_text=True
        ):
            return _dl_resp(ZIP_BYTES, "application/zip", "a.zip")

        _patch_download(router)
        try:
            dl = await download_sec_document(doc, dest_dir=tmp_path)
        finally:
            patch.stopall()
        assert dl.content == ZIP_BYTES  # single download keeps bytes
        assert dl.path == tmp_path / "a.zip" and dl.path.exists()
