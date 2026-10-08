"""SEC Form 59 (แบบ 59): directors' and executives' changes in securities holdings.

Every director and executive of a listed company must report each change in their (and their
related persons') holdings of the company's securities and derivatives to the Thai SEC. The SEC
publishes the reports at ``https://market.sec.or.th/public/idisc/{th|en}/r59``; this module reads
that listing and, optionally, each report's detail.

**Who traded is not who is named.** The ``ชื่อผู้บริหาร`` (Name of Management) column is the
**reporter**. A row can describe a trade by the reporter's spouse, a minor child, or a company the
family controls; that person is named in parentheses in the relationship cell and identified by the
row's ``executor`` id. :attr:`ExecutiveTrade.reporter_name` and :attr:`ExecutiveTrade.executor_name`
keep the two apart.

**One trade can appear twice.** When both spouses are executives of the same company, both must
report the trade, so the listing shows it once per reporter. The site says so in its own footnote.
The same happens when two executives report one company they both control.
:attr:`ExecutiveTrade.duplicate_of` marks the copy, :attr:`ExecutiveTrade.duplicate_basis` says
which rule did, and :meth:`ExecutiveTradeList.economic_trades` leaves the copy out. Rows are never
dropped; see :func:`_mark_duplicates`. A related-person row is **not** always a copy: on 2026-09-14
a KCG executive and his spouse each bought 5,000 at 9.95, and the detail shows two different
holdings (2,515,000 → 2,520,000 and 910,000 → 915,000).

**Revoked rows stay in the listing.** A filing withdrawn by its reporter shows its quantity struck
through, with ``Revoked by Reporter``. 4,366 of 91,245 rows were revoked on 2026-10-07, mostly
re-filings: the same trade submitted again in a later batch. They are kept and marked
(:attr:`ExecutiveTrade.is_revoked`), never counted as trades.

**This is not the site's default page.** Opening the page with no search shows "data recorded into
the system on <today>", only for trades up to a month old. No query reproduces it: on 2026-10-07 it
had 27 rows, while the same day by SEC received date had 21, with 18 in common. This module queries
by **received date** or by **transaction date**, and today's received-date set can still grow
during the day.

Transport. The search page's postback renders at most 100 rows and links to a "display all results"
page (``/public/idisc/{lang}/ViewMore/r59-2``), a plain GET that returned every row for every window
probed. This module uses only that GET. Each response's stated count must equal the rows parsed,
or it raises, so a truncated page cannot pass as a complete one. The GET is never built without
dates: undated, it returns the whole database (91,245 rows, 70 MB).

The detail "Link" page (``/r59/{lang}/report``) is a JavaScript shell. Its data is a JSON POST to
``/r59/publicapi/report`` with ``{"BatchNo", "Lang"}``. One call returns a whole batch: every
transaction in that filing, with holdings before and after, the trading channel and broker, the
counterparty and an unrounded average price.

robots.txt (``https://market.sec.or.th/robots.txt``, read 2026-10-07) is exactly::

    User-agent: *
    Disallow: /public/idisc/*.aspx$

None of the URLs this module requests matches it: ``/public/idisc/{lang}/r59``,
``/public/idisc/{lang}/ViewMore/r59-2?...``, ``/r59/{lang}/report`` and ``/r59/publicapi/report``.
The host is stateless; requests go out with ``use_session=False``, like every SEC service.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterator
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import TYPE_CHECKING, Any, Literal, overload
from urllib.parse import parse_qs, urlencode, urlparse
from zoneinfo import ZoneInfo

from loguru import logger
from pydantic import BaseModel, Field, computed_field

from settfex.exceptions import (
    CompanyNotFoundError,
    FetchError,
    HTTPStatusError,
    InvalidDateError,
    ParseError,
)
from settfex.services.sec.company import resolve_company
from settfex.services.sec.constants import (
    SEC_BASE_URL,
    SEC_R59_DATE_TYPES,
    SEC_R59_MAX_DETAIL_BATCHES,
    SEC_R59_MAX_WINDOW_DAYS,
    SEC_R59_PAGE_ENDPOINT,
    SEC_R59_REPORT_API_ENDPOINT,
    SEC_R59_REPORT_PAGE_ENDPOINT,
    SEC_R59_REVOKED_MARKER,
    SEC_R59_TABLE_ID,
    SEC_R59_VIEWMORE_ENDPOINT,
)
from settfex.services.sec.utils import _dmy_to_date, build_sec_headers, split_section_count
from settfex.services.set.stock.utils import Language, normalize_language, normalize_symbol
from settfex.utils.data_fetcher import AsyncDataFetcher, FetcherConfig
from settfex.utils.parsing import BlockedError

if TYPE_CHECKING:
    import pandas as pd

BANGKOK = ZoneInfo("Asia/Bangkok")

DateType = Literal["received", "transaction"]
Side = Literal["buy", "sell", "transfer_in", "transfer_out", "other"]
DuplicateBasis = Literal["holdings", "executor", "executor_own_row"]

# --- Vocabulary (harvested from the full listing, 91,245 Thai rows, 2026-10-07) -------------------
# The method vocabulary is OPEN: ten Thai labels over the full history, four in the last year, and
# the detail API is finer still ("โอน (โอนให้บุตร)", transfer to a child). So `method` stays the
# verbatim label and `side` is a normalised direction. An unmapped label becomes "other" and is
# counted on ExecutiveTradeList.unknown_labels; it never raises.
_TH_METHOD_SIDE: dict[str, Side] = {
    "ซื้อ": "buy",  # buy
    "ขาย": "sell",  # sell
    "ขาย-เพื่อผู้ฝาก": "sell",  # sell for a depositor
    "โอน": "transfer_out",  # transfer (holding falls; HENG 2026-09-30: 330,783,525 -> 290,783,525)
    "โอนออก": "transfer_out",  # transfer out
    "โอนออก-เพื่อฝาก": "transfer_out",  # transfer out to deposit
    "รับโอน": "transfer_in",  # receive a transfer
    "รับโอน-เพื่อผู้ฝาก": "transfer_in",  # receive for a depositor
    "รับโอน-คืนจากผู้รับฝาก": "transfer_in",  # returned by the depositary
    "แปลงจาก NVDR": "other",  # converted from NVDR: direction not stated by the label
}
# English labels, from th/en rows joined on transId (1,812 of 1,812 joined, one-to-one). The rarer
# Thai labels above were never seen on the English page, so their English form is unknown.
_EN_METHOD_SIDE: dict[str, Side] = {
    "Purchase": "buy",
    "Sale": "sell",
    "Transfer": "transfer_out",
    "Acceptance of Transfer": "transfer_in",
}
_METHOD_SIDE: dict[str, Side] = {**_TH_METHOD_SIDE, **_EN_METHOD_SIDE}

_KNOWN_SECURITY_TYPES: frozenset[str] = frozenset(
    {
        # Thai, every label in the full history
        "หุ้นสามัญ",
        "ใบสำคัญแสดงสิทธิที่จะซื้อหุ้น",
        "ใบสำคัญแสดงสิทธิที่จะซื้อหุ้น2",
        "ใบสำคัญแสดงสิทธิที่จะซื้อหุ้น3",
        "ใบสำคัญแสดงสิทธิที่จะซื้อหุ้น4",
        "ใบสำคัญแสดงสิทธิที่จะซื้อหุ้น5",
        "ใบสำคัญแสดงสิทธิที่จะซื้อหุ้น6",
        "ใบสำคัญแสดงสิทธิที่จะซื้อหุ้น7",
        "หน่วยทรัสต์",
        "ใบแสดงสิทธิในผลประโยชน์ที่เกิดจากหลักทรัพย์อ้างอิงไทย (NVDR)อ้างอิง หุ้นสามัญ",
        "ใบแสดงสิทธิในผลประโยชน์ที่เกิดจากหลักทรัพย์อ้างอิงไทย (NVDR) อ้างอิง ใบแสดงสิทธิในการซื้อหุ้นเพิ่มทุนที่โอนสิทธิได้",
        "ใบแสดงสิทธิในผลประโยชน์ที่เกิดจากหลักทรัพย์อ้างอิงไทย (NVDR) อ้างอิง ใบสำคัญแสดงสิทธิที่จะซื้อหุ้น",
        "ใบแสดงสิทธิในผลประโยชน์ที่เกิดจากหลักทรัพย์อ้างอิงไทย (NVDR) อ้างอิง หุ้นบุริมสิทธิ์",
        "สัญญาซื้อขายล่วงหน้าที่อ้างอิงราคาหรือผลตอบแทนในหุ้นของบริษัทจดทะเบียน "
        "(Single Stock Future) ที่มีการซื้อขายใน TFEX",
        "ใบแสดงสิทธิที่จะซื้อหุ้นที่โอนเปลี่ยนมือได้",
        "ใบแสดงสิทธิที่จะซื้อหุ้นเพิ่มที่โอนเปลี่ยนมือได้",
        "ใบสำคัญแสดงสิทธิอนุพันธ์ที่มีหลักทรัพย์ของบริษัทจดทะเบียนเป็นปัจจัยอ้างอิง (DW)",
        "หุ้นกู้ที่มีอนุพันธ์แฝง",
        "หุ้นกู้แปลงสภาพ",
        "หุ้นบุริมสิทธิ",
        "ใบสำคัญแสดงสิทธิซื้อหุ้นบุริมสิทธิ",
        # English, every label seen on the English page
        "Common Share",
        "Warrant",
        "NVDR : underlying securities ordinary SHARE",
        "Units",
        "Single Stock Future (TFEX)",
        "Structured Debenture",
    }
)

# The relationship labels that mean "the reporter is the one who traded".
_SELF_LABELS = frozenset({"ผู้รายงาน", "ผู้จัดทำ", "Reporter"})

# The listing's column headers, per language, in page order. Anything else is a layout change.
_HEADERS: dict[str, list[str]] = {
    "th": [
        "ชื่อบริษัท",
        "ชื่อผู้บริหาร",
        "ความสัมพันธ์ *",
        "ประเภทหลักทรัพย์",
        "วันที่ได้มา/จำหน่าย",
        "จำนวน",
        "ราคา",
        "วิธีการได้มา/จำหน่าย",
        "หมายเหตุ",
    ],
    "en": [
        "Name of Company",
        "Name of Management",
        "Relationship to Management",
        "Types of Securities",
        "Transaction Date",
        "Amount",
        "Average Price (baht)",
        "The methods of Acquisition/Disposition",
        "Remark",
    ],
}
_RAW_KEYS = (
    "company",
    "reporter_name",
    "relationship",
    "security_type",
    "transaction_date",
    "quantity",
    "price",
    "method",
    "remark",
)
_QUANTITY = re.compile(r"\d{1,3}(?:,\d{3})*")
_PRICE = re.compile(r"\d{1,3}(?:,\d{3})*\.\d{2}")
_DECIMAL = re.compile(r"\d{1,3}(?:,\d{3})*(?:\.\d+)?")
_BLANK_ID = re.compile(r"(?:CTRL|TEMP)_[PC]_")
_BR = re.compile(r"<br\s*/?>", re.IGNORECASE)
_WARRANT = re.compile(r"ใบสำคัญแสดงสิทธิที่จะซื้อหุ้น\d*")


# ==================================================================================================
# Models
# ==================================================================================================


class ExecutiveTradeDetail(BaseModel):
    """One transaction inside a Form 59 report (a batch), from the detail API.

    Carries what the listing does not: holdings before and after, the unrounded average price,
    the trading channel and broker, and the counterparty of a transfer.
    """

    holder_label: str = Field(
        description="Who the holding belongs to, relative to the reporter: the label part of "
        "TransExecutor, e.g. 'ผู้รายงาน' (the reporter) or 'คู่สมรส/ผู้ที่อยู่กินด้วยกันฉันสามีภริยา' (spouse)."
    )
    executor: str = Field(
        description="TransExecutor verbatim, e.g. 'คู่สมรส/ผู้ที่อยู่กินด้วยกันฉันสามีภริยา<br/>(นาย ประทีป "
        "ตั้งมติธรรม)'. Includes the person's name when it is not the reporter."
    )
    security_type: str = Field(description="SecuType verbatim, e.g. 'หุ้นสามัญ' (common share).")
    transaction_date: date | None = Field(
        description="Trade date, converted to the Christian era. None if the cell is empty."
    )
    holding_before: int = Field(description="Units held before this transaction.")
    quantity: int = Field(description="Units in this transaction (always positive).")
    avg_price: Decimal = Field(
        description="Average price at full precision as filed (up to 4 dp, e.g. 8.7333). 0.00 on a "
        "transfer. Prefer this over the listing's rounded price."
    )
    holding_after: int = Field(description="Units held after this transaction.")
    method: str = Field(
        description="TransType verbatim. Finer than the listing's label, e.g. 'โอน (โอนให้บุตร)' "
        "(transfer to a child)."
    )
    side: Side = Field(description="Normalised direction of the method; 'other' when unknown.")
    market_source: str = Field(
        description="MarketSource verbatim: channel and broker, e.g. 'ทำรายการผ่านตลาดหลักทรัพย์ (Auto "
        "Matching) (บริษัท หลักทรัพย์...)' (on-exchange) or 'ทำรายการนอกตลาดหลักทรัพย์ (...)' "
        "(off-exchange)."
    )
    counterparty: str | None = Field(
        description="TargetInfo: the purchaser or transferee as filed; None when empty."
    )
    remark: str | None = Field(
        default=None,
        description="Markers stripped from numeric cells, e.g. \"holding_before: '*'\" for a "
        "holding filed as '3,840,000 *'. None when there were none.",
    )
    record_status: str = Field(
        description="RecordStatus verbatim. Seen: NORMAL, EFFECTED, EDITED, CANCELED. It does not "
        "mirror the listing's revoked flag one-to-one; use ExecutiveTrade.is_revoked for that."
    )
    trans_id: str | None = Field(
        default=None,
        description="The listing row this transaction was linked to. The detail API carries no id, "
        "so it is set only when the row was matched unambiguously; None otherwise.",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def holding_consistent(self) -> bool:
        """Whether before ± quantity == after for this side. A mismatch is flagged, never raised.

        Buy and receive add, sell and transfer-out subtract. For 'other' either direction counts.
        Reporters file these by hand, so a mismatch is a filing error to be aware of, not a
        reason to reject the row.
        """
        up = self.holding_before + self.quantity == self.holding_after
        down = self.holding_before - self.quantity == self.holding_after
        if self.side in ("buy", "transfer_in"):
            return up
        if self.side in ("sell", "transfer_out"):
            return down
        return up or down


class ExecutiveTradeReport(BaseModel):
    """One Form 59 report (a batch) from the detail API: a header and its transactions."""

    batch_no: str = Field(description="The report's BatchNo, as in the listing row's link.")
    company_name: str = Field(description="Company verbatim, as the detail header states it.")
    symbol: str | None = Field(
        default=None,
        description="Trading symbol. The detail API does not state one; filled from the listing "
        "when the report was fetched through get_executive_trades(with_details=True).",
    )
    reporter_name: str = Field(description="The executive who filed the report.")
    position: str = Field(description="The reporter's position, verbatim.")
    submitted_at: datetime = Field(
        description="When SEC received the filing (SubmitDate), Asia/Bangkok, Christian era."
    )
    business_type_code: str = Field(
        description="BusinessTypeCode verbatim: '0106300010' securities, '0106300015' trust units."
    )
    lang: Language = Field(description="Language the report was requested in.")
    transactions: list[ExecutiveTradeDetail] = Field(
        default_factory=list,
        description="Every transaction in the batch, in the API's order (by date, not by transId).",
    )


class ExecutiveTrade(BaseModel):
    """One row of the Form 59 listing: one reported transaction.

    ``reporter_name`` is who FILED; who TRADED is ``executor_name`` / ``executor_id``. Check
    ``is_revoked`` and ``duplicate_of`` before counting a row as a trade, or use
    :meth:`ExecutiveTradeList.economic_trades`, which does both.
    """

    symbol: str = Field(
        description="Trading symbol from the '(SYMBOL)' suffix of the company cell. Verbatim, so "
        "historic oddities survive, e.g. 'BANPU ยุติ' (BANPU, deactivated after a merger)."
    )
    company_name: str = Field(description="The company cell verbatim, symbol suffix included.")
    reporter_name: str = Field(
        description="The ชื่อผู้บริหาร (Name of Management) column: the executive who REPORTED. Not "
        "necessarily who traded; see executor_name / executor_id."
    )
    reporter_id: str | None = Field(
        description="Reporter id from the row's link (e.g. 'CTRL_P_0000012061'). None for rows "
        "without a link (19% of the history, mostly before 2016) or with a blank id."
    )
    executor_id: str | None = Field(
        description="Id of who actually traded, from the link: CTRL_P_/TEMP_P_ a person, "
        "CTRL_C_/TEMP_C_ a company. None when absent or blank."
    )
    executor_name: str | None = Field(
        description="The person or company named in parentheses in the relationship cell, e.g. "
        "the spouse. None when the reporter traded, or when the cell names nobody (360 older "
        "spouse rows in the full history carry an executor id but no name)."
    )
    relationship: str = Field(
        description="Relationship of the trader to the reporter, verbatim without the name in "
        "parentheses, e.g. 'ผู้รายงาน' (the reporter), 'คู่สมรส/ผู้ที่อยู่กินด้วยกันฉันสามีภริยา' (spouse)."
    )
    is_self: bool | None = Field(
        description="True when reporter_id == executor_id; None when either id is missing."
    )
    security_type: str = Field(description="Security type verbatim, e.g. 'หุ้นสามัญ' (common share).")
    method: str = Field(
        description="Method verbatim, e.g. 'ซื้อ' (buy), 'ขาย' (sell), 'โอน' (transfer)."
    )
    side: Side = Field(
        description="Normalised direction of method. 'other' for a label with no known direction; "
        "such labels are counted on ExecutiveTradeList.unknown_labels."
    )
    transaction_date: date | None = Field(
        description="Trade date, converted to the Christian era. None when the cell is empty."
    )
    received_date: date | None = Field(
        default=None,
        description="SEC received date, known only when the query asked for exactly one "
        "received day; None otherwise. Not the site's 'recorded into the system' date.",
    )
    quantity: int = Field(
        description="Units. For a revoked row, the struck-through figure as filed."
    )
    price: Decimal | None = Field(
        description="Average price as the LISTING shows it, ROUNDED TO 2 dp (e.g. 8.73 for a filed "
        "8.7333). Prefer detail.avg_price when present. None when the page shows '-'."
    )
    is_revoked: bool = Field(
        description="True when the reporter revoked this filing (struck through, 'Revoked by "
        "Reporter'). A revoked row is not a trade."
    )
    remark: str | None = Field(
        default=None,
        description="Text in the remark column other than the link, e.g. 'แก้ไขข้อมูล' (data "
        "corrected). None when empty.",
    )
    batch_no: str | None = Field(
        description="BatchNo from the link: the report this row belongs to. None without a link."
    )
    trans_id: str | None = Field(description="transId from the link. None without a link.")
    report_url: str | None = Field(description="Absolute URL of the report page, if linked.")
    duplicate_of: str | None = Field(
        default=None,
        description="trans_id of the row this one duplicates (the same trade filed by another "
        "reporter). None for an original. Rows are never dropped.",
    )
    duplicate_basis: DuplicateBasis | None = Field(
        default=None,
        description="Which rule marked the copy. 'holdings': both rows' reports show the same "
        "holding before and after. 'executor_own_row': the same trader under a different "
        "reporter, and the trader (an executive) filed the trade as their own row, which is the "
        "original (the spouse case). 'executor': the same trader under a different reporter, the "
        "trader filed no row of their own, e.g. a company two executives control. None for an "
        "original.",
    )
    holding_conflict: bool | None = Field(
        default=None,
        description="Only on a copy. True: the two rows' reports show DIFFERENT holdings for the "
        "same trader (one filing is inconsistent; the merge stands). False: both reports are known "
        "and agree (always False for basis 'holdings'). None: an original, or a copy whose "
        "holdings are unknown because a report was not fetched. Never False for 'unknown'.",
    )
    detail: ExecutiveTradeDetail | None = Field(
        default=None,
        description="The matching transaction from the detail API, when fetched with "
        "with_details=True and matched unambiguously; None otherwise.",
    )


class ExecutiveTradeQuery(BaseModel):
    """What was asked for, echoed back with the result."""

    date_type: DateType = Field(description="'received' (SEC received date) or 'transaction'.")
    start: date = Field(description="First day of the window, inclusive.")
    end: date = Field(description="Last day of the window, inclusive.")
    unique_id: str | None = Field(default=None, description="Company filter, if any.")
    symbol: str | None = Field(default=None, description="Symbol the company was resolved from.")
    windows: int = Field(description="How many ViewMore requests the window was split into.")


class ExecutiveTradeList(BaseModel):
    """The Form 59 rows for a query, plus the evidence that none were lost.

    Behaves like a sequence of :class:`ExecutiveTrade`: ``len()``, iteration, indexing and ``in``.
    Slicing returns another ``ExecutiveTradeList`` that keeps the query and counts.
    ``reported_count`` is what the site said the query holds; every response was checked against it,
    so
    ``len(items) == reported_count`` on a freshly fetched list.
    """

    items: list[ExecutiveTrade] = Field(default_factory=list, description="The rows.")
    reported_count: int = Field(
        default=0, description="Total rows the site stated for the query (sum over windows)."
    )
    query: ExecutiveTradeQuery = Field(description="The query that produced this list.")
    lang: Language = Field(default="th", description="Page language.")
    fetched_at: datetime = Field(description="When the listing was fetched (Asia/Bangkok).")
    details_requested: bool = Field(
        default=False, description="Whether the detail of each report was fetched."
    )
    reports: list[ExecutiveTradeReport] = Field(
        default_factory=list, description="The detail reports fetched, one per batch."
    )
    detail_failures: dict[str, str] = Field(
        default_factory=dict,
        description="batch_no -> error, for detail requests that failed. Those rows keep detail "
        "None; the listing itself is complete.",
    )

    def __iter__(self) -> Iterator[ExecutiveTrade]:  # type: ignore[override]
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __contains__(self, item: object) -> bool:
        return item in self.items

    @overload
    def __getitem__(self, index: int) -> ExecutiveTrade: ...

    @overload
    def __getitem__(self, index: slice) -> ExecutiveTradeList: ...

    def __getitem__(self, index: int | slice) -> ExecutiveTrade | ExecutiveTradeList:
        if isinstance(index, slice):
            return self._with_items(self.items[index])
        return self.items[index]

    def _with_items(self, items: list[ExecutiveTrade]) -> ExecutiveTradeList:
        return self.model_copy(update={"items": items})

    @computed_field  # type: ignore[prop-decorator]
    @property
    def revoked_count(self) -> int:
        """Rows the reporter revoked."""
        return sum(1 for t in self.items if t.is_revoked)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def duplicate_count(self) -> int:
        """Rows marked as another reporter's copy of the same trade."""
        return sum(1 for t in self.items if t.duplicate_of is not None)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def unknown_labels(self) -> dict[str, dict[str, int]]:
        """Labels outside the known vocabulary: {"method": {...}, "security_type": {...}}.

        Empty dicts when every label is known. An unknown method's side is 'other'.
        """
        methods = Counter(t.method for t in self.items if t.method not in _METHOD_SIDE)
        types = Counter(
            t.security_type for t in self.items if t.security_type not in _KNOWN_SECURITY_TYPES
        )
        return {"method": dict(methods), "security_type": dict(types)}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def detail_unmatched(self) -> int:
        """Linked rows left without detail although details were requested (0 otherwise)."""
        if not self.details_requested:
            return 0
        return sum(1 for t in self.items if t.batch_no and t.detail is None)

    def economic_trades(self) -> ExecutiveTradeList:
        """The rows that are trades: not void (revoked, or CANCELED in its report), not a copy.

        Known overcount: a trade one reporter filed twice in different batches, the original left
        live, is counted twice. The duplicate rules never merge rows from the same reporter, so
        the re-filing survives. Example: CREDIT 2026-09-28, 10,000 shares, filed as 165104_2_1
        (holdings 220,000 -> 230,000) and again as 165237_3_1 (270,000 -> 280,000, EFFECTED in its
        report).
        """
        return self._with_items(
            [t for t in self.items if not _is_void(t) and t.duplicate_of is None]
        )

    def to_table(self, *, include_revoked: bool = False, with_details: bool = False) -> str:
        """Render a Markdown table in Thai: sells first, then buys, then other methods.

        Within a side, rows are ordered by symbol, then by transaction date. ``**`` after a name
        marks a row whose trader is not the reporter. Warrants show as ``Warrant``, quantities
        with thousands separators, prices to 2 dp, dates as dd/mm/B.E. (as the Thai page shows
        them). Void rows (revoked, or CANCELED in their report) are skipped unless
        ``include_revoked``. ``with_details`` adds
        ถือก่อน (held before), ถือหลัง (held after), ราคาเฉลี่ย (average price, full precision) and
        ทำรายการผ่าน (traded through); '-' where no detail was matched.
        """
        header = ["หลักทรัพย์", "ชื่อผู้บริหาร", "รายการ", "จำนวน", "ราคา", "ประเภท", "วันที่"]
        if with_details:
            header += ["ถือก่อน", "ถือหลัง", "ราคาเฉลี่ย", "ทำรายการผ่าน"]
        rank = {"sell": 0, "buy": 1, "transfer_out": 2, "transfer_in": 3, "other": 4}
        rows = [t for t in self.items if include_revoked or not _is_void(t)]
        rows.sort(key=lambda t: (rank[t.side], t.symbol, t.transaction_date or date.max))
        lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
        for t in rows:
            cells = [
                t.symbol,
                t.reporter_name + ("**" if _traded_by_other(t) else ""),
                t.method,
                f"{t.quantity:,}",
                "-" if t.price is None else f"{t.price:,.2f}",
                "Warrant" if _WARRANT.fullmatch(t.security_type) else t.security_type,
                _be_date(t.transaction_date),
            ]
            if with_details:
                d = t.detail
                cells += (
                    ["-"] * 4
                    if d is None
                    else [
                        f"{d.holding_before:,}",
                        f"{d.holding_after:,}",
                        str(d.avg_price),
                        d.market_source,
                    ]
                )
            lines.append("| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |")
        return "\n".join(lines)

    def to_dataframe(self, columns: list[str] | None = None) -> pd.DataFrame:
        """One row per listing row. Requires pandas (``pip install settfex[dataframe]``).

        Prices are floats here (NaN where absent); the models keep exact ``Decimal`` values.
        Detail columns are NaN for rows without a matched detail.
        """
        try:
            import pandas as pd
        except ImportError as exc:  # pragma: no cover - exercised via monkeypatched sys.modules
            raise ImportError(
                "pandas is required for ExecutiveTradeList.to_dataframe(). Install it with "
                "'pip install settfex[dataframe]' (or 'uv add pandas')."
            ) from exc
        cols = columns or list(_DATAFRAME_ACCESSORS)
        unknown = [c for c in cols if c not in _DATAFRAME_ACCESSORS]
        if unknown:
            raise ValueError(
                f"Unknown DataFrame column(s): {unknown}. "
                f"Available columns: {sorted(_DATAFRAME_ACCESSORS)}"
            )
        rows = [[_DATAFRAME_ACCESSORS[c](t) for c in cols] for t in self.items]
        return pd.DataFrame(rows, columns=cols)

    def __repr__(self) -> str:
        return (
            f"ExecutiveTradeList({len(self.items)} rows of {self.reported_count} reported, "
            f"{self.revoked_count} revoked, {self.duplicate_count} duplicates, "
            f"{self.query.date_type} {self.query.start}..{self.query.end})"
        )


def _float(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


_DATAFRAME_ACCESSORS: dict[str, Any] = {
    "symbol": lambda t: t.symbol,
    "reporter_name": lambda t: t.reporter_name,
    "executor_name": lambda t: t.executor_name,
    "relationship": lambda t: t.relationship,
    "is_self": lambda t: t.is_self,
    "security_type": lambda t: t.security_type,
    "method": lambda t: t.method,
    "side": lambda t: t.side,
    "transaction_date": lambda t: t.transaction_date,
    "received_date": lambda t: t.received_date,
    "quantity": lambda t: t.quantity,
    "price": lambda t: _float(t.price),
    "is_revoked": lambda t: t.is_revoked,
    "duplicate_of": lambda t: t.duplicate_of,
    "duplicate_basis": lambda t: t.duplicate_basis,
    "holding_conflict": lambda t: t.holding_conflict,
    "batch_no": lambda t: t.batch_no,
    "trans_id": lambda t: t.trans_id,
    "holding_before": lambda t: t.detail.holding_before if t.detail else None,
    "holding_after": lambda t: t.detail.holding_after if t.detail else None,
    "avg_price": lambda t: _float(t.detail.avg_price) if t.detail else None,
    "market_source": lambda t: t.detail.market_source if t.detail else None,
    "record_status": lambda t: t.detail.record_status if t.detail else None,
}


def _is_void(trade: ExecutiveTrade) -> bool:
    """Not a trade: the listing shows it revoked, or its report marks it CANCELED.

    On 2026-10-07 both CANCELED transactions seen were revoked in the listing too, but the two
    signals are not the same: three revoked rows had NORMAL/EFFECTED in their report. Either one
    voids the row.
    """
    cancelled = trade.detail is not None and trade.detail.record_status == "CANCELED"
    return trade.is_revoked or cancelled


def _traded_by_other(trade: ExecutiveTrade) -> bool:
    """True when the trader is not the reporter (falls back to the label when an id is missing)."""
    if trade.is_self is not None:
        return not trade.is_self
    return trade.relationship not in _SELF_LABELS


def _be_date(value: date | None) -> str:
    return "-" if value is None else f"{value.day:02d}/{value.month:02d}/{value.year + 543}"


# ==================================================================================================
# Listing: HTML parsing
# ==================================================================================================


class _Cell:
    __slots__ = ("plain", "struck", "hrefs", "colspan")

    def __init__(self, colspan: int) -> None:
        self.plain: list[str] = []
        self.struck: list[str] = []
        self.hrefs: list[str] = []
        self.colspan = colspan


class _ListingParser(HTMLParser):
    """Collect the card heading, the header row and the cells of the Form 59 result table."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.heading: list[str] = []
        self.headers: list[str] = []
        self.rows: list[list[_Cell]] = []
        self.table_found = False
        self.nested_table = False
        self._div_depth = 0
        self._heading_at: int | None = None
        self._in_table = False
        self._inner_tables = 0
        self._row: list[_Cell] | None = None
        self._cell: _Cell | None = None
        self._th: list[str] | None = None
        self._strike = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: v or "" for k, v in attrs}
        if tag == "div":
            self._div_depth += 1
            if self._heading_at is None and "card-heading" in a.get("class", ""):
                self._heading_at = self._div_depth
        elif tag == "table":
            if self._in_table:
                self._inner_tables += 1
                self.nested_table = True
            elif a.get("id") == SEC_R59_TABLE_ID:
                self._in_table = True
                self.table_found = True
        elif not self._in_table or self._inner_tables:
            return
        elif tag == "tr":
            self._row = []
        elif tag == "th":
            self._th = []
        elif tag == "td":
            colspan = a.get("colspan", "1")
            self._cell = _Cell(int(colspan) if colspan.isdigit() else 1)
        elif self._cell is not None:
            if tag == "span" and (self._strike or "line-through" in a.get("style", "")):
                self._strike += 1
            elif tag == "br":
                self._cell.plain.append(" ")
            elif tag == "a" and a.get("href"):
                self._cell.hrefs.append(a["href"])

    def handle_endtag(self, tag: str) -> None:
        if tag == "div":
            if self._heading_at == self._div_depth:
                self._heading_at = -1  # closed; only the first card heading counts
            self._div_depth -= 1
        elif tag == "table" and self._in_table:
            if self._inner_tables:
                self._inner_tables -= 1
            else:
                self._in_table = False
        elif not self._in_table or self._inner_tables:
            return
        elif tag == "span" and self._strike:
            self._strike -= 1
        elif tag == "th" and self._th is not None:
            self.headers.append(" ".join("".join(self._th).split()))
            self._th = None
        elif tag == "td" and self._cell is not None and self._row is not None:
            self._row.append(self._cell)
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._heading_at is not None and self._heading_at > 0:
            self.heading.append(data)
        if self._th is not None:
            self._th.append(data)
        elif self._cell is not None:
            (self._cell.struck if self._strike else self._cell.plain).append(data)


def _norm(parts: list[str]) -> str:
    return " ".join("".join(parts).split())


def _parse_listing(html: str, url: str, lang: Language) -> tuple[int, list[dict[str, str]]]:
    """Return (the count the page states, the rows as verbatim string dicts).

    Raises :class:`ParseError` on anything that is not a recognisable Form 59 result: no table,
    an unknown column layout, a heading without a count, a row of the wrong width, a nested table,
    or a row count that differs from the stated count.
    """
    parser = _ListingParser()
    parser.feed(html)
    parser.close()
    if not parser.table_found:
        raise ParseError(
            f"Not a Form 59 result page (no table {SEC_R59_TABLE_ID!r}): {url}", url=url
        )
    if parser.nested_table:
        raise ParseError(f"Form 59 result table contains a nested table: {url}", url=url)
    if parser.headers != _HEADERS[lang]:
        raise ParseError(
            f"Unknown Form 59 column layout {parser.headers!r}; expected {_HEADERS[lang]!r}: {url}",
            url=url,
            unknown_sections=parser.headers,
        )
    heading = _norm(parser.heading)
    _, reported = split_section_count(heading)
    if reported is None:
        raise ParseError(f"Form 59 heading states no record count ({heading!r}): {url}", url=url)

    rows: list[dict[str, str]] = []
    placeholders = 0
    for cells in parser.rows:
        if len(cells) == 1 and cells[0].colspan >= len(_HEADERS[lang]):
            placeholders += 1  # "ไม่พบข้อมูล" (no data): the site's empty-result row
            continue
        if len(cells) != len(_HEADERS[lang]):
            raise ParseError(
                f"Form 59 row has {len(cells)} cells, expected {len(_HEADERS[lang])}: {url}",
                url=url,
                rows_parsed=len(rows),
            )
        rows.append(_raw_row(cells))

    if placeholders and (rows or reported):
        raise ParseError(
            f"Form 59 page shows the no-data row but states {reported} record(s): {url}",
            url=url,
            rows_parsed=len(rows),
        )
    if len(rows) != reported:
        raise ParseError(
            f"Form 59 page states {reported} record(s) but {len(rows)} row(s) were parsed — "
            f"a truncated or altered page, refused rather than returned short: {url}",
            url=url,
            rows_parsed=len(rows),
        )
    return reported, rows


def _raw_row(cells: list[_Cell]) -> dict[str, str]:
    raw = {key: _norm(cell.plain + cell.struck) for key, cell in zip(_RAW_KEYS, cells, strict=True)}
    qty = cells[5]
    struck = _norm(qty.struck)
    raw["quantity"] = struck if struck else _norm(qty.plain)
    raw["quantity_note"] = _norm(qty.plain) if struck else ""
    raw["revoked"] = "true" if struck else "false"
    href = next((h for cell in cells for h in cell.hrefs), "")
    raw["href"] = href
    params = {k: v[0] for k, v in parse_qs(urlparse(href).query, keep_blank_values=True).items()}
    for key in ("batchNo", "transId", "reporter", "executor"):
        raw[key] = params.get(key, "")
    return raw


# ==================================================================================================
# Listing: raw rows -> models
# ==================================================================================================


def _split_last_group(text: str) -> tuple[str, str | None]:
    """Split ``"label (name (with) parens)"`` into ``("label", "name (with) parens")``."""
    text = text.strip()
    if not text.endswith(")"):
        return text, None
    depth = 0
    for i in range(len(text) - 1, -1, -1):
        if text[i] == ")":
            depth += 1
        elif text[i] == "(":
            depth -= 1
            if depth == 0:
                return text[:i].strip(), text[i + 1 : -1].strip()
    return text, None


def _clean_id(value: str) -> str | None:
    value = value.strip()
    if not value or value == "__" or _BLANK_ID.fullmatch(value):
        return None
    return value


def _strict_int(value: str, what: str, url: str | None) -> int:
    if not _QUANTITY.fullmatch(value):
        raise ParseError(f"Form 59 {what} {value!r} is not a whole number", url=url)
    return int(value.replace(",", ""))


def _strict_decimal(value: str, what: str, url: str | None, *, listing: bool) -> Decimal:
    pattern = _PRICE if listing else _DECIMAL
    if not pattern.fullmatch(value):
        raise ParseError(f"Form 59 {what} {value!r} is not a price", url=url)
    try:
        return Decimal(value.replace(",", ""))
    except InvalidOperation as exc:  # pragma: no cover - the pattern already guarantees a number
        raise ParseError(f"Form 59 {what} {value!r} is not a price", url=url) from exc


def _strict_date(value: str, what: str, url: str | None) -> date | None:
    if not value.strip():
        return None
    try:
        return _dmy_to_date(value)
    except ValueError as exc:
        raise ParseError(f"Form 59 {what} {value!r} is not a dd/mm/yyyy date", url=url) from exc


def side_for(method: str) -> Side:
    """Normalised direction of a Form 59 method label (listing or detail), 'other' if unknown.

    A detail label such as ``"โอน (โอนให้บุตร)"`` is reduced to its base label first.
    """
    base, _ = _split_last_group(method)
    return _METHOD_SIDE.get(method) or _METHOD_SIDE.get(base) or "other"


def _trade_from_raw(
    raw: dict[str, str], *, url: str | None = None, received_date: date | None = None
) -> ExecutiveTrade:
    _, symbol = _split_last_group(raw["company"])
    if not symbol:
        raise ParseError(f"Form 59 company cell has no (SYMBOL): {raw['company']!r}", url=url)
    relationship, executor_name = _split_last_group(raw["relationship"])
    revoked = raw.get("revoked") == "true"
    note = raw.get("quantity_note", "")
    if revoked and note != SEC_R59_REVOKED_MARKER:
        raise ParseError(
            f"Form 59 quantity is struck through but reads {note!r}, not "
            f"{SEC_R59_REVOKED_MARKER!r}: the revoked-row format changed",
            url=url,
        )
    price = raw["price"].strip()
    reporter_id = _clean_id(raw.get("reporter", ""))
    executor_id = _clean_id(raw.get("executor", ""))
    remark = raw["remark"].strip()
    href = raw.get("href", "").strip()
    return ExecutiveTrade(
        symbol=symbol,
        company_name=raw["company"],
        reporter_name=raw["reporter_name"],
        reporter_id=reporter_id,
        executor_id=executor_id,
        executor_name=executor_name or None,
        relationship=relationship,
        is_self=(reporter_id == executor_id) if reporter_id and executor_id else None,
        security_type=raw["security_type"],
        method=raw["method"],
        side=side_for(raw["method"]),
        transaction_date=_strict_date(raw["transaction_date"], "transaction date", url),
        received_date=received_date,
        quantity=_strict_int(raw["quantity"], "quantity", url),
        price=None if price == "-" else _strict_decimal(price, "price", url, listing=True),
        is_revoked=revoked,
        remark=None if remark in ("", "Link") else remark,
        batch_no=raw.get("batchNo", "").strip() or None,
        trans_id=raw.get("transId", "").strip() or None,
        report_url=href.replace(" ", "%20") or None,
    )


# ==================================================================================================
# Duplicates
# ==================================================================================================


def _mark_duplicates(items: list[ExecutiveTrade]) -> None:
    """Set ``duplicate_of`` / ``duplicate_basis`` on copies of another row's trade. Never drops.

    A row is a copy when either rule holds:

    1. **Holdings** (only when both rows have their report): the same symbol, security type,
       date, quantity, holding before and holding after. The copy points at the reporter's own row
       if there is one, otherwise at the lowest trans_id. Basis ``"holdings"``.
    2. **Executor**: the same non-blank executor id, a DIFFERENT non-blank reporter, and the same
       symbol, security type, date, quantity, price and method. Rows from the same reporter are
       never merged by this rule. The copy points at the executor's own row when the executor filed
       one (basis ``"executor_own_row"``, the spouse case the site's footnote describes),
       otherwise at the rows of the reporter with the lowest trans_id (basis ``"executor"``).
       Rows pair one-to-one, so two genuine identical trades reported by two people stay two
       trades. When both rows have reports and their holdings differ, the merge stands and
       ``holding_conflict`` is True; it is None when either report is unknown, and False only
       when both are known and agree.

    Decided 2026-10-08 from all 28 September 2026 pairs checked against holdings:

    - SPALI (11): one trade from two spouse-executives, so a copy.
    - KCG (7): two traders, so never a copy.
    - CREDIT, one executive's own and spouse rows (2): holdings identical, so a copy by holdings,
      although the executor ids differ.
    - CREDIT, one reporter filing twice (1): never merged.
    - STX (7): one company reported by two executives. A copy by executor, with
      ``holding_conflict``: their holdings stay 70,000 apart.

    Void rows (revoked, or CANCELED in their report) are never marked and never pointed at.
    """
    live = [t for t in items if not _is_void(t) and t.trans_id]

    def tid(t: ExecutiveTrade) -> str:
        return t.trans_id or ""

    groups: dict[tuple[Any, ...], list[ExecutiveTrade]] = defaultdict(list)
    for t in live:
        if t.detail is not None:
            d = t.detail
            key = (t.symbol, t.security_type, t.transaction_date, t.quantity)
            groups[(*key, d.holding_before, d.holding_after)].append(t)
    for members in groups.values():
        if len(members) < 2:
            continue
        canon = next((m for m in members if m.is_self), None) or min(members, key=tid)
        for m in members:
            if m is not canon:
                m.duplicate_of, m.duplicate_basis = canon.trans_id, "holdings"
                m.holding_conflict = False  # the rule itself says the holdings agree

    by_trade: dict[tuple[Any, ...], list[ExecutiveTrade]] = defaultdict(list)
    for t in sorted(live, key=tid):
        if t.duplicate_of is None and t.executor_id and t.reporter_id:
            trade = (t.symbol, t.security_type, t.transaction_date, t.quantity, t.price, t.method)
            by_trade[(t.executor_id, *trade)].append(t)
    for members in by_trade.values():
        by_reporter: dict[str, list[ExecutiveTrade]] = defaultdict(list)
        for m in members:
            by_reporter[m.reporter_id or ""].append(m)
        if len(by_reporter) < 2:
            continue
        executor = members[0].executor_id or ""
        basis: DuplicateBasis
        if executor in by_reporter:
            canon_reporter, basis = executor, "executor_own_row"
        else:
            canon_reporter = min(by_reporter, key=lambda r: tid(by_reporter[r][0]))
            basis = "executor"
        canon_rows = by_reporter[canon_reporter]
        for reporter, rows in by_reporter.items():
            if reporter == canon_reporter:
                continue
            for row, twin in zip(rows, canon_rows, strict=False):
                row.duplicate_of = twin.trans_id
                row.duplicate_basis = basis
                if row.detail is None or twin.detail is None:
                    row.holding_conflict = None  # unknown, never False
                else:
                    row.holding_conflict = (
                        row.detail.holding_before,
                        row.detail.holding_after,
                    ) != (twin.detail.holding_before, twin.detail.holding_after)


# ==================================================================================================
# Detail: JSON -> models
# ==================================================================================================


def _int_with_marker(value: str, what: str, notes: list[str]) -> int:
    text = value.strip()
    match = re.fullmatch(r"([\d,]+)\s*(\*+)?", text)
    if not match or not _QUANTITY.fullmatch(match.group(1)):
        raise ParseError(f"Form 59 detail {what} {value!r} is not a whole number")
    if match.group(2):
        notes.append(f"{what}: {match.group(2)!r}")
    return int(match.group(1).replace(",", ""))


def _submitted_at(value: str) -> datetime:
    match = re.fullmatch(r"(\d{1,2}/\d{1,2}/\d{4})\s+(\d{1,2}):(\d{2}):(\d{2})", value.strip())
    if not match:
        raise ParseError(f"Form 59 detail SubmitDate {value!r} is not 'dd/mm/yyyy HH:MM:SS'")
    try:
        day = _dmy_to_date(match.group(1))
    except ValueError as exc:
        raise ParseError(f"Form 59 detail SubmitDate {value!r} is not a valid date") from exc
    hour, minute, second = (int(match.group(i)) for i in (2, 3, 4))
    return datetime(day.year, day.month, day.day, hour, minute, second, tzinfo=BANGKOK)


_REPORT_KEYS = ("BatchNo", "Company", "Reporter", "Position", "SubmitDate", "BusinessTypeCode")
_TX_KEYS = (
    "TransExecutor",
    "SecuType",
    "TransDate",
    "OutstandingBefore",
    "TransVolumn",
    "AvgPrice",
    "OutstandingAfter",
    "TransType",
    "MarketSource",
    "TargetInfo",
    "RecordStatus",
)


def _check_report_payload(payload: Any, batch_no: str) -> dict[str, Any]:
    """Validate the detail API envelope; return its ``Report``. Raises, never returns partial."""
    if not isinstance(payload, dict) or not isinstance(payload.get("ResponseStatus"), dict):
        raise ParseError(f"Form 59 detail for batch {batch_no} has no ResponseStatus envelope")
    status = payload["ResponseStatus"]
    if status.get("Value") != "Y":
        reason = status.get("TextEn") or status.get("TextTh") or "no reason given"
        raise FetchError(
            f"SEC returned no Form 59 report for batch {batch_no} "
            f"(ResponseStatus {status.get('Value')!r}: {reason})"
        )
    report = payload.get("Report")
    if not isinstance(report, dict) or not isinstance(report.get("TransactionList"), list):
        raise ParseError(f"Form 59 detail for batch {batch_no} has no Report.TransactionList")
    missing = [k for k in _REPORT_KEYS if not isinstance(report.get(k), str)]
    if missing:
        raise ParseError(f"Form 59 detail for batch {batch_no} lacks header field(s) {missing}")
    if report["BatchNo"] != batch_no:
        raise ParseError(
            f"Form 59 detail answered batch {report['BatchNo']!r} when {batch_no!r} was asked for"
        )
    return report


def _detail_from_raw(tx: dict[str, Any], batch_no: str) -> ExecutiveTradeDetail:
    missing = [k for k in _TX_KEYS if not isinstance(tx.get(k), str)]
    if missing:
        raise ParseError(f"Form 59 detail for batch {batch_no} has a transaction without {missing}")
    notes: list[str] = []
    executor = tx["TransExecutor"]
    label = _BR.split(executor, maxsplit=1)[0].strip()
    return ExecutiveTradeDetail(
        holder_label=label,
        executor=executor,
        security_type=tx["SecuType"],
        transaction_date=_strict_date(tx["TransDate"], "detail TransDate", None),
        holding_before=_int_with_marker(tx["OutstandingBefore"], "holding_before", notes),
        quantity=_int_with_marker(tx["TransVolumn"], "quantity", notes),
        avg_price=_strict_decimal(tx["AvgPrice"].strip(), "detail AvgPrice", None, listing=False),
        holding_after=_int_with_marker(tx["OutstandingAfter"], "holding_after", notes),
        method=tx["TransType"],
        side=side_for(tx["TransType"]),
        market_source=tx["MarketSource"],
        counterparty=tx["TargetInfo"].strip() or None,
        remark="; ".join(notes) or None,
        record_status=tx["RecordStatus"],
    )


def _report_from_raw(report: dict[str, Any], lang: Language) -> ExecutiveTradeReport:
    batch_no = report["BatchNo"]
    return ExecutiveTradeReport(
        batch_no=batch_no,
        company_name=report["Company"],
        reporter_name=report["Reporter"],
        position=report["Position"],
        submitted_at=_submitted_at(report["SubmitDate"]),
        business_type_code=report["BusinessTypeCode"],
        lang=lang,
        transactions=[_detail_from_raw(tx, batch_no) for tx in report["TransactionList"]],
    )


def _price_matches(listing: Decimal | None, detail: Decimal) -> bool:
    if listing is None:  # the listing shows '-' where the detail files 0.00
        return detail == 0
    cent = Decimal("0.01")
    return listing in (
        detail.quantize(cent, rounding=ROUND_HALF_UP),
        detail.quantize(cent, rounding=ROUND_HALF_EVEN),
    )


def _link_details(items: list[ExecutiveTrade], reports: list[ExecutiveTradeReport]) -> None:
    """Attach each report's transactions to their listing rows, without guessing.

    The detail API has no transaction id, and its order is by date while the listing's transId
    sequence is by entry (PEACE batch 592000452610: 6 of 53 matched by position). So rows are
    matched on (transaction date, quantity, method, security type, price within the listing's
    rounding) plus the reporter's name.

    A key that occurs once on each side links. A key that occurs N times on each side links only
    when the N detail transactions are identical in every field, so any pairing attaches the same
    data: the CANCELED re-filings of CREDIT batch 592001242610 are such a pair. Anything else stays
    ``detail=None`` and is counted on ``ExecutiveTradeList.detail_unmatched`` (about 1.3% of
    linked rows on 2026-10-07).
    """
    by_batch: dict[str, list[ExecutiveTrade]] = defaultdict(list)
    for t in items:
        if t.batch_no:
            by_batch[t.batch_no].append(t)

    def listing_key(t: ExecutiveTrade) -> tuple[Any, ...]:
        return (t.transaction_date, t.quantity, side_for(t.method), t.method, t.security_type)

    def detail_key(d: ExecutiveTradeDetail) -> tuple[Any, ...]:
        base, _ = _split_last_group(d.method)
        return (d.transaction_date, d.quantity, d.side, base, d.security_type)

    for report in reports:
        rows = by_batch.get(report.batch_no, [])
        if rows and report.symbol is None:
            report.symbol = rows[0].symbol
        reporter = " ".join(report.reporter_name.split())
        row_groups: dict[tuple[Any, ...], list[ExecutiveTrade]] = defaultdict(list)
        for t in sorted(rows, key=lambda r: r.trans_id or ""):
            if " ".join(t.reporter_name.split()) == reporter:
                row_groups[listing_key(t)].append(t)
        detail_groups: dict[tuple[Any, ...], list[ExecutiveTradeDetail]] = defaultdict(list)
        for d in report.transactions:
            detail_groups[detail_key(d)].append(d)
        for key, group in row_groups.items():
            details = detail_groups.get(key, [])
            if not details or len(details) != len(group):
                continue
            first = details[0].model_dump()
            if any(d.model_dump() != first for d in details[1:]):
                continue
            if not all(_price_matches(t.price, details[0].avg_price) for t in group):
                continue
            for t, d in zip(group, details, strict=True):
                t.detail = d.model_copy(update={"trans_id": t.trans_id})


# ==================================================================================================
# Transport
# ==================================================================================================


def _stateless(config: FetcherConfig | None) -> FetcherConfig:
    return (config or FetcherConfig()).model_copy(update={"use_session": False})


def _viewmore_url(
    lang: Language,
    date_type: DateType,
    start: date | None,
    end: date | None,
    unique_id: str | None = None,
) -> str:
    """Build the "display all results" URL. Refuses to build one without both dates.

    Undated, this page returns the WHOLE Form 59 database: 91,245 rows and 70 MB on 2026-10-07.
    That is never what a caller wants and is a heavy load on the SEC, so it is an invariant here
    rather than a convention at the call sites.
    """
    if start is None or end is None:
        raise ValueError(
            "refusing to build an undated Form 59 ViewMore URL: without DateFrom/DateTo it returns "
            "the entire database (91,245 rows, 70 MB on 2026-10-07)"
        )
    if start > end:
        raise InvalidDateError(f"Form 59 window starts after it ends: {start} > {end}")
    if date_type not in SEC_R59_DATE_TYPES:
        raise ValueError(f"date_type must be 'received' or 'transaction', got {date_type!r}")
    params: list[tuple[str, str]] = []
    if unique_id is not None:
        if not unique_id.isdigit():
            raise ValueError(f"unique_id must be the SEC's numeric id, got {unique_id!r}")
        params.append(("UniqueIdReference", unique_id))
    params += [
        ("DateType", SEC_R59_DATE_TYPES[date_type]),
        ("DateFrom", start.strftime("%Y%m%d")),
        ("DateTo", end.strftime("%Y%m%d")),
    ]
    return SEC_BASE_URL + SEC_R59_VIEWMORE_ENDPOINT.format(lang=lang) + "?" + urlencode(params)


def _windows(start: date, end: date) -> list[tuple[date, date]]:
    """Split [start, end] into consecutive windows of at most SEC_R59_MAX_WINDOW_DAYS days."""
    out: list[tuple[date, date]] = []
    current = start
    while current <= end:
        last = min(end, current + timedelta(days=SEC_R59_MAX_WINDOW_DAYS - 1))
        out.append((current, last))
        current = last + timedelta(days=1)
    return out


def _coerce_date(value: date | str | None, name: str) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise InvalidDateError(f"{name} must be a date or 'YYYY-MM-DD', got {value!r}") from exc


def _today() -> date:
    return datetime.now(BANGKOK).date()


async def _fetch_windows(
    fetcher: AsyncDataFetcher,
    *,
    lang: Language,
    date_type: DateType,
    start: date,
    end: date,
    unique_id: str | None,
) -> list[tuple[tuple[date, date], int, list[dict[str, str]]]]:
    referer = SEC_BASE_URL + SEC_R59_PAGE_ENDPOINT.format(lang=lang)
    pages = []
    for window in _windows(start, end):
        url = _viewmore_url(lang, date_type, *window, unique_id=unique_id)
        response = await fetcher.fetch(url, headers=build_sec_headers(referer=referer))
        if not 200 <= response.status_code < 300:
            raise HTTPStatusError(
                f"Form 59 listing returned HTTP {response.status_code}: {url}",
                status_code=response.status_code,
                url=url,
            )
        reported, rows = _parse_listing(response.text, url, lang)
        pages.append((window, reported, rows))
    return pages


async def _fetch_report_payload(
    fetcher: AsyncDataFetcher, batch_no: str, lang: Language
) -> dict[str, Any]:
    url = SEC_BASE_URL + SEC_R59_REPORT_API_ENDPOINT
    page = SEC_BASE_URL + SEC_R59_REPORT_PAGE_ENDPOINT.format(lang=lang)
    headers = {
        **build_sec_headers(referer=f"{page}?batchNo={batch_no}", origin=True),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
    }
    payload = await fetcher.fetch_json(
        url, headers, method="POST", json_body={"BatchNo": batch_no, "Lang": lang.capitalize()}
    )
    return _check_report_payload(payload, batch_no)


def _check_batch_no(batch_no: str) -> str:
    value = str(batch_no).strip()
    if not value.isdigit():
        raise ValueError(f"batch_no must be the digits of a Form 59 BatchNo, got {batch_no!r}")
    return value


# ==================================================================================================
# Public API — listing
# ==================================================================================================


async def fetch_executive_trades_raw(
    start: date,
    end: date,
    *,
    unique_id: str | None = None,
    date_type: DateType = "received",
    lang: str = "th",
    config: FetcherConfig | None = None,
) -> list[dict[str, str]]:
    """Form 59 listing rows as verbatim strings: the escape hatch below the models.

    Each dict has the nine cells (``company``, ``reporter_name``, ``relationship``,
    ``security_type``, ``transaction_date``, ``quantity``, ``price``, ``method``, ``remark``), the
    link's ``href`` and its ``batchNo`` / ``transId`` / ``reporter`` / ``executor`` parameters
    ('' when absent), and ``revoked`` ('true'/'false') with ``quantity_note`` (the text under a
    struck quantity). The stated count is still verified: a short page raises.

    Args:
        start, end: inclusive window, split into ≤ 366-day requests.
        unique_id: the SEC's company id (``resolve_company(...).unique_id``); None for all.
        date_type: 'received' (SEC received date) or 'transaction' (trade date).
        lang: 'th' or 'en'. Thai dates are B.E. in the raw strings; English ones C.E.
    """
    language = normalize_language(lang)
    async with AsyncDataFetcher(config=_stateless(config)) as fetcher:
        pages = await _fetch_windows(
            fetcher, lang=language, date_type=date_type, start=start, end=end, unique_id=unique_id
        )
    return [row for _, _, rows in pages for row in rows]


async def fetch_executive_trades(
    start: date,
    end: date,
    *,
    unique_id: str | None = None,
    date_type: DateType = "received",
    lang: str = "th",
    with_details: bool = False,
    config: FetcherConfig | None = None,
    symbol: str | None = None,
) -> ExecutiveTradeList:
    """Form 59 rows for a window, as validated models (see :func:`get_executive_trades`).

    Takes the SEC company id rather than a symbol; ``get_executive_trades`` resolves symbols.
    ``symbol`` is only echoed on the query.
    """
    language = normalize_language(lang)
    fetched_at = datetime.now(BANGKOK)
    async with AsyncDataFetcher(config=_stateless(config)) as fetcher:
        pages = await _fetch_windows(
            fetcher, lang=language, date_type=date_type, start=start, end=end, unique_id=unique_id
        )
        items: list[ExecutiveTrade] = []
        for (w_start, w_end), _, rows in pages:
            day = w_start if date_type == "received" and w_start == w_end else None
            items += [_trade_from_raw(r, url=None, received_date=day) for r in rows]
        result = ExecutiveTradeList(
            items=items,
            reported_count=sum(reported for _, reported, _ in pages),
            query=ExecutiveTradeQuery(
                date_type=date_type,
                start=start,
                end=end,
                unique_id=unique_id,
                symbol=symbol,
                windows=len(pages),
            ),
            lang=language,
            fetched_at=fetched_at,
            details_requested=with_details,
        )
        if with_details:
            await _enrich(fetcher, result, language)
    _mark_duplicates(result.items)
    unknown = result.unknown_labels
    if unknown["method"] or unknown["security_type"]:
        logger.warning(f"Form 59: labels outside the known vocabulary: {unknown}")
    logger.info(f"Form 59: {result!r}")
    return result


async def _enrich(fetcher: AsyncDataFetcher, result: ExecutiveTradeList, lang: Language) -> None:
    """Fetch each distinct batch's detail once, sequentially, and link it to the rows.

    A failed batch is recorded on ``detail_failures`` and its rows keep ``detail=None`` (a partial
    loss reports). If every batch fails, the first failure is raised (a total loss raises). A
    block page stops everything at once: sending more to a host that has started refusing only
    deepens the block.
    """
    batches = list(dict.fromkeys(t.batch_no for t in result.items if t.batch_no))
    if len(batches) > SEC_R59_MAX_DETAIL_BATCHES:
        raise ValueError(
            f"with_details=True would send {len(batches)} detail requests (one per report); the "
            f"cap is {SEC_R59_MAX_DETAIL_BATCHES}. Narrow the window or filter by symbol."
        )
    failures: list[FetchError] = []
    for batch_no in batches:
        try:
            report = _report_from_raw(await _fetch_report_payload(fetcher, batch_no, lang), lang)
        except BlockedError:
            raise
        except FetchError as exc:
            failures.append(exc)
            result.detail_failures[batch_no] = f"{type(exc).__name__}: {exc}"
            logger.warning(f"Form 59 detail for batch {batch_no} failed: {exc}")
            continue
        result.reports.append(report)
    if batches and len(failures) == len(batches):
        first = failures[0]
        if len(failures) > 1:
            first.add_note(f"All {len(failures)} Form 59 detail requests failed.")
        raise first
    _link_details(result.items, result.reports)


async def get_executive_trades(
    received_date: date | str | None = None,
    *,
    symbol: str | None = None,
    date_type: DateType = "received",
    start: date | str | None = None,
    end: date | str | None = None,
    lang: str = "th",
    with_details: bool = False,
    config: FetcherConfig | None = None,
) -> ExecutiveTradeList:
    """Directors' and executives' reported trades (SEC Form 59, แบบ 59).

    With no arguments: every report SEC **received today** (Asia/Bangkok). That is NOT the site's
    default page, which shows what was *recorded into the system* today, limited to trades up to
    a month old. Today's received-date set can also still grow during the day.

    Args:
        received_date: one SEC received day (a date or 'YYYY-MM-DD'). Mutually exclusive with
            start/end.
        symbol: e.g. 'SPALI'. Resolved strictly to the SEC company id (no name matching); an
            unknown symbol raises CompanyNotFoundError. None = all companies.
        date_type: with start/end, filter by 'received' (SEC received date, the default) or
            'transaction' (trade date).
        start, end: an inclusive range (dates or 'YYYY-MM-DD'). ``end`` defaults to today. Ranges
            are fetched in ≤ 366-day windows.
        lang: 'th' (default; Thai labels) or 'en'.
        with_details: also fetch each report's detail (one request per distinct report, at most
            100, or ValueError before any detail request is sent): holdings before and after,
            unrounded price, channel and counterparty. Duplicates are then decided by holdings.
        config: optional FetcherConfig; SEC requests always run with use_session=False.

    Returns:
        An ExecutiveTradeList. ``economic_trades()`` drops revoked rows and duplicate copies;
        ``to_table()`` renders the Thai summary table; ``to_dataframe()`` needs pandas.

    Raises:
        InvalidDateError: conflicting or malformed dates.
        CompanyNotFoundError / AmbiguousCompanyError: the symbol did not resolve to one issuer.
        ParseError: a page whose stated count differs from its rows, or an unknown layout.
        HTTPStatusError, FetchError: transport failures (BlockedError for a WAF block page).
    """
    language = normalize_language(lang)
    day = _coerce_date(received_date, "received_date")
    first = _coerce_date(start, "start")
    last = _coerce_date(end, "end")
    if day is not None:
        if first is not None or last is not None:
            raise InvalidDateError("Pass either received_date or start/end, not both")
        if date_type != "received":
            raise InvalidDateError("received_date filters by received date; use start/end instead")
        first = last = day
    elif first is None:
        if last is not None:
            raise InvalidDateError("end was given without start")
        if date_type != "received":
            raise InvalidDateError("date_type='transaction' needs start (and optionally end)")
        first = last = _today()
    elif last is None:
        last = _today()
    assert first is not None and last is not None  # every branch above sets both
    if first > last:
        raise InvalidDateError(f"start {first} is after end {last}")

    unique_id: str | None = None
    normalized: str | None = None
    if symbol is not None:
        normalized = normalize_symbol(symbol)
        match = await resolve_company(normalized, lang=language, config=config)
        if match is None:
            raise CompanyNotFoundError(f"No SEC issuer matched {normalized!r}")
        unique_id = match.unique_id
    return await fetch_executive_trades(
        first,
        last,
        unique_id=unique_id,
        date_type=date_type,
        lang=language,
        with_details=with_details,
        config=config,
        symbol=normalized,
    )


# ==================================================================================================
# Public API — detail
# ==================================================================================================


async def fetch_executive_trade_report_raw(
    batch_no: str, lang: str = "th", *, config: FetcherConfig | None = None
) -> dict[str, Any]:
    """The detail API's ``Report`` object for one batch, verbatim (after envelope checks).

    Raises FetchError when SEC answers ``ResponseStatus`` other than 'Y', ParseError when the
    envelope or a header field is missing.
    """
    language = normalize_language(lang)
    number = _check_batch_no(batch_no)
    async with AsyncDataFetcher(config=_stateless(config)) as fetcher:
        return await _fetch_report_payload(fetcher, number, language)


async def fetch_executive_trade_report(
    batch_no: str, lang: str = "th", *, config: FetcherConfig | None = None
) -> ExecutiveTradeReport:
    """One Form 59 report (a batch) as a validated model; see :func:`get_executive_trade_report`."""
    language = normalize_language(lang)
    return _report_from_raw(
        await fetch_executive_trade_report_raw(batch_no, language, config=config), language
    )


async def get_executive_trade_report(
    batch_no: str, lang: str = "th", *, config: FetcherConfig | None = None
) -> ExecutiveTradeReport:
    """The full Form 59 report behind a listing row: every transaction with holdings.

    ``batch_no`` is :attr:`ExecutiveTrade.batch_no` (the ``batchNo`` of the row's link). One call
    returns every transaction in the batch, in date order, each with holding before and after,
    the unrounded average price, the channel and broker, the counterparty, and a
    ``holding_consistent`` check. ``symbol`` is None here: the API does not state it.
    """
    return await fetch_executive_trade_report(batch_no, lang, config=config)
