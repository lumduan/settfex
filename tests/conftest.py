"""Pytest configuration and fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _no_live_listing_lookups(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unit tests never ask the network whether a symbol is listed.

    Since 0.25.0, ``settfex.services.set.list._is_listed_symbol`` may load the SET stock list to
    tell an unknown symbol from a listed-but-uncovered one. A test that patches only its own
    service's fetcher would otherwise send that request for real — to a host the live-probe rules
    say this suite must never touch. Here it answers ``None`` ("cannot know"), which is exactly the
    pre-0.25.0 behaviour; a test that exercises the classification sets its own answer, and the
    helper's own tests call the original, which they import directly.

    Live (``integration``) tests are left alone.
    """
    if request.node.get_closest_marker("integration"):
        return

    async def unknowable(symbol: str) -> bool | None:
        return None

    monkeypatch.setattr("settfex.services.set.list._is_listed_symbol", unknowable)


#: The token every unit test sees for the Bank of Thailand API (1.0.0).
BOT_TEST_TOKEN = "test-bot-token"


@pytest.fixture(autouse=True)
def _bot_token_never_from_the_real_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Give every test a dummy BOT token, so no test can read a developer's real ``.env``.

    The suite runs from the repo root, where a developer's ``.env`` may hold real tokens. The
    fallback variable resolves before any ``.env`` file is read, so with it set, the file is never
    opened. The product-specific variables are cleared so the fallback is what tests get. Tests of
    token resolution itself clear this too and pass their own ``env_file``.
    """
    from settfex.services.bot.constants import BOT_TOKEN_ENV, BotProduct

    for product in BotProduct:
        monkeypatch.delenv(product.env_key, raising=False)
    monkeypatch.setenv(BOT_TOKEN_ENV, BOT_TEST_TOKEN)
