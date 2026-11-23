"""Bank of Thailand Interest Rates product: policy rate, BIBOR, deposit/loan, interbank (1.0.0).

Daily endpoints take a ``YYYY-MM-DD`` window. Leave both dates out for the last 7 calendar days
(Asia/Bangkok), or give only ``start_date`` for that one day. BOT answers a call without its
periods with HTTP 404, so settfex always sends both.

⚠️ Four tables in this product have returned only empty rows since 2024-12-27 (their
``last_updated``), while still answering HTTP 200:
- external interest rates, the spot rate and swap points carry BOT's remark that the table "has
  been discontinued", so ``report.header.is_discontinued`` is ``True``;
- THB implied rates carries no such remark.
``report.has_values`` is ``False`` for all four.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from settfex.services.bot.auth import DEFAULT_ENV_FILE
from settfex.services.bot.client import BotClient, default_day_window, result_of
from settfex.services.bot.constants import (
    BIBOR_AVERAGE_PATH,
    BIBOR_PATH,
    DEPOSIT_RATE_PATH,
    DEPOSIT_RATE_RANGE_PATH,
    EXTERNAL_RATE_PATH,
    IMPLIED_RATE_PATH,
    INTERBANK_RATE_PATH,
    LOAN_RATE_AVERAGE_PATH,
    LOAN_RATE_PATH,
    POLICY_RATE_PATH,
    SPOT_RATE_PATH,
    SWAP_POINT_PATH,
    BotProduct,
)
from settfex.services.bot.models import (
    BiborRate,
    BotReport,
    DepositRate,
    InterbankRate,
    LoanRate,
    PolicyRate,
    RateTypeQuote,
    SpotRate,
    SwapPoint,
    build_report,
)
from settfex.utils.data_fetcher import FetcherConfig
from settfex.utils.parsing import validate_or_raise

DayLike = date | datetime | str | None


class InterestRatesService:
    """The BOT Interest Rates product (token: ``BANK_OF_THAILAND_TOKEN_INTEREST_RATES``)."""

    def __init__(
        self,
        *,
        token: str | None = None,
        env_file: str | Path | None = DEFAULT_ENV_FILE,
        config: FetcherConfig | None = None,
    ) -> None:
        self.client = BotClient(
            BotProduct.INTEREST_RATES, token=token, env_file=env_file, config=config
        )

    async def _window(
        self, path: str, start: DayLike, end: DayLike, extra: dict[str, str | None] | None = None
    ) -> Any:
        start_text, end_text = default_day_window(start, end)
        params: dict[str, str] = {"start_period": start_text, "end_period": end_text}
        params.update({k: v for k, v in (extra or {}).items() if v})
        return await self.client.get_json(path, params)

    async def fetch_policy_rate(self) -> PolicyRate:
        """The current policy rate (percent per annum) and its MPC announcement."""
        data = await self.client.get_json(POLICY_RATE_PATH)
        return validate_or_raise(PolicyRate, result_of(data, "BOT policy rate"), context="policy")

    async def fetch_bibor(
        self, start_date: DayLike = None, end_date: DayLike = None, *, bank: str | None = None
    ) -> BotReport[BiborRate]:
        """BIBOR quoted by each panel bank (``bank`` filters by BOT's bank name)."""
        data = await self._window(BIBOR_PATH, start_date, end_date, {"bank": bank})
        return build_report(data, BiborRate, "BOT BIBOR by bank")

    async def fetch_bibor_average(
        self, start_date: DayLike = None, end_date: DayLike = None
    ) -> BotReport[BiborRate]:
        """The average BIBOR fixing for each day (O/N to 1 year)."""
        data = await self._window(BIBOR_AVERAGE_PATH, start_date, end_date)
        return build_report(data, BiborRate, "BOT BIBOR average")

    async def fetch_deposit_rates(
        self, start_date: DayLike = None, end_date: DayLike = None
    ) -> BotReport[DepositRate]:
        """Deposit rates for individuals, per commercial bank."""
        data = await self._window(DEPOSIT_RATE_PATH, start_date, end_date)
        return build_report(data, DepositRate, "BOT deposit rates")

    async def fetch_deposit_rate_ranges(
        self, start_date: DayLike = None, end_date: DayLike = None
    ) -> BotReport[DepositRate]:
        """Min-max deposit rates per group of banks (the ``avg_deposit_rate`` endpoint)."""
        data = await self._window(DEPOSIT_RATE_RANGE_PATH, start_date, end_date)
        return build_report(data, DepositRate, "BOT deposit rate ranges")

    async def fetch_loan_rates(
        self, start_date: DayLike = None, end_date: DayLike = None
    ) -> BotReport[LoanRate]:
        """Loan rates (MOR, MLR, MRR, ceiling, default, credit card), per commercial bank."""
        data = await self._window(LOAN_RATE_PATH, start_date, end_date)
        return build_report(data, LoanRate, "BOT loan rates")

    async def fetch_loan_rate_averages(
        self, start_date: DayLike = None, end_date: DayLike = None
    ) -> BotReport[LoanRate]:
        """Average loan rates per group of banks."""
        data = await self._window(LOAN_RATE_AVERAGE_PATH, start_date, end_date)
        return build_report(data, LoanRate, "BOT loan rate averages")

    async def fetch_interbank_rates(
        self, start_date: DayLike = None, end_date: DayLike = None, *, term: str | None = None
    ) -> BotReport[InterbankRate]:
        """Interbank transaction rates per term (``term`` e.g. ``"O/N"`` filters)."""
        data = await self._window(INTERBANK_RATE_PATH, start_date, end_date, {"term_type": term})
        return build_report(data, InterbankRate, "BOT interbank rates")

    async def fetch_external_rates(
        self, start_date: DayLike = None, end_date: DayLike = None, *, rate_type: str | None = None
    ) -> BotReport[RateTypeQuote]:
        """External interest rates. ⚠️ Discontinued 2024-12-27 (empty rows; see the header)."""
        data = await self._window(
            EXTERNAL_RATE_PATH, start_date, end_date, {"rate_type": rate_type}
        )
        return build_report(data, RateTypeQuote, "BOT external rates")

    async def fetch_spot_rates(
        self, start_date: DayLike = None, end_date: DayLike = None
    ) -> BotReport[SpotRate]:
        """USD/THB spot bid/offer. ⚠️ Discontinued 2024-12-27 (empty rows)."""
        data = await self._window(SPOT_RATE_PATH, start_date, end_date)
        return build_report(data, SpotRate, "BOT spot rate")

    async def fetch_swap_points(
        self, start_date: DayLike = None, end_date: DayLike = None, *, term: str | None = None
    ) -> BotReport[SwapPoint]:
        """Onshore swap points in satangs. ⚠️ Discontinued 2024-12-27 (empty rows)."""
        data = await self._window(SWAP_POINT_PATH, start_date, end_date, {"term_type": term})
        return build_report(data, SwapPoint, "BOT swap points")

    async def fetch_implied_rates(
        self, start_date: DayLike = None, end_date: DayLike = None, *, rate_type: str | None = None
    ) -> BotReport[RateTypeQuote]:
        """THB implied interest rates. ⚠️ Empty rows since 2024-12-27 (no "discontinued" remark)."""
        data = await self._window(IMPLIED_RATE_PATH, start_date, end_date, {"rate_type": rate_type})
        return build_report(data, RateTypeQuote, "BOT THB implied rates")

    async def fetch_raw(self, path: str, params: dict[str, str] | None = None) -> Any:
        """Any endpoint of this product, as decoded JSON (escape hatch)."""
        return await self.client.fetch_raw(path, params)


def _service(
    token: str | None, env_file: str | Path | None, config: FetcherConfig | None
) -> InterestRatesService:
    return InterestRatesService(token=token, env_file=env_file, config=config)


async def get_policy_rate(
    *,
    token: str | None = None,
    env_file: str | Path | None = DEFAULT_ENV_FILE,
    config: FetcherConfig | None = None,
) -> PolicyRate:
    """The Bank of Thailand policy rate, e.g. ``(await get_policy_rate()).rate == 1.0``."""
    return await _service(token, env_file, config).fetch_policy_rate()


async def get_bibor(
    start_date: DayLike = None,
    end_date: DayLike = None,
    *,
    average: bool = True,
    bank: str | None = None,
    token: str | None = None,
    env_file: str | Path | None = DEFAULT_ENV_FILE,
    config: FetcherConfig | None = None,
) -> BotReport[BiborRate]:
    """BIBOR: the average fixing by default, or each bank's quotes with ``average=False``."""
    service = _service(token, env_file, config)
    if average:
        return await service.fetch_bibor_average(start_date, end_date)
    return await service.fetch_bibor(start_date, end_date, bank=bank)


async def get_deposit_rates(
    start_date: DayLike = None,
    end_date: DayLike = None,
    *,
    ranges: bool = False,
    token: str | None = None,
    env_file: str | Path | None = DEFAULT_ENV_FILE,
    config: FetcherConfig | None = None,
) -> BotReport[DepositRate]:
    """Deposit rates per bank, or each group's min-max with ``ranges=True``."""
    service = _service(token, env_file, config)
    if ranges:
        return await service.fetch_deposit_rate_ranges(start_date, end_date)
    return await service.fetch_deposit_rates(start_date, end_date)


async def get_loan_rates(
    start_date: DayLike = None,
    end_date: DayLike = None,
    *,
    averages: bool = False,
    token: str | None = None,
    env_file: str | Path | None = DEFAULT_ENV_FILE,
    config: FetcherConfig | None = None,
) -> BotReport[LoanRate]:
    """Loan rates per bank, or each group's average with ``averages=True``."""
    service = _service(token, env_file, config)
    if averages:
        return await service.fetch_loan_rate_averages(start_date, end_date)
    return await service.fetch_loan_rates(start_date, end_date)


async def get_interbank_rates(
    start_date: DayLike = None,
    end_date: DayLike = None,
    *,
    term: str | None = None,
    token: str | None = None,
    env_file: str | Path | None = DEFAULT_ENV_FILE,
    config: FetcherConfig | None = None,
) -> BotReport[InterbankRate]:
    """Interbank transaction rates (min/max/mode/weighted average) per term."""
    return await _service(token, env_file, config).fetch_interbank_rates(
        start_date, end_date, term=term
    )
