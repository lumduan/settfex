"""Live-endpoint probes (L4 backward-compat gate) — opt-in, excluded from the default run.

Run them (and only them) with:

    uv run pytest -m integration --no-cov

``--no-cov`` matters: the coverage floor in addopts is calibrated for the full suite and a
5-test subset would trip it misleadingly. These probes hit the real production hosts through
the library's public ``get_*()`` entry points, exactly as documented, so they exercise the
whole stack including SessionManager warmup and the curl_cffi TLS fingerprint against the
Incapsula-protected SET origins — the layer the mocked unit suite cannot see. They are the
mandatory evidence step after any curl_cffi bump (see the Dependency policy in CLAUDE.md).

Environment knobs (used by the dependency-refresh live-probe protocol):

- ``SETTFEX_PROBE_DIR``: when set, each probe writes ``{service, elapsed_seconds, meta,
  dump}`` JSON (with ``dump = model_dump(mode="json")``) into that directory, enabling a
  structural before/after diff across an upgrade.
- ``SETTFEX_PROBE_CLEAR_CACHE=1``: clears the SessionManager singletons and the on-disk
  session cache (``~/.settfex/cache``) first, so warmup re-runs with the installed HTTP
  client instead of replaying cached cookies (cached cookies would mask a TLS-fingerprint
  regression). The SEC probe records its ``ListingAccounting`` rather than the document list
  (``SecDocumentList`` is a plain list, not a model), which is also the part worth diffing.

**Diff the SHAPES, never the values.** On a closed market — any weekend or Thai holiday —
SET serves a frozen snapshot, so before/after payloads are byte-identical in value,
``marketDateTime`` included. That is indistinguishable from a cache replay by inspection,
so value equality proves nothing in either direction; compare added/removed fields and
fields that newly went null. A large runtime drop between the two runs is Python bytecode
warmup after ``uv sync``, not the network.

**What actually clears a fingerprint change is a cold-cache fetch, not this diff.** Nothing
in the probe output proves the clear above took effect. Confirm it out of band:
``rm -rf ~/.settfex/cache`` then a single live ``get_*()`` — a 200 means a genuinely fresh
TLS handshake was accepted by the Incapsula origin with no cached cookie to hide behind.

The holiday endpoint is deliberately probed ONCE with a patient retry config: it answers
transient bare-401s and degrades under polling (see CLAUDE.md Known Gotchas). A 401 here is
that endpoint misbehaving, not a curl_cffi regression — re-run it alone before concluding.
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from settfex.services.sec import get_sec_documents
from settfex.services.set import (
    get_highlight_data,
    get_holidays,
    get_stock_info,
    get_stock_list,
)
from settfex.services.tfex import get_series_list
from settfex.services.thaibma import get_government_yield_curve
from settfex.utils.data_fetcher import FetcherConfig
from settfex.utils.session_cache import SessionCache
from settfex.utils.session_manager import SessionManager

pytestmark = pytest.mark.integration

# Mirrors scripts/.../verify_holiday.py: the holiday endpoint 401s transiently.
PATIENT = FetcherConfig(max_retries=6, retry_delay=2.0)


@pytest.fixture(scope="module", autouse=True)
def _optionally_clear_session_state():
    """With SETTFEX_PROBE_CLEAR_CACHE=1, force a genuine re-warmup for this run."""
    if os.environ.get("SETTFEX_PROBE_CLEAR_CACHE") == "1":
        SessionManager.reset_instance()
        SessionCache().clear()
    yield


def _record(name: str, model: Any, elapsed: float, **meta: Any) -> None:
    probe_dir = os.environ.get("SETTFEX_PROBE_DIR")
    if not probe_dir:
        return
    path = Path(probe_dir)
    path.mkdir(parents=True, exist_ok=True)
    payload = {
        "service": name,
        "elapsed_seconds": round(elapsed, 3),
        "meta": meta,
        "dump": model.model_dump(mode="json"),
    }
    (path / f"{name}.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_live_set_stock_list():
    t0 = time.perf_counter()
    response = await get_stock_list()
    elapsed = time.perf_counter() - t0
    assert response.count > 500
    assert any(s.symbol == "CPALL" for s in response.security_symbols)
    _record("set_stock_list", response, elapsed, count=response.count)


@pytest.mark.asyncio
async def test_live_set_highlight_data():
    t0 = time.perf_counter()
    data = await get_highlight_data("CPALL")
    elapsed = time.perf_counter() - t0
    assert data.symbol == "CPALL"
    assert data.market_cap is not None and data.market_cap > 1e9
    _record("set_highlight_data", data, elapsed, symbol=data.symbol)


@pytest.mark.asyncio
async def test_live_set_stock_info():
    """The quote block is the only live source of a symbol's trading sign."""
    t0 = time.perf_counter()
    info = await get_stock_info("CPALL")
    elapsed = time.perf_counter() - t0
    assert info.symbol == "CPALL"
    assert info.security_type == "S"
    assert info.prior is not None and info.prior > 0
    # sign is "" for an untagged security, never null-and-unparseable
    assert isinstance(info.signs, list)
    _record("set_stock_info", info, elapsed, symbol=info.symbol, sign=info.sign)


@pytest.mark.asyncio
async def test_live_tfex_series_list():
    t0 = time.perf_counter()
    response = await get_series_list()
    elapsed = time.perf_counter() - t0
    assert response.count > 50
    _record("tfex_series_list", response, elapsed, count=response.count)


@pytest.mark.asyncio
async def test_live_set_holidays():
    t0 = time.perf_counter()
    calendar = await get_holidays(config=PATIENT)
    elapsed = time.perf_counter() - t0
    assert calendar.year == datetime.now(ZoneInfo("Asia/Bangkok")).year
    assert calendar.count >= 10
    _record("set_holidays", calendar, elapsed, count=calendar.count)


@pytest.mark.asyncio
@pytest.mark.parametrize("lang", ["en", "th"])
async def test_live_sec_listing_parses_cleanly(lang: str):
    """The SEC listing is the one service here whose payload is HTML, not JSON.

    Every other probe fails loudly if the payload shape moves. This one cannot: the parser's
    job is to turn tables into records, and a renamed column or a changed link shape makes it
    return *fewer* records rather than raise — which is the whole subject of issues #123/#127.
    So the assertion is on the parser's own accounting, not just on the count:

    * ``no_link == 0`` — the site served a data row whose download link we could not resolve.
    * ``unmapped_headers == []`` — the site serves a column this library does not model.

    Both are zero on every captured page in the test corpus, so either going non-zero is a
    real site change and is exactly what a live probe is for. Run in both languages because
    the header map has a separate entry per language: one half can rot while the other works.

    **The window and the category set are load-bearing, not incidental.** A narrow, recent
    window over two categories passed while two Key Financial Ratio rows from 2018/2019 were
    being dropped: old filings use old download-URL shapes, and only a wide window reaches
    them. All five categories, back to 2015, is the smallest query that covers every shape
    known to exist.
    """
    t0 = time.perf_counter()
    docs = await get_sec_documents(
        "CPALL",
        from_date="01/01/2015",
        to_date="31/12/2026",
        lang=lang,
    )
    elapsed = time.perf_counter() - t0
    accounting = docs.accounting

    assert len(docs) > 0, "CPALL has filed; an empty list here is the bug this probe exists for"
    assert accounting.no_link == 0, f"the live site served {accounting.no_link} unlinked row(s)"
    assert not accounting.unmapped_headers, (
        f"market.sec.or.th now serves column(s) settfex does not model: "
        f"{accounting.unmapped_headers}"
    )
    assert accounting.is_balanced, "every parsed row must land in exactly one bucket"

    # P4: the Thai 56-1/56-2 `Receive Date` column was unmapped until #127, so this was None
    # on the Thai side while the English side had it.
    annual = [d for d in docs if d.category.value in ("form_56_1", "form_56_2") and d.year]
    assert annual, "expected annual-report filings in this window"
    assert all(d.receive_date is not None for d in annual), "56-x rows carry a Receive Date"
    assert all(2000 < d.receive_date.year < 2100 for d in annual), "B.E. must be converted"

    _record(
        f"sec_listing_{lang}",
        accounting,
        elapsed,
        lang=lang,
        documents=len(docs),
        completeness=docs.completeness(),
    )


@pytest.mark.asyncio
async def test_live_thaibma_yield_curve():
    t0 = time.perf_counter()
    curve = await get_government_yield_curve()
    elapsed = time.perf_counter() - t0
    assert len(curve.points) > 10
    ten_year = curve.yield_at(10.0)
    assert ten_year is not None and 0.0 < ten_year < 15.0
    _record("thaibma_yield_curve", curve, elapsed, as_of=str(curve.as_of))
