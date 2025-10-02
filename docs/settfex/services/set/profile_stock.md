# Stock Profile Service

The Stock Profile Service provides async methods to fetch comprehensive profile information for individual stock symbols from the Stock Exchange of Thailand (SET).

## Overview

This service fetches detailed company and listing information including:
- Company identification (name, symbol, market)
- Classification (sector, industry)
- Listing details (dates, status, IPO price)
- Share structure (listed shares, par value, free float)
- Foreign ownership limits and availability
- ISIN codes for different trading types
- Fiscal year information
- Derivative-specific data (for warrants)

**Key Features:**
- **Type Safety**: Complete Pydantic model with 30+ profile fields
- **Dual Language Support**: English ('en') and Thai ('th') responses
- **Async-First**: Built on AsyncDataFetcher for optimal performance
- **Bot Detection Bypass**: Automatic symbol-specific referer and landing_url cookie for reliable data fetching
- **Concurrent Request Support**: Fetch multiple stock profiles simultaneously without delays

## Installation

```bash
pip install settfex
```

## Quick Start

### Using Convenience Function

```python
import asyncio
from settfex.services.set.stock import get_profile

async def main():
    # Fetch profile for PTT
    profile = await get_profile("PTT")

    print(f"Company: {profile.name}")
    print(f"Symbol: {profile.symbol}")
    print(f"Market: {profile.market}")
    print(f"Sector: {profile.sector_name}")
    print(f"Industry: {profile.industry_name}")
    print(f"Status: {profile.status}")
    print(f"Listed Date: {profile.listed_date}")
    print(f"IPO Price: {profile.ipo} {profile.currency}")
    print(f"Listed Shares: {profile.listed_share:,}")
    print(f"Free Float: {profile.percent_free_float}%")
    print(f"Foreign Limit: {profile.percent_foreign_limit}%")
    print(f"Foreign Room: {profile.percent_foreign_room}%")

asyncio.run(main())
```

### Using Service Class

```python
import asyncio
from settfex.services.set.stock import StockProfileService
from settfex.utils.data_fetcher import FetcherConfig

async def main():
    # Create service with custom configuration
    config = FetcherConfig(timeout=60, max_retries=5)
    service = StockProfileService(config=config)

    # Fetch profile data
    profile = await service.fetch_profile("CPALL", lang="en")

    print(f"\n{profile.name} ({profile.symbol})")
    print(f"{'=' * 60}")
    print(f"Market: {profile.market}")
    print(f"Sector: {profile.sector_name} ({profile.sector})")
    print(f"Industry: {profile.industry_name} ({profile.industry})")
    print(f"Security Type: {profile.security_type_name}")
    print(f"\nListing Information:")
    print(f"  Status: {profile.status}")
    print(f"  Listed Date: {profile.listed_date}")
    print(f"  First Trade: {profile.first_trade_date}")
    print(f"  IPO Price: {profile.ipo} {profile.currency}")
    print(f"\nShare Structure:")
    print(f"  Par Value: {profile.par} {profile.currency}")
    print(f"  Listed Shares: {profile.listed_share:,}")
    print(f"  Free Float: {profile.percent_free_float:.2f}%")
    print(f"\nForeign Ownership:")
    print(f"  Foreign Limit: {profile.percent_foreign_limit:.2f}%")
    print(f"  Foreign Room: {profile.percent_foreign_room:.2f}%")
    print(f"  Available Shares: {profile.foreign_available:,}")
    print(f"\nISIN Codes:")
    print(f"  Local: {profile.isin_local}")
    print(f"  Foreign: {profile.isin_foreign}")
    print(f"  NVDR: {profile.isin_nvdr}")

asyncio.run(main())
```

### Using with Unified Stock Class

```python
import asyncio
from settfex.services.set import Stock

async def main():
    # Create Stock instance
    stock = Stock("PTT")

    # Fetch profile (when implemented in Stock class)
    # profile = await stock.get_profile()
    # print(f"{profile.name}: {profile.sector_name}")

asyncio.run(main())
```

## Language Support

The service supports both English and Thai languages:

```python
# English (default)
profile = await get_profile("PTT", lang="en")

# Thai
profile_th = await get_profile("PTT", lang="th")

# Multiple language code formats supported
profile = await get_profile("PTT", lang="english")  # Normalized to 'en'
profile = await get_profile("PTT", lang="thai")     # Normalized to 'th'
```

## Authentication

For production use with real API access, provide browser session cookies:

```python
from settfex.services.set.stock import StockProfileService

# Get cookies from an authenticated browser session
cookies = "charlot=abc123; incap_ses_357_2046605=xyz789; ..."

# Create service with session cookies
service = StockProfileService(session_cookies=cookies)
profile = await service.fetch_profile("PTT")
```

Without session cookies, the service generates Incapsula-aware cookies automatically, but these may be blocked by Incapsula bot protection.

## Raw Data Access

For debugging or custom processing, fetch raw API response:

```python
service = StockProfileService()

# Get raw dictionary instead of Pydantic model
raw_data = await service.fetch_profile_raw("PTT")
print(raw_data.keys())
print(raw_data)
```

## API Reference

### `StockProfile`

Pydantic model representing stock profile data.

**Key Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | `str` | Stock symbol/ticker |
| `name` | `str` | Company name |
| `market` | `str` | Market (SET, mai, etc.) |
| `industry` | `str` | Industry code |
| `industry_name` | `str` | Industry name |
| `sector` | `str` | Sector code |
| `sector_name` | `str` | Sector name |
| `security_type` | `str` | Security type code |
| `security_type_name` | `str` | Security type name |
| `status` | `str` | Listing status |
| `listed_date` | `datetime \| None` | Date when listed |
| `first_trade_date` | `datetime \| None` | First trade date |
| `ipo` | `float \| None` | IPO price |
| `par` | `float \| None` | Par value per share |
| `currency` | `str \| None` | Currency code |
| `listed_share` | `int \| None` | Number of listed shares |
| `percent_free_float` | `float \| None` | Free float percentage |
| `percent_foreign_limit` | `float \| None` | Foreign ownership limit |
| `percent_foreign_room` | `float \| None` | Foreign room available |
| `foreign_available` | `int \| None` | Shares available for foreign ownership |
| `isin_local` | `str \| None` | ISIN for local trading |
| `isin_foreign` | `str \| None` | ISIN for foreign trading |
| `isin_nvdr` | `str \| None` | ISIN for NVDR |
| `fiscal_year_end` | `str \| None` | Fiscal year end (DD/MM) |
| `account_form` | `str \| None` | Accounting form type |

### `StockProfileService`

Service class for fetching stock profile data.

#### `__init__(config, session_cookies)`

Initialize the service.

**Parameters:**
- `config` (`FetcherConfig | None`): Optional fetcher configuration
- `session_cookies` (`str | None`): Optional browser session cookies

#### `fetch_profile(symbol, lang)`

Fetch profile data for a stock symbol.

**Parameters:**
- `symbol` (`str`): Stock symbol (e.g., "PTT", "CPALL")
- `lang` (`str`): Language code ('en' or 'th', default: 'en')

**Returns:** `StockProfile`

**Raises:**
- `ValueError`: If symbol is empty or language is invalid
- `Exception`: If request fails or response cannot be parsed

#### `fetch_profile_raw(symbol, lang)`

Fetch raw profile data without validation.

**Parameters:**
- `symbol` (`str`): Stock symbol
- `lang` (`str`): Language code

**Returns:** `dict[str, Any]`

### `get_profile(symbol, lang, config, session_cookies)`

Convenience function to fetch stock profile.

**Parameters:**
- `symbol` (`str`): Stock symbol
- `lang` (`str`): Language code (default: 'en')
- `config` (`FetcherConfig | None`): Optional configuration
- `session_cookies` (`str | None`): Optional session cookies

**Returns:** `StockProfile`

## Configuration

Customize fetcher behavior using `FetcherConfig`:

```python
from settfex.utils.data_fetcher import FetcherConfig
from settfex.services.set.stock import StockProfileService

config = FetcherConfig(
    browser_impersonate="chrome120",  # Browser to impersonate
    timeout=60,                       # Request timeout (seconds)
    max_retries=5,                    # Maximum retry attempts
    retry_delay=2.0,                  # Base retry delay (seconds)
)

service = StockProfileService(config=config)
profile = await service.fetch_profile("PTT")
```

## Error Handling

```python
from loguru import logger
from settfex.services.set.stock import get_profile

async def fetch_with_error_handling():
    try:
        profile = await get_profile("INVALID_SYMBOL")
    except ValueError as e:
        logger.error(f"Invalid input: {e}")
    except Exception as e:
        logger.error(f"Failed to fetch profile: {e}")
        # Common errors:
        # - HTTP 452: Incapsula bot detection (use real browser cookies)
        # - HTTP 404: Invalid symbol
        # - JSON decode error: Empty or malformed response
```

## Important Notes on Bot Detection

**Incapsula/Imperva Protection**: The SET API is protected by Incapsula bot detection. This service implements several techniques to bypass detection:

1. **Symbol-Specific Referer** (✓ Implemented): Each request includes a referer header that matches the stock symbol being fetched:
   ```
   Referer: https://www.set.or.th/en/market/product/stock/quote/{symbol}/price
   ```
   This mimics real browser behavior and is **critical** for bypassing Incapsula.

2. **Browser Impersonation**: Uses curl_cffi to impersonate Chrome 120 with proper headers

3. **Incapsula Cookies**: Generates realistic Incapsula-aware cookies automatically

**Best Practices**:
- ✅ **Concurrent Requests Work**: Thanks to symbol-specific referers, you can now fetch multiple stocks concurrently without issues
- ✅ **No Delays Needed**: The referer fix eliminates the need for artificial delays between requests
- 💡 **Optional**: For maximum reliability in production, consider using real browser session cookies

**Concurrent Requests Example** (Recommended):
```python
import asyncio
from settfex.services.set.stock import get_profile

async def fetch_multiple():
    symbols = ["PTT", "CPALL", "KBANK", "AOT"]

    # ✓ RECOMMENDED: Concurrent requests work perfectly with symbol-specific referers
    profiles = await asyncio.gather(*[get_profile(s) for s in symbols])

    for profile in profiles:
        print(f"{profile.symbol}: {profile.name}")

asyncio.run(fetch_multiple())
```

## Example: Compare Multiple Stocks

```python
import asyncio
from settfex.services.set.stock import get_profile

async def compare_stocks():
    symbols = ["PTT", "CPALL", "KBANK", "AOT"]

    # Fetch profiles concurrently (works perfectly with symbol-specific referers!)
    profiles = await asyncio.gather(*[get_profile(symbol) for symbol in symbols])

    # Display comparison
    print(f"\n{'Symbol':<10} {'Name':<40} {'Sector':<20} {'IPO':>10}")
    print("=" * 82)
    for profile in profiles:
        print(f"{profile.symbol:<10} {profile.name:<40} "
              f"{profile.sector_name:<20} {profile.ipo or 0:>10.2f}")

asyncio.run(compare_stocks())
```

## Example: Analyze Foreign Ownership

```python
import asyncio
from settfex.services.set.stock import get_profile

async def analyze_foreign_ownership(symbol: str):
    profile = await get_profile(symbol)

    print(f"\n{profile.name} ({profile.symbol})")
    print(f"{'=' * 60}")
    print(f"Foreign Ownership Analysis:")
    print(f"  Foreign Limit: {profile.percent_foreign_limit:.2f}%")
    print(f"  Foreign Room: {profile.percent_foreign_room:.2f}%")
    print(f"  Available Shares: {profile.foreign_available:,}")
    print(f"  As of: {profile.foreign_limit_as_of}")

    # Calculate used foreign quota
    if profile.percent_foreign_limit and profile.percent_foreign_room:
        used = profile.percent_foreign_limit - profile.percent_foreign_room
        print(f"  Used Foreign Quota: {used:.2f}%")
        print(f"  Utilization: {(used / profile.percent_foreign_limit * 100):.1f}%")

asyncio.run(analyze_foreign_ownership("PTT"))
```

## Integration with Other Services

Combine with other services for comprehensive analysis:

```python
import asyncio
from settfex.services.set import Stock, get_profile, get_highlight_data

async def full_stock_analysis(symbol: str):
    # Fetch profile and highlight data concurrently
    profile, highlight = await asyncio.gather(
        get_profile(symbol),
        get_highlight_data(symbol)
    )

    print(f"\n{profile.name} ({symbol})")
    print(f"{'=' * 60}")

    print(f"\nProfile:")
    print(f"  Sector: {profile.sector_name}")
    print(f"  Industry: {profile.industry_name}")
    print(f"  Listed: {profile.listed_date}")
    print(f"  IPO: {profile.ipo} {profile.currency}")

    print(f"\nValuation:")
    print(f"  Market Cap: {highlight.market_cap:,.0f}")
    print(f"  P/E Ratio: {highlight.pe_ratio}")
    print(f"  P/B Ratio: {highlight.pb_ratio}")
    print(f"  Dividend Yield: {highlight.dividend_yield}%")

asyncio.run(full_stock_analysis("CPALL"))
```

## Important Notes on Bot Detection

The service implements a two-part bot detection bypass pattern that is critical for reliable data fetching:

### 1. Symbol-Specific Referer Header (✓ Implemented)
Each request automatically includes a referer header that matches the stock symbol being fetched:
```
Referer: https://www.set.or.th/en/market/product/stock/quote/{symbol}/price
```

### 2. Landing URL Cookie (✓ Implemented)
The service automatically generates a `landing_url` cookie matching the referer for symbols with stricter Incapsula rules:
```
landing_url=https://www.set.or.th/en/market/product/stock/quote/{symbol}/price
```

**Why This Matters:**
- Incapsula/Imperva bot protection checks **both** the HTTP referer header and the `landing_url` cookie value
- Some symbols (like CPN) have stricter security rules and require both to be present and matching
- Without both, requests may fail with HTTP 452 (bot detection blocked)

**Implementation:**
```python
# Automatically applied in fetch_profile()
referer = f"https://www.set.or.th/en/market/product/stock/quote/{symbol}/price"
headers = AsyncDataFetcher.get_set_api_headers(referer=referer)
cookies = AsyncDataFetcher.generate_incapsula_cookies(landing_url=referer)
```

**Best Practices:**
- ✅ **Concurrent Requests Work**: Thanks to symbol-specific referers and landing_url cookies, you can fetch multiple stocks concurrently without issues
- ✅ **No Delays Needed**: The bypass fixes eliminate the need for artificial delays between requests
- ✅ **All Symbols Supported**: Works with symbols having both standard and strict Incapsula rules (PTT, CPALL, CPN, etc.)

## Notes

- Stock symbols are automatically normalized to uppercase
- Language codes are normalized (en/eng/english → 'en', th/tha/thai → 'th')
- All datetime fields are timezone-aware (Asia/Bangkok)
- Optional fields may be `None` depending on security type
- Derivative-specific fields (exercise_price, underlying) are only populated for warrants
- Free float and foreign ownership data have separate as-of dates

## See Also

- [Stock Highlight Data Service](highlight_data.md) - Valuation metrics and trading statistics
- [Stock List Service](list.md) - Complete SET stock listing
- [AsyncDataFetcher](../../utils/data_fetcher.md) - HTTP client with Thai/Unicode support
- [Stock Utilities](../stock/utils.md) - Symbol and language normalization
