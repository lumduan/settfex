"""``BankOfThailand``: one object holding the settings for all six BOT products (1.0.0)."""

from __future__ import annotations

from pathlib import Path

from settfex.services.bot.auth import DEFAULT_ENV_FILE
from settfex.services.bot.debt_securities import DebtSecuritiesAuctionService
from settfex.services.bot.exchange_rates import ExchangeRatesService
from settfex.services.bot.holidays import HolidaysService
from settfex.services.bot.interest_rates import InterestRatesService
from settfex.services.bot.license_check import LicenseCheckService
from settfex.services.bot.statistics import StatisticsService
from settfex.utils.data_fetcher import FetcherConfig


class BankOfThailand:
    """Facade over the BOT API products.

    Tokens are read per product from the environment or ``env_file`` (each product has its own),
    so one facade serves all six. Pass ``tokens={"statistics": "..."}`` to give them directly.

    Example:
        >>> bot = BankOfThailand()
        >>> rate = await bot.interest_rates.fetch_policy_rate()
        >>> thor = await bot.statistics.fetch_observations("FMRTTHORD00003", "2026-11-01")
    """

    def __init__(
        self,
        *,
        tokens: dict[str, str] | None = None,
        env_file: str | Path | None = DEFAULT_ENV_FILE,
        config: FetcherConfig | None = None,
    ) -> None:
        tok = dict(tokens or {})
        self.interest_rates = InterestRatesService(
            token=tok.get("interest_rates"), env_file=env_file, config=config
        )
        self.statistics = StatisticsService(
            token=tok.get("statistics"), env_file=env_file, config=config
        )
        self.exchange_rates = ExchangeRatesService(
            token=tok.get("exchange_rates"), env_file=env_file, config=config
        )
        self.debt_securities = DebtSecuritiesAuctionService(
            token=tok.get("debt_securities_auction"), env_file=env_file, config=config
        )
        self.holidays = HolidaysService(token=tok.get("others"), env_file=env_file, config=config)
        self.licenses = LicenseCheckService(
            token=tok.get("license_check"), env_file=env_file, config=config
        )

    def __repr__(self) -> str:  # never show a token
        return "BankOfThailand()"
