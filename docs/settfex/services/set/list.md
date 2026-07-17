# SET Stock List Service

## Overview

The Stock List Service provides async methods to fetch the complete list of stocks traded on the Stock Exchange of Thailand (SET). This service returns detailed information about each security including company names (Thai and English), market classifications, and industry sectors.

## Key Features

- **Async-First Design**: Built on `AsyncDataFetcher` for optimal performance
- **Full Type Safety**: Complete Pydantic models with runtime validation
- **Thai/Unicode Support**: Proper handling of Thai company names
- **Filtering Capabilities**: Filter stocks by market, industry, index membership, or lookup by symbol
- **Index Memberships**: Each stock lists its headline sub-index memberships (SET50, SET100,
  sSET, SETESG, ...) by default — see `include_indices`
- **Browser Impersonation**: Bypasses bot detection using realistic browser headers
- **Shared Configuration**: Reusable base URL for all SET services

## Installation

The Stock List Service is included with `settfex`:

```bash
pip install settfex
```

## Quick Start

### Basic Usage

```python
import asyncio
from settfex.services.set import get_stock_list

async def main():
    # Fetch complete stock list
    stock_list = await get_stock_list()

    print(f"Total stocks: {stock_list.count}")

    # Display first 5 stocks
    for stock in stock_list.security_symbols[:5]:
        print(f"{stock.symbol}: {stock.name_en}")

asyncio.run(main())
```

### Filter by Market

```python
async def filter_by_market_example():
    stock_list = await get_stock_list()

    # Get stocks from SET main board
    set_stocks = stock_list.filter_by_market("SET")
    print(f"SET market: {len(set_stocks)} stocks")

    # Get stocks from mai (Market for Alternative Investment)
    mai_stocks = stock_list.filter_by_market("mai")
    print(f"mai market: {len(mai_stocks)} stocks")

    # Display mai stocks
    for stock in mai_stocks[:10]:
        print(f"{stock.symbol}: {stock.name_en} (Industry: {stock.industry})")
```

### Lookup Specific Stock

```python
async def lookup_stock_example():
    stock_list = await get_stock_list()

    # Find PTT stock
    ptt = stock_list.get_symbol("PTT")
    if ptt:
        print(f"Symbol: {ptt.symbol}")
        print(f"English Name: {ptt.name_en}")
        print(f"Thai Name: {ptt.name_th}")
        print(f"Market: {ptt.market}")
        print(f"Industry: {ptt.industry}")
        print(f"Sector: {ptt.sector}")
```

### Filter by Industry

```python
async def filter_by_industry_example():
    stock_list = await get_stock_list()

    # Get all stocks in PROPCON (Property & Construction)
    propcon_stocks = stock_list.filter_by_industry("PROPCON")
    print(f"PROPCON industry: {len(propcon_stocks)} stocks")

    for stock in propcon_stocks[:5]:
        print(f"{stock.symbol}: {stock.name_en}")
```

## API Reference

### Models

#### StockSymbol

Model representing individual stock information.

**Fields:**
- `symbol: str` - Stock symbol/ticker (e.g., "PTT", "KBANK")
- `name_th: str` - Company name in Thai
- `name_en: str` - Company name in English
- `market: str` - Market type ("SET", "mai", etc.)
- `security_type: str` - Security type code
- `type_sequence: int` - Type sequence number
- `industry: str` - Industry classification (e.g., "PROPCON", "BANK", "TECH")
- `sector: str` - Sector classification
- `query_sector: str` - Queryable sector name
- `is_iff: bool` - Infrastructure Fund Flag
- `is_foreign_listing: bool` - Foreign listing flag
- `remark: str` - Additional remarks (default: "")
- `indices: list[str]` - Market index memberships (e.g. `['SET50', 'SET100', 'SETESG']`);
  populated when fetching with `include_indices=True` (the default), empty otherwise

**Example:**
```python
stock = stock_list.get_symbol("PTT")
print(f"Symbol: {stock.symbol}")
print(f"English: {stock.name_en}")
print(f"Thai: {stock.name_th}")
print(f"Market: {stock.market}")
print(f"Industry: {stock.industry}")
print(f"Indices: {stock.indices}")
```

#### StockListResponse

Response model for the complete stock list API.

**Fields:**
- `security_symbols: list[StockSymbol]` - List of all stock symbols

**Properties:**
- `count: int` - Total number of securities

**Methods:**

##### `filter_by_market(market: str) -> list[StockSymbol]`

Filter securities by market type.

**Parameters:**
- `market: str` - Market type (e.g., "SET", "mai")

**Returns:**
- `list[StockSymbol]` - Stocks in the specified market

**Example:**
```python
set_stocks = response.filter_by_market("SET")
mai_stocks = response.filter_by_market("mai")
```

##### `filter_by_industry(industry: str) -> list[StockSymbol]`

Filter securities by industry.

**Parameters:**
- `industry: str` - Industry classification (e.g., "BANK", "TECH")

**Returns:**
- `list[StockSymbol]` - Stocks in the specified industry

**Example:**
```python
bank_stocks = response.filter_by_industry("BANK")
tech_stocks = response.filter_by_industry("TECH")
```

##### `filter_by_index(index: str) -> list[StockSymbol]`

Filter securities by market index membership (case-insensitive). Requires the list to have
been fetched with `include_indices=True` (the default); otherwise every `indices` list is
empty and this returns nothing.

**Parameters:**
- `index: str` - Index symbol (e.g., "SET50", "SETESG", "sset")

**Returns:**
- `list[StockSymbol]` - Stocks that are members of the specified index

**Example:**
```python
set50_stocks = response.filter_by_index("SET50")    # 50 stocks
esg_stocks = response.filter_by_index("SETESG")
```

##### `get_symbol(symbol: str) -> StockSymbol | None`

Get a specific stock by symbol.

**Parameters:**
- `symbol: str` - Stock symbol to find

**Returns:**
- `StockSymbol` if found, `None` otherwise

**Example:**
```python
ptt = response.get_symbol("PTT")
if ptt:
    print(ptt.name_en)
else:
    print("Stock not found")
```

### Services

#### StockListService

Main service class for fetching stock lists.

##### `__init__(config: FetcherConfig | None = None)`

Initialize the stock list service.

**Parameters:**
- `config: FetcherConfig | None` - Optional fetcher configuration

**Example:**
```python
from settfex.services.set import StockListService
from settfex.utils.data_fetcher import FetcherConfig

# Use defaults
service = StockListService()

# Custom configuration
config = FetcherConfig(timeout=60, max_retries=5)
service = StockListService(config=config)
```

##### `async fetch_stock_list(include_indices: bool = True) -> StockListResponse`

Fetch the complete stock list with Pydantic validation.

By default each stock is enriched with its market index memberships by fetching the nine
headline sub-index compositions (SET50, SET50FF, SET100, SET100FF, sSET, SETCLMV, SETHD,
SETESG, SETWB) **concurrently** — one index-directory request plus nine composition requests
(~10 extra requests). Enrichment failures are logged and degrade to empty `indices` lists;
they never fail the stock list call.

**Parameters:**
- `include_indices: bool` - Whether to populate `StockSymbol.indices` (default: `True`).
  Pass `False` for the single-request behavior.

**Returns:**
- `StockListResponse` - Validated response with all stocks

**Raises:**
- `FetchError` - If the request fails (subclass of `Exception`)
- `ResponseParseError` - If the response cannot be parsed (subclass of `ValueError`)

**Example:**
```python
service = StockListService()
response = await service.fetch_stock_list()
print(f"Total: {response.count}")
print(response.get_symbol("CPALL").indices)   # ['SET50', 'SET50FF', ...]

# Single-request (no index memberships)
response = await service.fetch_stock_list(include_indices=False)
```

##### `async fetch_stock_list_raw() -> dict[str, Any]`

Fetch stock list as raw dictionary without validation.

Useful for debugging or when you need the raw API response.

**Returns:**
- `dict[str, Any]` - Raw dictionary from API

**Raises:**
- `FetchError` - If the request fails (subclass of `Exception`)

**Example:**
```python
service = StockListService()
raw_data = await service.fetch_stock_list_raw()
print(raw_data.keys())
```

### Convenience Functions

#### `get_stock_list(config: FetcherConfig | None = None, include_indices: bool = True) -> StockListResponse`

Quick one-line function to fetch stock list.

**Parameters:**
- `config: FetcherConfig | None` - Optional fetcher configuration
- `include_indices: bool` - Whether to populate `StockSymbol.indices` with index memberships
  (default: `True`; ~10 extra concurrent requests)

**Returns:**
- `StockListResponse` - Complete stock list

**Example:**
```python
from settfex.services.set import get_stock_list

# Quick access (index memberships included by default)
stock_list = await get_stock_list()
print(stock_list.get_symbol("CPALL").indices)

# Without index memberships (single request, fastest)
stock_list = await get_stock_list(include_indices=False)

# With custom config
config = FetcherConfig(timeout=60)
stock_list = await get_stock_list(config=config)
```

## Advanced Usage

### Custom Configuration

```python
from settfex.services.set import StockListService
from settfex.utils.data_fetcher import FetcherConfig

# Configure with longer timeout and more retries
config = FetcherConfig(
    browser_impersonate="safari17_0",  # Use Safari
    timeout=60,                        # 60 second timeout
    max_retries=5,                     # Retry up to 5 times
    retry_delay=2.0                    # 2 second base delay
)

service = StockListService(config=config)
response = await service.fetch_stock_list()
```

### Market Analysis

```python
async def analyze_markets():
    stock_list = await get_stock_list()

    # Analyze by market
    markets = {}
    for stock in stock_list.security_symbols:
        market = stock.market
        if market not in markets:
            markets[market] = 0
        markets[market] += 1

    print("Market Distribution:")
    for market, count in sorted(markets.items()):
        print(f"  {market}: {count} stocks")
```

### Industry Analysis

```python
async def analyze_industries():
    stock_list = await get_stock_list()

    # Count by industry
    industries = {}
    for stock in stock_list.security_symbols:
        industry = stock.industry
        if industry not in industries:
            industries[industry] = []
        industries[industry].append(stock.symbol)

    print("Industry Distribution:")
    for industry, symbols in sorted(industries.items()):
        print(f"  {industry}: {len(symbols)} stocks")
        print(f"    Examples: {', '.join(symbols[:3])}")
```

### Export to Different Formats

```python
async def export_to_csv():
    import csv

    stock_list = await get_stock_list()

    with open("stocks.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Symbol", "Name EN", "Name TH", "Market", "Industry"])

        for stock in stock_list.security_symbols:
            writer.writerow([
                stock.symbol,
                stock.name_en,
                stock.name_th,
                stock.market,
                stock.industry
            ])

    print(f"Exported {stock_list.count} stocks to stocks.csv")
```

## Error Handling

settfex raises typed exceptions from `settfex.exceptions` (all re-exported from the top-level
`settfex` package). Fetch errors subclass `Exception` and validation errors subclass `ValueError`,
so pre-0.9 `except Exception` / `except ValueError` handlers keep working.

### Basic Error Handling

```python
from settfex.exceptions import FetchError

async def safe_fetch():
    try:
        stock_list = await get_stock_list()
        print(f"Fetched {stock_list.count} stocks")
    except FetchError as e:            # HTTP/transport failure; has .status_code and .symbol
        print(f"Failed to fetch stock list: {e}")
```

### Retry on Failure

```python
from settfex.exceptions import FetchError

async def fetch_with_retry():
    from settfex.utils.data_fetcher import FetcherConfig

    # Configure aggressive retry
    config = FetcherConfig(
        max_retries=10,
        retry_delay=2.0
    )

    try:
        stock_list = await get_stock_list(config=config)
        return stock_list
    except FetchError as e:
        print(f"All retries failed: {e}")
        return None
```

### Symbol suggestions ("did you mean?")

Fetching the stock list also warms an in-process cache that powers a **network-free** "did you
mean?" hint on `SymbolNotFoundError` — so a later typo on any stock service suggests the closest
real symbol, with no extra request (the suggestion is `None`, and no fetch happens, when no list
has been fetched this session):

```python
from settfex import get_highlight_data, get_stock_list
from settfex.exceptions import SymbolNotFoundError
from settfex.services.set import suggest_symbol

await get_stock_list()                      # once per session — warms the suggestion cache

try:
    await get_highlight_data("CPALLL")      # typo
except SymbolNotFoundError as exc:
    print(exc)                              # "... HTTP 404 — did you mean 'CPALL'?"
    print(exc.suggestion)                   # "CPALL"

print(suggest_symbol("CPALLL"))             # "CPALL"  (or None if no list fetched yet)
```

## Performance

### Caching Results

```python
from datetime import datetime, timedelta

class StockListCache:
    def __init__(self, cache_duration: int = 3600):
        self.cache_duration = cache_duration
        self.cached_data = None
        self.cache_time = None

    async def get_stock_list(self) -> StockListResponse:
        now = datetime.now()

        # Check if cache is valid
        if (self.cached_data is not None and
            self.cache_time is not None and
            now - self.cache_time < timedelta(seconds=self.cache_duration)):
            print("Returning cached data")
            return self.cached_data

        # Fetch fresh data
        print("Fetching fresh data")
        stock_list = await get_stock_list()

        # Update cache
        self.cached_data = stock_list
        self.cache_time = now

        return stock_list

# Usage
cache = StockListCache(cache_duration=3600)  # 1 hour cache
stock_list = await cache.get_stock_list()
```

## Logging

### Enable Logging

```python
from loguru import logger
from settfex.utils.logging import setup_logger

# Configure logging
setup_logger(level="DEBUG", log_file="logs/stock_list.log")

# Fetch with logging
stock_list = await get_stock_list()
```

### Log Levels

- **DEBUG**: Detailed request/response information
- **INFO**: Successful operations with counts
- **WARNING**: Retry attempts
- **ERROR**: Failed requests

## Common Use Cases

### Stock Symbol Validation

```python
async def validate_symbol(symbol: str) -> bool:
    """Check if a stock symbol exists."""
    stock_list = await get_stock_list()
    return stock_list.get_symbol(symbol) is not None

# Usage
is_valid = await validate_symbol("PTT")  # True
is_valid = await validate_symbol("INVALID")  # False
```

### Get All Symbols

```python
async def get_all_symbols() -> list[str]:
    """Get list of all stock symbols."""
    stock_list = await get_stock_list()
    return [s.symbol for s in stock_list.security_symbols]

# Usage
symbols = await get_all_symbols()
print(f"Total symbols: {len(symbols)}")
print(f"First 10: {symbols[:10]}")
```

### Find Stocks by Name

```python
async def search_by_name(query: str) -> list[StockSymbol]:
    """Search stocks by English or Thai name."""
    stock_list = await get_stock_list()
    query_lower = query.lower()

    results = []
    for stock in stock_list.security_symbols:
        if (query_lower in stock.name_en.lower() or
            query in stock.name_th):
            results.append(stock)

    return results

# Usage
results = await search_by_name("bank")
for stock in results:
    print(f"{stock.symbol}: {stock.name_en}")
```

## Integration Examples

### With pandas

```python
import pandas as pd

async def to_dataframe() -> pd.DataFrame:
    """Convert stock list to pandas DataFrame."""
    stock_list = await get_stock_list()

    data = [
        {
            "symbol": s.symbol,
            "name_en": s.name_en,
            "name_th": s.name_th,
            "market": s.market,
            "industry": s.industry,
            "sector": s.sector
        }
        for s in stock_list.security_symbols
    ]

    return pd.DataFrame(data)

# Usage
df = await to_dataframe()
print(df.head())
print(df.describe())
```

### With Database

```python
import sqlite3

async def save_to_database(db_path: str):
    """Save stock list to SQLite database."""
    stock_list = await get_stock_list()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stocks (
            symbol TEXT PRIMARY KEY,
            name_en TEXT,
            name_th TEXT,
            market TEXT,
            industry TEXT,
            sector TEXT
        )
    """)

    # Insert data
    for stock in stock_list.security_symbols:
        cursor.execute("""
            INSERT OR REPLACE INTO stocks
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            stock.symbol,
            stock.name_en,
            stock.name_th,
            stock.market,
            stock.industry,
            stock.sector
        ))

    conn.commit()
    conn.close()

    print(f"Saved {stock_list.count} stocks to {db_path}")
```

## Constants

The service uses shared constants defined in [settfex/services/set/constants.py](../../../settfex/services/set/constants.py):

- `SET_BASE_URL`: `"https://www.set.or.th"`
- `SET_STOCK_LIST_ENDPOINT`: `"/api/set/stock/list"`

## Performance Note: Index Membership Enrichment

`fetch_stock_list()` / `get_stock_list()` enrich each stock with its index memberships **by
default**. This adds one index-directory request plus nine composition requests (all fetched
concurrently) on top of the single stock-list request — typically well under a second with a
warm session. If any of those requests fail, the affected index is skipped (or the whole
enrichment is skipped) with a warning; the stock list itself is never affected. Pass
`include_indices=False` when you only need the raw universe.

## See Also

- [Market Index Service](index.md) - Index directory, quotations, and constituents
- [AsyncDataFetcher](../../utils/data_fetcher.md) - Underlying HTTP client
- [Logging Utilities](../../utils/logging.md) - Logging configuration
- [FetcherConfig](../../utils/data_fetcher.md#fetcherconfig) - Configuration options

## Troubleshooting

### Issue: Request blocked by server

**Solution:** The service uses browser impersonation. Try different browser:

```python
from settfex.utils.data_fetcher import FetcherConfig

config = FetcherConfig(browser_impersonate="safari17_0")
stock_list = await get_stock_list(config=config)
```

### Issue: Timeout errors

**Solution:** Increase timeout and retries:

```python
config = FetcherConfig(
    timeout=60,
    max_retries=5,
    retry_delay=2.0
)
stock_list = await get_stock_list(config=config)
```

### Issue: Thai characters appear corrupted

**Solution:** The service handles Thai encoding automatically. If you see issues, ensure your terminal/IDE supports UTF-8:

```python
# Verify encoding
stock = stock_list.get_symbol("PTT")
print(stock.name_th)  # Should display Thai correctly
```

## Best Practices

1. **Cache Results**: Stock list doesn't change frequently, cache for at least 1 hour
2. **Handle Errors**: Always wrap calls in try/except blocks
3. **Use Filters**: Use built-in filter methods instead of manual iteration
4. **Logging**: Enable logging during development for debugging
5. **Custom Config**: Configure timeouts based on your network conditions
6. **Async Patterns**: Use `asyncio.gather()` if fetching multiple resources

## Example: Complete Application

```python
import asyncio
from loguru import logger
from settfex.services.set import get_stock_list
from settfex.utils.logging import setup_logger
from settfex.utils.data_fetcher import FetcherConfig

async def main():
    # Setup logging
    setup_logger(level="INFO", log_file="logs/app.log")

    # Configure with custom settings
    config = FetcherConfig(
        timeout=60,
        max_retries=3,
        browser_impersonate="chrome120"
    )

    try:
        # Fetch stock list
        logger.info("Fetching stock list...")
        stock_list = await get_stock_list(config=config)
        logger.info(f"Fetched {stock_list.count} stocks")

        # Analyze markets
        set_stocks = stock_list.filter_by_market("SET")
        mai_stocks = stock_list.filter_by_market("mai")

        print(f"\nMarket Summary:")
        print(f"  SET: {len(set_stocks)} stocks")
        print(f"  mai: {len(mai_stocks)} stocks")

        # Top 10 stocks
        print(f"\nFirst 10 stocks:")
        for stock in stock_list.security_symbols[:10]:
            print(f"  {stock.symbol:8} {stock.name_en}")

        # Search for specific stock
        symbol = "PTT"
        stock = stock_list.get_symbol(symbol)
        if stock:
            print(f"\nStock Details for {symbol}:")
            print(f"  English: {stock.name_en}")
            print(f"  Thai: {stock.name_th}")
            print(f"  Market: {stock.market}")
            print(f"  Industry: {stock.industry}")

    except Exception as e:
        logger.error(f"Application failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
```
