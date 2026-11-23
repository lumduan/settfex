"""Bank of Thailand Debt Securities Auction product: auction results (1.0.0).

Without its periods the endpoint answers HTTP 200 with ``success: "false"`` and an error list.
settfex always sends both, and raises :class:`~settfex.exceptions.BotApiError` if it ever gets
such an answer. With no dates, the last 30 days are asked for.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from settfex.services.bot.auth import DEFAULT_ENV_FILE
from settfex.services.bot.client import BotClient, default_day_window
from settfex.services.bot.constants import BOND_AUCTION_PATH, BotProduct
from settfex.services.bot.models import BondAuctionResult, BotReport, build_report
from settfex.utils.data_fetcher import FetcherConfig

DayLike = date | datetime | str | None


class DebtSecuritiesAuctionService:
    """The BOT Debt Securities Auction product.

    Token: ``BANK_OF_THAILAND_TOKEN_DEBT_SECURITIES_AUCTION``.
    """

    def __init__(
        self,
        *,
        token: str | None = None,
        env_file: str | Path | None = DEFAULT_ENV_FILE,
        config: FetcherConfig | None = None,
    ) -> None:
        self.client = BotClient(
            BotProduct.DEBT_SECURITIES_AUCTION, token=token, env_file=env_file, config=config
        )

    async def fetch_auction_results(
        self, start_date: DayLike = None, end_date: DayLike = None
    ) -> BotReport[BondAuctionResult]:
        """Government and BOT debt securities auctions between two dates."""
        start, end = default_day_window(start_date, end_date, days=30)
        data = await self.client.get_json(
            BOND_AUCTION_PATH, {"start_period": start, "end_period": end}
        )
        return build_report(data, BondAuctionResult, "BOT bond auction results")

    async def fetch_raw(self, path: str, params: dict[str, str] | None = None) -> Any:
        """Any endpoint of this product, as decoded JSON (escape hatch)."""
        return await self.client.fetch_raw(path, params)


async def get_bond_auction_results(
    start_date: DayLike = None,
    end_date: DayLike = None,
    *,
    token: str | None = None,
    env_file: str | Path | None = DEFAULT_ENV_FILE,
    config: FetcherConfig | None = None,
) -> BotReport[BondAuctionResult]:
    """Debt securities auction results (yields, amounts, bid coverage)."""
    service = DebtSecuritiesAuctionService(token=token, env_file=env_file, config=config)
    return await service.fetch_auction_results(start_date, end_date)
