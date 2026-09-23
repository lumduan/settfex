"""A hard request budget for live runs — the politeness rule, enforced rather than remembered.

CLAUDE.md's live-probe rule says *set an explicit request budget before starting, and make the
script stop at it*. With ``SETTFEX_LIVE_BUDGET=N`` in the environment, every request attempt that
goes through ``AsyncDataFetcher`` is counted, and attempt ``N + 1`` is refused before it leaves the
machine. Without the variable, nothing is counted and manual runs behave as before.

The refusal raises :class:`LiveBudgetExhaustedError`, a ``BaseException`` on purpose: the
fetcher's retry loop catches ``Exception``, so an ordinary exception would be retried — a budget
that sends four more requests to announce itself is not a budget.

**Not counted:** ``SessionManager`` warmups (one page view per site per process, sent by
curl_cffi directly rather than through the fetcher). A run's true request count is therefore this
counter plus at most one warmup per site.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import pytest

from settfex.utils.data_fetcher import AsyncDataFetcher


class LiveBudgetExhaustedError(BaseException):
    """Raised instead of sending a request past ``SETTFEX_LIVE_BUDGET``."""


@pytest.fixture(scope="session", autouse=True)
def _live_request_budget() -> Iterator[None]:
    raw = os.environ.get("SETTFEX_LIVE_BUDGET")
    if not raw:
        yield
        return

    limit = int(raw)
    sent = 0
    original = AsyncDataFetcher._make_request

    async def counted(self: AsyncDataFetcher, *args: Any, **kwargs: Any) -> Any:
        nonlocal sent
        if sent >= limit:
            raise LiveBudgetExhaustedError(
                f"live request budget of {limit} reached; refusing request {sent + 1} "
                f"({args[0] if args else kwargs.get('url')})"
            )
        sent += 1
        return await original(self, *args, **kwargs)

    with patch.object(AsyncDataFetcher, "_make_request", counted):
        yield
    print(f"\nlive request budget: {sent} of {limit} used (warmups not counted)")
