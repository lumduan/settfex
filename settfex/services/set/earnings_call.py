"""SET Earnings Call (Opportunity Day) Calendar Service.

Fetches the SET "Earnings Call (OPPDAY)" calendar from the opportunity-day backend
(``https://api.lcp.setgroup.or.th/api/v1``) and returns typed Pydantic models plus an
optional pandas DataFrame convenience.

Unlike the main SET API, this host is **stateless**: it sits behind no Incapsula bot wall,
needs no cookies and no auth header. The service therefore uses a plain (sessionless)
``AsyncDataFetcher`` — there is no cookie warm-up.

Note on the ``period`` field — it means two different things in the two endpoints:

- in the **list** response (used here for :attr:`EarningsCallItem.period`) it is the video
  **duration** as shown on the website card, e.g. ``"45:00"`` (MM:SS);
- in the **detail** response it is the meeting **clock-time range**, e.g. ``"16:15 - 17:00"``
  (exposed as :attr:`EarningsCallDetail.meeting_time`).

The list duration is authoritative for ``video_clip_time`` and is never overwritten by
enrichment.
"""

import asyncio
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from settfex.services.set.constants import (
    SET_EARNINGS_CALL_DETAIL_ENDPOINT,
    SET_EARNINGS_CALL_FILTER_ENDPOINT,
    SET_EARNINGS_CALL_SEARCH_ENDPOINT,
    SET_LCP_BASE_URL,
    SET_OPPDAY_ORIGIN,
    SET_OPPDAY_REFERER,
)
from settfex.services.set.stock.utils import normalize_language, normalize_symbol
from settfex.utils.data_fetcher import AsyncDataFetcher, FetcherConfig
from settfex.utils.parsing import (
    ResponseParseError,
    validate_list_or_raise,
    validate_or_raise,
)

if TYPE_CHECKING:
    import pandas as pd

# Extracts the YouTube video id from a thumbnail URL like
# ``https://img.youtube.com/vi/<VIDEO_ID>/mqdefault.jpg``.
_YOUTUBE_ID_RE = re.compile(r"/vi/([^/]+)/")


def _extract_youtube_id(image_path: str | None) -> str | None:
    """Extract the YouTube video id from a thumbnail URL.

    Args:
        image_path: Thumbnail URL from the API (e.g. ``.../vi/<id>/mqdefault.jpg``).

    Returns:
        The video id, or ``None`` if ``image_path`` is missing/empty or is not a
        YouTube thumbnail (e.g. an upcoming item with no recording).
    """
    if not image_path or "youtube.com" not in image_path:
        return None
    match = _YOUTUBE_ID_RE.search(image_path)
    return match.group(1) if match else None


def _build_earnings_call_headers(language: str) -> dict[str, str]:
    """Build browser-like headers for the opportunity-day API.

    No cookie/authorization header is required (the host is stateless). ``Content-Type`` is
    set automatically by curl_cffi when a JSON body is sent, so it is intentionally omitted.

    Args:
        language: Normalized language code (``"en"`` or ``"th"``) driving ``Accept-Language``.

    Returns:
        Header dictionary suitable for the search/detail/filter endpoints.
    """
    accept_language = "th,en-US;q=0.9,en;q=0.8" if language == "th" else "en-US,en;q=0.9,th;q=0.8"
    return {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": accept_language,
        "Origin": SET_OPPDAY_ORIGIN,
        "Referer": SET_OPPDAY_REFERER,
        "Sec-Ch-Ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"macOS"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "cross-site",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
        ),
    }


class FilterOption(BaseModel):
    """A single filter option from ``/investor/filter/{name}``.

    ``id`` is an ``int`` for the ``types``/``years``/``trusts``/``stages`` filters and a
    ``str`` code for ``industries``/``markets``/``themes``.
    """

    id: int | str = Field(description="Option id (int or string code, depends on the filter)")
    name: str = Field(description="Human-readable option name")

    model_config = ConfigDict(str_strip_whitespace=True)


class EarningsCallDetail(BaseModel):
    """Enrichment fields from ``GET /investor/vdo/{id}`` (fetched only when ``enrich=True``)."""

    id: int = Field(description="Presentation/event id")
    symbol: str | None = Field(default=None, description="Stock symbol/ticker")
    type_id: int | None = Field(default=None, description="Presentation type id (1 = OPPDAY)")
    type: str | None = Field(default=None, description="Presentation type label")
    year: int | None = Field(default=None, description="Fiscal year")
    round: int | None = Field(default=None, description="Round number within the year")
    round_name: str | None = Field(default=None, description='Round name, e.g. "Q1/2026"')
    company_name: str | None = Field(default=None, description="Company name (English, raw)")
    company_name_th: str | None = Field(default=None, description="Company name (Thai, raw)")
    description: str | None = Field(default=None, description="Presentation description")
    meeting_time: str | None = Field(
        default=None,
        alias="period",
        description=(
            'Meeting clock-time range, e.g. "16:15 - 17:00". Distinct from the list '
            "endpoint's MM:SS video duration — see the module docstring."
        ),
    )
    video_link: str | None = Field(default=None, description="YouTube embed URL")
    document_link: str | None = Field(default=None, description="Presentation document path")
    snapshot_link: str | None = Field(default=None, description="Listed-company snapshot URL")
    company_link: str | None = Field(default=None, description="SET company profile URL")
    logo_path: str | None = Field(default=None, description="Company logo URL")
    has_qa: bool | None = Field(default=None, description="Whether a Q&A is available")

    model_config = ConfigDict(populate_by_name=True, extra="ignore", str_strip_whitespace=True)


class EarningsCallItem(BaseModel):
    """A single Earnings Call (Opportunity Day) calendar entry from the list endpoint."""

    id: int = Field(description="Unique presentation/event id")
    name: str = Field(description="Presentation title (Thai, as shown on the card)")
    company_name: str = Field(description='Raw company name, prefixed "<SYMBOL>: ..."')
    industry: str = Field(default="", description="Industry classification")
    symbol: str = Field(description="Stock symbol/ticker")
    image_path: str | None = Field(
        default=None, description="YouTube thumbnail URL (present only when recorded)"
    )
    view_mode: bool | None = Field(default=None, description="Whether the recording is viewable")
    meeting_date: datetime = Field(
        description="Meeting date (tz-aware UTC; the API reports midnight UTC)"
    )
    period: str | None = Field(
        default=None,
        description='Video clip duration as shown on the card, e.g. "45:00" (MM:SS)',
    )
    detail: EarningsCallDetail | None = Field(
        default=None,
        description="Enrichment from the detail endpoint, populated only when enrich=True",
    )

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    @field_validator("meeting_date")
    @classmethod
    def _ensure_tz_aware(cls, value: datetime) -> datetime:
        """Guarantee a tz-aware datetime (assume UTC if the API ever omits the offset)."""
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

    @computed_field  # type: ignore[prop-decorator]
    @property
    def company_name_clean(self) -> str:
        """Company name with the leading ``"<SYMBOL>: "`` prefix removed.

        Uses a literal prefix check (not a regex) so symbols containing regex-special
        characters (e.g. ``88TH``) are handled safely.
        """
        prefix = f"{self.symbol}:"
        if self.company_name.startswith(prefix):
            return self.company_name[len(prefix) :].strip()
        return self.company_name.strip()

    @computed_field  # type: ignore[prop-decorator]
    @property
    def youtube_video_id(self) -> str | None:
        """YouTube video id derived from ``image_path`` (``None`` if not a YouTube thumb)."""
        return _extract_youtube_id(self.image_path)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def youtube_url(self) -> str | None:
        """Canonical ``https://www.youtube.com/watch?v=<id>`` URL, or ``None``."""
        video_id = self.youtube_video_id
        return f"https://www.youtube.com/watch?v={video_id}" if video_id else None


# DataFrame column name -> accessor. The first five are the user-facing default columns; the
# rest are opt-in extras selectable via ``to_dataframe(columns=[...])``.
_DATAFRAME_ACCESSORS: dict[str, Callable[[EarningsCallItem], Any]] = {
    "stock_name": lambda item: item.symbol,
    "company_name": lambda item: item.company_name_clean,
    "earnings_call_date": lambda item: item.meeting_date.date(),
    "video_clip_time": lambda item: item.period,
    "youtube_url": lambda item: item.youtube_url,
    "company_name_raw": lambda item: item.company_name,
    "earnings_call_datetime": lambda item: item.meeting_date,
    "youtube_video_id": lambda item: item.youtube_video_id,
    "id": lambda item: item.id,
    "name": lambda item: item.name,
    "industry": lambda item: item.industry,
    "view_mode": lambda item: item.view_mode,
}
_DEFAULT_DATAFRAME_COLUMNS: tuple[str, ...] = (
    "stock_name",
    "company_name",
    "earnings_call_date",
    "video_clip_time",
    "youtube_url",
)


class EarningsCallResponse(BaseModel):
    """Response from the earnings-call list endpoint (``no_records`` + ``items``)."""

    no_records: int = Field(description="Total number of records across all pages")
    items: list[EarningsCallItem] = Field(
        default_factory=list, description="Calendar entries for this page (or accumulated)"
    )

    model_config = ConfigDict(populate_by_name=True)

    @property
    def count(self) -> int:
        """Number of items currently held (this page, or accumulated by ``fetch_all``)."""
        return len(self.items)

    def to_dataframe(self, columns: list[str] | None = None) -> "pd.DataFrame":
        """Render the items as a pandas DataFrame.

        pandas is an optional dependency; it is imported lazily here so that importing this
        service never requires pandas.

        Args:
            columns: Column names to include, in order. Defaults to
                ``["stock_name", "company_name", "earnings_call_date", "video_clip_time",
                "youtube_url"]``. See ``_DATAFRAME_ACCESSORS`` for the full set of selectable
                columns (e.g. ``"company_name_raw"``, ``"youtube_video_id"``,
                ``"earnings_call_datetime"``, ``"industry"``, ``"id"``).

        Returns:
            A DataFrame with one row per item (empty — but with the requested columns — when
            there are no items).

        Raises:
            ImportError: If pandas is not installed.
            ValueError: If an unknown column name is requested.
        """
        try:
            import pandas as pd
        except ImportError as exc:  # pragma: no cover - exercised via monkeypatched sys.modules
            raise ImportError(
                "pandas is required for EarningsCallResponse.to_dataframe(). Install it with "
                "'pip install settfex[dataframe]' (or 'uv add pandas')."
            ) from exc

        cols = list(columns) if columns is not None else list(_DEFAULT_DATAFRAME_COLUMNS)
        unknown = [c for c in cols if c not in _DATAFRAME_ACCESSORS]
        if unknown:
            raise ValueError(
                f"Unknown DataFrame column(s): {unknown}. "
                f"Available columns: {sorted(_DATAFRAME_ACCESSORS)}"
            )

        rows = [{col: _DATAFRAME_ACCESSORS[col](item) for col in cols} for item in self.items]
        return pd.DataFrame(rows, columns=cols)


class EarningsCallService:
    """Service for fetching the SET Earnings Call (Opportunity Day) calendar.

    The opportunity-day host is stateless, so this service always uses a sessionless
    ``AsyncDataFetcher`` (no cookie warm-up). Any injected :class:`FetcherConfig` is honored
    for everything except ``use_session``, which is forced to ``False``.
    """

    def __init__(self, config: FetcherConfig | None = None) -> None:
        """Initialize the service.

        Args:
            config: Optional fetcher configuration. ``use_session`` is always coerced to
                ``False`` for this stateless host; all other settings (timeout, retries,
                browser impersonation, rate limiting) are preserved.
        """
        base = config or FetcherConfig()
        # This host needs no cookies; never warm up a SET session for it.
        self.config = base.model_copy(update={"use_session": False})
        self.base_url = SET_LCP_BASE_URL
        logger.info(f"EarningsCallService initialized with base_url={self.base_url}")

    @staticmethod
    def _build_search_body(
        *,
        type_id: int,
        quarter_id: int,
        keyword: str | None,
        industries_id: str | None,
        composition_id: int | None,
        start: int,
        page_size: int,
    ) -> dict[str, Any]:
        """Build (and validate) the JSON body for the search endpoint.

        Raises:
            ValueError: If ``start`` or ``page_size`` is out of range.
        """
        if start < 1:
            raise ValueError(f"start must be >= 1 (1-based page number), got {start}")
        if page_size < 1:
            raise ValueError(f"page_size must be >= 1, got {page_size}")

        return {
            "start": start,
            "page_size": page_size,
            "keyword": normalize_symbol(keyword) if keyword else None,
            "quarter_id": quarter_id,
            "industries_id": industries_id,
            "composition_id": composition_id,
            "type_id": type_id,
        }

    async def _search_page(
        self, fetcher: AsyncDataFetcher, body: dict[str, Any], language: str
    ) -> EarningsCallResponse:
        """POST a single search page and validate the response."""
        url = f"{self.base_url}{SET_EARNINGS_CALL_SEARCH_ENDPOINT}"
        headers = _build_earnings_call_headers(language)
        logger.debug(
            f"POST earnings-call search: start={body['start']} page_size={body['page_size']} "
            f"type_id={body['type_id']} quarter_id={body['quarter_id']} "
            f"keyword={body['keyword']!r}"
        )
        data = await fetcher.fetch_json(url, headers=headers, method="POST", json_body=body)
        response = validate_or_raise(EarningsCallResponse, data, context="set earnings-call search")
        logger.info(
            f"Fetched {response.count} earnings-call item(s) (no_records={response.no_records})"
        )
        return response

    async def fetch_earnings_calls(
        self,
        *,
        type_id: int = 1,
        quarter_id: int = 0,
        keyword: str | None = None,
        industries_id: str | None = None,
        composition_id: int | None = None,
        start: int = 1,
        page_size: int = 12,
        language: str = "en",
        enrich: bool = False,
    ) -> EarningsCallResponse:
        """Fetch one page of earnings-call entries.

        Args:
            type_id: Presentation type (1 = Earnings Call/OPPDAY, 2 = Digital Roadshow,
                3 = C-Sign Public Presentation).
            quarter_id: Quarter filter id (0 = all quarters); see ``fetch_filter_years()``.
            keyword: Free-text symbol/company search (normalized via ``normalize_symbol``).
            industries_id: Industry filter code (see ``fetch_filter_industries()``).
            composition_id: Optional composition/theme filter id.
            start: 1-based page number.
            page_size: Items per page.
            language: ``"en"`` or ``"th"`` (drives ``Accept-Language``).
            enrich: If True, also fetch per-item detail concurrently (bounded). Off by
                default — all five required columns come from the list endpoint.

        Returns:
            An :class:`EarningsCallResponse` for the requested page.

        Raises:
            ValueError: If ``start``/``page_size`` are out of range or ``language`` is invalid.
            ResponseParseError: If the response cannot be decoded.

        Example:
            >>> service = EarningsCallService()
            >>> response = await service.fetch_earnings_calls(keyword="HANN")
            >>> response.items[0].youtube_url
        """
        language = normalize_language(language)
        body = self._build_search_body(
            type_id=type_id,
            quarter_id=quarter_id,
            keyword=keyword,
            industries_id=industries_id,
            composition_id=composition_id,
            start=start,
            page_size=page_size,
        )

        async with AsyncDataFetcher(config=self.config) as fetcher:
            response = await self._search_page(fetcher, body, language)
            if enrich:
                await self._enrich_items(fetcher, response.items, language)
            return response

    async def fetch_earnings_calls_raw(
        self,
        *,
        type_id: int = 1,
        quarter_id: int = 0,
        keyword: str | None = None,
        industries_id: str | None = None,
        composition_id: int | None = None,
        start: int = 1,
        page_size: int = 12,
        language: str = "en",
    ) -> dict[str, Any]:
        """Fetch one page as a raw dict (no Pydantic validation).

        Returns:
            The raw JSON object from the API.

        Raises:
            ValueError: If ``start``/``page_size`` are out of range or ``language`` is invalid.
            ResponseParseError: If the response is not a JSON object.
        """
        language = normalize_language(language)
        body = self._build_search_body(
            type_id=type_id,
            quarter_id=quarter_id,
            keyword=keyword,
            industries_id=industries_id,
            composition_id=composition_id,
            start=start,
            page_size=page_size,
        )
        url = f"{self.base_url}{SET_EARNINGS_CALL_SEARCH_ENDPOINT}"
        headers = _build_earnings_call_headers(language)

        async with AsyncDataFetcher(config=self.config) as fetcher:
            data: Any = await fetcher.fetch_json(
                url, headers=headers, method="POST", json_body=body
            )
            # Guard the documented dict return type explicitly (asserts are stripped under -O).
            if not isinstance(data, dict):
                raise ResponseParseError(
                    f"Expected a JSON object for set earnings-call search, "
                    f"got {type(data).__name__}"
                )
            logger.debug(f"Raw response keys: {list(data.keys())}")
            return data

    async def fetch_all_earnings_calls(
        self,
        *,
        type_id: int = 1,
        quarter_id: int = 0,
        keyword: str | None = None,
        industries_id: str | None = None,
        composition_id: int | None = None,
        start: int = 1,
        page_size: int = 50,
        language: str = "en",
        enrich: bool = False,
        max_records: int | None = None,
        max_pages: int | None = None,
        throttle: float = 0.3,
    ) -> EarningsCallResponse:
        """Auto-paginate across pages, bounded and polite.

        Reuses a single fetcher across pages and sleeps ``throttle`` seconds between page
        requests. Stops at the first short/empty page, once ``no_records`` is reached, or when
        a cap is hit.

        Args:
            max_records: Stop once this many items have been accumulated (then truncate).
            max_pages: Stop after this many pages.
            throttle: Delay in seconds between page requests (0 disables).
            (Other args mirror :meth:`fetch_earnings_calls`.)

        Returns:
            An :class:`EarningsCallResponse` with the accumulated items and the API's
            ``no_records`` total.

        Raises:
            ValueError: If ``max_records``/``max_pages`` are set but < 1, or other inputs are
                invalid.
        """
        language = normalize_language(language)
        if max_records is not None and max_records < 1:
            raise ValueError(f"max_records must be >= 1 when set, got {max_records}")
        if max_pages is not None and max_pages < 1:
            raise ValueError(f"max_pages must be >= 1 when set, got {max_pages}")

        items: list[EarningsCallItem] = []
        no_records = 0
        page = start
        pages_fetched = 0

        async with AsyncDataFetcher(config=self.config) as fetcher:
            while True:
                body = self._build_search_body(
                    type_id=type_id,
                    quarter_id=quarter_id,
                    keyword=keyword,
                    industries_id=industries_id,
                    composition_id=composition_id,
                    start=page,
                    page_size=page_size,
                )
                response = await self._search_page(fetcher, body, language)
                no_records = response.no_records
                items.extend(response.items)
                pages_fetched += 1

                if max_records is not None and len(items) >= max_records:
                    break
                if max_pages is not None and pages_fetched >= max_pages:
                    break
                if not response.items or len(response.items) < page_size:
                    break
                if len(items) >= no_records:
                    break

                page += 1
                if throttle > 0:
                    await asyncio.sleep(throttle)

            if max_records is not None:
                items = items[:max_records]
            if enrich:
                await self._enrich_items(fetcher, items, language)

        logger.info(
            f"Fetched {len(items)} earnings-call item(s) across {pages_fetched} page(s) "
            f"(no_records={no_records})"
        )
        return EarningsCallResponse(no_records=no_records, items=items)

    async def _fetch_detail(
        self, fetcher: AsyncDataFetcher, item_id: int, language: str
    ) -> EarningsCallDetail:
        """Fetch and validate the detail record for a single item."""
        endpoint = SET_EARNINGS_CALL_DETAIL_ENDPOINT.format(id=item_id)
        url = f"{self.base_url}{endpoint}"
        headers = _build_earnings_call_headers(language)
        data = await fetcher.fetch_json(url, headers=headers)
        return validate_or_raise(
            EarningsCallDetail, data, context=f"set earnings-call detail id={item_id}"
        )

    async def _enrich_items(
        self,
        fetcher: AsyncDataFetcher,
        items: list[EarningsCallItem],
        language: str,
        *,
        concurrency: int = 5,
    ) -> None:
        """Populate ``item.detail`` for each item via bounded-concurrent detail fetches.

        A failed detail fetch is logged and tolerated (that item keeps ``detail=None``); it
        never fails the whole batch.
        """
        if not items:
            return

        semaphore = asyncio.Semaphore(concurrency)

        async def _attach(item: EarningsCallItem) -> None:
            async with semaphore:
                try:
                    item.detail = await self._fetch_detail(fetcher, item.id, language)
                except Exception as exc:  # noqa: BLE001 - tolerate one bad detail, keep the row
                    logger.warning(
                        f"Failed to enrich earnings-call item id={item.id} ({item.symbol}): {exc}"
                    )

        await asyncio.gather(*(_attach(item) for item in items))

    async def _fetch_filter(self, name: str, language: str = "en") -> list[FilterOption]:
        """Fetch a single filter endpoint and validate it into a list of options."""
        language = normalize_language(language)
        endpoint = SET_EARNINGS_CALL_FILTER_ENDPOINT.format(name=name)
        url = f"{self.base_url}{endpoint}"
        headers = _build_earnings_call_headers(language)

        async with AsyncDataFetcher(config=self.config) as fetcher:
            data = await fetcher.fetch_json(url, headers=headers)
            return validate_list_or_raise(
                FilterOption, data, context=f"set earnings-call filter/{name}"
            )

    async def fetch_filter_types(self, language: str = "en") -> list[FilterOption]:
        """Fetch presentation types (e.g. 1 = Earnings Call/OPPDAY)."""
        return await self._fetch_filter("types", language)

    async def fetch_filter_years(self, language: str = "en") -> list[FilterOption]:
        """Fetch quarter/year filter options (ids usable as ``quarter_id``)."""
        return await self._fetch_filter("years", language)

    async def fetch_filter_industries(self, language: str = "en") -> list[FilterOption]:
        """Fetch industry filter options (string codes usable as ``industries_id``)."""
        return await self._fetch_filter("industries", language)

    async def fetch_filter_markets(self, language: str = "en") -> list[FilterOption]:
        """Fetch market filter options (e.g. SET / mai / LiVEx)."""
        return await self._fetch_filter("markets", language)

    async def fetch_filter_themes(self, language: str = "en") -> list[FilterOption]:
        """Fetch theme filter options (e.g. SET50, SET100, SETESG)."""
        return await self._fetch_filter("themes", language)

    async def fetch_filter_trusts(self, language: str = "en") -> list[FilterOption]:
        """Fetch trust/security-kind filter options (e.g. Common Stock, REIT)."""
        return await self._fetch_filter("trusts", language)

    async def fetch_filter_stages(self, language: str = "en") -> list[FilterOption]:
        """Fetch stage filter options (e.g. Upcoming, Live, Video)."""
        return await self._fetch_filter("stages", language)


async def get_earnings_calls(
    *,
    type_id: int = 1,
    quarter_id: int = 0,
    keyword: str | None = None,
    industries_id: str | None = None,
    composition_id: int | None = None,
    start: int = 1,
    page_size: int = 12,
    language: str = "en",
    enrich: bool = False,
    config: FetcherConfig | None = None,
) -> EarningsCallResponse:
    """Convenience: fetch one page of earnings-call entries.

    Example:
        >>> from settfex.services.set import get_earnings_calls
        >>> response = await get_earnings_calls(keyword="HANN")
        >>> for item in response.items:
        ...     print(item.symbol, item.company_name_clean, item.youtube_url)
    """
    service = EarningsCallService(config=config)
    return await service.fetch_earnings_calls(
        type_id=type_id,
        quarter_id=quarter_id,
        keyword=keyword,
        industries_id=industries_id,
        composition_id=composition_id,
        start=start,
        page_size=page_size,
        language=language,
        enrich=enrich,
    )


async def get_earnings_calls_dataframe(
    *,
    type_id: int = 1,
    quarter_id: int = 0,
    keyword: str | None = None,
    industries_id: str | None = None,
    composition_id: int | None = None,
    start: int = 1,
    page_size: int = 12,
    language: str = "en",
    columns: list[str] | None = None,
    config: FetcherConfig | None = None,
) -> "pd.DataFrame":
    """Convenience: fetch one page and return it as a pandas DataFrame.

    Defaults to the five columns ``stock_name, company_name, earnings_call_date,
    video_clip_time, youtube_url``. For the full calendar, use
    :meth:`EarningsCallService.fetch_all_earnings_calls` then :meth:`to_dataframe`.

    Requires pandas (``pip install settfex[dataframe]``).

    Example:
        >>> from settfex.services.set import get_earnings_calls_dataframe
        >>> df = await get_earnings_calls_dataframe()
        >>> list(df.columns)
        ['stock_name', 'company_name', 'earnings_call_date', 'video_clip_time', 'youtube_url']
    """
    response = await get_earnings_calls(
        type_id=type_id,
        quarter_id=quarter_id,
        keyword=keyword,
        industries_id=industries_id,
        composition_id=composition_id,
        start=start,
        page_size=page_size,
        language=language,
        config=config,
    )
    return response.to_dataframe(columns=columns)
