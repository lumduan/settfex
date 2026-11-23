"""Bank of Thailand Statistics product: categories, series search, observations (1.0.0).

The Statistics API reaches the BOT's whole statistical database (403 categories on 2026-11-23),
including THOR, THOR averages, and the monthly government T-bill/bond yields. Useful codes are in
:data:`~settfex.services.bot.constants.KNOWN_SERIES`.

⚠️ Two traps, both live-verified:
- **The search lists discontinued series first.** For example, the government-yield codes
  ``FMRTINTM00027``-``49`` ended 2025-07. Check ``observation_end`` before choosing a code.
- **An unknown series code is not a 404.** BOT answers HTTP 200 with every field ``null``.
  settfex raises :class:`~settfex.exceptions.BotSeriesNotFoundError` for it.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

from settfex.exceptions import BotSeriesNotFoundError
from settfex.services.bot.auth import DEFAULT_ENV_FILE
from settfex.services.bot.client import BotClient, day_param, result_of
from settfex.services.bot.constants import (
    STAT_CATEGORY_LIST_PATH,
    STAT_OBSERVATIONS_PATH,
    STAT_SEARCH_PATH,
    STAT_SERIES_LIST_PATH,
    BotProduct,
)
from settfex.services.bot.models import StatCategory, StatSeries, StatSeriesInfo
from settfex.utils.data_fetcher import FetcherConfig
from settfex.utils.parsing import ResponseParseError, validate_or_raise


def _series_info(raw: dict[str, Any], context: str) -> StatSeriesInfo:
    row = dict(raw)
    cats = row.pop("series_categories", None)
    if isinstance(cats, list):
        row["categories"] = [
            str(c["category"]) for c in cats if isinstance(c, dict) and c.get("category")
        ]
    if "last_updated_date" in row and "last_update_date" not in row:
        row["last_update_date"] = row.pop("last_updated_date")
    return validate_or_raise(StatSeriesInfo, row, context=context)


class StatisticsService:
    """The BOT Statistics product (token: ``BANK_OF_THAILAND_TOKEN_STATISTICS``)."""

    def __init__(
        self,
        *,
        token: str | None = None,
        env_file: str | Path | None = DEFAULT_ENV_FILE,
        config: FetcherConfig | None = None,
    ) -> None:
        self.client = BotClient(
            BotProduct.STATISTICS, token=token, env_file=env_file, config=config
        )

    async def fetch_categories(self) -> list[StatCategory]:
        """Every Statistics category (code + Thai/English description)."""
        result = result_of(await self.client.get_json(STAT_CATEGORY_LIST_PATH), "BOT categories")
        return [
            validate_or_raise(StatCategory, c, context="BOT category")
            for c in result.get("category") or []
        ]

    async def fetch_series_list(self, category: str) -> list[StatSeriesInfo]:
        """The series in one category, e.g. ``"FM_RT_013"`` (THOR and THOR Average)."""
        data = await self.client.get_json(STAT_SERIES_LIST_PATH, {"category": category.strip()})
        result = result_of(data, f"BOT series list {category}")
        return [_series_info(s, f"BOT series list {category}") for s in result.get("series") or []]

    async def search_series(self, keyword: str) -> list[StatSeriesInfo]:
        """Series whose metadata matches ``keyword`` (Thai or English). At most 100 come back."""
        if not keyword or not keyword.strip():
            raise ValueError("keyword must not be empty")
        data = await self.client.get_json(STAT_SEARCH_PATH, {"keyword": keyword.strip()})
        result = result_of(data, f"BOT series search {keyword!r}")
        return [_series_info(s, "BOT series search") for s in result.get("series_details") or []]

    async def fetch_observations(
        self,
        series_code: str,
        start_date: date | datetime | str,
        end_date: date | datetime | str | None = None,
        *,
        sort: Literal["asc", "desc"] | None = None,
    ) -> StatSeries:
        """One series' values from ``start_date`` (``YYYY-MM-DD``) to ``end_date`` (optional).

        Raises:
            BotSeriesNotFoundError: BOT does not know ``series_code`` (it answers HTTP 200 with
                every field null, not 404).
        """
        code = series_code.strip()
        params = {"series_code": code, "start_period": day_param(start_date, "start_date")}
        if end_date is not None:
            params["end_period"] = day_param(end_date, "end_date")
        if sort:
            params["sort_by"] = sort
        result = result_of(
            await self.client.get_json(STAT_OBSERVATIONS_PATH, params), f"BOT {code}"
        )
        series = result.get("series")
        if not isinstance(series, list) or not series:
            raise ResponseParseError(f"BOT observations {code}: no 'series' in the answer")
        first = series[0] if isinstance(series[0], dict) else {}
        if not first.get("series_code"):
            raise BotSeriesNotFoundError(
                f"Bank of Thailand Statistics has no series {code!r} (HTTP 200 with an all-null "
                f"series). Find codes with search_series() or fetch_series_list().",
                series_code=code,
            )
        return validate_or_raise(StatSeries, first, context=f"BOT observations {code}")

    async def fetch_raw(self, path: str, params: dict[str, str] | None = None) -> Any:
        """Any endpoint of this product, as decoded JSON (escape hatch)."""
        return await self.client.fetch_raw(path, params)


def _service(
    token: str | None, env_file: str | Path | None, config: FetcherConfig | None
) -> StatisticsService:
    return StatisticsService(token=token, env_file=env_file, config=config)


async def get_stat_categories(
    *,
    token: str | None = None,
    env_file: str | Path | None = DEFAULT_ENV_FILE,
    config: FetcherConfig | None = None,
) -> list[StatCategory]:
    """Every BOT Statistics category."""
    return await _service(token, env_file, config).fetch_categories()


async def get_stat_series_list(
    category: str,
    *,
    token: str | None = None,
    env_file: str | Path | None = DEFAULT_ENV_FILE,
    config: FetcherConfig | None = None,
) -> list[StatSeriesInfo]:
    """The series in one BOT Statistics category."""
    return await _service(token, env_file, config).fetch_series_list(category)


async def search_stat_series(
    keyword: str,
    *,
    token: str | None = None,
    env_file: str | Path | None = DEFAULT_ENV_FILE,
    config: FetcherConfig | None = None,
) -> list[StatSeriesInfo]:
    """Search BOT Statistics series by keyword (check ``observation_end``: old codes come first)."""
    return await _service(token, env_file, config).search_series(keyword)


async def get_stat_observations(
    series_code: str,
    start_date: date | datetime | str,
    end_date: date | datetime | str | None = None,
    *,
    sort: Literal["asc", "desc"] | None = None,
    token: str | None = None,
    env_file: str | Path | None = DEFAULT_ENV_FILE,
    config: FetcherConfig | None = None,
) -> StatSeries:
    """One BOT series' observations, e.g. THOR: ``get_stat_observations("FMRTTHORD00003", ...)``."""
    return await _service(token, env_file, config).fetch_observations(
        series_code, start_date, end_date, sort=sort
    )
