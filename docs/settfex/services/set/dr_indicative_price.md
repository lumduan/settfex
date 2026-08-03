# DR Indicative Price Service (TradingView)

Compute a DR's **indicative (fair value) price** — `underlying price × FX rate ÷ conversion
ratio` in THB — by evaluating the TradingView expression SET publishes per DR (see
[profile_dr.md](profile_dr.md)). This is the number behind the "Indicative Price" menu on
SET's DR pages, and it keeps moving while SET is closed because the underlying market trades
on its own hours.

## Overview

- **Endpoint:** `POST https://scanner.tradingview.com/global/scan` — one batch request
  fetches every expression leg (underlying + FX) together
- **Host:** `scanner.tradingview.com` — foreign, unauthenticated, **stateless**: the service
  forces `use_session=False` for TradingView calls (never SessionManager; the scan is a POST,
  which the persistent-session path does not support anyway). The SET-host DR-profile fetch
  keeps the caller's config untouched.
- **Freshness:** the `close` column is the last price — **~15-minute delayed** for exchange
  legs (`update_mode: "delayed_streaming_900"`), streaming for `FX_IDC` legs. The `lp` /
  `lp_time` columns are null over plain HTTP (websocket-only) and are deliberately not used.
- Verified live 2026-08-03: GOOG80 → `356.65 USD × 33.33 THB/USD ÷ 2000 ≈ 5.94 THB` vs the
  DR's own SET close of 5.75 — **divergence is expected** (the US session moved after SET
  closed), not a bug.

## Quick Start

```python
from settfex.services.set import get_dr_indicative_price

price = await get_dr_indicative_price("GOOG80")
print(price.indicative_price)    # 5.9454 (THB)
print(price.underlying.close)    # 356.65 (USD, ~15-min delayed)
print(price.fx.close)            # 33.34 (USDTHB, streaming)
print(price.ratio)               # 2000.0
print(price.is_delayed)          # True
```

### `Stock.get_latest_price()` auto-switch (DRs)

For DR symbols, `Stock.get_latest_price()` returns the TradingView indicative price by
default, falling back to SET chart data on **any** TradingView failure:

```python
from settfex.services.set import DrIndicativeQuotation, Stock

stock = Stock("GOOG80")
q = await stock.get_latest_price()                # DrIndicativeQuotation (indicative)
q.price                                            # 5.9454 THB
q.volume                                           # None — fair value, not a SET trade
q.indicative.expression                            # 'NASDAQ:GOOG*FX_IDC:USDTHB/2000.0'
isinstance(q, DrIndicativeQuotation)               # True — provenance check

q = await stock.get_latest_price(prefer_dr_indicative=False)   # SET traded price instead
```

Rules of the switch:

- Applies only to DRs (detected via one cached DR-profile probe per `Stock` instance; the
  probe's 404 marks a non-DR permanently for that instance — zero overhead afterwards).
- Skipped when an explicit `as_of` is passed — TradingView serves only "now" and cannot
  answer a historical instant; the SET chart path is used instead.
- `period` / `accumulated` only affect the SET chart path.
- Any TradingView/profile failure logs a warning and falls back to SET chart data.

## Models

### `TradingViewQuote`

One leg quote: `ticker`, `name`, `close` (the delayed last price), `change` (percent),
`currency`, `update_mode`.

### `DrIndicativePrice`

| Field | Notes |
|---|---|
| `symbol` | DR symbol |
| `indicative_price` | THB: `product(leg closes) / ratio` |
| `ratio` / `expression` | From the parsed expression |
| `tradingview_url` | SET's chart link |
| `legs` | `list[TradingViewQuote]`, in expression order |
| `as_of` | Computation instant, aware Asia/Bangkok (TradingView provides no usable timestamp over HTTP) |

Properties: `underlying` (first non-`FX_IDC:` leg), `fx` (first `FX_IDC:` leg), `is_delayed`;
`to_quotation()` → `DrIndicativeQuotation`.

### `DrIndicativeQuotation(Quotation)`

A `Quotation` subclass: `price` = indicative price, `quote_datetime` = `as_of`,
`volume`/`value`/`change`/`percent_change` = `None`, plus `.indicative` carrying the full
`DrIndicativePrice`. Use `isinstance(...)` or `.indicative` to tell it apart from a real SET
quotation.

## Service Class

### `DrIndicativePriceService(config: FetcherConfig | None = None)`

- `fetch_quotes(tickers) -> dict[str, TradingViewQuote]` — one batch scan; result keyed by
  UPPERCASED ticker; duplicates deduped. TradingView answers **unknown tickers with HTTP 200
  and the row simply missing** — missing rows raise `FetchError` explicitly.
- `fetch_quotes_raw(tickers) -> dict` — the raw scan response
- `fetch_indicative_price(symbol, *, profile=None) -> DrIndicativePrice` — pass a pre-fetched
  `DrProfile` to skip the profile request (the `Stock` class does this)

## Error Handling

| Case | Raised |
|---|---|
| Empty tickers | `ValueError` |
| Empty symbol | `InvalidSymbolError` |
| Non-DR symbol | `SymbolNotFoundError` (from the profile fetch; no suggestion) |
| TradingView non-2xx / transport | `FetchError` (explicit status check — `AsyncDataFetcher` retries exceptions only, never a non-2xx status) |
| Requested ticker missing from scan / null `close` leg | `FetchError` naming the leg(s) |
| No usable expression (both `indicativePriceSymbol` and URL unusable) | `FetchError` |
| Malformed body | `ResponseParseError` |

## Related Services

- [profile_dr.md](profile_dr.md) — the expression source
- [chart_quotation.md](chart_quotation.md) — the SET fallback path used by
  `Stock.get_latest_price()`
