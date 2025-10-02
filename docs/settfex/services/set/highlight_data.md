# Stock Highlight Data Service

## Overview

The Stock Highlight Data Service provides async methods to fetch highlight data for individual stock symbols from the Stock Exchange of Thailand (SET). This service returns key metrics including market capitalization, P/E ratio, P/B ratio, dividend yield, beta, and trading statistics.

## Key Features

- **Single Stock Focus**: Fetch detailed highlight data for one stock at a time
- **Type Safety**: Complete Pydantic models for all data structures
- **Thai/Unicode Support**: Proper handling of Thai text in responses
- **Dual Language Support**: Request data in English ('en') or Thai ('th')
- **Symbol Normalization**: Automatic uppercase conversion for stock symbols
- **Async-First**: Built on AsyncDataFetcher for optimal performance
- **Flexible Cookie Support**: Accepts real browser session cookies or generates them

## Installation

The service is included with `settfex`:

```bash
pip install settfex
```

## Quick Start

### Using the Stock Class (Recommended)

```python
import asyncio
from settfex.services.set import Stock

async def main():
    # Create Stock instance
    stock = Stock("CPALL")

    # Fetch highlight data
    data = await stock.get_highlight_data()

    print(f"Symbol: {data.symbol}")
    print(f"Market Cap: {data.market_cap:,.0f} THB")
    print(f"P/E Ratio: {data.pe_ratio}")
    print(f"P/B Ratio: {data.pb_ratio}")
    print(f"Dividend Yield: {data.dividend_yield}%")
    print(f"Beta: {data.beta}")
    print(f"YTD Change: {data.ytd_percent_change:.2f}%")
    print(f"52-Week High: {data.year_high_price}")
    print(f"52-Week Low: {data.year_low_price}")

asyncio.run(main())
```

### Using Convenience Function

```python
import asyncio
from settfex.services.set.stock import get_highlight_data

async def main():
    # Quick one-line fetch
    data = await get_highlight_data("CPALL")

    print(f"Market Cap: {data.market_cap:,.0f} THB")
    print(f"P/E Ratio: {data.pe_ratio}")

asyncio.run(main())
```

### Thai Language Support

```python
# Fetch data in Thai
data = await get_highlight_data("CPALL", lang="th")
print(f"Symbol: {data.symbol}")
print(f"Market Cap: {data.market_cap:,.0f} บาท")
```

### Using the Service Class

```python
from settfex.services.set.stock import StockHighlightDataService
from settfex.utils.data_fetcher import FetcherConfig

# Custom configuration
config = FetcherConfig(
    timeout=60,
    max_retries=5,
    retry_delay=2.0
)

# Initialize service
service = StockHighlightDataService(config=config)

# Fetch data
data = await service.fetch_highlight_data("PTT")
print(f"Market Cap: {data.market_cap:,.0f}")

# Fetch multiple stocks
symbols = ["CPALL", "PTT", "KBANK", "AOT", "BBL"]
for symbol in symbols:
    data = await service.fetch_highlight_data(symbol)
    print(f"{data.symbol}: P/E={data.pe_ratio}, P/B={data.pb_ratio}")
```

## API Reference

### Models

#### StockHighlightData

Complete model representing stock highlight data.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | `str` | Stock symbol/ticker |
| `as_of_date` | `datetime` | Data as of date |
| `market_cap` | `float \| None` | Market capitalization (THB) |
| `pe_ratio` | `float \| None` | Price to Earnings ratio |
| `pb_ratio` | `float \| None` | Price to Book ratio |
| `dividend_yield` | `float \| None` | Dividend yield percentage |
| `beta` | `float \| None` | Beta coefficient (volatility measure) |
| `ytd_percent_change` | `float \| None` | Year-to-date percent change |
| `xd_date` | `datetime \| None` | Ex-dividend date |
| `xd_session` | `str \| None` | Ex-dividend session |
| `dividend` | `float \| None` | Dividend amount per share |
| `dividend_ratio` | `float \| None` | Dividend ratio |
| `free_float_as_of_date` | `datetime \| None` | Free float data as of date |
| `percent_free_float` | `float \| None` | Percentage of free float |
| `year_high_price` | `float \| None` | 52-week high price |
| `year_low_price` | `float \| None` | 52-week low price |
| `listed_share` | `int \| None` | Number of listed shares |
| `par` | `float \| None` | Par value |
| `currency` | `str \| None` | Currency code (e.g., "THB") |
| `nvdr_buy_volume` | `float \| None` | NVDR buy volume |
| `nvdr_sell_volume` | `float \| None` | NVDR sell volume |
| `nvdr_buy_value` | `float \| None` | NVDR buy value |
| `nvdr_sell_value` | `float \| None` | NVDR sell value |
| `outstanding_date` | `datetime \| None` | Outstanding shares date |
| `outstanding_share` | `int \| None` | Number of outstanding shares |
| `dividend_yield_12m` | `float \| None` | 12-month dividend yield |
| `turnover_ratio` | `float \| None` | Turnover ratio |
| `nvdr_net_volume` | `float \| None` | NVDR net volume |
| `nvdr_net_value` | `float \| None` | NVDR net value |

### Service Class

#### StockHighlightDataService

Main service class for fetching stock highlight data.

**Constructor:**

```python
def __init__(
    config: FetcherConfig | None = None,
    session_cookies: str | None = None
) -> None
```

**Parameters:**
- `config`: Optional fetcher configuration (timeout, retries, etc.)
- `session_cookies`: Optional browser session cookies for bypassing Incapsula

**Methods:**

##### fetch_highlight_data()

```python
async def fetch_highlight_data(
    symbol: str,
    lang: str = "en"
) -> StockHighlightData
```

Fetch highlight data for a specific stock symbol.

**Parameters:**
- `symbol`: Stock symbol (e.g., "CPALL", "PTT", "kbank") - automatically normalized to uppercase
- `lang`: Language for response ('en' or 'th', default: 'en')

**Returns:**
- `StockHighlightData` with all metrics and statistics

**Raises:**
- `ValueError`: If symbol is empty or language is invalid
- `Exception`: If request fails or response cannot be parsed

**Example:**

```python
service = StockHighlightDataService()
data = await service.fetch_highlight_data("CPALL", lang="en")
print(f"Market Cap: {data.market_cap:,.0f}")
```

##### fetch_highlight_data_raw()

```python
async def fetch_highlight_data_raw(
    symbol: str,
    lang: str = "en"
) -> dict[str, Any]
```

Fetch highlight data as raw dictionary without Pydantic validation.

**Parameters:**
- `symbol`: Stock symbol
- `lang`: Language for response ('en' or 'th')

**Returns:**
- Raw dictionary from API

**Example:**

```python
service = StockHighlightDataService()
raw_data = await service.fetch_highlight_data_raw("CPALL")
print(raw_data.keys())
```

### Convenience Functions

#### get_highlight_data()

```python
async def get_highlight_data(
    symbol: str,
    lang: str = "en",
    config: FetcherConfig | None = None,
    session_cookies: str | None = None
) -> StockHighlightData
```

Quick one-line access to stock highlight data.

**Parameters:**
- `symbol`: Stock symbol (e.g., "CPALL", "PTT")
- `lang`: Language for response ('en' or 'th', default: 'en')
- `config`: Optional fetcher configuration
- `session_cookies`: Optional browser session cookies

**Returns:**
- `StockHighlightData` with all metrics

**Example:**

```python
from settfex.services.set.stock import get_highlight_data

data = await get_highlight_data("CPALL")
print(f"{data.symbol}: P/E={data.pe_ratio}")
```

### Utility Functions

#### normalize_symbol()

```python
def normalize_symbol(symbol: str) -> str
```

Normalize stock symbol to uppercase.

**Example:**

```python
from settfex.services.set.stock import normalize_symbol

symbol = normalize_symbol("cpall")  # Returns "CPALL"
```

#### normalize_language()

```python
def normalize_language(lang: str) -> str
```

Normalize language code to 'en' or 'th'.

**Accepted values:**
- English: "en", "EN", "eng", "english"
- Thai: "th", "TH", "tha", "thai"

**Example:**

```python
from settfex.services.set.stock import normalize_language

lang = normalize_language("english")  # Returns "en"
lang = normalize_language("TH")       # Returns "th"
```

## Usage Examples

### Example 1: Basic Stock Analysis

```python
import asyncio
from settfex.services.set.stock import get_highlight_data

async def analyze_stock(symbol: str):
    """Analyze key metrics for a stock."""
    data = await get_highlight_data(symbol)

    print(f"\n{data.symbol} - Stock Analysis")
    print("=" * 50)
    print(f"Market Cap:      {data.market_cap:,.0f} THB")
    print(f"P/E Ratio:       {data.pe_ratio}")
    print(f"P/B Ratio:       {data.pb_ratio}")
    print(f"Dividend Yield:  {data.dividend_yield}%")
    print(f"Beta:            {data.beta}")
    print(f"YTD Change:      {data.ytd_percent_change:.2f}%")
    print(f"52-Week Range:   {data.year_low_price} - {data.year_high_price}")

asyncio.run(analyze_stock("CPALL"))
```

### Example 2: Compare Multiple Stocks

```python
import asyncio
from settfex.services.set.stock import StockHighlightDataService

async def compare_stocks(symbols: list[str]):
    """Compare P/E and P/B ratios across multiple stocks."""
    service = StockHighlightDataService()

    print(f"{'Symbol':<10} {'P/E':<10} {'P/B':<10} {'Div Yield':<12}")
    print("-" * 50)

    for symbol in symbols:
        data = await service.fetch_highlight_data(symbol)
        print(f"{data.symbol:<10} {data.pe_ratio:<10.2f} {data.pb_ratio:<10.2f} {data.dividend_yield:<12.2f}%")

asyncio.run(compare_stocks(["CPALL", "PTT", "KBANK", "AOT", "BBL"]))
```

### Example 3: Dividend Analysis

```python
async def dividend_analysis(symbol: str):
    """Analyze dividend metrics for a stock."""
    data = await get_highlight_data(symbol)

    print(f"\n{data.symbol} - Dividend Analysis")
    print("=" * 50)
    print(f"Dividend per Share:    {data.dividend} THB")
    print(f"Dividend Yield:        {data.dividend_yield}%")
    print(f"12M Dividend Yield:    {data.dividend_yield_12m}%")
    print(f"Ex-Dividend Date:      {data.xd_date}")
    print(f"Ex-Dividend Session:   {data.xd_session}")

asyncio.run(dividend_analysis("CPALL"))
```

### Example 4: NVDR Trading Data

```python
async def nvdr_analysis(symbol: str):
    """Analyze NVDR (Non-Voting Depositary Receipt) trading data."""
    data = await get_highlight_data(symbol)

    print(f"\n{data.symbol} - NVDR Analysis")
    print("=" * 50)
    print(f"NVDR Buy Volume:   {data.nvdr_buy_volume:,.0f}")
    print(f"NVDR Sell Volume:  {data.nvdr_sell_volume:,.0f}")
    print(f"NVDR Net Volume:   {data.nvdr_net_volume:,.0f}")
    print(f"NVDR Buy Value:    {data.nvdr_buy_value:,.0f} THB")
    print(f"NVDR Sell Value:   {data.nvdr_sell_value:,.0f} THB")
    print(f"NVDR Net Value:    {data.nvdr_net_value:,.0f} THB")

asyncio.run(nvdr_analysis("CPALL"))
```

### Example 5: Custom Configuration with Session Cookies

```python
from settfex.utils.data_fetcher import FetcherConfig

async def fetch_with_custom_config():
    """Fetch data with custom configuration and real session cookies."""

    # Custom fetcher config
    config = FetcherConfig(
        browser_impersonate="safari17_0",
        timeout=60,
        max_retries=5,
        retry_delay=2.0
    )

    # Real browser session cookies (recommended for production)
    cookies = "charlot=abc123; incap_ses_357_2046605=xyz789; ..."

    # Fetch data
    data = await get_highlight_data(
        "CPALL",
        lang="th",
        config=config,
        session_cookies=cookies
    )

    print(f"Symbol: {data.symbol}")
    print(f"Market Cap: {data.market_cap:,.0f} บาท")

asyncio.run(fetch_with_custom_config())
```

### Example 6: Error Handling

```python
async def safe_fetch(symbol: str):
    """Fetch data with proper error handling."""
    try:
        data = await get_highlight_data(symbol)
        return data
    except ValueError as e:
        print(f"Invalid input: {e}")
        return None
    except Exception as e:
        print(f"Failed to fetch data: {e}")
        return None

# Test with various inputs
asyncio.run(safe_fetch("CPALL"))     # Valid
asyncio.run(safe_fetch(""))          # ValueError: empty symbol
asyncio.run(safe_fetch("INVALID"))   # May fail if symbol doesn't exist
```

## Authentication and Cookies

The service supports two cookie modes:

### 1. Generated Cookies (Default)

By default, the service generates Incapsula-compatible cookies:

```python
service = StockHighlightDataService()
data = await service.fetch_highlight_data("CPALL")
```

**Note:** Generated cookies may be blocked by Incapsula bot protection.

### 2. Real Browser Session Cookies (Recommended)

For production use, provide real browser session cookies:

```python
# Extract cookies from authenticated browser session
cookies = "charlot=abc123; incap_ses_357_2046605=xyz789; nlbi_2046605=...; visid_incap_2046605=..."

service = StockHighlightDataService(session_cookies=cookies)
data = await service.fetch_highlight_data("CPALL")
```

**How to get browser session cookies:**
1. Open SET website in browser: https://www.set.or.th
2. Open Developer Tools (F12)
3. Go to Network tab
4. Refresh page
5. Click on any request to www.set.or.th
6. Copy the Cookie header value

## Error Handling

The service raises specific exceptions:

### ValueError

Raised when inputs are invalid:

```python
try:
    data = await get_highlight_data("")  # Empty symbol
except ValueError as e:
    print(f"Invalid input: {e}")

try:
    data = await get_highlight_data("CPALL", lang="invalid")  # Invalid language
except ValueError as e:
    print(f"Invalid language: {e}")
```

### Request Exceptions

Raised when API requests fail:

```python
try:
    data = await get_highlight_data("CPALL")
except Exception as e:
    print(f"Request failed: {e}")
```

## Logging

The service uses loguru for comprehensive logging:

```python
from loguru import logger
from settfex.utils.logging import setup_logger

# Configure logging
setup_logger(level="DEBUG", log_file="logs/highlight_data.log")

# Use service (logs will be captured)
data = await get_highlight_data("CPALL")
```

**Log Levels:**
- **DEBUG**: Request details, cookie generation, normalization
- **INFO**: Successful fetches, service initialization
- **WARNING**: Retry attempts
- **ERROR**: Failed requests, validation errors

## Performance

### Concurrent Requests

Fetch data for multiple stocks concurrently:

```python
import asyncio
from settfex.services.set.stock import get_highlight_data

async def fetch_multiple():
    symbols = ["CPALL", "PTT", "KBANK", "AOT", "BBL"]

    # Fetch all concurrently
    results = await asyncio.gather(
        *[get_highlight_data(symbol) for symbol in symbols],
        return_exceptions=True
    )

    for symbol, result in zip(symbols, results):
        if isinstance(result, Exception):
            print(f"{symbol}: Error - {result}")
        else:
            print(f"{symbol}: P/E={result.pe_ratio}")

asyncio.run(fetch_multiple())
```

### Connection Reuse

Use the service class for multiple requests:

```python
# Good: Reuse service instance
service = StockHighlightDataService()
for symbol in symbols:
    data = await service.fetch_highlight_data(symbol)

# Avoid: Creating new service for each request
for symbol in symbols:
    data = await get_highlight_data(symbol)  # Less efficient
```

## API Endpoint

The service fetches data from:

```
https://www.set.or.th/api/set/stock/{symbol}/highlight-data?lang={lang}
```

**Parameters:**
- `{symbol}`: Stock symbol (uppercase)
- `{lang}`: Language code ('en' or 'th')

**Example:**
```
https://www.set.or.th/api/set/stock/CPALL/highlight-data?lang=en
```

## See Also

- [Stock List Service](list.md) - Fetch complete list of SET stocks
- [AsyncDataFetcher](../../utils/data_fetcher.md) - Low-level async HTTP client
- [SET Client](client.md) - High-level SET API client
- [Constants](constants.md) - SET API constants and endpoints

## Notes

- All timestamps are in Bangkok timezone (UTC+7)
- Market cap and values are in Thai Baht (THB)
- Some fields may be `None` if data is not available
- NVDR = Non-Voting Depositary Receipt
- Symbol normalization is automatic (case-insensitive)
- Language normalization accepts multiple formats
