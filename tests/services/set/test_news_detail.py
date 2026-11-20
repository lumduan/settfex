"""SET news detail (0.30.0): one item's record, including the attachment's URL.

The endpoint (``/api/set/news/{id}/detail?symbol=&lang=``) is not linked from any index. It was
found in the site's own bundle (``getNewsDetail``) and live-verified on 2026-11-20 against CPALL's
Q3/2569 statement items. Thai and English are separate items with separate ids, each linking its
own language's zip. Payloads below are the live ones; only ``content`` (an HTML disclaimer) is cut
short.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from settfex.exceptions import FetchError, NewsNotFoundError, NotFoundError
from settfex.services.set import NewsDetail, get_news_detail
from settfex.services.set.news import NewsItem, NewsService
from settfex.utils.data_fetcher import FetchResponse
from settfex.utils.parsing import ResponseParseError

CONTENT = '<strong style="text-decoration: underline;">Disclaimer</strong>\nThis announcement…'
EN: dict[str, Any] = {
    "id": "17943525757510",
    "datetime": "2026-11-11T17:00:00+07:00",
    "symbol": "CPALL",
    "source": "CPALL",
    "headline": "Financial Statement Quarter 3/2026 (Reviewed)",
    "tag": "financial-statement",
    "downloadUrl": "https://weblink.set.or.th/dat/news/202611/0737FIN111120261328040207E.zip",
    "fileType": "ZIP",
    "content": CONTENT,
}
TH: dict[str, Any] = {
    **EN,
    "id": "17943525757301",
    "headline": "งบการเงิน ไตรมาสที่ 3/2569 (สอบทานแล้ว)",
    "downloadUrl": "https://weblink.set.or.th/dat/news/202611/0737FIN111120261328030954T.zip",
}
MDA: dict[str, Any] = {
    **EN,
    "id": "107584300",
    "datetime": "2026-11-11T17:14:00+07:00",
    "headline": "Management Discussion and Analysis Quarter 3 Ending 30 Sep 2026",
    "tag": "",
    "downloadUrl": "https://weblink.set.or.th/dat/news/202611/0737NWS111120261714435360E.pdf",
    "fileType": "PDF",
}


def _response(body: Any, status: int = 200) -> FetchResponse:
    text = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
    return FetchResponse(
        status_code=status,
        content=text.encode("utf-8"),
        text=text,
        headers={},
        url="https://www.set.or.th/api/set/news/x/detail",
        elapsed=0.1,
    )


@pytest.fixture
def fetcher() -> Any:
    with patch("settfex.services.set.news.AsyncDataFetcher") as cls:
        instance = AsyncMock()
        cls.return_value.__aenter__.return_value = instance
        cls.return_value.__aexit__.return_value = None
        cls.get_set_api_headers = Mock(side_effect=lambda referer: {"Referer": referer})
        instance.cls = cls
        yield instance


class TestTheModel:
    def test_the_live_payload_parses_and_file_path_is_secs_fileid(self) -> None:
        detail = NewsDetail.model_validate(TH)
        assert detail.id == "17943525757301"
        assert detail.tag == "financial-statement"
        assert detail.file_type == "ZIP"
        assert detail.news_datetime.isoformat() == "2026-11-11T17:00:00+07:00"
        assert detail.file_path == "dat/news/202611/0737FIN111120261328030954T.zip"

    def test_file_path_survives_model_dump(self) -> None:
        dumped = NewsDetail.model_validate(EN).model_dump(mode="json")
        assert dumped["file_path"] == "dat/news/202611/0737FIN111120261328040207E.zip"
        assert dumped["download_url"] == EN["downloadUrl"], "the URL is kept verbatim"

    @pytest.mark.parametrize(
        "url", [None, "", "https://example.com/dat/news/x.zip"], ids=["none", "empty", "other-host"]
    )
    def test_no_attachment_or_another_host_has_no_file_path(self, url: str | None) -> None:
        assert NewsDetail.model_validate({**EN, "downloadUrl": url}).file_path is None

    def test_a_non_statement_item_has_its_attachment_too(self) -> None:
        detail = NewsDetail.model_validate(MDA)
        assert (detail.tag, detail.file_type) == ("", "PDF")
        assert detail.file_path == "dat/news/202611/0737NWS111120261714435360E.pdf"


class TestTheRequest:
    @pytest.mark.asyncio
    async def test_an_id_builds_the_endpoint_url(self, fetcher: Any) -> None:
        fetcher.fetch.return_value = _response(EN)
        detail = await get_news_detail("17943525757510", symbol="cpall")
        url = fetcher.fetch.call_args.args[0]
        assert url == (
            "https://www.set.or.th/api/set/news/17943525757510/detail?symbol=CPALL&lang=en"
        )
        assert detail.download_url == EN["downloadUrl"]
        referer = fetcher.cls.get_set_api_headers.call_args.kwargs["referer"]
        assert referer.startswith("https://www.set.or.th/en/market/news-and-alert/newsdetails?id=")

    @pytest.mark.asyncio
    async def test_a_news_item_supplies_its_own_id_symbol_and_language(self, fetcher: Any) -> None:
        fetcher.fetch.return_value = _response(TH)
        item = NewsItem.model_validate(
            {
                "id": "17943525757301",
                "datetime": "2026-11-11T17:00:00+07:00",
                "symbol": "CPALL",
                "source": "CPALL",
                "url": "https://www.set.or.th/th/market/news-and-alert/newsdetails?id=17943525757301&symbol=CPALL",
                "headline": TH["headline"],
                "isTodayNews": False,
                "tag": "financial-statement",
                "product": "S",
                "lang": "th",
            }
        )  # fmt: skip
        detail = await NewsService().fetch_news_detail(item)
        assert fetcher.fetch.call_args.args[0].endswith(
            "/api/set/news/17943525757301/detail?symbol=CPALL&lang=th"
        )
        assert detail.file_path is not None and detail.file_path.endswith("T.zip")

    @pytest.mark.asyncio
    async def test_the_symbol_is_optional(self, fetcher: Any) -> None:
        fetcher.fetch.return_value = _response(EN)
        await get_news_detail("17943525757510")
        assert fetcher.fetch.call_args.args[0].endswith("/17943525757510/detail?lang=en")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad", ["", "  ", "abc", "1/../2", "17943525757510?x=1"])
    async def test_a_non_numeric_id_is_refused_before_any_request(
        self, fetcher: Any, bad: str
    ) -> None:
        with pytest.raises(ValueError):
            await get_news_detail(bad)
        fetcher.fetch.assert_not_called()


class TestTheErrors:
    @pytest.mark.asyncio
    async def test_an_unknown_id_is_news_not_found(self, fetcher: Any) -> None:
        fetcher.fetch.return_value = _response(
            {"message": "Invalid News [99999999999999] "}, status=404
        )
        with pytest.raises(NewsNotFoundError) as excinfo:
            await get_news_detail("99999999999999")
        exc = excinfo.value
        assert (exc.news_id, exc.status_code) == ("99999999999999", 404)
        assert isinstance(exc, NotFoundError) and isinstance(exc, FetchError)

    @pytest.mark.asyncio
    async def test_another_status_is_a_fetch_error_not_a_not_found(self, fetcher: Any) -> None:
        fetcher.fetch.return_value = _response("busy", status=503)
        with pytest.raises(FetchError) as excinfo:
            await get_news_detail("17943525757510")
        assert not isinstance(excinfo.value, NotFoundError)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("body", [{}, [], "not json"], ids=["empty-object", "array", "text"])
    async def test_an_unusable_body_raises_a_parse_error(self, fetcher: Any, body: Any) -> None:
        fetcher.fetch.return_value = _response(body)
        with pytest.raises(ResponseParseError):
            await get_news_detail("17943525757510")

    @pytest.mark.asyncio
    async def test_raw_returns_the_dict_and_refuses_a_non_object(self, fetcher: Any) -> None:
        fetcher.fetch.return_value = _response(EN)
        assert await NewsService().fetch_news_detail_raw("17943525757510") == EN
        fetcher.fetch.return_value = _response([EN])
        with pytest.raises(ResponseParseError):
            await NewsService().fetch_news_detail_raw("17943525757510")
