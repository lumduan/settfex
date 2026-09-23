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
