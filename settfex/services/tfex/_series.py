"""Shared fetch for the TFEX per-series endpoints: an HTTP 404 means the series is unknown."""

from typing import Any

from settfex.exceptions import HTTPStatusError, SeriesNotFoundError
from settfex.utils.data_fetcher import AsyncDataFetcher


async def fetch_series_json(
    fetcher: AsyncDataFetcher,
    url: str,
    *,
    headers: dict[str, str],
    symbol: str,
    endpoint: str,
) -> Any:
    """``fetcher.fetch_json(url)``, with an HTTP 404 re-raised as :class:`SeriesNotFoundError`.

    Only for endpoints whose URL carries a series symbol. Live-probed 2026-11-03: an unknown
    series ("ZZZZ99") answers HTTP 404 on both trading-statistics and underlying-price. Every
    other status is re-raised unchanged.
    """
    try:
        return await fetcher.fetch_json(url, headers=headers)
    except HTTPStatusError as exc:
        if exc.status_code != 404:
            raise
        raise SeriesNotFoundError(
            f"TFEX series {symbol!r} not found: HTTP 404 from the {endpoint} endpoint ({url}). "
            "Check the series symbol; retrying will not help.",
            status_code=404,
            url=exc.url or url,
            symbol=symbol,
        ) from exc
