"""Golden tests: Pydantic serialization contracts, one representative model per service (L3 gate).

Each golden file under ``tests/golden/model_contract/`` holds a realistic API payload
(``input``, copied from the service test suite's sample constants) and the expected
``model_dump(mode="json")`` output (``expected_dump``). A dependency upgrade — above all a
pydantic/pydantic-core bump — that changes field names, optionality, aliases, datetime or
float rendering, enum coercion, or computed-field emission fails here loudly.

The roster deliberately includes the repo's known serialization traps: the ``Holiday``
trailing-``" *"`` footnote (str_strip_whitespace deliberately off), ``YieldCurve``'s
computed fields on a rolled-back date, a nanosecond ``+07:00`` timestamp (TFEX underlying),
a ``Z``-suffixed UTC datetime (earnings call), and long-precision floats (analyst consensus).

Regenerate expected dumps (only for an INTENDED, reviewed behavior change):

    uv run python -m tests.test_model_contract --regen

``--regen`` recomputes ``expected_dump`` from each golden's stored ``input``; it never
invents inputs. Do NOT regenerate to make a dependency bump pass — that inverts the gate.
"""

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

GOLDEN_DIR = Path(__file__).parent / "golden" / "model_contract"

# golden name -> dotted model class. The registry is the source of truth; each golden
# file also records the model path and the test asserts the two agree.
REGISTRY: dict[str, str] = {
    "analyst_consensus": "settfex.services.set.stock.analyst_consensus.AnalystConsensus",
    "dr_profile": "settfex.services.set.stock.profile_dr.DrProfile",
    "earnings_call_item": "settfex.services.set.earnings_call.EarningsCallItem",
    "highlight_data": "settfex.services.set.stock.highlight_data.StockHighlightData",
    "holiday_calendar": "settfex.services.set.holiday.HolidayCalendar",
    "index_list_response": "settfex.services.set.index.list.IndexListResponse",
    "news_search_response": "settfex.services.set.news.NewsSearchResponse",
    "sec_company_match": "settfex.services.sec.company.CompanyMatch",
    "stock_list_response": "settfex.services.set.list.StockListResponse",
    "tfex_series_list_response": "settfex.services.tfex.list.TFEXSeriesListResponse",
    "tfex_trading_statistics": "settfex.services.tfex.trading_statistics.TradingStatistics",
    "tfex_underlying_price": "settfex.services.tfex.underlying_price.UnderlyingPrice",
    "yield_curve": "settfex.services.thaibma.yield_curve.YieldCurve",
}


def _resolve(dotted: str) -> Any:
    module_name, _, class_name = dotted.rpartition(".")
    return getattr(importlib.import_module(module_name), class_name)


def _load_golden(name: str) -> dict[str, Any]:
    path = GOLDEN_DIR / f"{name}.json"
    assert path.exists(), (
        f"missing golden {path} — generate with "
        "`uv run python -m tests.test_model_contract --regen`"
    )
    golden: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return golden


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


@pytest.mark.parametrize("name", sorted(REGISTRY))
def test_model_dump_contract(name):
    """model_validate(input).model_dump(mode='json') must match the committed golden."""
    golden = _load_golden(name)
    assert golden["model"] == REGISTRY[name], "registry and golden disagree on the model class"
    model_cls = _resolve(REGISTRY[name])
    dump = model_cls.model_validate(golden["input"]).model_dump(mode="json")
    assert dump == golden["expected_dump"]
    # Byte-level canary: dict-equal but byte-different (e.g. float re-rendering that
    # json round-trips) is worth knowing about, not worth failing on.
    if _canonical(dump) != _canonical(golden["expected_dump"]):  # pragma: no cover
        print(f"[model-contract] {name}: dict-equal but byte-different serialization")


def test_every_golden_has_a_registry_entry():
    """A stray golden file means the registry and the directory drifted apart."""
    on_disk = {p.stem for p in GOLDEN_DIR.glob("*.json")}
    assert on_disk == set(REGISTRY)


if __name__ == "__main__":
    if "--regen" not in sys.argv[1:]:
        sys.exit("usage: python -m tests.test_model_contract --regen")
    for name in sorted(REGISTRY):
        path = GOLDEN_DIR / f"{name}.json"
        golden = json.loads(path.read_text(encoding="utf-8"))
        model_cls = _resolve(REGISTRY[name])
        golden["model"] = REGISTRY[name]
        golden["expected_dump"] = model_cls.model_validate(golden["input"]).model_dump(mode="json")
        path.write_text(
            json.dumps(golden, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"regenerated {path}")
