# settfex Hardening Pass — Comprehensive Audit

**Branch:** `claude-settfex-overhaul` (off `chore/adopt-python-template-tooling`)
**Scope:** robustness / financial-correctness + performance / concurrency hardening of the
SET/TFEX async client, with the public API contract preserved exactly.

---

## 1. Executive summary

| Metric | Before | After |
|---|---|---|
| Tests passing | 116 | **149** (+33) |
| Test runtime | 3.77 s | 2.81 s |
| Coverage (gate = 45%) | 49.26% | **61.25%** (+11.99 pts) |
| `ruff check` / `ruff format` / `mypy --strict` | clean | clean |

- **5 classes of defect fixed** — the headline one being **silent NaN/Infinity acceptance**
  into financial models (prices, P/E, margins), plus context-free parse failures, an
  `assert`-based type check stripped under `python -O`, a cold-start **warmup stampede**, and
  blocking disk I/O on the event loop.
- **~15 service parse sites** routed through one hardened helper, **removing ~111 net lines**
  of duplicated decode/validation boilerplate while *adding* guarantees.
- **+33 regression tests**; two previously-0%-covered TFEX services now tested.
- **Performance:** measured every candidate; applied only the wins that benchmarks justified
  (header hoist; warmup stampede 25→1). Notably, **blanket lazy-logging was measured to be a
  regression here and deliberately NOT applied** (see §3).
- **Public API:** unchanged — verified by signature/return-type/field smoke test (§6).

---

## 2. Bugs & robustness

The shared fix is a new internal module **`settfex/utils/parsing.py`**
(`decode_json`, `validate_or_raise`, `validate_list_or_raise`, `ResponseParseError`), routed
into every service. Untrusted payloads still go through **full** Pydantic validation
(`model_validate`) — no `model_construct` bypass.

| # | Location (pre-change) | Trigger (malformed input) | Root cause | Fix | Regression test |
|---|---|---|---|---|---|
| 1 | All numeric models, via every service decode + `data_fetcher.fetch_json` | API returns `{"pe": NaN}` / `Infinity` / `-Infinity` | `json.loads` accepts non-finite literals by default and Pydantic `float` defaults to `allow_inf_nan=True`, so a non-finite **price/P-E/margin enters the model silently** | `decode_json` parses with `parse_constant=` a hook that **rejects** NaN/Infinity, raising `ResponseParseError` with symbol+endpoint context | `test_parsing.py::TestDecodeJson::test_nonfinite_rejected`; end-to-end `test_shareholder.py::...rejects_nan`, `test_financial.py::...rejects_nan_in_financial_amount`, `test_data_fetcher.py::...rejects_nonfinite` |
| 2 | Every `Model(**data)` / `[Model(**x) for x in data]` across ~15 services | Any missing key / wrong type / partial record | Bare `pydantic.ValidationError` surfaced with **no symbol/endpoint**, so logs/tracebacks weren't actionable | `validate_or_raise` / `validate_list_or_raise` log `symbol (endpoint)` (+ item index for lists) and re-raise; decode failures wrapped in `ResponseParseError` carrying context | `test_parsing.py` (unit); `test_board_of_director/corporate_action/shareholder ...json_decode_error` now assert the symbol appears |
| 3 | `tfex/trading_statistics.py:210`, `tfex/list.py:276` | Raw endpoint returns a JSON array (or `null`) instead of an object | `assert isinstance(data, dict)` is **stripped under `python -O`** and yields a context-free `AssertionError` | Explicit `if not isinstance(data, dict): raise ResponseParseError(... symbol/endpoint ...)` | `test_trading_statistics.py::...raw_rejects_non_dict_response`, `test_list.py::...raw_rejects_non_dict_response` |
| 4 | `session_manager.py::ensure_initialized` | N concurrent fetches on a cold cache (first use) | Method was unguarded: every coroutine passed the `not _initialized` check before any finished warming up → **N duplicate warmup round-trips** (wasteful; can trip Incapsula bot detection) | Per-instance `asyncio.Lock` serializes init; double-checked so the rest reuse the warmed session. **Measured 25 → 1** | `test_session_manager.py::...concurrent_cold_start_warms_once` |
| 5 | `session_cache.py::get_global_cache` | First cache use (cold) | `SessionCache.__init__` does blocking `mkdir` + opens the diskcache SQLite DB **directly on the event loop** | Construction offloaded via `asyncio.to_thread` | covered by session-manager init path; existing cache tests still green |

Also hardened in passing: the existing list-shape guards (`Expected list response …`) were
**kept** for defense-in-depth and backward-compatible non-list behavior; `validate_list_or_raise`
adds the same guard centrally with per-item index context.

---

## 3. Performance & memory

Method: throwaway `timeit`/`tracemalloc` micro-benchmarks (200k iterations, loguru at ERROR so
`debug()` is disabled — the production default), deleted before finishing. Numbers are µs/call.

| Hot path | Change | Before | After | Verdict |
|---|---|---|---|---|
| Cold-start warmup under concurrency | per-instance init lock | **25** round-trips (25 callers) | **1** round-trip | **Real correctness + latency + politeness win** (avoids bot-detection risk) |
| `fetch()` request headers | hoist 11-entry literal → module constant, copy per call | 0.378 / 0.385 | **0.146** | Real ~2.6× micro-win (≈0.2µs/call; negligible vs network, zero-risk, de-duplicates) |
| JSON decode NaN guard | `json.loads(parse_constant=…)` on finite payload | 53.7 | ~50–52 | **Free** — within run-to-run noise; the hook fires only on NaN/Inf tokens |
| Pydantic build | `Model(**d)` → `model_validate(d)` | 2.11 | ~2.09 | Equivalent within noise (~0.3µs); no regression from the switch |
| Decode/validate de-duplication | ~15 inline `import json` + try/except blocks → 1 helper | — | — | **−111 net LOC**; fewer per-call closures/objects, single maintained path |
| Debug logging (`text[:500]`, `list(keys())`) | **considered `logger.opt(lazy=True)`; rejected** | eager 0.755 | lazy **1.841** | **Lazy is WORSE here** — `.opt()` overhead exceeds the bounded/cheap interpolation it would defer; kept eager (see note) |

**Lazy-logging note (evidence over assumption).** The brief suggested converting eager debug
logs to loguru lazy form. Benchmarks show that for this codebase's debug statements — all cheap,
bounded interpolations (`text[:500]`, `list(data.keys())` over ~15–40 keys) — `logger.opt(lazy=True)`
*adds* ~1µs/call of its own overhead and is a net regression when the level is disabled. There are
no debug logs inside hot loops or over unbounded data. So lazy conversion was **measured and
declined** rather than applied blindly; the logging win instead came from **removing ~15 duplicated
decode-error log lines** into the single helper. (At request scale all of these are <2µs vs ~50µs
JSON parse + network I/O, i.e. noise either way — reported honestly, not inflated.)

---

## 4. Test summary

| | Before | After |
|---|---|---|
| Passing | 116 | 149 |
| Runtime | 3.77 s | 2.81 s |
| Coverage | 49.26% | 61.25% |

New tests (+33): `tests/utils/test_parsing.py` (18), `tests/utils/test_session_manager.py` (3),
`tests/services/tfex/test_trading_statistics.py` (5), `tests/services/tfex/test_list.py` (4),
plus end-to-end NaN/decode cases in `test_data_fetcher.py`, `test_shareholder.py`,
`test_financial.py`. Three existing JSON-decode tests were updated from the over-specific
`json.JSONDecodeError` to the new context-rich `ResponseParseError` (now also asserting the symbol).

Coverage movers: `utils/parsing.py` 100%; `tfex/list.py` 0% → ~80%;
`tfex/trading_statistics.py` 0% → covered; `session_manager.py` 14% → 45%.

**Slowest-tests delta:** unchanged in shape — the four `test_data_fetcher` retry/rate-limit tests
(~0.30 s each) still dominate because they exercise real `retry_delay`/`rate_limit_delay`
`asyncio.sleep`s. The new concurrency and NaN tests run in ~0.01 s; no new slow tests introduced.

---

## 5. Risks / deferred (intentionally not changed)

- **NaN rejection is coarse.** A single non-finite field fails the whole record (with context),
  chosen deliberately for financial correctness over silently dropping data. `parse_constant`
  catches the realistic case (a backend serializing the `NaN`/`Infinity` literal). It does **not**
  catch numeric *overflow* to `inf` (e.g. `1e999`, which `json` parses to `float('inf')` without a
  constant token). **Recommendation:** add `model_config = ConfigDict(allow_inf_nan=False)` to the
  numeric-heavy models as a belt-and-suspenders follow-up; deferred here to avoid touching every
  model's config in this pass.
- **Module/class-scope `asyncio.Lock`** (`session_manager._lock`, `session_cache._cache_lock`):
  reviewed and left as-is. On Python 3.11 (the project floor) `asyncio.Lock()` binds to the running
  loop lazily on first `await` (since 3.10), so construction at import/class scope is safe for the
  normal single-event-loop process. Caveat: code that drives the singletons from *multiple* event
  loops in one process could hit "bound to a different loop"; this pre-exists and the constraint to
  not introduce new global state / respect the singleton argued against changing it now.
- **Monetary/price fields use `float`, not `Decimal`.** This is the existing **public** Pydantic
  contract; switching would break field types, so per the brief it is **documented, not changed**.
  Worth a future decision if exact decimal precision becomes a requirement.
- **No comma/locale-formatted numeric coercion was added.** An early hypothesis was that the API
  might return `"1,234.56"` strings (which would fail `float()`); the test fixtures and observed
  payloads use **native JSON numbers**, and adding silent comma-stripping coercion risks masking
  malformed data. Left out by design; flagged as a watch item if such a payload is ever observed.

---

## 6. Public API compatibility

Confirmed unchanged (smoke-tested via `inspect.signature` + attribute checks):

- `fetch_*()` (models), `fetch_*_raw()` (dicts), and `get_*()` convenience functions keep identical
  signatures and return types (`symbol`, `lang="en"`, `config=None`); the unified
  `Stock` class and all its accessor methods are present; `en`/`th` + symbol normalization
  (`Stock("cpall").symbol == "CPALL"`) is intact.
- Pydantic model class names, field names, and field types are untouched.
- The new `settfex/utils/parsing.py` is **internal** (not exported from `settfex.utils.__all__`).
- Exception types: the documented `Raises: ValueError` contract is preserved —
  `ResponseParseError` subclasses `ValueError`, and original exceptions are chained (`from e`) or
  re-raised unchanged (`ValidationError`), so existing `except ValueError`/`Exception` handlers and
  `pytest.raises` continue to work.
