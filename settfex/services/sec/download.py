"""SEC document download service — fetch the raw document bytes and (optionally) save to disk.

Downloads are plain GETs that return the original file package (e.g. a zip containing
``FINANCIAL_STATEMENTS.XLSX``). The SEC host answers a dead link with an HTML "file not found"
page under **HTTP 200**, so every download is validated (content-type / soft-404 marker) and a
clear :class:`FetchError` is raised instead of returning a garbage payload.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Iterable, Sequence
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
    """A downloaded SEC document: filename + raw bytes, with optional source metadata.

    ``size`` is always the real byte count. When a bulk download saves to disk without keeping
    bytes (see ``download_all(keep_bytes=...)``), ``content`` is emptied to save memory and
    ``path`` records where the file was written.
    """

    filename: str = Field(description="Filename (from Content-Disposition, or a sensible fallback)")
    content: bytes = Field(description="Raw file bytes (empty if dropped after saving to disk)")
    content_type: str = Field(default="", description="Response Content-Type header")
    size: int = Field(description="Number of bytes downloaded (real size, even if content dropped)")
    file_url: str = Field(description="URL the bytes were fetched from")
    path: Path | None = Field(default=None, description="On-disk path, if the file was saved")
    document: SecDocument | None = Field(
        default=None, description="The source SecDocument, when downloaded from a listing"
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def save(self, dest: str | Path) -> Path:
        """
        Write the bytes to disk. If ``dest`` is a directory (existing or trailing-slash), the
        file is written as ``dest/<filename>``; otherwise ``dest`` is treated as the full path.
        Parent directories are created. Records and returns the path written.
        """
        path = Path(dest)
        if path.is_dir() or str(dest).endswith(("/", "\\")):
            path = path / self.filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.content)
        self.path = path
        logger.info(f"Saved {self.size} bytes -> {path}")
        return path


class FailedDownload(BaseModel):
    """One target that could not be downloaded, and why.

    A failed item used to leave the batch as ``None`` and be filtered out, so a partial batch was
    shaped exactly like a complete one and "I downloaded the filings" and "I downloaded some of the
    filings" had the same return value. The reason survives here instead of only in a log line.
    """

    target: str = Field(description="The resolved download URL (or the raw target string)")
    document: SecDocument | None = Field(
        default=None, description="The source SecDocument, when the target was one"
    )
    error: str = Field(description="The exception message")
    error_type: str = Field(description="The exception class name, e.g. 'FetchError'")


class DownloadResult(list[DownloadedFile]):
    """The files a bulk download produced, **plus the ones it could not**.

    It **is** a ``list[DownloadedFile]`` — ``len()``, iteration, indexing, slicing and passing it
    on all behave exactly as the plain list did, so this is additive. What is new is that a partial
    batch can now be told from a complete one without parsing logs:

        >>> files = await sec.download_all(docs)
        >>> if not files.is_complete:
        ...     print([f.target for f in files.failed])

    Same shape as :class:`~settfex.services.sec.financial_report.SecDocumentList`, for the same
    reason: the extra information rides along instead of breaking every existing caller.
    """

    def __init__(
        self,
        iterable: Iterable[DownloadedFile] = (),
        *,
        failed: Sequence[FailedDownload] = (),
        requested: int | None = None,
    ) -> None:
        super().__init__(iterable)
        self.failed: list[FailedDownload] = list(failed)
        """Every target that raised, with its reason. Empty on a complete batch."""
        self.requested: int = len(self) + len(self.failed) if requested is None else requested
        """How many unique files were attempted (duplicates already collapsed)."""

    @property
    def is_complete(self) -> bool:
        """True when every attempted download succeeded."""
        return not self.failed


def _filename_from_disposition(disposition: str, fallback: str) -> str:
    """Extract a filename from a Content-Disposition header (handles both SEC variants)."""
    if disposition:
        match = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)\"?", disposition, re.IGNORECASE)
        if match:
            return unquote(match.group(1).strip().strip('"'))
        # IDISC returns the bare filename as the whole header value (no "filename=" key).
        bare = disposition.strip().strip('"')
        if bare and "=" not in bare:
            return bare
    return fallback


def _fallback_filename(file_url: str, document: SecDocument | None) -> str:
    """Best-effort filename when Content-Disposition is absent.

    A real FILEID is a path (``dat/news/…/0737FIN.zip``) whose last segment is the filename.
    The synthetic ids — ``ipos:<id>``, ``fsdl:<blob>`` — are not paths and must not be sliced
    like one; the colon is what tells them apart, since a FILEID path never contains one.
    """
    if document and document.file_id and ":" not in document.file_id:
        return document.file_id.rsplit("/", 1)[-1]
    path = urlparse(file_url).path
    base = path.rsplit("/", 1)[-1]
    return base or "sec_download"


# SEC documents are large binaries (56-1/56-2 One Reports run 15-25 MB), so downloads default
# to a much longer per-file timeout than the 30 s used for JSON/listing calls.
DEFAULT_DOWNLOAD_TIMEOUT = 180


def _effective_download_config(config: FetcherConfig | None, timeout: int | None) -> FetcherConfig:
    """
    Resolve the fetcher config for a download (stateless host).

    Precedence: an explicit ``timeout`` wins; otherwise a caller-supplied ``config`` is honored
    as-is; otherwise the document default (:data:`DEFAULT_DOWNLOAD_TIMEOUT`) applies instead of
    the 30 s ``FetcherConfig`` default. ``use_session`` is always forced off.
    """
    if config is None:
        base = FetcherConfig(timeout=timeout if timeout is not None else DEFAULT_DOWNLOAD_TIMEOUT)
    elif timeout is not None:
        base = config.model_copy(update={"timeout": timeout})
    else:
        base = config
    return base.model_copy(update={"use_session": False})


class DocumentDownloadService:
    """Download SEC documents to bytes (and optionally disk). Stateless host — no SessionManager."""

    def __init__(self, config: FetcherConfig | None = None, *, timeout: int | None = None) -> None:
        self.config = _effective_download_config(config, timeout)
        logger.info(
            f"DocumentDownloadService initialized (host=market.sec.or.th, "
            f"timeout={self.config.timeout}s)"
        )

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

        content_type = resp.headers.get("Content-Type") or resp.headers.get("content-type") or ""
        # A real document is a binary type; an HTML body means a soft error (e.g. dead FILEID).
        if "text/html" in content_type.lower():
            snippet = resp.content[:400].decode("utf-8", "replace")
            if SEC_FILE_NOT_FOUND_MARKER in snippet or "not found" in snippet.lower():
                raise FetchError(f"SEC reports the file does not exist (soft 404): {url}")
            raise FetchError(f"Unexpected HTML response (not a document) downloading {url}")

        disposition = (
            resp.headers.get("Content-Disposition") or resp.headers.get("content-disposition") or ""
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
        targets: Sequence[SecDocument | str],
        *,
        dest_dir: str | Path | None = None,
        max_concurrency: int = 3,
        continue_on_error: bool = True,
        keep_bytes: bool | None = None,
        progress: bool = False,
    ) -> DownloadResult:
        """
        Download many documents concurrently (bounded), optionally saving each to ``dest_dir``.

        Duplicate targets that resolve to the **same URL** are downloaded once (a statement's
        Company and Consolidated rows share one zip), so the result has one entry per unique file.

        Args:
            targets: SecDocuments / URLs / FILEIDs to download (deduped by resolved URL). Any
                sequence is accepted, so a ``SecDocumentList`` / ``list[SecDocument]`` straight
                from :meth:`list_documents` can be passed as-is.
            dest_dir: If set, each file is written here (created if needed).
            max_concurrency: Max simultaneous downloads (default 3 — big files share bandwidth).
            continue_on_error: If True (default) a failed item is recorded on the result's
                ``.failed`` and skipped; if False the first failure propagates.
            keep_bytes: Whether to keep each file's bytes on the returned ``DownloadedFile``.
                Default (``None``) keeps bytes only when NOT saving to disk; when ``dest_dir`` is
                set the bytes are dropped after saving (``content=b""``, ``path`` set) to bound
                memory. Pass ``True`` to always keep bytes, ``False`` to always drop them.
            progress: Show a tqdm progress bar if the optional ``progress`` extra is installed.

        Returns:
            A :class:`DownloadResult` — a ``list[DownloadedFile]`` of the successes (one per unique
            URL; order not guaranteed) that also carries ``.failed``, ``.requested`` and
            ``.is_complete``, so a partial batch can be told from a complete one.
        """
        # Dedupe by resolved URL, preserving first-seen order.
        unique: list[SecDocument | str] = []
        seen: set[str] = set()
        for target in targets:
            url, _ = self._resolve_url(target)
            if url and url not in seen:
                seen.add(url)
                unique.append(target)
        if len(unique) != len(targets):
            logger.info(
                f"download_all: {len(targets)} targets -> {len(unique)} unique files "
                f"({len(targets) - len(unique)} duplicate(s) skipped)"
            )

        keep = keep_bytes if keep_bytes is not None else (dest_dir is None)
        semaphore = asyncio.Semaphore(max(1, max_concurrency))
        results: list[DownloadedFile] = []
        failures: list[FailedDownload] = []
        bar = _make_progress_bar(len(unique)) if progress else None

        async with AsyncDataFetcher(config=self.config) as fetcher:

            async def one(target: SecDocument | str) -> DownloadedFile | FailedDownload:
                async with semaphore:
                    try:
                        dl = await self.download(target, fetcher=fetcher)
                    except Exception as exc:  # noqa: BLE001 - tolerant batch download
                        if not continue_on_error:
                            raise
                        url, document = self._resolve_url(target)
                        logger.warning(f"Skipping download that failed ({url}): {exc}")
                        return FailedDownload(
                            target=url,
                            document=document,
                            error=str(exc),
                            error_type=type(exc).__name__,
                        )
                    if dest_dir is not None:
                        dl.save(dest_dir)
                    if not keep:
                        dl.content = b""  # bytes are on disk (or unwanted); free the memory
                    return dl

            tasks = [asyncio.create_task(one(t)) for t in unique]
            for coro in asyncio.as_completed(tasks):
                outcome = await coro
                if bar is not None:
                    bar.update(1)
                if isinstance(outcome, FailedDownload):
                    failures.append(outcome)
                else:
                    results.append(outcome)

        if bar is not None:
            bar.close()
        if failures:
            logger.warning(
                f"Downloaded {len(results)}/{len(unique)} document(s); {len(failures)} failed and "
                f"are on the result's `.failed` (targets: "
                f"{', '.join(f.target for f in failures[:3])}"
                f"{', …' if len(failures) > 3 else ''})"
            )
        else:
            logger.info(f"Downloaded {len(results)}/{len(unique)} document(s)")
        return DownloadResult(results, failed=failures, requested=len(unique))


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
    timeout: int | None = None,
    config: FetcherConfig | None = None,
) -> DownloadedFile:
    """
    Convenience: download one SEC document (optionally saving it to ``dest_dir``).

    Args:
        target: A :class:`SecDocument`, an absolute URL, or a bare FILEID path.
        dest_dir: If set, also write the file here (``.path`` is recorded).
        timeout: Per-file timeout in seconds (default 180 — documents are large). Bump for very
            large files on a slow link (max 300).
        config: Optional fetcher configuration.
    """
    service = DocumentDownloadService(config=config, timeout=timeout)
    dl = await service.download(target)
    if dest_dir is not None:
        dl.save(dest_dir)
    return dl


async def download_sec_documents(
    targets: Sequence[SecDocument | str],
    *,
    dest_dir: str | Path | None = None,
    max_concurrency: int = 3,
    continue_on_error: bool = True,
    keep_bytes: bool | None = None,
    timeout: int | None = None,
    progress: bool = False,
    config: FetcherConfig | None = None,
) -> DownloadResult:
    """
    Convenience: download many SEC documents concurrently (optionally saving to ``dest_dir``).

    Duplicate targets sharing a URL are downloaded once. ``timeout`` sets the per-file timeout
    (default 180s). Returns a :class:`DownloadResult` — still a list of the successes, and also
    carrying ``.failed``. See :meth:`DocumentDownloadService.download_all` for the rest.
    """
    service = DocumentDownloadService(config=config, timeout=timeout)
    return await service.download_all(
        targets,
        dest_dir=dest_dir,
        max_concurrency=max_concurrency,
        continue_on_error=continue_on_error,
        keep_bytes=keep_bytes,
        progress=progress,
    )
