"""Tests for the SET Earnings Call (Opportunity Day) calendar service.

All HTTP is mocked (the suite runs offline). Fixtures are built from the real payloads
captured in the opportunity-day HAR.
"""

import sys
from datetime import date, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from settfex.services.set.earnings_call import (
    EarningsCallDetail,
    EarningsCallItem,
    EarningsCallResponse,
    EarningsCallService,
    FilterOption,
    fetch_transcripts,
    get_all_earnings_calls,
    get_earnings_call_detail,
    get_earnings_call_transcript,
    get_earnings_calls,
    get_earnings_calls_dataframe,
)
from settfex.utils.parsing import ResponseParseError

# --- payloads from the real HAR ------------------------------------------------------------

MOCK_ITEM = {
    "id": 10647,
    "name": "การนำเสนอข้อมูลงบการเงิน ผลการดำเนินงานประจำ Q1/2026",
    "company_name": "HANN: MUKDAHAN INTERNATIONAL HOSPITAL PUBLIC COMPANY LIMITED",
    "industry": "Services",
    "symbol": "HANN",
    "image_path": "https://img.youtube.com/vi/qCw7HH77f0U/mqdefault.jpg",
    "view_mode": True,
    "meeting_date": "2026-06-05T00:00:00Z",
    "period": "45:00",
}
MOCK_ITEM_2 = {
    "id": 10646,
    "name": "OPPDAY ACE",
    "company_name": "ACE: ABSOLUTE CLEAN ENERGY PUBLIC COMPANY LIMITED",
    "industry": "Resources",
    "symbol": "ACE",
    "image_path": "https://img.youtube.com/vi/H-lEE0CWmXg/mqdefault.jpg",
    "view_mode": True,
    "meeting_date": "2026-06-04T00:00:00Z",
    "period": "25:51",
}
# Upcoming item with no recording: null image_path/period (null youtube).
MOCK_UPCOMING = {
    "id": 99,
    "name": "OPPDAY PTT",
    "company_name": "PTT: PTT PUBLIC COMPANY LIMITED",
    "industry": "Resources",
    "symbol": "PTT",
    "image_path": None,
    "view_mode": False,
    "meeting_date": "2026-07-01T00:00:00Z",
    "period": None,
}
MOCK_PAGE = {"no_records": 9520, "items": [MOCK_ITEM, MOCK_ITEM_2]}

MOCK_DETAIL = {
    "id": 10647,
    "year": 2026,
    "round": 1,
    "round_name": "Q1/2026",
    "type_id": 1,
    "type": "Earnings Call (OPPDAY)",
    "company_name": "HANN: MUKDAHAN INTERNATIONAL HOSPITAL PUBLIC COMPANY LIMITED",
    "company_name_th": "HANN: บริษัท โรงพยาบาลมุกดาหารอินเตอร์เนชั่นแนล จำกัด (มหาชน)",
    "description": "การนำเสนอข้อมูลงบการเงิน",
    "meeting_date": "2026-06-05T00:00:00Z",
    "period": "16:15 - 17:00",
    "symbol": "HANN",
    "video_link": "https://www.youtube.com/embed/qCw7HH77f0U?",
    "image_path": "https://img.youtube.com/vi/qCw7HH77f0U/maxresdefault.jpg",
    "document_link": "/file/presentation/10647",
    "snapshot_link": "https://example.com/snapshot.html",
    "has_qa": True,
}
MOCK_TYPES = [
    {"id": 1, "name": "Earnings Call (OPPDAY)"},
    {"id": 3, "name": "C-Sign Public Presentation"},
    {"id": 2, "name": "Digital Roadshow"},
]
MOCK_INDUSTRIES = [
    {"id": "AGRO", "name": "Agro & Food Industry"},
    {"id": "SERVICE", "name": "Services"},
]


@pytest.fixture
def mock_fetcher() -> Any:
    """Patch AsyncDataFetcher inside the service module and yield its async instance."""
    with patch("settfex.services.set.earnings_call.AsyncDataFetcher") as mock:
        fetcher_instance = AsyncMock()
        mock.return_value.__aenter__.return_value = fetcher_instance
        mock.return_value.__aexit__.return_value = None
        yield fetcher_instance


# --- models --------------------------------------------------------------------------------


class TestModels:
    def test_item_parsing_and_derived_fields(self) -> None:
        item = EarningsCallItem.model_validate(MOCK_ITEM)
        assert item.symbol == "HANN"
        assert item.company_name_clean == "MUKDAHAN INTERNATIONAL HOSPITAL PUBLIC COMPANY LIMITED"
        assert item.youtube_video_id == "qCw7HH77f0U"
        assert item.youtube_url == "https://www.youtube.com/watch?v=qCw7HH77f0U"

    def test_meeting_date_is_tz_aware_utc(self) -> None:
        item = EarningsCallItem.model_validate(MOCK_ITEM)
        assert isinstance(item.meeting_date, datetime)
        offset = item.meeting_date.utcoffset()
        assert offset is not None and offset.total_seconds() == 0  # tz-aware UTC
        assert item.meeting_date.date() == date(2026, 6, 5)

    def test_company_name_clean_with_special_symbol(self) -> None:
        # "88TH" contains digits; literal-prefix strip must still work.
        item = EarningsCallItem.model_validate(
            {
                **MOCK_ITEM,
                "symbol": "88TH",
                "company_name": "88TH: 88(THAILAND) PUBLIC COMPANY LIMITED",
            }
        )
        assert item.company_name_clean == "88(THAILAND) PUBLIC COMPANY LIMITED"

    def test_company_name_clean_without_prefix(self) -> None:
        item = EarningsCallItem.model_validate({**MOCK_ITEM, "company_name": "NO PREFIX COMPANY"})
        assert item.company_name_clean == "NO PREFIX COMPANY"

    def test_youtube_none_when_no_recording(self) -> None:
        item = EarningsCallItem.model_validate(MOCK_UPCOMING)
        assert item.youtube_video_id is None
        assert item.youtube_url is None
        assert item.period is None

    def test_youtube_none_for_non_youtube_image(self) -> None:
        item = EarningsCallItem.model_validate(
            {**MOCK_ITEM, "image_path": "https://example.com/thumb.jpg"}
        )
        assert item.youtube_video_id is None
        assert item.youtube_url is None

    def test_youtube_none_for_empty_image(self) -> None:
        item = EarningsCallItem.model_validate({**MOCK_ITEM, "image_path": ""})
        assert item.youtube_url is None

    def test_detail_period_is_aliased_to_meeting_time(self) -> None:
        detail = EarningsCallDetail.model_validate(MOCK_DETAIL)
        # The list's `period` is a duration; the detail's `period` is a clock-time range and
        # must surface separately (never overwriting the list duration).
        assert detail.meeting_time == "16:15 - 17:00"
        assert detail.company_name_th is not None
        assert detail.company_name_th.startswith("HANN:")
        assert detail.video_link == "https://www.youtube.com/embed/qCw7HH77f0U?"

    def test_detail_derives_youtube_from_image_path(self) -> None:
        detail = EarningsCallDetail.model_validate(MOCK_DETAIL)
        assert detail.youtube_video_id == "qCw7HH77f0U"
        assert detail.youtube_url == "https://www.youtube.com/watch?v=qCw7HH77f0U"
        # no image_path -> None
        assert EarningsCallDetail.model_validate({"id": 1}).youtube_url is None

    def test_detail_cleans_malformed_video_link(self) -> None:
        # Some legacy records (e.g. vdo/6319) embed a stray newline mid-URL.
        detail = EarningsCallDetail.model_validate(
            {
                "id": 6319,
                "video_link": "https://www.youtube.com/embed/eOC0S8A4QEE\n?",
                "image_path": "https://img.youtube.com/vi/eOC0S8A4QEE/maxresdefault.jpg",
            }
        )
        assert detail.video_link == "https://www.youtube.com/embed/eOC0S8A4QEE?"
        # youtube_url comes from the clean image_path, never the malformed video_link
        assert detail.youtube_url == "https://www.youtube.com/watch?v=eOC0S8A4QEE"

    def test_filter_option_id_types(self) -> None:
        assert FilterOption.model_validate({"id": 1, "name": "x"}).id == 1
        assert FilterOption.model_validate({"id": "SERVICE", "name": "Services"}).id == "SERVICE"

    def test_response_count(self) -> None:
        resp = EarningsCallResponse.model_validate(MOCK_PAGE)
        assert resp.count == 2
        assert resp.no_records == 9520

    def test_industry_can_be_null(self) -> None:
        # Newly-listed companies (e.g. ISTORE22) come back with industry=null in the OPPDAY
        # list; this must not fail validation (regression: large page_size / deep pages).
        item = EarningsCallItem.model_validate({**MOCK_ITEM, "industry": None})
        assert item.industry is None
        # derived fields and the DataFrame still work with a null industry
        assert item.youtube_url == "https://www.youtube.com/watch?v=qCw7HH77f0U"
        resp = EarningsCallResponse.model_validate(
            {"no_records": 1, "items": [{**MOCK_ITEM, "industry": None}]}
        )
        df = resp.to_dataframe(columns=["stock_name", "industry"])
        assert df.iloc[0]["industry"] is None


# --- to_dataframe --------------------------------------------------------------------------


class TestToDataFrame:
    def test_default_columns_order_and_values(self) -> None:
        resp = EarningsCallResponse.model_validate(
            {"no_records": 2, "items": [MOCK_ITEM, MOCK_UPCOMING]}
        )
        df = resp.to_dataframe()
        assert list(df.columns) == [
            "stock_name",
            "company_name",
            "earnings_call_date",
            "video_clip_time",
            "youtube_url",
        ]
        row0 = df.iloc[0].to_dict()
        assert row0["stock_name"] == "HANN"
        assert row0["company_name"] == "MUKDAHAN INTERNATIONAL HOSPITAL PUBLIC COMPANY LIMITED"
        assert isinstance(row0["earnings_call_date"], date)
        assert row0["video_clip_time"] == "45:00"
        assert row0["youtube_url"] == "https://www.youtube.com/watch?v=qCw7HH77f0U"
        # upcoming row: null youtube + null duration
        row1 = df.iloc[1].to_dict()
        assert row1["youtube_url"] is None
        assert row1["video_clip_time"] is None

    def test_custom_columns(self) -> None:
        resp = EarningsCallResponse.model_validate(MOCK_PAGE)
        df = resp.to_dataframe(columns=["id", "youtube_video_id", "company_name_raw"])
        assert list(df.columns) == ["id", "youtube_video_id", "company_name_raw"]
        assert df.iloc[0]["id"] == 10647
        assert df.iloc[0]["company_name_raw"].startswith("HANN:")

    def test_unknown_column_raises(self) -> None:
        resp = EarningsCallResponse.model_validate(MOCK_PAGE)
        with pytest.raises(ValueError, match="Unknown DataFrame column"):
            resp.to_dataframe(columns=["stock_name", "does_not_exist"])

    def test_empty_result_has_columns(self) -> None:
        resp = EarningsCallResponse.model_validate({"no_records": 0, "items": []})
        df = resp.to_dataframe()
        assert len(df) == 0
        assert list(df.columns) == [
            "stock_name",
            "company_name",
            "earnings_call_date",
            "video_clip_time",
            "youtube_url",
        ]

    def test_pandas_missing_raises_importerror(self, monkeypatch: pytest.MonkeyPatch) -> None:
        resp = EarningsCallResponse.model_validate(MOCK_PAGE)
        monkeypatch.setitem(sys.modules, "pandas", None)
        with pytest.raises(ImportError, match="settfex\\[dataframe\\]"):
            resp.to_dataframe()


# --- single-page fetch ---------------------------------------------------------------------


class TestFetchEarningsCalls:
    @pytest.mark.asyncio
    async def test_fetch_success(self, mock_fetcher: Any) -> None:
        mock_fetcher.fetch_json.return_value = MOCK_PAGE
        resp = await EarningsCallService().fetch_earnings_calls()
        assert isinstance(resp, EarningsCallResponse)
        assert resp.count == 2
        assert resp.items[0].symbol == "HANN"

    @pytest.mark.asyncio
    async def test_body_construction(self, mock_fetcher: Any) -> None:
        mock_fetcher.fetch_json.return_value = MOCK_PAGE
        await EarningsCallService().fetch_earnings_calls(
            type_id=2, quarter_id=20262, keyword="hann", page_size=20, start=3
        )
        kwargs = mock_fetcher.fetch_json.call_args.kwargs
        assert kwargs["method"] == "POST"
        body = kwargs["json_body"]
        assert body["type_id"] == 2
        assert body["quarter_id"] == 20262
        assert body["keyword"] == "HANN"  # normalized via normalize_symbol
        assert body["page_size"] == 20
        assert body["start"] == 3

    @pytest.mark.asyncio
    async def test_language_drives_accept_language(self, mock_fetcher: Any) -> None:
        mock_fetcher.fetch_json.return_value = MOCK_PAGE
        await EarningsCallService().fetch_earnings_calls(language="th")
        headers = mock_fetcher.fetch_json.call_args.kwargs["headers"]
        assert headers["Accept-Language"].startswith("th")

    @pytest.mark.asyncio
    async def test_invalid_page_size_raises(self, mock_fetcher: Any) -> None:
        with pytest.raises(ValueError, match="page_size"):
            await EarningsCallService().fetch_earnings_calls(page_size=0)

    @pytest.mark.asyncio
    async def test_invalid_start_raises(self, mock_fetcher: Any) -> None:
        with pytest.raises(ValueError, match="start"):
            await EarningsCallService().fetch_earnings_calls(start=0)

    @pytest.mark.asyncio
    async def test_invalid_language_raises(self, mock_fetcher: Any) -> None:
        with pytest.raises(ValueError, match="language"):
            await EarningsCallService().fetch_earnings_calls(language="xx")  # type: ignore[arg-type]  # intentional: runtime-permissive language


class TestFetchRaw:
    @pytest.mark.asyncio
    async def test_raw_returns_dict(self, mock_fetcher: Any) -> None:
        mock_fetcher.fetch_json.return_value = MOCK_PAGE
        raw = await EarningsCallService().fetch_earnings_calls_raw()
        assert isinstance(raw, dict)
        assert raw["no_records"] == 9520

    @pytest.mark.asyncio
    async def test_raw_rejects_non_dict(self, mock_fetcher: Any) -> None:
        mock_fetcher.fetch_json.return_value = ["unexpected", "list"]
        with pytest.raises(ResponseParseError, match="earnings-call search"):
            await EarningsCallService().fetch_earnings_calls_raw()


# --- pagination ----------------------------------------------------------------------------


class TestFetchAll:
    @pytest.mark.asyncio
    async def test_stops_on_short_page(self, mock_fetcher: Any) -> None:
        pages = {
            1: {"no_records": 3, "items": [MOCK_ITEM, MOCK_ITEM_2]},
            2: {"no_records": 3, "items": [MOCK_UPCOMING]},
        }

        def dispatch(url: str, *a: Any, **k: Any) -> Any:
            return pages[k["json_body"]["start"]]

        mock_fetcher.fetch_json.side_effect = dispatch
        resp = await EarningsCallService().fetch_all_earnings_calls(page_size=2, throttle=0)
        assert resp.count == 3
        assert resp.no_records == 3
        assert mock_fetcher.fetch_json.call_count == 2

    @pytest.mark.asyncio
    async def test_stops_at_no_records(self, mock_fetcher: Any) -> None:
        # Every page is full (2 items) but no_records caps the crawl at 4.
        def dispatch(url: str, *a: Any, **k: Any) -> Any:
            return {"no_records": 4, "items": [MOCK_ITEM, MOCK_ITEM_2]}

        mock_fetcher.fetch_json.side_effect = dispatch
        resp = await EarningsCallService().fetch_all_earnings_calls(page_size=2, throttle=0)
        assert resp.count == 4
        assert mock_fetcher.fetch_json.call_count == 2

    @pytest.mark.asyncio
    async def test_max_records_cap(self, mock_fetcher: Any) -> None:
        def dispatch(url: str, *a: Any, **k: Any) -> Any:
            return {"no_records": 100, "items": [MOCK_ITEM, MOCK_ITEM_2]}

        mock_fetcher.fetch_json.side_effect = dispatch
        resp = await EarningsCallService().fetch_all_earnings_calls(
            page_size=2, max_records=3, throttle=0
        )
        assert resp.count == 3  # truncated
        assert mock_fetcher.fetch_json.call_count == 2

    @pytest.mark.asyncio
    async def test_max_pages_cap(self, mock_fetcher: Any) -> None:
        def dispatch(url: str, *a: Any, **k: Any) -> Any:
            return {"no_records": 100, "items": [MOCK_ITEM, MOCK_ITEM_2]}

        mock_fetcher.fetch_json.side_effect = dispatch
        resp = await EarningsCallService().fetch_all_earnings_calls(
            page_size=2, max_pages=2, throttle=0
        )
        assert resp.count == 4
        assert mock_fetcher.fetch_json.call_count == 2

    @pytest.mark.asyncio
    async def test_invalid_caps_raise(self, mock_fetcher: Any) -> None:
        with pytest.raises(ValueError, match="max_records"):
            await EarningsCallService().fetch_all_earnings_calls(max_records=0, throttle=0)
        with pytest.raises(ValueError, match="max_pages"):
            await EarningsCallService().fetch_all_earnings_calls(max_pages=0, throttle=0)


# --- enrichment ----------------------------------------------------------------------------


class TestEnrich:
    @pytest.mark.asyncio
    async def test_enrich_attaches_detail(self, mock_fetcher: Any) -> None:
        page = {"no_records": 2, "items": [MOCK_ITEM, MOCK_UPCOMING]}

        def dispatch(url: str, *a: Any, **k: Any) -> Any:
            if url.endswith("/search/archive"):
                return page
            if url.endswith("/vdo/10647"):
                return MOCK_DETAIL
            if url.endswith("/vdo/99"):
                return {"id": 99, "period": "10:00 - 11:00", "symbol": "PTT"}
            raise AssertionError(f"unexpected url {url}")

        mock_fetcher.fetch_json.side_effect = dispatch
        resp = await EarningsCallService().fetch_earnings_calls(enrich=True)
        by_id = {item.id: item for item in resp.items}
        assert by_id[10647].detail is not None
        assert by_id[10647].detail.meeting_time == "16:15 - 17:00"
        assert by_id[99].detail is not None
        assert by_id[99].detail.meeting_time == "10:00 - 11:00"

    @pytest.mark.asyncio
    async def test_enrich_tolerates_detail_failure(self, mock_fetcher: Any) -> None:
        page = {"no_records": 2, "items": [MOCK_ITEM, MOCK_UPCOMING]}

        def dispatch(url: str, *a: Any, **k: Any) -> Any:
            if url.endswith("/search/archive"):
                return page
            if url.endswith("/vdo/10647"):
                return MOCK_DETAIL
            raise ResponseParseError("detail boom")

        mock_fetcher.fetch_json.side_effect = dispatch
        resp = await EarningsCallService().fetch_earnings_calls(enrich=True)
        by_id = {item.id: item for item in resp.items}
        assert by_id[10647].detail is not None  # succeeded
        assert by_id[99].detail is None  # failed but tolerated


# --- filter helpers ------------------------------------------------------------------------


class TestFilters:
    @pytest.mark.asyncio
    async def test_fetch_filter_types(self, mock_fetcher: Any) -> None:
        mock_fetcher.fetch_json.return_value = MOCK_TYPES
        options = await EarningsCallService().fetch_filter_types()
        assert [o.id for o in options] == [1, 3, 2]
        assert options[0].name == "Earnings Call (OPPDAY)"

    @pytest.mark.asyncio
    async def test_fetch_filter_industries_string_ids(self, mock_fetcher: Any) -> None:
        mock_fetcher.fetch_json.return_value = MOCK_INDUSTRIES
        options = await EarningsCallService().fetch_filter_industries()
        assert options[0].id == "AGRO"
        assert options[1].id == "SERVICE"

    @pytest.mark.asyncio
    async def test_filter_rejects_non_list(self, mock_fetcher: Any) -> None:
        mock_fetcher.fetch_json.return_value = {"unexpected": "object"}
        with pytest.raises(ResponseParseError, match="filter/markets"):
            await EarningsCallService().fetch_filter_markets()


# --- error paths ---------------------------------------------------------------------------


class TestErrorPaths:
    @pytest.mark.asyncio
    async def test_fetch_propagates_request_error(self, mock_fetcher: Any) -> None:
        mock_fetcher.fetch_json.side_effect = Exception("HTTP 500")
        with pytest.raises(Exception, match="HTTP 500"):
            await EarningsCallService().fetch_earnings_calls()

    @pytest.mark.asyncio
    async def test_fetch_propagates_parse_error(self, mock_fetcher: Any) -> None:
        mock_fetcher.fetch_json.side_effect = ResponseParseError("bad json")
        with pytest.raises(ResponseParseError):
            await EarningsCallService().fetch_earnings_calls()

    @pytest.mark.asyncio
    async def test_empty_items(self, mock_fetcher: Any) -> None:
        mock_fetcher.fetch_json.return_value = {"no_records": 0, "items": []}
        resp = await EarningsCallService().fetch_earnings_calls()
        assert resp.count == 0
        assert len(resp.to_dataframe()) == 0


# --- convenience functions -----------------------------------------------------------------


class TestCoverageExtras:
    """Cheap tests for safety-net branches and the thin filter-helper passthroughs."""

    def test_meeting_date_naive_assumed_utc(self) -> None:
        # If the API ever omits the offset, the validator must attach UTC.
        item = EarningsCallItem.model_validate({**MOCK_ITEM, "meeting_date": "2026-06-05T00:00:00"})
        offset = item.meeting_date.utcoffset()
        assert offset is not None and offset.total_seconds() == 0

    @pytest.mark.asyncio
    async def test_enrich_empty_items_is_noop(self, mock_fetcher: Any) -> None:
        mock_fetcher.fetch_json.return_value = {"no_records": 0, "items": []}
        resp = await EarningsCallService().fetch_earnings_calls(enrich=True)
        assert resp.count == 0

    @pytest.mark.asyncio
    async def test_fetch_all_with_enrich(self, mock_fetcher: Any) -> None:
        def dispatch(url: str, *a: Any, **k: Any) -> Any:
            if url.endswith("/search/archive"):
                return {"no_records": 1, "items": [MOCK_ITEM]}
            return MOCK_DETAIL

        mock_fetcher.fetch_json.side_effect = dispatch
        resp = await EarningsCallService().fetch_all_earnings_calls(
            page_size=2, enrich=True, throttle=0
        )
        assert resp.items[0].detail is not None
        assert resp.items[0].detail.meeting_time == "16:15 - 17:00"

    @pytest.mark.parametrize(
        "method_name",
        [
            "fetch_filter_types",
            "fetch_filter_years",
            "fetch_filter_industries",
            "fetch_filter_markets",
            "fetch_filter_themes",
            "fetch_filter_trusts",
            "fetch_filter_stages",
        ],
    )
    @pytest.mark.asyncio
    async def test_all_filter_helpers(self, mock_fetcher: Any, method_name: str) -> None:
        mock_fetcher.fetch_json.return_value = MOCK_TYPES
        options = await getattr(EarningsCallService(), method_name)()
        assert len(options) == 3
        assert isinstance(options[0], FilterOption)


class TestDetailById:
    @pytest.mark.asyncio
    async def test_fetch_earnings_call_detail(self, mock_fetcher: Any) -> None:
        mock_fetcher.fetch_json.return_value = MOCK_DETAIL
        detail = await EarningsCallService().fetch_earnings_call_detail(10647)
        assert isinstance(detail, EarningsCallDetail)
        assert detail.id == 10647
        assert detail.symbol == "HANN"
        assert detail.meeting_time == "16:15 - 17:00"
        assert detail.youtube_url == "https://www.youtube.com/watch?v=qCw7HH77f0U"
        # GET hits the /investor/vdo/{id} endpoint
        assert mock_fetcher.fetch_json.call_args.args[0].endswith("/investor/vdo/10647")

    @pytest.mark.asyncio
    async def test_get_earnings_call_detail(self, mock_fetcher: Any) -> None:
        mock_fetcher.fetch_json.return_value = MOCK_DETAIL
        detail = await get_earnings_call_detail(10647)
        assert isinstance(detail, EarningsCallDetail)
        assert detail.id == 10647

    @pytest.mark.asyncio
    async def test_fetch_detail_invalid_language(self, mock_fetcher: Any) -> None:
        with pytest.raises(ValueError, match="language"):
            await EarningsCallService().fetch_earnings_call_detail(10647, language="xx")  # type: ignore[arg-type]  # intentional: runtime-permissive language


def _paged(no_records: int, per_page: int) -> Any:
    """side_effect: return `per_page` items per page, ids encoded as start*100+i (order check)."""

    def dispatch(url: str, *a: Any, **k: Any) -> Any:
        start = k["json_body"]["start"]
        return {
            "no_records": no_records,
            "items": [{**MOCK_ITEM, "id": start * 100 + i} for i in range(per_page)],
        }

    return dispatch


class TestFetchAllConcurrency:
    @pytest.mark.asyncio
    async def test_concurrent_pagination_in_order(self, mock_fetcher: Any) -> None:
        mock_fetcher.fetch_json.side_effect = _paged(no_records=6, per_page=2)
        resp = await EarningsCallService().fetch_all_earnings_calls(page_size=2, max_concurrency=4)
        assert resp.count == 6
        # pages reassembled in order despite concurrent fetching
        assert [it.id for it in resp.items] == [100, 101, 200, 201, 300, 301]
        assert mock_fetcher.fetch_json.call_count == 3  # 1 first + 2 concurrent

    @pytest.mark.asyncio
    async def test_max_concurrency_respected(self, mock_fetcher: Any) -> None:
        import asyncio

        state = {"live": 0, "peak": 0}

        async def dispatch(url: str, *a: Any, **k: Any) -> Any:
            start = k["json_body"]["start"]
            state["live"] += 1
            state["peak"] = max(state["peak"], state["live"])
            await asyncio.sleep(0.02)
            state["live"] -= 1
            return {
                "no_records": 20,
                "items": [{**MOCK_ITEM, "id": start * 100 + i} for i in range(2)],
            }

        mock_fetcher.fetch_json.side_effect = dispatch
        await EarningsCallService().fetch_all_earnings_calls(page_size=2, max_concurrency=3)
        assert state["peak"] <= 3

    @pytest.mark.asyncio
    async def test_invalid_max_concurrency(self, mock_fetcher: Any) -> None:
        with pytest.raises(ValueError, match="max_concurrency"):
            await EarningsCallService().fetch_all_earnings_calls(max_concurrency=0)

    @pytest.mark.asyncio
    async def test_progress_callback(self, mock_fetcher: Any) -> None:
        mock_fetcher.fetch_json.side_effect = _paged(no_records=6, per_page=2)
        seen: list[tuple[int, int]] = []
        await EarningsCallService().fetch_all_earnings_calls(
            page_size=2, progress_callback=lambda d, t: seen.append((d, t))
        )
        assert seen[-1] == (6, 6)
        assert all(seen[i][0] <= seen[i + 1][0] for i in range(len(seen) - 1))

    @pytest.mark.asyncio
    async def test_progress_bar_uses_tqdm(self, mock_fetcher: Any) -> None:
        mock_fetcher.fetch_json.side_effect = _paged(no_records=4, per_page=2)
        bar = MagicMock()
        with patch("tqdm.auto.tqdm", return_value=bar) as tqdm_ctor:
            await EarningsCallService().fetch_all_earnings_calls(page_size=2, progress=True)
        assert tqdm_ctor.called
        assert bar.update.called
        assert bar.close.called

    @pytest.mark.asyncio
    async def test_progress_without_tqdm_falls_back(
        self, mock_fetcher: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_fetcher.fetch_json.side_effect = _paged(no_records=4, per_page=2)
        # Make `from tqdm.auto import tqdm` fail.
        monkeypatch.setitem(sys.modules, "tqdm", None)
        monkeypatch.setitem(sys.modules, "tqdm.auto", None)
        resp = await EarningsCallService().fetch_all_earnings_calls(page_size=2, progress=True)
        assert resp.count == 4  # still returns full data via the log fallback

    @pytest.mark.asyncio
    async def test_fetch_all_enrich_progress(self, mock_fetcher: Any) -> None:
        def dispatch(url: str, *a: Any, **k: Any) -> Any:
            if url.endswith("/search/archive"):
                return {"no_records": 1, "items": [MOCK_ITEM]}
            return MOCK_DETAIL

        mock_fetcher.fetch_json.side_effect = dispatch
        seen: list[tuple[int, int]] = []
        resp = await EarningsCallService().fetch_all_earnings_calls(
            page_size=2, enrich=True, progress_callback=lambda d, t: seen.append((d, t))
        )
        assert resp.items[0].detail is not None
        assert (1, 1) in seen  # both phases reported


class TestTranscripts:
    _PATCH = "settfex.services.set.earnings_call.fetch_youtube_transcript"

    @pytest.mark.asyncio
    async def test_fetch_transcripts_attaches_and_skips(self) -> None:
        with_video = EarningsCallItem.model_validate(MOCK_ITEM)  # has youtube_video_id
        no_video = EarningsCallItem.model_validate(MOCK_UPCOMING)  # image_path None

        async def fake(video_id: str, **k: Any) -> str:
            return f"TXT[{video_id}]"

        with patch(self._PATCH, side_effect=fake):
            out = await fetch_transcripts([with_video, no_video])
        assert out[0].transcript == "TXT[qCw7HH77f0U]"
        assert out[1].transcript is None  # no video -> skipped

    @pytest.mark.asyncio
    async def test_fetch_transcripts_tolerates_failure(self) -> None:
        a = EarningsCallItem.model_validate(MOCK_ITEM)
        b = EarningsCallItem.model_validate(MOCK_ITEM_2)

        async def fake(video_id: str, **k: Any) -> str:
            if video_id == a.youtube_video_id:
                raise RuntimeError("blocked")
            return "OK"

        with patch(self._PATCH, side_effect=fake):
            out = await fetch_transcripts([a, b])
        assert out[0].transcript is None  # failed but tolerated
        assert out[1].transcript == "OK"

    @pytest.mark.asyncio
    async def test_fetch_transcripts_progress(self) -> None:
        items = [
            EarningsCallItem.model_validate(MOCK_ITEM),
            EarningsCallItem.model_validate(MOCK_ITEM_2),
        ]
        seen: list[tuple[int, int]] = []

        async def fake(video_id: str, **k: Any) -> str:
            return "x"

        with patch(self._PATCH, side_effect=fake):
            await fetch_transcripts(items, progress_callback=lambda d, t: seen.append((d, t)))
        assert seen[-1] == (2, 2)

    @pytest.mark.asyncio
    async def test_fetch_transcripts_no_videos_is_noop(self) -> None:
        out = await fetch_transcripts([EarningsCallItem.model_validate(MOCK_UPCOMING)])
        assert out[0].transcript is None

    @pytest.mark.asyncio
    async def test_get_earnings_call_transcript(self, mock_fetcher: Any) -> None:
        mock_fetcher.fetch_json.return_value = MOCK_DETAIL  # has image_path -> youtube_video_id

        async def fake(video_id: str, **k: Any) -> str:
            return "THAI TEXT"

        with patch(self._PATCH, side_effect=fake):
            text = await get_earnings_call_transcript(10647)
        assert text == "THAI TEXT"

    @pytest.mark.asyncio
    async def test_get_earnings_call_transcript_no_video(self, mock_fetcher: Any) -> None:
        mock_fetcher.fetch_json.return_value = {"id": 1}  # no image_path -> no youtube video
        assert await get_earnings_call_transcript(1) is None


class TestGetAllConvenience:
    @pytest.mark.asyncio
    async def test_get_all_earnings_calls(self, mock_fetcher: Any) -> None:
        mock_fetcher.fetch_json.side_effect = _paged(no_records=4, per_page=2)
        resp = await get_all_earnings_calls(page_size=2)
        assert isinstance(resp, EarningsCallResponse)
        assert resp.count == 4


class TestConvenience:
    @pytest.mark.asyncio
    async def test_get_earnings_calls(self, mock_fetcher: Any) -> None:
        mock_fetcher.fetch_json.return_value = MOCK_PAGE
        resp = await get_earnings_calls(keyword="HANN")
        assert isinstance(resp, EarningsCallResponse)
        assert resp.count == 2

    @pytest.mark.asyncio
    async def test_get_earnings_calls_dataframe(self, mock_fetcher: Any) -> None:
        mock_fetcher.fetch_json.return_value = MOCK_PAGE
        df = await get_earnings_calls_dataframe()
        assert list(df.columns) == [
            "stock_name",
            "company_name",
            "earnings_call_date",
            "video_clip_time",
            "youtube_url",
        ]
        assert len(df) == 2
