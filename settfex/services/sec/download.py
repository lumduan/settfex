"""SEC document download service — fetch the raw document bytes and (optionally) save to disk.

Downloads are plain GETs that return the original file package (e.g. a zip containing
``FINANCIAL_STATEMENTS.XLSX``). The SEC host answers a dead link with an HTML "file not found"
page under **HTTP 200**, so every download is validated (content-type / soft-404 marker) and a
clear :class:`FetchError` is raised instead of returning a garbage payload.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from settfex.exceptions import FetchError
from settfex.services.sec.constants import (
    SEC_BASE_URL,
    SEC_DOWNLOAD_ENDPOINT,
    SEC_FILE_NOT_FOUND_MARKER,
    SEC_REFERER,
)
from settfex.services.sec.financial_report import SecDocument
from settfex.services.sec.utils import build_sec_headers
from settfex.utils.data_fetcher import AsyncDataFetcher, FetcherConfig


class DownloadedFile(BaseModel):
    """A downloaded SEC document: filename + raw bytes, with optional source metadata."""

    filename: str = Field(description="Filename (from Content-Disposition, or a sensible fallback)")
    content: bytes = Field(description="Raw file bytes (e.g. a zip of the original XLSX/PDF)")
    content_type: str = Field(default="", description="Response Content-Type header")
    size: int = Field(description="Number of bytes")
    file_url: str = Field(description="URL the bytes were fetched from")
    document: SecDocument | None = Field(
        default=None, description="The source SecDocument, when downloaded from a listing"
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def save(self, dest: str | Path) -> Path:
        """
        Write the bytes to disk. If ``dest`` is a directory (existing or trailing-slash), the
        file is written as ``dest/<filename>``; otherwise ``dest`` is treated as the full path.
        Parent directories are created. Returns the path written.
        """
        path = Path(dest)
        if path.is_dir() or str(dest).endswith(("/", "\\")):
            path = path / self.filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.content)
        logger.info(f"Saved {self.size} bytes -> {path}")
        return path


def _filename_from_disposition(disposition: str, fallback: str) -> str:
    """Extract a filename from a Content-Disposition header (handles both SEC variants)."""
    if disposition:
        match = re.search(
            r"filename\*?=(?:UTF-8'')?\"?([^\";]+)\"?", disposition, re.IGNORECASE
        )
        if match:
            return unquote(match.group(1).strip().strip('"'))
        # IDISC returns the bare filename as the whole header value (no "filename=" key).
        bare = disposition.strip().strip('"')
        if bare and "=" not in bare:
            return bare
    return fallback


def _fallback_filename(file_url: str, document: SecDocument | None) -> str:
    """Best-effort filename when Content-Disposition is absent."""
    if document and document.file_id and not document.file_id.startswith("ipos:"):
        return document.file_id.rsplit("/", 1)[-1]
    path = urlparse(file_url).path
    base = path.rsplit("/", 1)[-1]
    return base or "sec_download"


class DocumentDownloadService:
    """Download SEC documents to bytes (and optionally disk). Stateless host — no SessionManager."""

    def __init__(self, config: FetcherConfig | None = None) -> None:
        base = config or FetcherConfig()
        self.config = base.model_copy(update={"use_session": False})
        logger.info("DocumentDownloadService initialized (host=market.sec.or.th)")

    @staticmethod
    def _resolve_url(target: SecDocument | str) -> tuple[str, SecDocument | None]:
        """Resolve a download target into (absolute_url, source_document|None)."""
        if isinstance(target, SecDocument):
            return target.file_url, target
        text = target.strip()
        if text.lower().startswith("http"):
            return text, None
        # Treat a bare string as a FILEID path.
        return f"{SEC_BASE_URL}{SEC_DOWNLOAD_ENDPOINT}?FILEID={text}", None

    async def download(
        self,
        target: SecDocument | str,
        *,
        fetcher: AsyncDataFetcher | None = None,
        referer: str = SEC_REFERER,
    ) -> DownloadedFile:
        """
        Download one document to a :class:`DownloadedFile`.

        Args:
            target: A :class:`SecDocument`, an absolute download URL, or a bare FILEID path.
            fetcher: Optional shared fetcher (used by ``download_all`` for concurrency).
            referer: Referer header for the request.

        Raises:
            FetchError: On HTTP failure, or when the SEC host returns its HTML "file not found"
                page (a soft 404 served under HTTP 200).
        """
        url, document = self._resolve_url(target)
        headers = build_sec_headers(referer=referer)

        owns_fetcher = fetcher is None
        fetcher = fetcher or AsyncDataFetcher(config=self.config)
        try:
            resp = await fetcher.fetch(url, headers=headers, decode_text=False)
        finally:
            if owns_fetcher:
                await fetcher.__aexit__(None, None, None)

        if resp.status_code != 200:
            raise FetchError(
                f"Failed to download {url}: HTTP {resp.status_code}", status_code=resp.status_code
            )

        content_type = (resp.headers.get("Content-Type") or resp.headers.get("content-type") or "")
        # A real document is a binary type; an HTML body means a soft error (e.g. dead FILEID).
        if "text/html" in content_type.lower():
            snippet = resp.content[:400].decode("utf-8", "replace")
            if SEC_FILE_NOT_FOUND_MARKER in snippet or "not found" in snippet.lower():
                raise FetchError(f"SEC reports the file does not exist (soft 404): {url}")
            raise FetchError(f"Unexpected HTML response (not a document) downloading {url}")

        disposition = (
            resp.headers.get("Content-Disposition")
            or resp.headers.get("content-disposition")
            or ""
        )
        filename = _filename_from_disposition(disposition, _fallback_filename(url, document))

        logger.info(f"Downloaded {len(resp.content)} bytes ({content_type}) from {url}")
        return DownloadedFile(
            filename=filename,
            content=resp.content,
            content_type=content_type,
            size=len(resp.content),
            file_url=url,
            document=document,
        )

    async def download_all(
        self,
        targets: list[SecDocument | str],
        *,
        dest_dir: str | Path | None = None,
        max_concurrency: int = 5,
        continue_on_error: bool = True,
        progress: bool = False,
    ) -> list[DownloadedFile]:
        """
        Download many documents concurrently (bounded), optionally saving each to ``dest_dir``.

        Args:
            targets: SecDocuments / URLs / FILEIDs to download.
            dest_dir: If set, each file is also written here (created if needed).
            max_concurrency: Max simultaneous downloads (default 5).
            continue_on_error: If True (default) a failed item is logged and skipped; if False
                the first failure propagates.
            progress: Show a tqdm progress bar if the optional ``progress`` extra is installed.

        Returns:
            The successfully downloaded files (order not guaranteed under concurrency).
        """
        semaphore = asyncio.Semaphore(max(1, max_concurrency))
        results: list[DownloadedFile] = []
        bar = _make_progress_bar(len(targets)) if progress else None

        async with AsyncDataFetcher(config=self.config) as fetcher:

            async def one(target: SecDocument | str) -> DownloadedFile | None:
                async with semaphore:
                    try:
                        dl = await self.download(target, fetcher=fetcher)
                    except Exception as exc:  # noqa: BLE001 - tolerant batch download
                        if not continue_on_error:
                            raise
                        label = target.file_url if isinstance(target, SecDocument) else target
                        logger.warning(f"Skipping download that failed ({label}): {exc}")
                        return None
                    if dest_dir is not None:
                        dl.save(dest_dir)
                    return dl

            tasks = [asyncio.create_task(one(t)) for t in targets]
            for coro in asyncio.as_completed(tasks):
                dl = await coro
                if bar is not None:
                    bar.update(1)
                if dl is not None:
                    results.append(dl)

        if bar is not None:
            bar.close()
        logger.info(f"Downloaded {len(results)}/{len(targets)} document(s)")
        return results


def _make_progress_bar(total: int) -> Any | None:
    """Return a tqdm bar if the optional 'progress' extra is installed, else None."""
    try:
        from tqdm.auto import tqdm
    except ImportError:
        logger.warning("progress=True but tqdm is not installed; install settfex[progress]")
        return None
    return tqdm(total=total, desc="Downloading SEC documents", unit="file")


async def download_sec_document(
    target: SecDocument | str,
    *,
    dest_dir: str | Path | None = None,
    config: FetcherConfig | None = None,
) -> DownloadedFile:
    """
    Convenience: download one SEC document (optionally saving it to ``dest_dir``).

    Args:
        target: A :class:`SecDocument`, an absolute URL, or a bare FILEID path.
        dest_dir: If set, also write the file here.
        config: Optional fetcher configuration.
    """
    service = DocumentDownloadService(config=config)
    dl = await service.download(target)
    if dest_dir is not None:
        dl.save(dest_dir)
    return dl


async def download_sec_documents(
    targets: list[SecDocument | str],
    *,
    dest_dir: str | Path | None = None,
    max_concurrency: int = 5,
    continue_on_error: bool = True,
    progress: bool = False,
    config: FetcherConfig | None = None,
) -> list[DownloadedFile]:
    """
    Convenience: download many SEC documents concurrently (optionally saving to ``dest_dir``).

    See :meth:`DocumentDownloadService.download_all` for argument semantics.
    """
    service = DocumentDownloadService(config=config)
    return await service.download_all(
        targets,
        dest_dir=dest_dir,
        max_concurrency=max_concurrency,
        continue_on_error=continue_on_error,
        progress=progress,
    )
