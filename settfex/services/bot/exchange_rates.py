"""Bank of Thailand Exchange Rates product: THB averages and the THB/USD reference rate (1.0.0).

``frequency`` picks the endpoint and the period format:
- ``"daily"``: ``YYYY-MM-DD``;
- ``"monthly"``: ``YYYY-MM``;
- ``"quarterly"``: ``YYYY-QN``;
- ``"annual"``: ``YYYY``.
``date`` objects are converted for any frequency. A daily call with no dates covers the last 7 days.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

from settfex.services.bot.auth import DEFAULT_ENV_FILE
from settfex.services.bot.client import BotClient, default_day_window, period_param
from settfex.services.bot.constants import EXCHANGE_RATE_PATH, REFERENCE_RATE_PATH, BotProduct
from settfex.services.bot.models import BotReport, ExchangeRate, ReferenceRate, build_report
from settfex.utils.data_fetcher import FetcherConfig

Frequency = Literal["daily", "monthly", "quarterly", "annual"]
PeriodLike = date | datetime | str | int | None


def _periods(frequency: Frequency, start: PeriodLike, end: PeriodLike) -> dict[str, str]:
    if frequency not in ("daily", "monthly", "quarterly", "annual"):
        raise ValueError(f"frequency must be daily/monthly/quarterly/annual, got {frequency!r}")
    if frequency == "daily":
        s, e = default_day_window(
            None if start is None else str(start) if isinstance(start, int) else start,
            None if end is None else str(end) if isinstance(end, int) else end,
        )
        return {"start_period": s, "end_period": e}
    if start is None:
        raise ValueError(f"{frequency} data needs start_date (e.g. '2026-10', '2026-Q3', '2025')")
    s = period_param(start, "start_date", frequency)
    e = period_param(end, "end_date", frequency) if end is not None else s
    return {"start_period": s, "end_period": e}


class ExchangeRatesService:
    """The BOT Exchange Rates product (token: ``BANK_OF_THAILAND_TOKEN_EXCHANGE_RATES``)."""

    def __init__(
        self,
        *,
        token: str | None = None,
        env_file: str | Path | None = DEFAULT_ENV_FILE,
        config: FetcherConfig | None = None,
    ) -> None:
        self.client = BotClient(
            BotProduct.EXCHANGE_RATES, token=token, env_file=env_file, config=config
        )

    async def fetch_exchange_rates(
        self,
        frequency: Frequency = "daily",
        start_date: PeriodLike = None,
        end_date: PeriodLike = None,
        *,
        currency: str | None = None,
    ) -> BotReport[ExchangeRate]:
        """Average THB rates per foreign currency (``currency`` e.g. ``"USD"`` filters)."""
        params = _periods(frequency, start_date, end_date)
        if currency:
            params["currency"] = currency.strip().upper()
        path = EXCHANGE_RATE_PATH.format(frequency=frequency.upper())
        return build_report(
            await self.client.get_json(path, params), ExchangeRate, "BOT exchange rates"
        )

    async def fetch_reference_rates(
        self,
        frequency: Frequency = "daily",
        start_date: PeriodLike = None,
        end_date: PeriodLike = None,
    ) -> BotReport[ReferenceRate]:
        """The weighted-average interbank THB/USD rate."""
        path = REFERENCE_RATE_PATH.format(frequency=frequency.upper())
        data = await self.client.get_json(path, _periods(frequency, start_date, end_date))
        return build_report(data, ReferenceRate, "BOT THB/USD reference rate")

    async def fetch_raw(self, path: str, params: dict[str, str] | None = None) -> Any:
        """Any endpoint of this product, as decoded JSON (escape hatch)."""
        return await self.client.fetch_raw(path, params)


async def get_exchange_rates(
    frequency: Frequency = "daily",
    start_date: PeriodLike = None,
    end_date: PeriodLike = None,
    *,
    currency: str | None = None,
    token: str | None = None,
    env_file: str | Path | None = DEFAULT_ENV_FILE,
    config: FetcherConfig | None = None,
) -> BotReport[ExchangeRate]:
    """THB average exchange rates.

    Example: ``get_exchange_rates("monthly", "2026-08", "2026-10", currency="USD")``.
    """
    service = ExchangeRatesService(token=token, env_file=env_file, config=config)
    return await service.fetch_exchange_rates(frequency, start_date, end_date, currency=currency)


async def get_reference_rates(
    frequency: Frequency = "daily",
    start_date: PeriodLike = None,
    end_date: PeriodLike = None,
    *,
    token: str | None = None,
    env_file: str | Path | None = DEFAULT_ENV_FILE,
    config: FetcherConfig | None = None,
) -> BotReport[ReferenceRate]:
    """The weighted-average interbank THB/USD reference rate."""
    service = ExchangeRatesService(token=token, env_file=env_file, config=config)
    return await service.fetch_reference_rates(frequency, start_date, end_date)
