"""The six Bank of Thailand products on their real answers (fixtures captured 2026-11-23).

Each test feeds a captured body through the real client, by patching ``AsyncDataFetcher.fetch``.
It then checks what a caller relies on: values as numbers (BOT sends strings), ``""`` as
``None``, the endpoint and parameters sent, and the traps the API sets.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from settfex.exceptions import BotSeriesNotFoundError
from settfex.services.bot import (
    InterestRatesService,
    get_bibor,
    get_bond_auction_results,
    get_deposit_rates,
    get_exchange_rates,
    get_financial_institution_holidays,
    get_interbank_rates,
    get_license_document,
    get_licensed_entity,
    get_loan_rates,
    get_policy_rate,
    get_reference_rates,
    get_stat_categories,
    get_stat_observations,
    get_stat_series_list,
    search_licensed_entities,
    search_stat_series,
)
from settfex.utils.data_fetcher import AsyncDataFetcher, FetchResponse
from settfex.utils.parsing import ResponseParseError

FIXTURES = Path(__file__).parent / "fixtures_bot"


def _load(name: str) -> str:
    return (FIXTURES / f"{name}.json").read_text(encoding="utf-8")


def _resp(text: str, status: int = 200, content_type: str = "application/json") -> FetchResponse:
    return FetchResponse(
        status_code=status,
        content=text.encode(),
        text=text,
        headers={"content-type": content_type},
        url="https://gateway.api.bot.or.th/x",
        elapsed=0.1,
    )


class _Gateway:
    """Answers with one fixture and records the URLs it was asked for."""

    def __init__(self, fixture: str | FetchResponse) -> None:
        self.answer = fixture if isinstance(fixture, FetchResponse) else _resp(_load(fixture))
        self.urls: list[str] = []

    async def __call__(self, url: str, headers: Any = None, **kw: Any) -> FetchResponse:
        self.urls.append(url)
        return self.answer


def _patched(gw: _Gateway) -> Any:
    return patch.object(AsyncDataFetcher, "fetch", gw)


class TestInterestRates:
    @pytest.mark.asyncio
    async def test_policy_rate(self) -> None:
        gw = _Gateway("policy_rate")
        with _patched(gw):
            pr = await get_policy_rate()
        assert pr.rate == 1.0 and pr.announcement_date == date(2026, 10, 28)
        assert pr.effective_datetime is not None and pr.effective_datetime.hour == 14
        assert gw.urls == ["https://gateway.api.bot.or.th/PolicyRate/v3/policy_rate/"]

    @pytest.mark.asyncio
    async def test_bibor_average_is_numbers_and_empty_is_none(self) -> None:
        gw = _Gateway("bibor_avg_rate")
        with _patched(gw):
            rep = await get_bibor("2026-11-16", "2026-11-20")
        row = rep.rows[0]
        assert (row.period, row.three_months, row.six_months) == (date(2026, 11, 16), 1.15, 1.20994)
        assert row.nine_months is None, "BOT sends '' for a tenor with no fixing"
        assert "bibor_avg_rate/?start_period=2026-11-16&end_period=2026-11-20" in gw.urls[0]
        assert rep.has_values

    @pytest.mark.asyncio
    async def test_bibor_by_bank(self) -> None:
        gw = _Gateway("bibor_rate")
        with _patched(gw):
            rep = await get_bibor("2026-11-16", average=False, bank="Bangkok Bank")
        assert rep.rows[0].bank_name_eng == "Bangkok Bank"
        assert "bibor_rate/" in gw.urls[0] and "bank=Bangkok+Bank" in gw.urls[0]

    @pytest.mark.asyncio
    async def test_deposit_and_loan_rates(self) -> None:
        with _patched(_Gateway("deposit_rate")):
            d = await get_deposit_rates("2026-11-16")
        with _patched(_Gateway("avg_deposit_rate")):
            r = await get_deposit_rates("2026-11-16", ranges=True)
        with _patched(_Gateway("loan_rate")):
            lo = await get_loan_rates("2026-11-16")
        with _patched(_Gateway("avg_loan_rate")):
            la = await get_loan_rates("2026-11-16", averages=True)
        assert d.rows[0].bank_name_eng == "Bangkok Bank" and d.rows[0].fixed_3m_max == 0.65
        assert r.rows[0].name_eng is not None and r.rows[0].saving_max == 1.75
        assert lo.rows[0].mlr == 6.35 and la.rows[0].mlr == 7.0026

    @pytest.mark.asyncio
    async def test_interbank_rates_carry_the_header(self) -> None:
        gw = _Gateway("interbank_txn_rate")
        with _patched(gw):
            rep = await get_interbank_rates("2026-11-16", "2026-11-20", term="O/N")
        assert rep.header is not None and rep.header.last_updated == date(2026, 11, 23)
        assert rep.rows[0].term == "O/N" and rep.rows[0].weighted_average_rate == 0.95682
        assert "term_type=O%2FN" in gw.urls[0]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("method", "fixture", "remark"),
        [
            ("fetch_external_rates", "ext_int_rate", True),
            ("fetch_spot_rates", "spot_rate", True),
            ("fetch_swap_points", "swap_point", True),
            ("fetch_implied_rates", "thb_implied_rate", False),
        ],
    )
    async def test_the_four_stopped_tables_answer_200_with_no_values(
        self, method: str, fixture: str, remark: bool
    ) -> None:
        with _patched(_Gateway(fixture)):
            rep = await getattr(InterestRatesService(), method)("2026-11-20")
        assert rep.rows, "the API still sends placeholder rows"
        assert not rep.has_values, "but none carries a number"
        assert rep.header is not None and rep.header.last_updated == date(2024, 12, 27)
        assert rep.header.is_discontinued is remark, "only BOT's own remark sets it"
        assert rep.model_dump()["has_values"] is False


class TestExchangeRates:
    @pytest.mark.asyncio
    async def test_daily_average(self) -> None:
        gw = _Gateway("daily_avg_exg_rate")
        with _patched(gw):
            rep = await get_exchange_rates("daily", "2026-11-20", currency="usd")
        row = rep.rows[0]
        assert row.currency_id == "USD" and row.mid_rate == 33.9659
        assert "DAILY_AVG_EXG_RATE/" in gw.urls[0] and "currency=USD" in gw.urls[0]

    @pytest.mark.asyncio
    async def test_monthly_reference_rate_and_its_period_format(self) -> None:
        gw = _Gateway("monthly_ref_rate")
        with _patched(gw):
            rep = await get_reference_rates("monthly", date(2026, 8, 15), "2026-10")
        assert rep.rows[0].period is not None and rep.rows[0].rate is not None
        assert "MONTHLY_REF_RATE/?start_period=2026-08&end_period=2026-10" in gw.urls[0]

    @pytest.mark.asyncio
    async def test_non_daily_needs_a_start(self) -> None:
        with pytest.raises(ValueError):
            await get_exchange_rates("annual")


class TestStatistics:
    @pytest.mark.asyncio
    async def test_metadata(self) -> None:
        with _patched(_Gateway("category_list")):
            cats = await get_stat_categories()
        with _patched(_Gateway("series_list")):
            series = await get_stat_series_list("FM_RT_013")
        with _patched(_Gateway("search_series_bond_yield")):
            found = await search_stat_series("government bond yield")
        assert cats[0].category == "FM_RT_013"
        assert series[0].series_code.startswith("FMRTTHOR")
        first = found[0]
        assert first.observation_end == "2025-07", "the search puts a discontinued code first"
        assert first.frequency == "Monthly" and first.lag_time == "10 Days"
        assert first.last_update_date == date(2025, 8, 8)

    @pytest.mark.asyncio
    async def test_observations_daily_and_monthly(self) -> None:
        with _patched(_Gateway("obs_thor_avg_3m")):
            thor = await get_stat_observations("FMRTTHORAVG3MD00005", "2026-08-01")
        with _patched(_Gateway("obs_gov_6m_monthly")):
            gov = await get_stat_observations("FMRTINTM00286", "2026-08-01", sort="asc")
        assert thor.frequency == "Daily" and thor.latest is not None
        assert (thor.latest.period, thor.latest.value) == ("2026-11-23", 0.99566)
        assert gov.frequency == "Monthly" and gov.latest is not None and gov.latest.value == 0.97372

    @pytest.mark.asyncio
    async def test_an_unknown_series_is_not_an_empty_window(self) -> None:
        with (
            _patched(_Gateway("err_obs_badcode")),
            pytest.raises(BotSeriesNotFoundError) as excinfo,
        ):
            await get_stat_observations("NOSUCHSERIES000", "2026-11-01")
        assert excinfo.value.series_code == "NOSUCHSERIES000"


class TestDebtSecuritiesHolidaysLicenses:
    @pytest.mark.asyncio
    async def test_bond_auction_results(self) -> None:
        with _patched(_Gateway("bond_auction")):
            rep = await get_bond_auction_results("2026-11-01", "2026-11-20")
        row = rep.rows[0]
        assert row.auction_date == date(2026, 11, 3) and row.thaibma_symbol == "CB27204B"
        assert row.coupon_rate == "Discount", "coupon is text: 'Discount', 'Compounded THOR ...'"
        assert row.weighted_average_accepted_yield == 0.8139 and row.accepted_amount_ncb is None

    @pytest.mark.asyncio
    async def test_holidays_are_wrapped_although_the_spec_says_bare(self) -> None:
        gw = _Gateway("fi_holidays")
        with _patched(gw):
            rep = await get_financial_institution_holidays(2026)
        assert rep.rows[0].holiday_date == date(2026, 1, 1)
        assert rep.rows[0].description == "New Year’s Day"
        assert gw.urls[0].endswith("financial-institutions-holidays/?year=2026")

    @pytest.mark.asyncio
    async def test_license_search_and_detail(self) -> None:
        with _patched(_Gateway("license_search")):
            found = await search_licensed_entities("ธนาคาร", limit=2)
        with _patched(_Gateway("license_detail")):
            detail = await get_licensed_entity(55)
        assert found.total == 40 and found.entities[0].id == "55"
        assert (
            found.entities[0].takes_deposits is True
            and found.entities[0].hire_purchase_leasing is None
        )
        assert detail.entity.id == "55" and detail.licenses[0].status_name == "คงอยู่"

    @pytest.mark.asyncio
    async def test_a_license_search_without_its_result_set_is_an_error(self) -> None:
        with _patched(_Gateway(_resp("{}"))), pytest.raises(ResponseParseError):
            await search_licensed_entities("x")

    @pytest.mark.asyncio
    async def test_license_document_is_the_file(self) -> None:
        pdf = FetchResponse(
            status_code=200,
            content=b"%PDF-1.4 body",
            text="",
            headers={"content-type": "application/octet-stream"},
            url="https://gateway.api.bot.or.th/x",
            elapsed=0.1,
        )
        gw = _Gateway(pdf)
        with _patched(gw):
            doc = await get_license_document(55, 1)
        assert doc.content.startswith(b"%PDF") and doc.size == 13
        assert "License?authId=55&docId=1" in gw.urls[0]

    @pytest.mark.asyncio
    async def test_a_json_answer_to_the_document_call_is_an_error(self) -> None:
        with (
            _patched(_Gateway(_resp(json.dumps({"message": "no such document"})))),
            pytest.raises(ResponseParseError),
        ):
            await get_license_document(55, 99)
