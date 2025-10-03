# NVDR Holder Service

The NVDR Holder Service provides async methods to fetch Non-Voting Depository Receipt (NVDR) holder data for individual stock symbols from the Stock Exchange of Thailand (SET) API.

## Overview

NVDR (Non-Voting Depository Receipt) shares are depository receipts that carry the same rights as ordinary shares except for voting rights in shareholder meetings. This service allows you to:

- Fetch major NVDR holder information for any stock symbol
- Get ownership statistics including total holders and scriptless percentage
- Support both English and Thai language responses
- Access both structured (Pydantic models) and raw (dictionary) data formats

## Installation

The NVDR Holder Service is part of the `settfex` package:

```bash
pip install settfex
# or
uv add settfex
```

## Quick Start

### Using the Convenience Function

The simplest way to fetch NVDR holder data:

```python
import asyncio
from settfex.services.set import get_nvdr_holder_data

async def main():
    # Fetch NVDR holder data for MINT
    data = await get_nvdr_holder_data("MINT")

    print(f"Symbol: {data.symbol}")
    print(f"Total NVDR Holders: {data.total_shareholder:,}")
    print(f"Book Close Date: {data.book_close_date.strftime('%Y-%m-%d')}")

    # Display top 5 NVDR holders
    for holder in data.major_shareholders[:5]:
        print(f"{holder.sequence}. {holder.name}: {holder.percent_of_share:.2f}%")

asyncio.run(main())
```

### Using the Service Class

For more control and custom configuration:

```python
import asyncio
from settfex.services.set.stock import NVDRHolderService
from settfex.utils.data_fetcher import FetcherConfig

async def main():
    # Create service with custom configuration
    config = FetcherConfig(timeout=60, max_retries=3)
    service = NVDRHolderService(config=config)

    # Fetch data
    data = await service.fetch_nvdr_holder_data("CPN", lang="en")

    print(f"Symbol: {data.symbol}")
    print(f"Total NVDR Holders: {data.total_shareholder:,}")
    print(f"Major NVDR Holders: {len(data.major_shareholders)}")

asyncio.run(main())
```

## API Reference

### Models

#### `NVDRHolder`

Individual NVDR holder information.

**Fields:**
- `sequence` (int): Holder ranking sequence number
- `name` (str): Holder name (company or individual)
- `nationality` (str | None): Holder nationality
- `number_of_share` (int): Number of NVDR shares held
- `percent_of_share` (float): Percentage of total NVDR shares held
- `is_thai_nvdr` (bool): Whether holder is Thai NVDR

#### `NVDRHolderData`

Complete NVDR holder data response.

**Fields:**
- `symbol` (str): Stock symbol/ticker (may include -R suffix for NVDR)
- `book_close_date` (datetime): Book close date for NVDR holder data
- `ca_type` (str): Corporate action type (e.g., "XD", "XM")
- `total_shareholder` (int): Total number of NVDR holders
- `percent_scriptless` (float): Percentage of scriptless NVDR shares
- `major_shareholders` (list[NVDRHolder]): List of major NVDR holders
- `free_float` (Any | None): Free float information (typically null for NVDR)

### Service Class

#### `NVDRHolderService`

Main service class for fetching NVDR holder data.

**Constructor:**
```python
NVDRHolderService(config: FetcherConfig | None = None)
```

**Parameters:**
- `config` (FetcherConfig, optional): Custom fetcher configuration. Uses defaults if None.

**Methods:**

##### `fetch_nvdr_holder_data(symbol: str, lang: str = "en") -> NVDRHolderData`

Fetch NVDR holder data for a specific stock symbol.

**Parameters:**
- `symbol` (str): Stock symbol (e.g., "MINT", "PTT", "cpall")
- `lang` (str, optional): Language for response ('en' or 'th', default: 'en')

**Returns:**
- `NVDRHolderData`: Validated Pydantic model with NVDR holder information

**Raises:**
- `ValueError`: If symbol is empty or language is invalid
- `Exception`: If request fails or response cannot be parsed

**Example:**
```python
service = NVDRHolderService()
data = await service.fetch_nvdr_holder_data("MINT", lang="en")
```

##### `fetch_nvdr_holder_data_raw(symbol: str, lang: str = "en") -> dict[str, Any]`

Fetch NVDR holder data as raw dictionary without Pydantic validation.

Useful for debugging or when you need the raw API response.

**Parameters:**
- `symbol` (str): Stock symbol (e.g., "MINT", "PTT", "cpall")
- `lang` (str, optional): Language for response ('en' or 'th', default: 'en')

**Returns:**
- `dict[str, Any]`: Raw dictionary from API

**Raises:**
- `ValueError`: If symbol is empty or language is invalid
- `Exception`: If request fails

**Example:**
```python
service = NVDRHolderService()
raw_data = await service.fetch_nvdr_holder_data_raw("MINT")
print(raw_data.keys())
```

### Convenience Function

#### `get_nvdr_holder_data(symbol: str, lang: str = "en", config: FetcherConfig | None = None) -> NVDRHolderData`

Quick one-line access to NVDR holder data.

**Parameters:**
- `symbol` (str): Stock symbol (e.g., "MINT", "PTT", "cpall")
- `lang` (str, optional): Language for response ('en' or 'th', default: 'en')
- `config` (FetcherConfig, optional): Custom fetcher configuration

**Returns:**
- `NVDRHolderData`: Validated Pydantic model with NVDR holder information

**Example:**
```python
from settfex.services.set import get_nvdr_holder_data

data = await get_nvdr_holder_data("MINT")
print(f"{data.symbol}: {len(data.major_shareholders)} major NVDR holders")
```

## Usage Examples

### Basic Usage

```python
import asyncio
from settfex.services.set import get_nvdr_holder_data

async def main():
    # Fetch NVDR holder data
    data = await get_nvdr_holder_data("MINT")

    print(f"Symbol: {data.symbol}")  # MINT-R (includes -R suffix)
    print(f"Total NVDR Holders: {data.total_shareholder:,}")
    print(f"Percent Scriptless: {data.percent_scriptless}%")
    print(f"Book Close Date: {data.book_close_date.strftime('%Y-%m-%d')}")
    print(f"Corporate Action: {data.ca_type}")

asyncio.run(main())
```

### Displaying NVDR Holder Details

```python
import asyncio
from settfex.services.set import get_nvdr_holder_data

async def main():
    data = await get_nvdr_holder_data("CPN")

    print(f"\nNVDR Holders for {data.symbol}")
    print(f"Book Close Date: {data.book_close_date.strftime('%Y-%m-%d')}")
    print(f"Total Holders: {data.total_shareholder:,}\n")

    print("Major NVDR Holders:")
    print("-" * 80)
    for holder in data.major_shareholders:
        nationality = f" ({holder.nationality})" if holder.nationality else ""
        thai_nvdr = " [Thai NVDR]" if holder.is_thai_nvdr else ""
        print(
            f"{holder.sequence}. {holder.name}{nationality}{thai_nvdr}\n"
            f"   Shares: {holder.number_of_share:,} ({holder.percent_of_share:.2f}%)"
        )

asyncio.run(main())
```

### Thai Language Support

```python
import asyncio
from settfex.services.set import get_nvdr_holder_data

async def main():
    # Fetch data in Thai
    data_th = await get_nvdr_holder_data("PTT", lang="th")

    print(f"Symbol: {data_th.symbol}")
    print(f"Total Holders: {data_th.total_shareholder:,}")

    # Language normalization also works
    data_en = await get_nvdr_holder_data("PTT", lang="english")
    data_thai = await get_nvdr_holder_data("PTT", lang="thai")

asyncio.run(main())
```

### Raw Data Access

```python
import asyncio
from settfex.services.set.stock import NVDRHolderService

async def main():
    service = NVDRHolderService()

    # Get raw dictionary data
    raw_data = await service.fetch_nvdr_holder_data_raw("MINT")

    print("Raw API Response Keys:")
    print(raw_data.keys())

    print(f"\nSymbol: {raw_data['symbol']}")
    print(f"Total Shareholders: {raw_data['totalShareholder']:,}")
    print(f"Major Shareholders: {len(raw_data['majorShareholders'])}")

asyncio.run(main())
```

### Custom Configuration

```python
import asyncio
from settfex.services.set.stock import NVDRHolderService
from settfex.utils.data_fetcher import FetcherConfig

async def main():
    # Custom timeout and retry settings
    config = FetcherConfig(
        timeout=60,
        max_retries=5,
        rate_limit=1.0  # 1 second between requests
    )

    service = NVDRHolderService(config=config)
    data = await service.fetch_nvdr_holder_data("CPN")

    print(f"Fetched data for {data.symbol}")

asyncio.run(main())
```

### Analyzing NVDR Ownership

```python
import asyncio
from settfex.services.set import get_nvdr_holder_data

async def analyze_nvdr_ownership(symbol: str):
    """Analyze NVDR ownership concentration."""
    data = await get_nvdr_holder_data(symbol)

    # Calculate top 10 ownership concentration
    top_10_ownership = sum(h.percent_of_share for h in data.major_shareholders[:10])

    # Count Thai NVDR holders
    thai_nvdr_count = sum(1 for h in data.major_shareholders if h.is_thai_nvdr)

    print(f"\nNVDR Ownership Analysis for {data.symbol}")
    print(f"{'=' * 60}")
    print(f"Total NVDR Holders: {data.total_shareholder:,}")
    print(f"Top 10 Ownership: {top_10_ownership:.2f}%")
    print(f"Thai NVDR Holders in Top 10: {thai_nvdr_count}")
    print(f"Book Close Date: {data.book_close_date.strftime('%Y-%m-%d')}")
    print(f"Corporate Action: {data.ca_type}")

async def main():
    symbols = ["MINT", "CPN", "PTT"]
    for symbol in symbols:
        await analyze_nvdr_ownership(symbol)

asyncio.run(main())
```

## Features

### Automatic Input Normalization

The service automatically normalizes inputs:

- **Symbol**: Converted to uppercase (e.g., "mint" → "MINT")
- **Language**: Supports multiple formats:
  - `"en"`, `"EN"`, `"english"` → `"en"`
  - `"th"`, `"TH"`, `"thai"`, `"tha"` → `"th"`

### Session Management

The service uses `AsyncDataFetcher` with automatic session management:

- **Automatic Cookie Handling**: SessionManager handles bot detection bypass
- **Session Caching**: 25x speedup after first request
- **Auto-Retry**: Handles bot detection and re-warming automatically

### Error Handling

The service provides clear error handling:

```python
try:
    data = await get_nvdr_holder_data("INVALID")
except ValueError as e:
    print(f"Validation error: {e}")
except Exception as e:
    print(f"Request failed: {e}")
```

### Type Safety

All data is validated using Pydantic models:

- Full type hints throughout
- Runtime validation of API responses
- IDE autocomplete support

## Notes

### NVDR Symbol Convention

- The API returns NVDR symbols with a `-R` suffix (e.g., "MINT-R")
- Input symbols are normalized (uppercase) before the request
- The response `symbol` field will include the `-R` suffix

### Free Float Field

The `free_float` field is typically `null` for NVDR holder data, as free float statistics are available in the regular shareholder service.

### Corporate Action Types

Common `ca_type` values:
- `XD`: Ex-dividend date
- `XM`: Ex-meeting date
- Other corporate action types as defined by SET

### Book Close Date

The `book_close_date` represents the date when the shareholder register was closed for the corporate action.

## Related Services

- **[Shareholder Service](./shareholder.md)**: Fetch regular shareholder data (non-NVDR)
- **[Stock Profile Service](./profile_stock.md)**: Get stock profile and listing information
- **[Corporate Action Service](./corporate_action.md)**: Track corporate actions and events

## API Endpoint

The service fetches data from:
```
https://www.set.or.th/api/set/stock/{symbol}/nvdr-holder?lang={lang}
```

## Further Reading

- [AsyncDataFetcher Documentation](../../utils/data_fetcher.md)
- [SET API Documentation](https://www.set.or.th)
- [NVDR Information (SET)](https://www.set.or.th/en/products/nvdr/overview)
