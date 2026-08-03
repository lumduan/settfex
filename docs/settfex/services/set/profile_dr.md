# DR Profile Service

Fetch Depositary Receipt (DR) details from the SET API — issuer and underlying information,
the conversion ratio, and the **TradingView "Indicative Price" chart link** shown on SET's DR
pages (e.g. GOOG80, MICRON01).

## Overview

- **Endpoint:** `GET https://www.set.or.th/api/set/dr/{symbol}/profile?lang={en|th}`
- **Host:** `www.set.or.th` (SessionManager/Incapsula handling applies, like every SET service)
- **Scope:** DR symbols only — the endpoint answers **every** non-DR symbol (including valid
  listed stocks like `CPALL`) with HTTP 404 body `{"message": "Invalid DR"}`
- Backs `Stock.get_dr_profile()`, `Stock.get_tradingview_url()`, and the DR indicative price
  service (see [dr_indicative_price.md](dr_indicative_price.md))

## Quick Start

```python
from settfex.services.set import get_dr_profile

profile = await get_dr_profile("GOOG80")
print(profile.underlying)              # "GOOG"
print(profile.underlying_exchange)     # "The Nasdaq Global Select Market"
print(profile.conversion_ratio)        # "2,000 : 1" (verbatim string)
print(profile.tradingview_url)         # https://th.tradingview.com/chart/?symbol=NASDAQ%3AGOOG*FX_IDC%3AUSDTHB%2F2000.0

expr = profile.indicative_expression   # parsed IndicativePriceExpression
print(expr.tickers, expr.ratio)        # ['NASDAQ:GOOG', 'FX_IDC:USDTHB'] 2000.0
```

Via the unified `Stock` class (cached per language on the instance):

```python
from settfex.services.set import Stock

stock = Stock("GOOG80")
dr = await stock.get_dr_profile()
url = await stock.get_tradingview_url()   # None for non-DR symbols
```

## Models

### `DrProfile`

Every field except `symbol` is optional (`| None`) — the payload is live-probed, not
documented by SET. Key fields:

| Field | Alias | Notes |
|---|---|---|
| `symbol` | — | DR symbol, e.g. `GOOG80` |
| `issuer` / `issuer_name` | `issuerName` | e.g. `KTB` / KRUNG THAI BANK |
| `security_type` / `security_type_name` | `securityType` / `securityTypeName` | `"X"` / `"Depositary Receipts"` |
| `conversion_ratio` | `conversionRatio` | **Verbatim string** (`"2,000 : 1"`) — the numeric ratio used for pricing comes from the expression instead |
| `underlying` / `underlying_name` | — / `underlyingName` | e.g. `GOOG` / ALPHABET INC. |
| `underlying_exchange` / `underlying_url` | `underlyingExchange` / `underlyingUrl` | Home exchange + info link |
| `fractional_trade` | `fractionalTrade` | `True` for fractional (DRx) trading |
| `trading_session` | `tradingSession` | e.g. `"Day & Night Session"` |
| `indicative_price_symbol` | `indicativePriceSymbol` | TradingView expression, e.g. `NASDAQ:GOOG*FX_IDC:USDTHB/2000.0` — **sometimes null** (HERMES80, BYDCOM80, NDX01) |
| `indicative_price_url` | `indicativePriceUrl` | TradingView chart URL — always present in probes |

Derived properties:

- `tradingview_url` → the `indicative_price_url` (the "Indicative Price" menu link)
- `indicative_expression` → parsed `IndicativePriceExpression | None`; prefers
  `indicative_price_symbol`, and **recovers the expression from the URL's `symbol` query
  parameter when that field is null**. Logs and returns `None` on parse failure — never raises.
- `asset_type` → `AssetType.DEPOSITARY_RECEIPT` for a normal DR payload

### `IndicativePriceExpression` / `parse_indicative_price_expression()`

Observed grammar: `{EXCHANGE}:{TICKER}*FX_IDC:{CCY}THB/{ratio}` (NASDAQ, EURONEXT, HKEX seen;
HKEX tickers are numeric like `HKEX:1211`). Parsing is defensive:

- trailing `/<float>` → `ratio` (must be > 0); absent → `1.0`
- `*`-separated TradingView tickers (1..n) → `tickers`
- raises `ValueError` on empty input, no tickers, or a bad/non-positive ratio

## Service Class

### `DrProfileService(config: FetcherConfig | None = None)`

- `fetch_dr_profile(symbol, lang="en") -> DrProfile`
- `fetch_dr_profile_raw(symbol, lang="en") -> dict[str, Any]` — the raw tier **also** checks
  HTTP status first, so a non-DR symbol raises `SymbolNotFoundError` instead of a parse error

## Error Handling

| Case | Raised |
|---|---|
| Empty symbol | `InvalidSymbolError` |
| Non-DR symbol (HTTP 404 `Invalid DR`) | `SymbolNotFoundError` with **no suggestion** — the 404 fires for perfectly valid non-DR symbols, so a "did you mean?" would suggest the symbol back to you |
| Other non-2xx | `FetchError` (with `status_code`) |
| Malformed body | `ResponseParseError` |

## Related Services

- [dr_indicative_price.md](dr_indicative_price.md) — evaluates the expression via TradingView
- [profile_stock.md](profile_stock.md) — the generic stock profile (works for DRs too;
  source of `securityType` → `AssetType`)
- [list.md](list.md) — `filter_by_asset_type(AssetType.DEPOSITARY_RECEIPT)` lists all DRs
