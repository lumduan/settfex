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
  session cache first, so warmup genuinely re-runs with the installed HTTP client instead
  of replaying cached cookies (cached cookies would mask a TLS-fingerprint regression).

The holiday endpoint is deliberately probed ONCE with a patient retry config: it answers
transient bare-401s and degrades under polling (see CLAUDE.md Known Gotchas).
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from settfex.services.set import get_highlight_data, get_holidays, get_stock_list
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
async def test_live_thaibma_yield_curve():
    t0 = time.perf_counter()
    curve = await get_government_yield_curve()
    elapsed = time.perf_counter() - t0
    assert len(curve.points) > 10
    ten_year = curve.yield_at(10.0)
    assert ten_year is not None and 0.0 < ten_year < 15.0
    _record("thaibma_yield_curve", curve, elapsed, as_of=str(curve.as_of))
