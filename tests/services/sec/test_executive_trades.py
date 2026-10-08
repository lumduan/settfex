"""Tests for SEC Form 59 (แบบ 59): the executive-trade listing and its detail reports.

Every fixture under ``fixtures_sec/r59/`` is a real response from the 2026-10-07 probe, sliced or
copied verbatim (two are *assembled* from verbatim rows; see ``fixtures_sec/README.md``). The
transport is faked at ``AsyncDataFetcher.fetch``, so the fetcher's JSON wrapper, every parser and
every model stay real.
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest

from settfex.exceptions import (
    CompanyNotFoundError,
    FetchError,
    HTTPStatusError,
    InvalidDateError,
    ParseError,
)
from settfex.services.sec import executive_trades as et
from settfex.services.sec.company import CompanyMatch
from settfex.services.sec.executive_trades import (
    ExecutiveTrade,
    ExecutiveTradeDetail,
    ExecutiveTradeList,
    ExecutiveTradeQuery,
    fetch_executive_trades_raw,
    get_executive_trade_report,
    get_executive_trades,
    side_for,
)
from settfex.utils.data_fetcher import AsyncDataFetcher, FetchResponse
from settfex.utils.parsing import BlockedError

R59 = Path(__file__).parent / "fixtures_sec" / "r59"
BANGKOK = ZoneInfo("Asia/Bangkok")


def page(name: str) -> str:
    return (R59 / name).read_text(encoding="utf-8")


def parse(name: str, lang: et.Language = "th") -> list[ExecutiveTrade]:
    _, rows = et._parse_listing(page(name), name, lang)
    items = [et._trade_from_raw(r) for r in rows]
    et._mark_duplicates(items)
    return items


def by_tid(items: list[ExecutiveTrade]) -> dict[str, ExecutiveTrade]:
    return {t.trans_id: t for t in items if t.trans_id}


def _resp(body: str, status: int = 200, ctype: str = "text/html; charset=utf-8") -> FetchResponse:
    data = body.encode("utf-8")
    return FetchResponse(
        status_code=status,
        content=data,
        text=body,
        headers={"Content-Type": ctype},
        url="https://market.sec.or.th/",
        elapsed=0.1,
    )


class FakeSec:
    """Answers ViewMore GETs with a listing (a fixture name, or HTML) and detail POSTs with JSON."""

    def __init__(
        self,
        listing: str | None = None,
        *,
        details: dict[str, str] | None = None,
        lang: str = "th",
        detail_error: type[Exception] | None = FetchError,
    ) -> None:
        self.listing = listing
        self.details = details or {}
        self.lang = lang
        self.detail_error = detail_error
        self.urls: list[str] = []
        self.batches: list[str] = []

    async def fetch(self, _fetcher: Any, url: str, headers: Any = None, **kw: Any) -> FetchResponse:
        self.urls.append(url)
        if url.endswith("/r59/publicapi/report"):
            batch = kw["json_body"]["BatchNo"]
            self.batches.append(batch)
            assert kw["json_body"]["Lang"] == self.lang.capitalize()
            if batch in self.details:
                return _resp(self.details[batch], ctype="application/json")
            assert self.detail_error is not None
            raise self.detail_error(f"Failed to fetch {url} after 1 attempts")
        assert "/ViewMore/r59-2?" in url, url
        assert self.listing is not None
        html = self.listing
        return _resp(html if html.lstrip().startswith("<") else page(html))

    def patch(self) -> Any:
        sec = self

        async def fake_fetch(self: Any, url: str, headers: Any = None, **kw: Any) -> FetchResponse:
            return await sec.fetch(self, url, headers, **kw)

        return patch.object(AsyncDataFetcher, "fetch", fake_fetch)


def details(*batches: str, lang: str = "th") -> dict[str, str]:
    return {b: (R59 / f"detail_{b}_{lang}.json").read_text(encoding="utf-8") for b in batches}


SPALI_DETAIL_BATCHES = [
    "592000082610", "592000092610", "592002772609", "592002782609", "592003452609",
    "592003462609", "592004192609", "592004202609", "592004532609", "592004542609",
    "592004992609", "592005002609",
]  # fmt: skip
# The 35 reports behind the 28 September 2026 pairs (every one captured).
PAIR_BATCHES = [
    "592000082610", "592000092610", "592000102610", "592000142610", "592000152610",
    "592000532609", "592000542609", "592001242610", "592001262610", "592001352609",
    "592001372609", "592002622609", "592002632609", "592002772609", "592002782609",
    "592002882609", "592002892609", "592003112609", "592003122609", "592003452609",
    "592003462609", "592003632609", "592003652609", "592004042609", "592004052609",
    "592004192609", "592004202609", "592004532609", "592004542609", "592004802609",
    "592004812609", "592004992609", "592005002609", "592005172609", "592005182609",
]  # fmt: skip

# The pinned outcome of every September 2026 pair: copy -> (original, basis, holding_conflict).
# Rows not listed are originals: (None, None, None). holding_conflict is None whenever a report is
# missing, never False for "unknown". Decided 2026-10-08 (see _mark_duplicates).
ORIGINAL = (None, None, None)
SPALI_COPIES = {
    "164748_2_1": "164747_2_1", "164748_2_2": "164747_2_2", "164843_2_1": "164845_2_1",
    "164938_2_1": "164939_2_1", "164938_2_2": "164939_2_2", "164974_2_1": "164975_2_1",
    "164974_2_2": "164975_2_2", "165022_2_1": "165023_2_1", "165100_2_1": "165102_2_1",
    "165100_2_2": "165102_2_2", "165100_2_3": "165102_2_3",
}  # fmt: skip
STX_COPIES = {
    "164899_2_1": "164897_2_1", "164899_2_2": "164897_2_2", "164899_2_3": "164897_2_3",
    "164953_2_1": "164952_2_1", "164953_2_2": "164952_2_2", "164953_2_3": "164952_2_3",
    "164953_2_4": "164952_2_4",
}  # fmt: skip
CREDIT_COPIES = {"165233_2_1": "165109_2_1", "165233_2_2": "165110_2_1"}
KCG_ROWS = [
    "164499_2_1", "164500_2_1", "164610_2_1", "164612_2_1", "164754_2_1", "164755_2_1",
    "164780_2_1", "164781_2_1", "164804_2_1", "164805_2_1", "164867_2_1", "164868_2_1",
    "165046_2_1", "165047_2_1",
]  # fmt: skip
WITH_DETAILS = {
    **{c: (o, "holdings", False) for c, o in SPALI_COPIES.items()},
    **{c: (o, "holdings", False) for c, o in CREDIT_COPIES.items()},
    **{c: (o, "executor", True) for c, o in STX_COPIES.items()},
}
WITHOUT_DETAILS = {
    **{c: (o, "executor_own_row", None) for c, o in SPALI_COPIES.items()},
    **{c: (o, "executor", None) for c, o in STX_COPIES.items()},
}


def _trade(**overrides: Any) -> ExecutiveTrade:
    base: dict[str, Any] = {
        "symbol": "X",
        "company_name": "X บมจ.(X)",
        "reporter_name": "นาย ก",
        "reporter_id": "CTRL_P_1",
        "executor_id": "CTRL_P_1",
        "executor_name": None,
        "relationship": "ผู้รายงาน",
        "is_self": True,
        "security_type": "หุ้นสามัญ",
        "method": "ซื้อ",
        "side": "buy",
        "transaction_date": date(2026, 9, 30),
        "quantity": 1,
        "price": Decimal("1.00"),
        "is_revoked": False,
        "batch_no": "1",
        "trans_id": "1_2_1",
        "report_url": None,
    }
    base.update(overrides)
    return ExecutiveTrade(**base)


def _list(items: list[ExecutiveTrade], **kw: Any) -> ExecutiveTradeList:
    query = ExecutiveTradeQuery(
        date_type="received", start=date(2026, 10, 1), end=date(2026, 10, 1), windows=1
    )
    return ExecutiveTradeList(
        items=items, reported_count=len(items), query=query, fetched_at=datetime.now(BANGKOK), **kw
    )


# ==================================================================================================
# The listing page
# ==================================================================================================


class TestListingParse:
    def test_the_spali_spouse_copies_are_marked_not_dropped(self) -> None:
        """Both spouses are executives, so each files the same trade: 12 pairs, 24 rows."""
        items = parse("th_spali_txn_202609.html")
        assert len(items) == 24
        rows = by_tid(items)
        copy, own = rows["165100_2_1"], rows["165102_2_1"]
        assert copy.duplicate_of == "165102_2_1" and own.duplicate_of is None
        assert copy.reporter_id == "CTRL_P_0000012061" and copy.executor_id == "CTRL_P_0000012062"
        assert copy.is_self is False and own.is_self is True
        assert copy.reporter_name == "นาง อัจฉรา ตั้งมติธรรม"
        assert copy.executor_name == "นาย ประทีป ตั้งมติธรรม"
        assert copy.relationship == "คู่สมรส/ผู้ที่อยู่กินด้วยกันฉันสามีภริยา"
        assert sum(t.duplicate_of is not None for t in items) == 12
        assert len(_list(items).economic_trades()) == 12

    def test_a_spouse_without_an_executive_id_is_never_a_copy(self) -> None:
        """KCG: the reporter's own row and his spouse's look identical on many days, and are not.

        The detail shows two holdings (2,515,000 -> 2,520,000 and 910,000 -> 915,000); a rule on
        date/quantity/price alone would have merged them.
        """
        items = parse("th_kcg_txn_202609.html")
        assert len(items) == 30
        spouse = by_tid(items)["164755_2_1"]
        assert spouse.executor_id == "TEMP_P_9000001530"
        assert spouse.executor_name == "ดารุณี เพียรพัฒนาวิทย์"
        assert spouse.is_self is False
        assert all(t.duplicate_of is None for t in items)

    def test_a_page_short_of_its_stated_count_is_refused(self) -> None:
        """The search postback renders 100 rows and states 112; returning it would lose 12."""
        with pytest.raises(ParseError, match="states 112 record.*100 row") as info:
            et._parse_listing(page("th_capped_rcv_20261002.html"), "u", "th")
        assert info.value.rows_parsed == 100

    def test_an_empty_result_is_empty_not_an_error(self) -> None:
        assert et._parse_listing(page("th_empty.html"), "u", "th") == (0, [])

    def test_english_page(self) -> None:
        """Same 27 rows as the Thai page; C.E. dates and English labels."""
        en = parse("en_default_20261007.html", "en")
        th = parse("th_default_20261007.html")
        assert len(en) == len(th) == 27
        assert {t.trans_id for t in en} == {t.trans_id for t in th}
        row = by_tid(en)["165194_2_1"]
        assert row.method == "Sale" and row.side == "sell"
        assert row.transaction_date == date(2026, 10, 5)
        assert row.security_type == "Common Share" and row.relationship == "Reporter"
        # Same rows on both pages, same transaction dates after era conversion.
        assert {(t.trans_id, t.transaction_date) for t in en} == {
            (t.trans_id, t.transaction_date) for t in th
        }

    def test_the_unknown_label_count_is_empty_on_real_pages(self) -> None:
        for name, lang in [
            ("th_default_20261007.html", "th"),
            ("en_default_20261007.html", "en"),
            ("th_edge_rows.html", "th"),
        ]:
            items = parse(name, lang)  # type: ignore[arg-type]
            assert _list(items).unknown_labels == {"method": {}, "security_type": {}}, name


@pytest.fixture(scope="module")
def rows() -> list[ExecutiveTrade]:
    return parse("th_edge_rows.html")


class TestEdgeRows:
    """One row per edge the full 91,245-row history holds (an assembled fixture)."""

    def test_revoked_rows_are_kept_and_marked(self, rows: list[ExecutiveTrade]) -> None:
        revoked = by_tid(rows)["165152_2_1"]
        assert revoked.is_revoked is True
        assert revoked.quantity == 20000  # the struck-through figure as filed
        refiled = by_tid(rows)["165153_3_3"]
        assert refiled.is_revoked is False
        assert revoked not in _list(rows).economic_trades()

    def test_prices(self, rows: list[ExecutiveTrade]) -> None:
        assert by_tid(rows)["124877_2_1"].price is None  # '-' on a buy
        assert by_tid(rows)["165135_2_1"].price is None  # '-' on a transfer
        nvdr = next(t for t in rows if t.method == "แปลงจาก NVDR")
        assert nvdr.price == Decimal("0.00") and nvdr.side == "other"

    def test_zero_quantity_and_empty_date(self, rows: list[ExecutiveTrade]) -> None:
        assert by_tid(rows)["103283_2_1"].quantity == 0
        assert by_tid(rows)["162688_2_1"].transaction_date is None

    def test_buddhist_era_leap_day(self, rows: list[ExecutiveTrade]) -> None:
        assert by_tid(rows)["143003_2_1"].transaction_date == date(2024, 2, 29)

    def test_blank_ids_become_none(self, rows: list[ExecutiveTrade]) -> None:
        sanko = by_tid(rows)["124558_2_1"]  # reporter=CTRL_P_ (blank)
        assert sanko.reporter_id is None and sanko.executor_id == "TEMP_P_9000000106"
        assert sanko.is_self is None
        jmart = by_tid(rows)["113332_2_1"]  # executor=" __ "
        assert jmart.executor_id is None
        assert by_tid(rows)["143661_2_1"].executor_id is None  # executor=CTRL_C_ (blank)

    def test_rows_without_a_link(self, rows: list[ExecutiveTrade]) -> None:
        unlinked = [t for t in rows if t.trans_id is None]
        assert len(unlinked) == 8
        assert all(t.batch_no is None and t.report_url is None for t in unlinked)
        assert {t.remark for t in unlinked} >= {"แก้ไขข้อมูล", "รับโอนจาก คุณจินตนา ตั้งพานิชดี"}
        assert next(t for t in unlinked if t.symbol == "BANPU ยุติ").relationship == "ผู้จัดทำ"

    def test_company_and_child_executors(self, rows: list[ExecutiveTrade]) -> None:
        tfg = by_tid(rows)["124623_2_1"]
        assert tfg.executor_id == "CTRL_C_0000022156"
        assert tfg.executor_name == "บริษัท นิวสตาร์ วิคเตอร์ จำกัด"
        child = by_tid(rows)["163814_2_2"]
        assert child.relationship == "บุตรที่ยังไม่บรรลุนิติภาวะ"
        assert child.executor_id == "TEMP_P_9000002831"

    def test_rare_methods_map_to_a_side(self, rows: list[ExecutiveTrade]) -> None:
        sides = {t.method: t.side for t in rows}
        assert sides["รับโอน-คืนจากผู้รับฝาก"] == "transfer_in"
        assert sides["ขาย-เพื่อผู้ฝาก"] == "sell"
        assert sides["โอน"] == "transfer_out"


class TestFailLoud:
    """A cell or layout the parser does not recognise raises; nothing is coerced."""

    def _mutated(self, old: str, new: str, count: int = 1) -> str:
        html = page("th_default_20261007.html")
        assert old in html
        return html.replace(old, new, count)

    def test_unknown_column_layout(self) -> None:
        with pytest.raises(ParseError, match="column layout"):
            et._parse_listing(self._mutated("ประเภทหลักทรัพย์", "ประเภท"), "u", "th")

    def test_bracketed_quantity(self) -> None:
        _, rows = et._parse_listing(self._mutated(">18,200<", ">(18,200)<"), "u", "th")
        bad = next(r for r in rows if r["quantity"] == "(18,200)")
        with pytest.raises(ParseError, match="not a whole number"):
            et._trade_from_raw(bad)

    def test_non_numeric_price(self) -> None:
        _, rows = et._parse_listing(self._mutated(">6.65<", ">6.6x<"), "u", "th")
        bad = next(r for r in rows if r["price"] == "6.6x")
        with pytest.raises(ParseError, match="not a price"):
            et._trade_from_raw(bad)

    def test_malformed_date(self) -> None:
        _, rows = et._parse_listing(self._mutated(">06/10/2569<", ">31/02/2569<"), "u", "th")
        bad = next(r for r in rows if r["transaction_date"] == "31/02/2569")
        with pytest.raises(ParseError, match="dd/mm/yyyy"):
            et._trade_from_raw(bad)

    def test_struck_quantity_with_another_note(self) -> None:
        html = page("th_edge_rows.html").replace("Revoked by Reporter", "Withdrawn", 1)
        _, rows = et._parse_listing(html, "u", "th")
        bad = next(r for r in rows if r["revoked"] == "true")
        with pytest.raises(ParseError, match="revoked-row format changed"):
            et._trade_from_raw(bad)

    def test_a_row_of_the_wrong_width(self) -> None:
        html = self._mutated('<td class="RgCol_Right_Width_10">6.65</td>', "")
        with pytest.raises(ParseError, match="cells"):
            et._parse_listing(html, "u", "th")

    def test_no_table(self) -> None:
        with pytest.raises(ParseError, match="no table"):
            et._parse_listing("<html><body>Service unavailable</body></html>", "u", "th")

    def test_a_heading_without_a_count(self) -> None:
        html = self._mutated("(จำนวนรายการที่พบ 27 รายการ)", "")
        with pytest.raises(ParseError, match="no record count"):
            et._parse_listing(html, "u", "th")

    def test_the_no_data_row_under_a_nonzero_count(self) -> None:
        html = page("th_empty.html").replace(
            "(จำนวนรายการที่พบ 0 รายการ)", "(จำนวนรายการที่พบ 5 รายการ)"
        )
        with pytest.raises(ParseError, match="no-data row"):
            et._parse_listing(html, "u", "th")

    def test_an_unknown_method_is_other_and_counted(self) -> None:
        _, rows = et._parse_listing(self._mutated(">ซื้อ<", ">ซื้อพิเศษ<"), "u", "th")
        items = [et._trade_from_raw(r) for r in rows]
        odd = next(t for t in items if t.method == "ซื้อพิเศษ")
        assert odd.side == "other"
        assert _list(items).unknown_labels["method"] == {"ซื้อพิเศษ": 1}


class TestSides:
    @pytest.mark.parametrize(
        ("method", "side"),
        [
            ("ซื้อ", "buy"),
            ("ขาย", "sell"),
            ("โอน", "transfer_out"),
            ("รับโอน", "transfer_in"),
            ("โอน (โอนให้บุตร)", "transfer_out"),  # the detail API's finer label
            ("Purchase", "buy"),
            ("Sale", "sell"),
            ("Transfer", "transfer_out"),
            ("Acceptance of Transfer", "transfer_in"),
            ("แปลงจาก NVDR", "other"),
            ("something new", "other"),
        ],
    )
    def test_side_for(self, method: str, side: str) -> None:
        assert side_for(method) == side


# ==================================================================================================
# URL builder and windows
# ==================================================================================================


class TestViewMoreUrl:
    def test_refuses_to_build_an_undated_url(self) -> None:
        """Undated, the page returns the whole database: 91,245 rows, 70 MB."""
        for start, end in [(None, date(2026, 1, 1)), (date(2026, 1, 1), None), (None, None)]:
            with pytest.raises(ValueError, match="undated"):
                et._viewmore_url("th", "received", start, end)

    def test_shape(self) -> None:
        url = et._viewmore_url(
            "en", "transaction", date(2023, 10, 8), date(2026, 10, 7), unique_id="0000033922"
        )
        assert url == (
            "https://market.sec.or.th/public/idisc/en/ViewMore/r59-2?UniqueIdReference=0000033922"
            "&DateType=1&DateFrom=20231008&DateTo=20261007"
        )
        assert "DateType=2" in et._viewmore_url(
            "th", "received", date(2026, 1, 1), date(2026, 1, 1)
        )

    def test_rejects_bad_input(self) -> None:
        with pytest.raises(InvalidDateError):
            et._viewmore_url("th", "received", date(2026, 2, 1), date(2026, 1, 1))
        with pytest.raises(ValueError, match="numeric"):
            et._viewmore_url("th", "received", date(2026, 1, 1), date(2026, 1, 1), unique_id="1&x")

    def test_windows_tile_the_range_exactly(self) -> None:
        windows = et._windows(date(2023, 10, 8), date(2026, 10, 7))
        assert len(windows) == 3
        assert windows[0][0] == date(2023, 10, 8) and windows[-1][1] == date(2026, 10, 7)
        for (_, end), (start, _) in zip(windows, windows[1:], strict=False):
            assert (start - end).days == 1
        assert all((e - s).days < 366 for s, e in windows)
        assert et._windows(date(2026, 1, 1), date(2026, 1, 1)) == [
            (date(2026, 1, 1), date(2026, 1, 1))
        ]


# ==================================================================================================
# The service
# ==================================================================================================


class TestGetExecutiveTrades:
    @pytest.mark.asyncio
    async def test_no_arguments_means_received_today(self) -> None:
        sec = FakeSec("th_default_20261007.html")
        with sec.patch(), patch.object(et, "_today", return_value=date(2026, 10, 7)):
            result = await get_executive_trades()
        assert sec.urls == [
            "https://market.sec.or.th/public/idisc/th/ViewMore/r59-2"
            "?DateType=2&DateFrom=20261007&DateTo=20261007"
        ]
        assert len(result) == result.reported_count == 27
        assert all(t.received_date == date(2026, 10, 7) for t in result)
        assert result.query.date_type == "received" and result.query.windows == 1

    @pytest.mark.asyncio
    async def test_symbol_is_resolved_strictly(self) -> None:
        sec = FakeSec("th_spali_txn_202609.html")
        match = CompanyMatch(Text="SUPALAI PUBLIC COMPANY LIMITED", Value="0000001370", Flag=True)
        with sec.patch(), patch.object(et, "resolve_company", AsyncMock(return_value=match)) as rc:
            result = await get_executive_trades(
                symbol="spali", date_type="transaction", start="2026-09-01", end=date(2026, 10, 7)
            )
        rc.assert_awaited_once()
        assert rc.await_args.args[0] == "SPALI"
        assert "UniqueIdReference=0000001370&DateType=1&DateFrom=20260901" in sec.urls[0]
        assert result.query.symbol == "SPALI" and result.query.unique_id == "0000001370"
        assert all(t.received_date is None for t in result)

    @pytest.mark.asyncio
    async def test_an_unknown_symbol_raises(self) -> None:
        with (
            patch.object(et, "resolve_company", AsyncMock(return_value=None)),
            pytest.raises(CompanyNotFoundError),
        ):
            await get_executive_trades(symbol="NOPE")

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"received_date": "2026-10-01", "start": "2026-09-01"},
            {"end": "2026-10-01"},
            {"start": "2026-10-02", "end": "2026-10-01"},
            {"received_date": "01/10/2026"},
            {"date_type": "transaction"},
            {"received_date": "2026-10-01", "date_type": "transaction"},
        ],
    )
    @pytest.mark.asyncio
    async def test_conflicting_or_malformed_dates(self, kwargs: dict[str, Any]) -> None:
        with pytest.raises(InvalidDateError):
            await get_executive_trades(**kwargs)

    @pytest.mark.asyncio
    async def test_a_long_range_is_split_and_every_window_counted(self) -> None:
        sec = FakeSec("th_kcg_txn_202609.html")
        with sec.patch():
            result = await get_executive_trades(start="2023-10-08", end="2026-10-07")
        assert len(sec.urls) == 3 and result.query.windows == 3
        assert result.reported_count == 90 == len(result)

    @pytest.mark.asyncio
    async def test_a_non_2xx_raises(self) -> None:
        async def fake_fetch(self: Any, url: str, headers: Any = None, **kw: Any) -> FetchResponse:
            return _resp("<html>error</html>", status=505)

        with (
            patch.object(AsyncDataFetcher, "fetch", fake_fetch),
            pytest.raises(HTTPStatusError) as info,
        ):
            await get_executive_trades(received_date="2026-10-01")
        assert info.value.status_code == 505 and "ViewMore/r59-2" in (info.value.url or "")

    @pytest.mark.asyncio
    async def test_a_capped_page_raises_through_the_service(self) -> None:
        with FakeSec("th_capped_rcv_20261002.html").patch(), pytest.raises(ParseError):
            await get_executive_trades(received_date="2026-10-02")

    @pytest.mark.asyncio
    async def test_the_raw_tier_keeps_strings_and_link_params(self) -> None:
        with FakeSec("th_edge_rows.html").patch():
            rows = await fetch_executive_trades_raw(date(2026, 1, 1), date(2026, 1, 1))
        revoked = next(r for r in rows if r["transId"] == "165152_2_1")
        assert revoked["revoked"] == "true"
        assert revoked["quantity"] == "20,000"
        assert revoked["quantity_note"] == "Revoked by Reporter"
        assert revoked["reporter"] == revoked["executor"] == "CTRL_P_0000190947"
        assert next(r for r in rows if r["transId"] == "124558_2_1")["reporter"] == "CTRL_P_ "
        assert all(isinstance(v, str) for r in rows for v in r.values())


# ==================================================================================================
# Detail reports
# ==================================================================================================


class TestDetailReport:
    @pytest.mark.asyncio
    async def test_dtcent_reference_values(self) -> None:
        """Human-verified on the site: DTCENT, BatchNo 592001352610."""
        sec = FakeSec(details=details("592001352610"))
        with sec.patch():
            report = await get_executive_trade_report("592001352610")
        assert report.batch_no == "592001352610"
        assert report.company_name == "บริษัท ดี.ที.ซี. เอ็นเตอร์ไพรส์ จำกัด (มหาชน)"
        assert report.symbol is None  # the API does not state it
        assert report.position == "กรรมการ (ประธานกรรมการ)"
        assert report.submitted_at == datetime(2026, 10, 6, 17, 16, 42, tzinfo=BANGKOK)
        assert report.business_type_code == "0106300010"
        [tx] = report.transactions
        assert tx.holding_before == 31_744_180
        assert tx.quantity == 30_300
        assert tx.avg_price == Decimal("0.92")
        assert tx.holding_after == 31_774_480
        assert tx.method == "ซื้อ" and tx.side == "buy"
        assert tx.market_source == (
            "ทำรายการผ่านตลาดหลักทรัพย์ (Auto Matching) (บริษัท หลักทรัพย์เคจีไอ (ประเทศไทย) จำกัด (มหาชน))"
        )
        assert tx.holding_consistent is True
        assert tx.holder_label == "ผู้รายงาน" and tx.counterparty is None

    @pytest.mark.asyncio
    async def test_a_53_transaction_batch_with_a_marked_holding(self) -> None:
        with FakeSec(details=details("592000452610")).patch():
            report = await get_executive_trade_report("592000452610")
        assert len(report.transactions) == 53
        first = report.transactions[0]
        assert first.holding_before == 3_840_000 and first.remark == "holding_before: '*'"
        assert all(t.holding_consistent for t in report.transactions)
        dates = [t.transaction_date for t in report.transactions]
        assert dates == sorted(d for d in dates if d is not None)  # the API orders by date
        assert {t.side for t in report.transactions} == {"buy", "sell"}

    @pytest.mark.asyncio
    async def test_an_off_market_transfer_names_its_counterparty(self) -> None:
        with FakeSec(details=details("592000392610")).patch():
            [tx] = (await get_executive_trade_report("592000392610")).transactions
        assert tx.method == "โอน (โอนให้บุตร)" and tx.side == "transfer_out"
        assert tx.avg_price == Decimal("0.00")
        assert tx.counterparty == "นายชานน ศุภสาธิตกุล และนายชยานน ศุภสาธิตกุล (บุตร)"
        assert tx.market_source.startswith("ทำรายการนอกตลาดหลักทรัพย์")
        assert tx.holding_consistent is True

    @pytest.mark.asyncio
    async def test_english(self) -> None:
        sec = FakeSec(details=details("592001432610", lang="en"), lang="en")
        with sec.patch():
            report = await get_executive_trade_report("592001432610", lang="en")
        assert report.lang == "en"
        assert report.submitted_at == datetime(2026, 10, 7, 8, 47, 38, tzinfo=BANGKOK)
        assert report.transactions[0].method == "Purchase"
        assert report.transactions[0].side == "buy"

    def test_holding_consistent_flags_a_mismatch(self) -> None:
        tx = ExecutiveTradeDetail(
            holder_label="ผู้รายงาน",
            executor="ผู้รายงาน",
            security_type="หุ้นสามัญ",
            transaction_date=date(2026, 10, 6),
            holding_before=100,
            quantity=10,
            avg_price=Decimal("1.00"),
            holding_after=100,
            method="ซื้อ",
            side="buy",
            market_source="m",
            counterparty=None,
            record_status="NORMAL",
        )
        assert tx.holding_consistent is False
        assert tx.model_copy(update={"holding_after": 110}).holding_consistent is True

    @pytest.mark.asyncio
    async def test_envelope_errors(self) -> None:
        cases = [
            ('{"ResponseStatus": {"Value": "N", "TextEn": "none"}}', FetchError, "ResponseStatus"),
            ("{}", ParseError, "envelope"),
            ('{"ResponseStatus": {"Value": "Y"}, "Report": {}}', ParseError, "TransactionList"),
        ]
        for body, kind, text in cases:
            with FakeSec(details={"1": body}).patch(), pytest.raises(kind, match=text):
                await get_executive_trade_report("1")
        other = details("592001352610")["592001352610"]
        with (
            FakeSec(details={"999": other}).patch(),
            pytest.raises(ParseError, match="answered batch"),
        ):
            await get_executive_trade_report("999")

    @pytest.mark.asyncio
    async def test_a_batch_number_is_digits(self) -> None:
        with pytest.raises(ValueError, match="digits"):
            await get_executive_trade_report("59200135261O")


# ==================================================================================================
# Enrichment: with_details=True
# ==================================================================================================


class TestWithDetails:
    @pytest.mark.asyncio
    async def test_one_request_per_batch_and_a_partial_failure_is_reported(self) -> None:
        """12 of the SPALI listing's 14 batches were captured; the other 2 fail here."""
        sec = FakeSec("th_spali_txn_202609.html", details=details(*SPALI_DETAIL_BATCHES))
        with sec.patch():
            result = await get_executive_trades(
                date_type="transaction", start="2026-09-01", end="2026-10-07", with_details=True
            )
        assert len(sec.batches) == len(set(sec.batches)) == 14
        assert set(result.detail_failures) == {"592000892610", "592000902610"}
        assert len(result.reports) == 12
        assert all(r.symbol == "SPALI" for r in result.reports)
        linked = [t for t in result if t.detail is not None]
        failed_rows = [t for t in result if t.batch_no in result.detail_failures]
        assert len(failed_rows) == 2 and all(t.detail is None for t in failed_rows)
        assert len(linked) == 22 and result.detail_unmatched == 2
        assert all(t.detail.trans_id == t.trans_id for t in linked if t.detail)
        assert result.duplicate_count == 12
        bases = {t.duplicate_basis for t in result if t.duplicate_of}
        assert bases == {"holdings", "executor_own_row"}  # holdings where both reports came
        copy = next(t for t in result if t.trans_id == "165100_2_1")
        assert (copy.duplicate_of, copy.duplicate_basis) == ("165102_2_1", "holdings")
        assert copy.detail is not None and copy.detail.holding_before == 701_197_455

    @pytest.mark.asyncio
    async def test_all_28_september_pairs_with_details(self) -> None:
        """SPALI 11 and CREDIT 2 are copies by holdings; STX 7 by executor, holdings in conflict.

        KCG 7 and CREDIT's same-reporter pair (165104_2_1 / 165237_3_1) stay separate trades.
        """
        sec = FakeSec("th_sep_pairs.html", details=details(*PAIR_BATCHES))
        with sec.patch():
            result = await get_executive_trades(received_date="2026-10-01", with_details=True)
        assert len(result) == 58 and result.detail_unmatched == 0
        outcome = {
            t.trans_id: (t.duplicate_of, t.duplicate_basis, t.holding_conflict) for t in result
        }
        for trans_id, got in outcome.items():
            assert got == WITH_DETAILS.get(trans_id, ORIGINAL), trans_id
        assert outcome["165104_2_1"] == outcome["165237_3_1"] == ORIGINAL
        assert all(outcome[t] == ORIGINAL for t in KCG_ROWS)
        stx = next(t for t in result if t.trans_id == "164899_2_1")
        assert stx.detail is not None and stx.detail.holding_before == 37_900_050
        assert result.duplicate_count == 20

    def test_all_28_september_pairs_without_details(self) -> None:
        """Without reports: SPALI by executor_own_row, STX by executor, conflict unknown (None)."""
        items = parse("th_sep_pairs.html")
        outcome = {
            t.trans_id: (t.duplicate_of, t.duplicate_basis, t.holding_conflict) for t in items
        }
        for trans_id, got in outcome.items():
            assert got == WITHOUT_DETAILS.get(trans_id, ORIGINAL), trans_id
        assert sum(t.duplicate_of is not None for t in items) == 18

    @pytest.mark.asyncio
    async def test_a_cancelled_transaction_is_not_a_trade(self) -> None:
        """CREDIT batch 592001242610 re-files 01/10 13,000 twice; the report marks both CANCELED.

        The two transactions are identical in every field, so they link (any pairing attaches the
        same data) even though their key repeats. Both rows are revoked in the listing as well.
        """
        sec = FakeSec("th_sep_pairs.html", details=details(*PAIR_BATCHES))
        with sec.patch():
            result = await get_executive_trades(received_date="2026-10-01", with_details=True)
        cancelled = [t for t in result if t.trans_id in ("165233_2_3", "165233_2_4")]
        assert [t.detail.record_status for t in cancelled if t.detail] == ["CANCELED", "CANCELED"]
        economic = {t.trans_id for t in result.economic_trades()}
        assert not economic & {"165233_2_3", "165233_2_4"}
        # A row the listing still shows live but its report cancels is not a trade either.
        live = cancelled[0].model_copy(update={"is_revoked": False, "trans_id": "x"})
        both = _list([live, _trade(trans_id="y")])
        assert [t.trans_id for t in both.economic_trades()] == ["y"]
        assert "นาย ศุภชัย" not in both.to_table() and "นาย ศุภชัย" in both.to_table(
            include_revoked=True
        )

    @pytest.mark.asyncio
    async def test_over_the_batch_cap_nothing_is_sent(self) -> None:
        sec = FakeSec("th_spali_txn_202609.html", details=details(*SPALI_DETAIL_BATCHES))
        with (
            sec.patch(),
            patch.object(et, "SEC_R59_MAX_DETAIL_BATCHES", 13),
            pytest.raises(ValueError, match="14 detail requests"),
        ):
            await get_executive_trades(received_date="2026-10-01", with_details=True)
        assert sec.batches == []

    @pytest.mark.asyncio
    async def test_a_block_page_stops_at_once(self) -> None:
        sec = FakeSec("th_spali_txn_202609.html", detail_error=BlockedError)
        with sec.patch(), pytest.raises(BlockedError):
            await get_executive_trades(received_date="2026-10-01", with_details=True)
        assert len(sec.batches) == 1

    @pytest.mark.asyncio
    async def test_when_every_detail_fails_the_call_raises(self) -> None:
        sec = FakeSec("th_sep_pairs.html")
        with sec.patch(), pytest.raises(FetchError) as info:
            await get_executive_trades(received_date="2026-10-01", with_details=True)
        assert "All 35 Form 59 detail requests failed." in (info.value.__notes__ or [])


# ==================================================================================================
# The container
# ==================================================================================================


class TestContainer:
    def test_slicing_and_the_computed_counts(self) -> None:
        lst = _list(parse("th_edge_rows.html"))
        part = lst[:3]
        assert isinstance(part, ExecutiveTradeList) and len(part) == 3
        assert part.query == lst.query and part.reported_count == lst.reported_count
        assert isinstance(lst[0], ExecutiveTrade)
        dumped = lst.model_dump(mode="json")
        assert dumped["revoked_count"] == 1
        assert dumped["unknown_labels"] == {"method": {}, "security_type": {}}
        assert dumped["items"][0]["price"] == "8.95"
        json.dumps(dumped)  # serializes

    def test_economic_trades_drops_revoked_and_copies(self) -> None:
        items = [
            _trade(trans_id="a"),
            _trade(trans_id="b", is_revoked=True),
            _trade(trans_id="c", duplicate_of="a"),
        ]
        assert [t.trans_id for t in _list(items).economic_trades()] == ["a"]

    def test_to_table_matches_the_spec(self) -> None:
        """The four rows of the agreed rendering, in rule order (sells, buys; then by symbol)."""
        rows = [
            _trade(
                symbol="WHAIR",
                reporter_name="นาย ไกรลักขณ์ อัศวฉัตรโรจน์",
                method="ขาย",
                side="sell",
                quantity=50_000,
                price=Decimal("8.45"),
                security_type="หน่วยทรัสต์",
            ),
            _trade(
                symbol="PANEL",
                reporter_name="นาง จูเลีย ดับเบิ้ลยู เพ็ชญไพศิษฎ์",
                method="ขาย",
                side="sell",
                quantity=920_000,
                price=Decimal("0.08"),
                security_type="ใบสำคัญแสดงสิทธิที่จะซื้อหุ้น",
                transaction_date=date(2026, 9, 29),
            ),
            _trade(
                symbol="KCG",
                reporter_name="นาย ทรงธรรม เพียรพัฒนาวิทย์",
                executor_id="TEMP_P_9000001530",
                is_self=False,
                quantity=5_000,
                price=Decimal("9.95"),
            ),
            _trade(
                symbol="SPALI",
                reporter_name="นาง อัจฉรา ตั้งมติธรรม",
                executor_id="CTRL_P_0000012062",
                is_self=False,
                quantity=500_000,
                price=Decimal("16.00"),
                transaction_date=date(2026, 9, 29),
            ),
            _trade(symbol="ZZZ", is_revoked=True),
        ]
        assert _list(rows).to_table() == "\n".join(
            [
                "| หลักทรัพย์ | ชื่อผู้บริหาร | รายการ | จำนวน | ราคา | ประเภท | วันที่ |",
                "|---|---|---|---|---|---|---|",
                "| PANEL | นาง จูเลีย ดับเบิ้ลยู เพ็ชญไพศิษฎ์ | ขาย | 920,000 | 0.08 | Warrant | 29/09/2569 |",
                "| WHAIR | นาย ไกรลักขณ์ อัศวฉัตรโรจน์ | ขาย | 50,000 | 8.45 | หน่วยทรัสต์ | 30/09/2569 |",
                "| KCG | นาย ทรงธรรม เพียรพัฒนาวิทย์** | ซื้อ | 5,000 | 9.95 | หุ้นสามัญ | 30/09/2569 |",
                "| SPALI | นาง อัจฉรา ตั้งมติธรรม** | ซื้อ | 500,000 | 16.00 | หุ้นสามัญ | 29/09/2569 |",
            ]
        )
        assert "ZZZ" in _list(rows).to_table(include_revoked=True)

    def test_to_table_with_details(self) -> None:
        detail = ExecutiveTradeDetail(
            holder_label="ผู้รายงาน",
            executor="ผู้รายงาน",
            security_type="หุ้นสามัญ",
            transaction_date=date(2026, 9, 16),
            holding_before=80_000,
            quantity=30_000,
            avg_price=Decimal("8.7333"),
            holding_after=110_000,
            method="ซื้อ",
            side="buy",
            market_source="ทำรายการผ่านตลาดหลักทรัพย์ (Auto Matching)",
            counterparty=None,
            record_status="NORMAL",
        )
        table = _list([_trade(detail=detail), _trade(trans_id="2")]).to_table(with_details=True)
        lines = table.splitlines()
        assert lines[0].endswith("| ถือก่อน | ถือหลัง | ราคาเฉลี่ย | ทำรายการผ่าน |")
        assert "| 80,000 | 110,000 | 8.7333 | ทำรายการผ่านตลาดหลักทรัพย์ (Auto Matching) |" in lines[2]
        assert lines[3].endswith("| - | - | - | - |")

    def test_to_dataframe(self) -> None:
        pytest.importorskip("pandas")
        frame = _list(parse("th_sep_pairs.html")).to_dataframe()
        assert len(frame) == 58 and {"holding_before", "duplicate_basis"} <= set(frame.columns)
        assert frame["price"].dtype.kind == "f"
        assert list(_list([]).to_dataframe(["symbol"]).columns) == ["symbol"]
        with pytest.raises(ValueError, match="Unknown DataFrame column"):
            _list([]).to_dataframe(["nope"])

    def test_to_dataframe_without_pandas(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sys.modules, "pandas", None)
        with pytest.raises(ImportError, match=r"settfex\[dataframe\]"):
            _list([]).to_dataframe()


class TestRemainingBranches:
    """The less travelled paths: each one is a way the site could change under us."""

    def test_a_nested_table_is_refused(self) -> None:
        html = page("th_default_20261007.html").replace(
            ">Link<", "><table><tr><td>x</td></tr></table><", 1
        )
        with pytest.raises(ParseError, match="nested table"):
            et._parse_listing(html, "u", "th")

    def test_a_company_cell_without_a_symbol(self) -> None:
        _, rows = et._parse_listing(page("th_default_20261007.html"), "u", "th")
        with pytest.raises(ParseError, match=r"no \(SYMBOL\)"):
            et._trade_from_raw({**rows[0], "company": "บริษัท ไม่มีสัญลักษณ์"})

    def test_split_last_group(self) -> None:
        assert et._split_last_group("a (b (c) d)") == ("a", "b (c) d")
        assert et._split_last_group("plain") == ("plain", None)
        assert et._split_last_group("unbalanced)") == ("unbalanced)", None)

    @pytest.mark.parametrize(
        ("mutate", "match"),
        [
            (lambda r: r.pop("Position"), "header field"),
            (lambda r: r["TransactionList"][0].pop("AvgPrice"), "transaction without"),
            (lambda r: r.update(SubmitDate="2026-10-06"), "SubmitDate"),
            (lambda r: r.update(SubmitDate="31/02/2569 10:00:00"), "valid date"),
            (lambda r: r["TransactionList"][0].update(OutstandingBefore="n/a"), "whole number"),
        ],
    )
    def test_malformed_detail_fields(self, mutate: Any, match: str) -> None:
        payload = json.loads(details("592001352610")["592001352610"])
        mutate(payload["Report"])
        with pytest.raises(ParseError, match=match):
            et._report_from_raw(et._check_report_payload(payload, "592001352610"), "th")

    def test_a_dash_price_links_to_a_zero_detail_price(self) -> None:
        """HENG: the listing shows '-' where the report files 0.00 for a transfer."""
        items = parse("th_edge_rows.html")
        payload = json.loads(details("592000392610")["592000392610"])
        report = et._report_from_raw(et._check_report_payload(payload, "592000392610"), "th")
        et._link_details(items, [report])
        heng = by_tid(items)["165135_2_1"]
        assert heng.price is None and heng.detail is not None
        assert heng.detail.counterparty is not None and report.symbol == "HENG"

    def test_a_report_by_another_reporter_is_not_linked(self) -> None:
        items = parse("th_edge_rows.html")
        payload = json.loads(details("592000392610")["592000392610"])
        payload["Report"]["Reporter"] = "นาย คนอื่น"
        report = et._report_from_raw(et._check_report_payload(payload, "592000392610"), "th")
        et._link_details(items, [report])
        assert by_tid(items)["165135_2_1"].detail is None

    def test_other_side_holding_check_accepts_either_direction(self) -> None:
        base = {
            "holder_label": "ผู้รายงาน", "executor": "ผู้รายงาน", "security_type": "หุ้นสามัญ",
            "transaction_date": None, "quantity": 5, "avg_price": Decimal("0"), "method": "แปลงจาก NVDR",
            "side": "other", "market_source": "m", "counterparty": None, "record_status": "NORMAL",
        }  # fmt: skip
        assert ExecutiveTradeDetail(**base, holding_before=10, holding_after=5).holding_consistent
        assert ExecutiveTradeDetail(**base, holding_before=10, holding_after=15).holding_consistent
        assert not ExecutiveTradeDetail(
            **base, holding_before=10, holding_after=11
        ).holding_consistent

    def test_to_table_falls_back_on_the_label_when_an_id_is_missing(self) -> None:
        rows = [
            _trade(symbol="A", is_self=None, relationship="ผู้จัดทำ"),
            _trade(symbol="B", is_self=None, relationship="คู่สมรส"),
        ]
        table = _list(rows).to_table()
        assert "| A | นาย ก |" in table and "| B | นาย ก** |" in table

    def test_the_url_builder_rejects_an_unknown_date_type(self) -> None:
        with pytest.raises(ValueError, match="date_type"):
            et._viewmore_url("th", "recorded", date(2026, 1, 1), date(2026, 1, 1))  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_start_alone_runs_to_today_and_datetimes_are_dates(self) -> None:
        sec = FakeSec("th_empty.html")
        with sec.patch(), patch.object(et, "_today", return_value=date(2026, 10, 7)):
            result = await get_executive_trades(start=datetime(2026, 10, 1, 9, 30))
        assert "DateFrom=20261001&DateTo=20261007" in sec.urls[0]
        assert len(result) == 0 and result.query.end == date(2026, 10, 7)

    @pytest.mark.asyncio
    async def test_unknown_labels_are_logged(self) -> None:
        html = page("th_default_20261007.html").replace(">ซื้อ<", ">ซื้อพิเศษ<", 1)
        with FakeSec(html).patch(), patch.object(et.logger, "warning") as warn:
            result = await get_executive_trades(received_date="2026-10-07")
        assert result.unknown_labels["method"] == {"ซื้อพิเศษ": 1}
        assert "outside the known vocabulary" in warn.call_args.args[0]

    def test_the_own_row_shape_with_conflicting_holdings_is_merged_and_flagged(self) -> None:
        """The executor's own row and another reporter's, holdings different: merged, flagged."""
        detail = {
            "holder_label": "x", "executor": "x", "security_type": "หุ้นสามัญ",
            "transaction_date": date(2026, 9, 30), "quantity": 1, "avg_price": Decimal("1.00"),
            "method": "ซื้อ", "side": "buy", "market_source": "m", "counterparty": None,
            "record_status": "NORMAL",
        }  # fmt: skip
        copy = _trade(
            trans_id="a", reporter_id="CTRL_P_2", executor_id="CTRL_P_1", is_self=False,
            detail=ExecutiveTradeDetail(**detail, holding_before=0, holding_after=1),
        )  # fmt: skip
        own = _trade(
            trans_id="b", detail=ExecutiveTradeDetail(**detail, holding_before=5, holding_after=6)
        )
        et._mark_duplicates([copy, own])
        assert (copy.duplicate_of, copy.duplicate_basis, copy.holding_conflict) == (
            "b",
            "executor_own_row",
            True,
        )

    def test_the_executor_rule_never_merges_one_reporters_rows_and_pairs_one_to_one(self) -> None:
        same_reporter = [
            _trade(trans_id="a", executor_id="TEMP_C_1", is_self=False),
            _trade(trans_id="b", executor_id="TEMP_C_1", is_self=False),
        ]
        et._mark_duplicates(same_reporter)
        assert [t.duplicate_of for t in same_reporter] == [None, None]
        # Two identical trades filed by reporter 1, one by reporter 2: one copy, not two.
        rows = [
            _trade(trans_id="a", executor_id="TEMP_C_1", is_self=False),
            _trade(trans_id="b", executor_id="TEMP_C_1", is_self=False),
            _trade(trans_id="c", reporter_id="CTRL_P_2", executor_id="TEMP_C_1", is_self=False),
        ]
        et._mark_duplicates(rows)
        assert [(t.duplicate_of, t.duplicate_basis) for t in rows] == [
            (None, None),
            (None, None),
            ("a", "executor"),
        ]
        # A blank reporter id cannot prove "different reporter": never merged by the executor rule.
        blank = [
            _trade(trans_id="a", executor_id="TEMP_C_1", is_self=False),
            _trade(trans_id="b", reporter_id=None, executor_id="TEMP_C_1", is_self=None),
        ]
        et._mark_duplicates(blank)
        assert [t.duplicate_of for t in blank] == [None, None]


class TestHoldingConflictIsNeverFalseForUnknown:
    """holding_conflict: True / False only when both reports are known; None otherwise."""

    def _detail(self, before: int, after: int) -> ExecutiveTradeDetail:
        return ExecutiveTradeDetail(
            holder_label="x", executor="x", security_type="หุ้นสามัญ",
            transaction_date=date(2026, 9, 30), holding_before=before, quantity=1,
            avg_price=Decimal("1.00"), holding_after=after, method="ซื้อ", side="buy",
            market_source="m", counterparty=None, record_status="NORMAL",
        )  # fmt: skip

    def _pair(self, copy_detail: Any, own_detail: Any) -> tuple[ExecutiveTrade, ExecutiveTrade]:
        copy = _trade(trans_id="a", reporter_id="CTRL_P_2", executor_id="TEMP_C_1", is_self=False,
                      detail=copy_detail)  # fmt: skip
        other = _trade(trans_id="b", reporter_id="CTRL_P_3", executor_id="TEMP_C_1", is_self=False,
                       detail=own_detail)  # fmt: skip
        et._mark_duplicates([copy, other])
        return copy, other

    def test_one_report_missing_is_unknown(self) -> None:
        copy, other = self._pair(None, self._detail(5, 6))
        merged = copy if copy.duplicate_of else other
        assert merged.duplicate_basis == "executor" and merged.holding_conflict is None

    def test_both_reports_agreeing_is_false_but_they_merge_by_holdings(self) -> None:
        copy, other = self._pair(self._detail(5, 6), self._detail(5, 6))
        merged = copy if copy.duplicate_of else other
        assert merged.duplicate_basis == "holdings" and merged.holding_conflict is False

    def test_an_original_is_none(self) -> None:
        copy, other = self._pair(self._detail(0, 1), self._detail(5, 6))
        original = other if copy.duplicate_of else copy
        assert original.duplicate_of is None and original.holding_conflict is None
