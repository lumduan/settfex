# Shareholder Service

## Overview

The Shareholder Service provides async methods to fetch shareholder data for individual stock symbols from the Stock Exchange of Thailand (SET). It retrieves information about major shareholders, free float statistics, and ownership distribution.

## Quick Start

```python
import asyncio
from settfex.services.set import get_shareholder_data

async def main():
    # Fetch shareholder data for a stock
    data = await get_shareholder_data("MINT")

    print(f"Total Shareholders: {data.total_shareholder:,}")
    print(f"Free Float: {data.free_float.percent_free_float:.2f}%")

    # Display top shareholders
    for sh in data.major_shareholders[:5]:
        print(f"{sh.sequence}. {sh.name}: {sh.percent_of_share:.2f}%")

asyncio.run(main())
```

## Features

- **Full Type Safety**: Complete Pydantic models for shareholder and free float data
- **Dual Language Support**: Fetch data in English ('en') or Thai ('th')
- **Input Normalization**: Automatic symbol uppercase and language validation
- **Async-First**: Built on AsyncDataFetcher for optimal performance
- **Automatic Session Management**: Uses SessionManager for bot detection bypass (25x faster after first request)
- **Thai/Unicode Support**: Proper handling of Thai shareholder names

## API Reference

### Convenience Function

#### `get_shareholder_data(symbol, lang='en', config=None)`

Quick one-line access to shareholder data.

**Parameters:**
- `symbol: str` - Stock symbol (e.g., "MINT", "PTT", "cpall")
- `lang: str` - Language for response ('en' or 'th', default: 'en')
- `config: FetcherConfig | None` - Optional fetcher configuration

**Returns:**
- `ShareholderData` - Shareholder data with major shareholders and free float info

**Example:**
```python
from settfex.services.set import get_shareholder_data

# English (default)
data = await get_shareholder_data("MINT")

# Thai language
data_th = await get_shareholder_data("MINT", lang="th")

# Custom configuration
from settfex.utils.data_fetcher import FetcherConfig

config = FetcherConfig(timeout=60, max_retries=5)
data = await get_shareholder_data("MINT", config=config)
```

### ShareholderService Class

Main service class for fetching shareholder data.

#### Constructor

```python
ShareholderService(config: FetcherConfig | None = None)
```

**Parameters:**
- `config: FetcherConfig | None` - Optional fetcher configuration (uses defaults if None)

**Example:**
```python
from settfex.services.set.stock import ShareholderService
from settfex.utils.data_fetcher import FetcherConfig

# Default configuration (uses SessionManager automatically)
service = ShareholderService()

# Custom configuration
config = FetcherConfig(timeout=60, max_retries=5)
service = ShareholderService(config=config)
```

#### Methods

##### `fetch_shareholder_data(symbol, lang='en')`

Fetch shareholder data for a specific stock symbol.

**Parameters:**
- `symbol: str` - Stock symbol (e.g., "MINT", "PTT", "cpall")
- `lang: str` - Language for response ('en' or 'th', default: 'en')

**Returns:**
- `ShareholderData` - Shareholder data object with validated data

**Raises:**
- `ValueError` - If symbol is empty or language is invalid
- `Exception` - If request fails or response cannot be parsed

**Example:**
```python
service = ShareholderService()

# Fetch shareholder data
data = await service.fetch_shareholder_data("MINT", lang="en")

print(f"Symbol: {data.symbol}")
print(f"Total Shareholders: {data.total_shareholder:,}")
print(f"Percent Scriptless: {data.percent_scriptless:.2f}%")

# Free float information
print(f"Free Float: {data.free_float.percent_free_float:.2f}%")
print(f"Free Float Holders: {data.free_float.number_of_holder:,}")

# Major shareholders
for sh in data.major_shareholders[:10]:
    nvdr_flag = " (NVDR)" if sh.is_thai_nvdr else ""
    print(f"{sh.sequence}. {sh.name}{nvdr_flag}")
    print(f"   Shares: {sh.number_of_share:,} ({sh.percent_of_share:.2f}%)")
```

##### `fetch_shareholder_data_raw(symbol, lang='en')`

Fetch shareholder data as raw dictionary without Pydantic validation.

Useful for debugging or when you need the raw API response.

**Parameters:**
- `symbol: str` - Stock symbol (e.g., "MINT", "PTT", "cpall")
- `lang: str` - Language for response ('en' or 'th', default: 'en')

**Returns:**
- `dict[str, Any]` - Raw dictionary from API

**Example:**
```python
service = ShareholderService()

raw_data = await service.fetch_shareholder_data_raw("MINT")
print(raw_data.keys())
# dict_keys(['symbol', 'bookCloseDate', 'caType', 'totalShareholder',
#            'percentScriptless', 'majorShareholders', 'freeFloat'])
```

### Stock Class Integration

The shareholder service is integrated into the unified `Stock` class for convenient access.

```python
from settfex.services.set import Stock

# Create Stock instance
stock = Stock("MINT")

# Fetch shareholder data
data = await stock.get_shareholder_data()

# Fetch in Thai
data_th = await stock.get_shareholder_data(lang="th")
```

## Data Models

### ShareholderData

Main model for complete shareholder information.

**Fields:**
- `symbol: str` - Stock symbol/ticker
- `book_close_date: datetime` - Book close date for shareholder data
- `ca_type: str` - Corporate action type
- `total_shareholder: int` - Total number of shareholders
- `percent_scriptless: float` - Percentage of scriptless shares
- `major_shareholders: list[MajorShareholder]` - List of major shareholders
- `free_float: FreeFloat` - Free float information

**Example:**
```python
data = await get_shareholder_data("MINT")

print(f"Symbol: {data.symbol}")
print(f"Total Shareholders: {data.total_shareholder:,}")
print(f"Book Close Date: {data.book_close_date}")
print(f"Number of Major Shareholders: {len(data.major_shareholders)}")
```

### MajorShareholder

Model for individual major shareholder information.

**Fields:**
- `sequence: int` - Shareholder ranking sequence number
- `name: str` - Shareholder name (company or individual)
- `nationality: str | None` - Shareholder nationality
- `number_of_share: int` - Number of shares held
- `percent_of_share: float` - Percentage of total shares held
- `is_thai_nvdr: bool` - Whether shareholder is Thai NVDR

**Example:**
```python
for sh in data.major_shareholders[:5]:
    print(f"Rank: {sh.sequence}")
    print(f"Name: {sh.name}")
    print(f"Shares: {sh.number_of_share:,}")
    print(f"Ownership: {sh.percent_of_share:.2f}%")
    if sh.is_thai_nvdr:
        print("Type: NVDR")
```

### FreeFloat

Model for free float information.

**Fields:**
- `book_close_date: datetime` - Book close date for free float data
- `ca_type: str` - Corporate action type
- `percent_free_float: float` - Percentage of free float shares
- `number_of_holder: int` - Number of free float holders

**Example:**
```python
ff = data.free_float

print(f"Free Float: {ff.percent_free_float:.2f}%")
print(f"Holders: {ff.number_of_holder:,}")
print(f"Book Close Date: {ff.book_close_date}")
```

## Usage Examples

### Basic Usage

```python
from settfex.services.set import get_shareholder_data

# Fetch shareholder data
data = await get_shareholder_data("MINT")

print(f"Stock: {data.symbol}")
print(f"Total Shareholders: {data.total_shareholder:,}")
print(f"Free Float: {data.free_float.percent_free_float:.2f}%")
```

### Analyzing Major Shareholders

```python
data = await get_shareholder_data("MINT")

# Total ownership by major shareholders
total_major_ownership = sum(sh.percent_of_share for sh in data.major_shareholders)
print(f"Major shareholders own: {total_major_ownership:.2f}%")

# Find NVDR shareholders
nvdr_shareholders = [sh for sh in data.major_shareholders if sh.is_thai_nvdr]
print(f"NVDR shareholders: {len(nvdr_shareholders)}")

# Top 5 shareholders
print("\nTop 5 Shareholders:")
for sh in data.major_shareholders[:5]:
    print(f"{sh.sequence}. {sh.name[:50]}")
    print(f"   {sh.number_of_share:,} shares ({sh.percent_of_share:.2f}%)")
```

### Thai Language Support

```python
# Fetch in Thai
data_th = await get_shareholder_data("MINT", lang="th")

print("Top Thai Shareholders:")
for sh in data_th.major_shareholders[:3]:
    print(f"{sh.sequence}. {sh.name}")
    print(f"   {sh.percent_of_share:.2f}%")
```

### Comparing Multiple Stocks

```python
from settfex.services.set import get_shareholder_data

symbols = ["PTT", "CPALL", "AOT", "KBANK", "MINT"]

for symbol in symbols:
    data = await get_shareholder_data(symbol)
    print(f"\n{symbol}:")
    print(f"  Total Shareholders: {data.total_shareholder:,}")
    print(f"  Free Float: {data.free_float.percent_free_float:.2f}%")
    print(f"  Top Shareholder: {data.major_shareholders[0].name[:40]}")
    print(f"    Ownership: {data.major_shareholders[0].percent_of_share:.2f}%")
```

### Using with Stock Class

```python
from settfex.services.set import Stock

# Create Stock instance
stock = Stock("MINT")

# Fetch multiple data types
highlight = await stock.get_highlight_data()
shareholder = await stock.get_shareholder_data()

print(f"\n{stock.symbol} Analysis:")
print(f"Market Cap: {highlight.market_cap:,.0f}")
print(f"Free Float: {shareholder.free_float.percent_free_float:.2f}%")
print(f"Total Shareholders: {shareholder.total_shareholder:,}")
```

### Error Handling

```python
from settfex.services.set import get_shareholder_data

try:
    # Fetch shareholder data
    data = await get_shareholder_data("MINT")
    print(f"Successfully fetched data for {data.symbol}")

except ValueError as e:
    # Handle invalid input
    print(f"Invalid input: {e}")

except Exception as e:
    # Handle API errors
    print(f"Failed to fetch data: {e}")
```

## Performance Notes

The shareholder service uses SessionManager for automatic cookie handling and bot detection bypass:

- **First request**: ~3-5 seconds (includes session warmup)
- **Subsequent requests**: ~100-200ms (25x faster with cached session)
- **Session cache TTL**: 1 hour (automatically refreshed)

No manual cookie management required - SessionManager handles everything automatically.

## Language Support

The service supports both English and Thai languages:

```python
# English (default)
data_en = await get_shareholder_data("MINT", lang="en")

# Thai
data_th = await get_shareholder_data("MINT", lang="th")

# Alternative Thai inputs (all normalized to 'th')
data = await get_shareholder_data("MINT", lang="thai")
data = await get_shareholder_data("MINT", lang="tha")
```

## Symbol Normalization

Stock symbols are automatically normalized to uppercase:

```python
# All of these work identically
data1 = await get_shareholder_data("MINT")
data2 = await get_shareholder_data("mint")
data3 = await get_shareholder_data("MiNt")
data4 = await get_shareholder_data("  mint  ")  # Whitespace trimmed

# All return the same data for "MINT"
```

## Related Services

- **[Stock Profile Service](profile_stock.md)**: Company and listing information
- **[Company Profile Service](profile_company.md)**: Detailed company information
- **[Highlight Data Service](highlight_data.md)**: Key financial metrics
- **[Corporate Action Service](corporate_action.md)**: Dividend and meeting information

## API Endpoint

```
GET https://www.set.or.th/api/set/stock/{symbol}/shareholder?lang={lang}
```

**Parameters:**
- `symbol`: Stock symbol (uppercase)
- `lang`: Language code ('en' or 'th')

**Response:** JSON object with shareholder data

## See Also

- [Stock List Service](list.md) - Complete list of all SET stocks
- [Data Fetcher Utilities](../../utils/data_fetcher.md) - HTTP client and configuration
- [Session Manager](../../utils/session_manager.md) - Automatic session and cookie management
