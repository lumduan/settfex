"""Bank of Thailand "Others" product: financial institutions' holidays (1.0.0).

These are **bank** holidays, which are not the SET market calendar (for that, see
:func:`settfex.services.set.get_holidays`). The official spec documents a bare list; the API
wraps it in ``{"result": {"api", "timestamp", "data": [...]}}``, and settfex follows the API.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from settfex.services.bot.auth import DEFAULT_ENV_FILE
from settfex.services.bot.client import BANGKOK, BotClient
from settfex.services.bot.constants import FI_HOLIDAYS_PATH, BotProduct
from settfex.services.bot.models import BotReport, FinancialInstitutionHoliday, build_report
from settfex.utils.data_fetcher import FetcherConfig


class HolidaysService:
    """The BOT "Others" product (token: ``BANK_OF_THAILAND_TOKEN_OTHERS``)."""

    def __init__(
        self,
        *,
        token: str | None = None,
        env_file: str | Path | None = DEFAULT_ENV_FILE,
        config: FetcherConfig | None = None,
    ) -> None:
        self.client = BotClient(BotProduct.OTHERS, token=token, env_file=env_file, config=config)

    async def fetch_holidays(
        self, year: int | str | None = None
    ) -> BotReport[FinancialInstitutionHoliday]:
        """One year's financial institutions' holidays (default: this year in Asia/Bangkok)."""
        text = str(year if year is not None else datetime.now(BANGKOK).year).strip()
        if not (len(text) == 4 and text.isdigit()):
            raise ValueError(f"year must be YYYY, got {year!r}")
        data = await self.client.get_json(FI_HOLIDAYS_PATH, {"year": text})
        return build_report(data, FinancialInstitutionHoliday, f"BOT FI holidays {text}")

    async def fetch_raw(self, path: str, params: dict[str, str] | None = None) -> Any:
        """Any endpoint of this product, as decoded JSON (escape hatch)."""
        return await self.client.fetch_raw(path, params)


async def get_financial_institution_holidays(
    year: int | str | None = None,
    *,
    token: str | None = None,
    env_file: str | Path | None = DEFAULT_ENV_FILE,
    config: FetcherConfig | None = None,
) -> BotReport[FinancialInstitutionHoliday]:
    """Thai financial institutions' holidays for a year (bank holidays, not SET's calendar)."""
    return await HolidaysService(token=token, env_file=env_file, config=config).fetch_holidays(year)
