"""Pydantic models for the Bank of Thailand API (1.0.0), built from the live responses.

The official OpenAPI documents get several shapes wrong: lists declared as objects, the holiday
list declared bare while the API wraps it, and no schema at all for some endpoints. These models
follow what the API actually sent on 2026-11-23.

Every BOT value arrives as a STRING (``"1.15000"``), and a missing one as ``""``. Numeric fields
here are ``float | None`` (``""`` and ``"-"`` become ``None``). Text and period fields keep BOT's
text verbatim.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Generic, TypeVar

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, computed_field


def _to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    text = str(value).strip().replace(",", "")
    if text in ("", "-"):
        return None
    return float(text)


def _to_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_date(value: Any) -> date | None:
    if value is None or isinstance(value, date):
        return value
    text = str(value).strip().replace("/", "-")
    return date.fromisoformat(text[:10]) if text else None


def _to_flag(value: Any) -> bool | None:
    text = str(value or "").strip().upper()
    return {"T": True, "Y": True, "F": False, "N": False}.get(text)


Number = Annotated[float | None, BeforeValidator(_to_float)]
Text = Annotated[str | None, BeforeValidator(_to_text)]
Day = Annotated[date | None, BeforeValidator(_to_date)]
Flag = Annotated[bool | None, BeforeValidator(_to_flag)]

_CONFIG = ConfigDict(populate_by_name=True, str_strip_whitespace=True, extra="ignore")


class BotModel(BaseModel):
    """Base: aliases accepted, whitespace stripped, unknown fields ignored (BOT adds fields)."""

    model_config = _CONFIG


# --- report header (the Stat-* endpoints) -----------------------------------------------------


class ReportHeader(BotModel):
    """The ``data_header`` block of a Stat-* report: its name, unit, sources and remarks."""

    report_name_eng: Text = None
    report_name_th: Text = None
    unit_eng: Text = Field(default=None, alias="report_uoq_name_eng")
    unit_th: Text = Field(default=None, alias="report_uoq_name_th")
    last_updated: Day = None
    sources: list[dict[str, Any]] = Field(default_factory=list, alias="report_source_of_data")
    remarks: list[dict[str, Any]] = Field(default_factory=list, alias="report_remark")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_discontinued(self) -> bool:
        """Whether BOT's own remark says the table is discontinued.

        Seen 2026-11-23 on external interest rates, the spot rate and swap points, each
        ``last_updated`` 2024-12-27 with empty rows. THB implied rates has the same empty rows and
        date but NO such remark, so this is ``False`` for it: check ``BotReport.has_values`` for
        "is there data". A computed field, so it survives ``model_dump()``.
        """
        return any(
            "discontinued" in str(r.get("report_remark_eng", "")).lower() for r in self.remarks
        )


RowT = TypeVar("RowT", bound=BaseModel)


class BotReport(BotModel, Generic[RowT]):
    """One BOT response: its API label, timestamp, optional header, and the rows."""

    api: Text = None
    timestamp: Text = None
    header: ReportHeader | None = None
    rows: list[RowT] = Field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.rows)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_values(self) -> bool:
        """Whether any row carries a number. A stopped table still answers HTTP 200, with rows
        whose every value is empty, so ``len(report) > 0`` does not mean there is data.
        """
        return any(isinstance(value, float) for row in self.rows for value in row.__dict__.values())

    def __len__(self) -> int:
        return len(self.rows)


# --- Interest Rates ---------------------------------------------------------------------------


class PolicyRate(BotModel):
    """The policy rate and the MPC announcement behind it."""

    rate: Number = Field(default=None, alias="data", description="Percent per annum")
    announcement_date: Day = None
    effective_datetime: datetime | None = None
    news_text_en: Text = None
    news_text_th: Text = None
    api: Text = None
    timestamp: Text = None


class BiborRate(BotModel):
    """One day of BIBOR, for one bank (``bibor_rate``) or the average (``bibor_avg_rate``)."""

    period: Day = None
    bank_name_th: Text = Field(default=None, alias="bankname_th")
    bank_name_eng: Text = Field(default=None, alias="bankname_eng")
    overnight: Number = Field(default=None, alias="bibor_o_n")
    one_week: Number = Field(default=None, alias="bibor_1_week")
    one_month: Number = Field(default=None, alias="bibor_1_month")
    two_months: Number = Field(default=None, alias="bibor_2_month")
    three_months: Number = Field(default=None, alias="bibor_3_month")
    six_months: Number = Field(default=None, alias="bibor_6_month")
    nine_months: Number = Field(default=None, alias="bibor_9_month")
    one_year: Number = Field(default=None, alias="bibor_1_year")


class _BankNamed(BotModel):
    """Rows that name either a bank (per-bank) or a group summary (``name_*``, min-max/average)."""

    period: Day = None
    bank_type_name_th: Text = None
    bank_type_name_eng: Text = None
    bank_name_th: Text = None
    bank_name_eng: Text = None
    name_th: Text = Field(default=None, description="Summary rows: e.g. the min-max group's name")
    name_eng: Text = None


class DepositRate(_BankNamed):
    """Deposit rates for individuals: one bank, or a group's min-max (percent per annum)."""

    saving_min: Number = None
    saving_max: Number = None
    fixed_3m_min: Number = Field(default=None, alias="fix_3_mths_min")
    fixed_3m_max: Number = Field(default=None, alias="fix_3_mths_max")
    fixed_6m_min: Number = Field(default=None, alias="fix_6_mths_min")
    fixed_6m_max: Number = Field(default=None, alias="fix_6_mths_max")
    fixed_12m_min: Number = Field(default=None, alias="fix_12_mths_min")
    fixed_12m_max: Number = Field(default=None, alias="fix_12_mths_max")
    fixed_24m_min: Number = Field(default=None, alias="fix_24_mths_min")
    fixed_24m_max: Number = Field(default=None, alias="fix_24_mths_max")


class LoanRate(_BankNamed):
    """Loan rates of commercial banks: one bank, or a group's average (percent per annum)."""

    mor: Number = None
    mlr: Number = None
    mrr: Number = None
    ceiling_rate: Number = None
    default_rate: Number = None
    creditcard_min: Number = None
    creditcard_max: Number = None


class InterbankRate(BotModel):
    """Interbank transaction rates for one term (``O/N``, ``T/N``, ``1 month``... ``Total``)."""

    period: Day = None
    term_th: Text = Field(default=None, alias="term_type_name_th")
    term: Text = Field(default=None, alias="term_type_name_eng")
    min_rate: Number = Field(default=None, alias="min_interest_rate")
    max_rate: Number = Field(default=None, alias="max_interest_rate")
    mode_rate: Number = Field(default=None, alias="mode_interest_rate")
    weighted_average_rate: Number = Field(default=None, alias="weighted_average_interest_rate")


class RateTypeQuote(BotModel):
    """External or THB implied interest rate for one rate type (both empty since 2024-12-27)."""

    period: Day = None
    rate_type_th: Text = Field(default=None, alias="rate_type_name_th")
    rate_type: Text = Field(default=None, alias="rate_type_name_eng")
    rate: Number = Field(default=None, alias="interest_rate")


class SpotRate(BotModel):
    """USD/THB spot bid/offer (discontinued 2024-12-27: rows come back empty)."""

    period: Day = None
    bid_rate: Number = None
    offer_rate: Number = None


class SwapPoint(BotModel):
    """Onshore swap points for one term, in satangs (discontinued 2024-12-27)."""

    period: Day = None
    term_th: Text = Field(default=None, alias="term_type_name_th")
    term: Text = Field(default=None, alias="term_type_name_eng")
    bid_rate: Number = None
    offer_rate: Number = None


# --- Exchange Rates ---------------------------------------------------------------------------


class ExchangeRate(BotModel):
    """Average THB rate for one foreign currency over a period (baht per unit of currency).

    ``period`` is BOT's text for the frequency asked: ``2026-11-20``, ``2026-10``, ``2026-Q3`` or
    ``2025``.
    """

    period: Text = None
    currency_id: Text = None
    currency_name_th: Text = None
    currency_name_eng: Text = None
    buying_sight: Number = None
    buying_transfer: Number = None
    selling: Number = None
    mid_rate: Number = None


class ReferenceRate(BotModel):
    """The weighted-average interbank THB/USD rate over a period (``period`` as above)."""

    period: Text = None
    rate: Number = None


# --- Debt Securities Auction ------------------------------------------------------------------


class BondAuctionResult(BotModel):
    """One government or BOT debt securities auction (amounts in million baht, yields in %)."""

    auction_date: Day = None
    debt_securities_type: Text = None
    thaibma_symbol: Text = None
    isin_code: Text = None
    auction_name_th: Text = Field(default=None, alias="auction_nm_th")
    cfi_code: Text = None
    reopen_from_th: Text = Field(default=None, alias="re_open_from_th")
    coupon_rate: Text = Field(
        default=None, description="Verbatim: '2.44', 'Discount', 'Compounded THOR  0.05'..."
    )
    time_to_maturity: Text = None
    payment_date: Day = None
    start_date_of_interest_earning_period: Day = None
    maturity_date: Day = None
    issue_amount_ncb_cb: Number = None
    accepted_amount_ncb_cb: Number = None
    accepted_amount_ncb: Number = None
    accepted_amount_cb: Number = None
    greenshoe_option_amount: Number = None
    pao_amount: Number = None
    over_allotment_amount: Number = None
    grand_total_amount: Number = None
    accepted_lowest_yield: Number = None
    accepted_highest_yield: Number = None
    weighted_average_accepted_yield: Number = None
    bid_coverage_ratio: Number = None
    auction_status: Text = Field(default=None, alias="auction_st")


# --- Others: financial institutions' holidays -------------------------------------------------


class FinancialInstitutionHoliday(BotModel):
    """One financial institutions' holiday. Bank holidays, NOT the SET market calendar."""

    holiday_date: Day = Field(default=None, alias="Date")
    date_thai: Text = Field(default=None, alias="DateThai", description="BOT's B.E. text")
    weekday: Text = Field(default=None, alias="HolidayWeekDay")
    weekday_th: Text = Field(default=None, alias="HolidayWeekDayThai")
    description: Text = Field(default=None, alias="HolidayDescription")
    description_th: Text = Field(default=None, alias="HolidayDescriptionThai")


# --- Statistics -------------------------------------------------------------------------------


class StatCategory(BotModel):
    """One Statistics category (e.g. ``FM_RT_013``: THOR and THOR Average)."""

    category: str
    description_th: Text = None
    description_eng: Text = None


class StatSeriesInfo(BotModel):
    """A series as listed by a category or found by a search: its code and metadata.

    The search fills more fields than a category listing (frequency, unit, lag, schedule); the
    rest stay ``None``.
    """

    series_code: str
    series_name_th: Text = None
    series_name_eng: Text = None
    category: Text = None
    categories: list[str] = Field(default_factory=list)
    observation_start: Text = None
    observation_end: Text = None
    last_update_date: Day = None
    frequency: Text = None
    frequency_short: Text = None
    unit_th: Text = None
    unit_eng: Text = None
    data_type: Text = None
    seasonal_adjustment_flag: Text = None
    lag_time: Text = None
    release_schedule_eng: Text = None
    release_schedule_th: Text = None
    description_eng: Text = None
    description_th: Text = None
    source_of_data_eng: Text = None
    source_of_data_th: Text = None


class StatObservation(BotModel):
    """One value of a series; ``period`` is BOT's text (``2026-11-23``, ``2026-10``...)."""

    period: str = Field(alias="period_start")
    value: Number = None


class StatSeries(BotModel):
    """A series with its observations over the requested window."""

    series_code: str
    series_name_th: Text = None
    series_name_eng: Text = None
    unit_th: Text = None
    unit_eng: Text = None
    series_type: Text = None
    frequency: Text = None
    last_update_date: Day = None
    observations: list[StatObservation] = Field(default_factory=list)

    @property
    def latest(self) -> StatObservation | None:
        """The last observation with a value, or ``None``."""
        valued = [o for o in self.observations if o.value is not None]
        return max(valued, key=lambda o: o.period) if valued else None


# --- License Check ----------------------------------------------------------------------------


class LicensedEntity(BotModel):
    """A business the Bank of Thailand has licensed or registered."""

    id: str = Field(alias="Id")
    authorized_name: Text = Field(default=None, alias="AuthorizedName")
    branch_name: Text = Field(default=None, alias="BranchName")
    type_id: Text = Field(default=None, alias="TypeId")
    type_name: Text = Field(default=None, alias="TypeName")
    last_update: Text = Field(default=None, alias="LastUpdate", description="BOT's text")
    address: Text = Field(default=None, alias="Address")
    telephone: Text = Field(default=None, alias="Telephone")
    takes_deposits: Flag = Field(default=None, alias="DepositFlag")
    lends: Flag = Field(default=None, alias="LoanFlag")
    hire_purchase_leasing: Flag = Field(default=None, alias="HPLSFlag")


class License(BotModel):
    """One licence held by an entity (dates are BOT's Thai text, e.g. ``5 สิงหาคม 2492``)."""

    id: str = Field(alias="Id")
    name: Text = Field(default=None, alias="Name")
    code: Text = Field(default=None, alias="Code")
    license_no: Text = Field(default=None, alias="LcnNo")
    status_code: Text = Field(default=None, alias="StatusCode")
    status_name: Text = Field(default=None, alias="StatusName")
    permit_date: Text = Field(default=None, alias="PermitDate")
    start_date: Text = Field(default=None, alias="StartDate")
    end_date: Text = Field(default=None, alias="EndDate")


class LicenseSearchResult(BotModel):
    """A page of license-check search results, with BOT's totals."""

    entities: list[LicensedEntity] = Field(default_factory=list)
    total: int | None = None
    page: int | None = None
    per_page: int | None = None
    groups: list[dict[str, Any]] = Field(default_factory=list)


class LicensedEntityDetail(BotModel):
    """One entity's record, its licences, and its branches (as BOT sends them)."""

    entity: LicensedEntity
    licenses: list[License] = Field(default_factory=list)
    branches: list[dict[str, Any]] = Field(default_factory=list)


class LicenseDocument(BotModel):
    """A licence document file (BOT served a PDF on 2026-11-23)."""

    content: bytes
    content_type: str = ""
    size: int
    auth_id: str
    doc_id: str


def build_report(data: Any, row_model: type[RowT], context: str) -> BotReport[RowT]:
    """A :class:`BotReport` of ``row_model`` rows from a BOT ``{"result": {...}}`` body.

    Handles both shapes BOT uses: ``data: {data_header, data_detail: [...]}`` and ``data: [...]``
    (holidays). The rows are kept as sent, including the empty placeholder rows of a discontinued
    table: ``header.is_discontinued`` says so, the rows are not dropped.
    """
    from settfex.services.bot.client import result_of
    from settfex.utils.parsing import validate_or_raise

    result = result_of(data, context)
    payload = result.get("data")
    header: ReportHeader | None = None
    raw_rows: list[Any] = []
    if isinstance(payload, dict):
        if isinstance(payload.get("data_header"), dict):
            header = validate_or_raise(ReportHeader, payload["data_header"], context=context)
        detail = payload.get("data_detail")
        if isinstance(detail, list):
            raw_rows = detail
        elif isinstance(detail, dict):
            raw_rows = [detail]
    elif isinstance(payload, list):
        raw_rows = payload
    rows = [validate_or_raise(row_model, row, context=context) for row in raw_rows]
    report_cls = BotReport[row_model]  # type: ignore[valid-type]
    report: BotReport[RowT] = report_cls(
        api=result.get("api"), timestamp=result.get("timestamp"), header=header, rows=rows
    )
    return report
