# Price Performance Service

## Overview

The Price Performance Service provides async methods to fetch comprehensive price performance data for individual stock symbols from the Stock Exchange of Thailand (SET). It retrieves percentage price changes across multiple time periods (5-day, 1-month, 3-month, 6-month, YTD) along with key valuation metrics (P/E, P/B, turnover ratio) for the stock, its sector, and the overall market.

## Quick Start

```python
import asyncio
from settfex.services.set import get_price_performance

async def main():
    # Fetch price performance for a stock
    data = await get_price_performance("MINT")

    # Display stock performance
    print(f"Stock: {data.stock.symbol}")
    print(f"  5-Day: {data.stock.five_day_percent_change:.2f}%")
    print(f"  1-Month: {data.stock.one_month_percent_change:.2f}%")
    print(f"  YTD: {data.stock.ytd_percent_change:.2f}%")
    print(f"  P/E: {data.stock.pe_ratio}")
    print(f"  P/B: {data.stock.pb_ratio}")

    # Compare with sector
    print(f"\nSector: {data.sector.symbol}")
    print(f"  YTD: {data.sector.ytd_percent_change:.2f}%")

    # Compare with market
    print(f"\nMarket: {data.market.symbol}")
    print(f"  YTD: {data.market.ytd_percent_change:.2f}%")

asyncio.run(main())
```

## Features

- **Full Type Safety**: Complete Pydantic models for stock, sector, and market performance
- **Dual Language Support**: Fetch data in English ('en') or Thai ('th')
- **Input Normalization**: Automatic symbol uppercase and language validation
- **Async-First**: Built on AsyncDataFetcher for optimal performance
- **Automatic Session Management**: Uses SessionManager for bot detection bypass (25x faster after first request)
- **Multi-Period Data**: Returns performance for 5-day, 1-month, 3-month, 6-month, and YTD periods
- **Comparative Analysis**: Includes stock, sector, and market metrics for easy comparison
- **Valuation Metrics**: P/E ratio, P/B ratio, and turnover ratio for each entity

## API Reference

### Convenience Function

#### `get_price_performance(symbol, lang='en', config=None)`

Quick one-line access to price performance data.

**Parameters:**
- `symbol: str` - Stock symbol (e.g., "MINT", "PTT", "cpall")
- `lang: str` - Language for response ('en' or 'th', default: 'en')
- `config: FetcherConfig | None` - Optional fetcher configuration

**Returns:**
- `PricePerformanceData` - Object containing stock, sector, and market metrics

**Example:**
```python
from settfex.services.set import get_price_performance

# English (default)
data = await get_price_performance("MINT")

# Thai language
data_th = await get_price_performance("MINT", lang="th")

# Custom configuration
from settfex.utils.data_fetcher import FetcherConfig

config = FetcherConfig(timeout=60, max_retries=5)
data = await get_price_performance("MINT", config=config)

# Access specific metrics
print(f"Stock YTD: {data.stock.ytd_percent_change:.2f}%")
print(f"Sector YTD: {data.sector.ytd_percent_change:.2f}%")
print(f"Market YTD: {data.market.ytd_percent_change:.2f}%")
```

### PricePerformanceService Class

Main service class for fetching price performance data.

#### Constructor

```python
PricePerformanceService(config: FetcherConfig | None = None)
```

**Parameters:**
- `config: FetcherConfig | None` - Optional fetcher configuration (uses defaults if None)

**Example:**
```python
from settfex.services.set.stock import PricePerformanceService
from settfex.utils.data_fetcher import FetcherConfig

# Default configuration (uses SessionManager automatically)
service = PricePerformanceService()

# Custom configuration
config = FetcherConfig(timeout=60, max_retries=5)
service = PricePerformanceService(config=config)
```

#### Methods

##### `fetch_price_performance(symbol, lang='en')`

Fetch price performance data for a specific stock symbol.

**Parameters:**
- `symbol: str` - Stock symbol (e.g., "MINT", "PTT", "cpall")
- `lang: str` - Language for response ('en' or 'th', default: 'en')

**Returns:**
- `PricePerformanceData` - Complete performance data with stock, sector, and market metrics

**Raises:**
- `ValueError` - If symbol is empty or language is invalid
- `Exception` - If request fails or response cannot be parsed

**Example:**
```python
service = PricePerformanceService()
data = await service.fetch_price_performance("MINT", lang="en")

print(f"Stock: {data.stock.symbol}")
print(f"5-Day Change: {data.stock.five_day_percent_change:.2f}%")
print(f"P/E Ratio: {data.stock.pe_ratio}")
```

##### `fetch_price_performance_raw(symbol, lang='en')`

Fetch price performance as raw dictionary without Pydantic validation.

**Parameters:**
- `symbol: str` - Stock symbol (e.g., "MINT", "PTT", "cpall")
- `lang: str` - Language for response ('en' or 'th', default: 'en')

**Returns:**
- `dict[str, Any]` - Raw dictionary from API

**Raises:**
- `ValueError` - If symbol is empty or language is invalid
- `Exception` - If request fails

**Example:**
```python
service = PricePerformanceService()
raw_data = await service.fetch_price_performance_raw("MINT")
print(f"Keys: {raw_data.keys()}")
print(f"Stock data: {raw_data['stock']}")
```

### Data Models

#### PricePerformanceData

Complete price performance data model.

**Fields:**
- `stock: PricePerformanceMetrics` - Stock-specific performance metrics
- `sector: PricePerformanceMetrics` - Sector performance metrics for comparison
- `market: PricePerformanceMetrics` - Overall market (SET) performance metrics for comparison

**Example:**
```python
data = await get_price_performance("MINT")

# Access stock metrics
print(f"Stock: {data.stock.symbol}")
print(f"Stock YTD: {data.stock.ytd_percent_change:.2f}%")

# Access sector metrics
print(f"Sector: {data.sector.symbol}")
print(f"Sector YTD: {data.sector.ytd_percent_change:.2f}%")

# Access market metrics
print(f"Market: {data.market.symbol}")
print(f"Market YTD: {data.market.ytd_percent_change:.2f}%")
```

#### PricePerformanceMetrics

Performance metrics for stock, sector, or market.

**Fields:**
- `symbol: str` - Symbol identifier (stock symbol, sector code, or market code)
- `five_day_percent_change: float | None` - 5-day percentage price change
- `one_month_percent_change: float | None` - 1-month percentage price change
- `three_month_percent_change: float | None` - 3-month percentage price change
- `six_month_percent_change: float | None` - 6-month percentage price change
- `ytd_percent_change: float | None` - Year-to-date percentage price change
- `pe_ratio: float | None` - Price-to-Earnings ratio
- `pb_ratio: float | None` - Price-to-Book ratio
- `turnover_ratio: float | None` - Turnover ratio (trading volume / shares outstanding)

**Example:**
```python
data = await get_price_performance("MINT")

# Stock metrics
stock = data.stock
print(f"Symbol: {stock.symbol}")
print(f"5-Day: {stock.five_day_percent_change:.2f}%")
print(f"1-Month: {stock.one_month_percent_change:.2f}%")
print(f"3-Month: {stock.three_month_percent_change:.2f}%")
print(f"6-Month: {stock.six_month_percent_change:.2f}%")
print(f"YTD: {stock.ytd_percent_change:.2f}%")
print(f"P/E: {stock.pe_ratio}")
print(f"P/B: {stock.pb_ratio}")
print(f"Turnover: {stock.turnover_ratio:.2f}")
```

## Usage Examples

### Example 1: Basic Price Performance Fetch

```python
import asyncio
from settfex.services.set import get_price_performance

async def main():
    # Fetch price performance
    data = await get_price_performance("PTT")

    print(f"Stock: {data.stock.symbol}")
    print(f"YTD Change: {data.stock.ytd_percent_change:.2f}%")
    print(f"P/E Ratio: {data.stock.pe_ratio}")

asyncio.run(main())
```

### Example 2: Compare Stock, Sector, and Market Performance

```python
import asyncio
from settfex.services.set import get_price_performance

async def compare_performance(symbol: str):
    """Compare stock performance with sector and market."""
    data = await get_price_performance(symbol)

    print(f"YTD Performance Comparison for {symbol}:")
    print(f"  Stock ({data.stock.symbol}): {data.stock.ytd_percent_change:.2f}%")
    print(f"  Sector ({data.sector.symbol}): {data.sector.ytd_percent_change:.2f}%")
    print(f"  Market ({data.market.symbol}): {data.market.ytd_percent_change:.2f}%")

    # Calculate relative performance
    stock_vs_sector = data.stock.ytd_percent_change - data.sector.ytd_percent_change
    stock_vs_market = data.stock.ytd_percent_change - data.market.ytd_percent_change

    print(f"\nRelative Performance:")
    print(f"  vs Sector: {stock_vs_sector:+.2f}%")
    print(f"  vs Market: {stock_vs_market:+.2f}%")

asyncio.run(compare_performance("MINT"))
```

### Example 3: Multi-Period Analysis

```python
import asyncio
from settfex.services.set import get_price_performance

async def analyze_periods(symbol: str):
    """Analyze performance across all time periods."""
    data = await get_price_performance(symbol)

    stock = data.stock
    print(f"Performance Analysis for {stock.symbol}:")
    print(f"  5-Day:   {stock.five_day_percent_change:+7.2f}%")
    print(f"  1-Month: {stock.one_month_percent_change:+7.2f}%")
    print(f"  3-Month: {stock.three_month_percent_change:+7.2f}%")
    print(f"  6-Month: {stock.six_month_percent_change:+7.2f}%")
    print(f"  YTD:     {stock.ytd_percent_change:+7.2f}%")

    print(f"\nValuation Metrics:")
    print(f"  P/E Ratio: {stock.pe_ratio}")
    print(f"  P/B Ratio: {stock.pb_ratio}")
    print(f"  Turnover: {stock.turnover_ratio:.2f}")

asyncio.run(analyze_periods("CPALL"))
```

### Example 4: Multiple Stocks Concurrent Fetch

```python
import asyncio
from settfex.services.set import get_price_performance

async def fetch_multiple_stocks(symbols: list[str]):
    """Fetch price performance for multiple stocks concurrently."""
    tasks = [get_price_performance(symbol) for symbol in symbols]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for symbol, result in zip(symbols, results):
        if isinstance(result, Exception):
            print(f"{symbol}: Error - {result}")
        else:
            print(f"{symbol}: YTD {result.stock.ytd_percent_change:+.2f}%, "
                  f"P/E {result.stock.pe_ratio}")

symbols = ["PTT", "CPALL", "AOT", "KBANK", "BBL"]
asyncio.run(fetch_multiple_stocks(symbols))
```

### Example 5: Thai Language Support

```python
import asyncio
from settfex.services.set import get_price_performance

async def fetch_thai_data(symbol: str):
    """Fetch price performance with Thai language."""
    # English
    data_en = await get_price_performance(symbol, lang="en")

    # Thai
    data_th = await get_price_performance(symbol, lang="th")

    print(f"English: {data_en.stock.symbol}")
    print(f"Thai: {data_th.stock.symbol}")

asyncio.run(fetch_thai_data("MINT"))
```

### Example 6: Using Service Class

```python
import asyncio
from settfex.services.set.stock import PricePerformanceService
from settfex.utils.data_fetcher import FetcherConfig

async def main():
    # Create service with custom configuration
    config = FetcherConfig(timeout=60, max_retries=5)
    service = PricePerformanceService(config=config)

    # Fetch data
    data = await service.fetch_price_performance("PTT", lang="en")

    print(f"Stock: {data.stock.symbol}")
    print(f"YTD: {data.stock.ytd_percent_change:.2f}%")

asyncio.run(main())
```

### Example 7: Error Handling

```python
import asyncio
from settfex.services.set import get_price_performance

async def safe_fetch(symbol: str):
    """Fetch with error handling."""
    try:
        data = await get_price_performance(symbol)
        print(f"{symbol}: YTD {data.stock.ytd_percent_change:.2f}%")
    except ValueError as e:
        print(f"Validation error: {e}")
    except Exception as e:
        print(f"Failed to fetch {symbol}: {e}")

asyncio.run(safe_fetch("INVALID"))
```

### Example 8: Raw Data Access

```python
import asyncio
from settfex.services.set.stock import PricePerformanceService

async def fetch_raw_data(symbol: str):
    """Fetch raw data for debugging."""
    service = PricePerformanceService()

    # Get raw dictionary
    raw_data = await service.fetch_price_performance_raw(symbol)

    print("Raw response keys:", raw_data.keys())
    print("Stock data:", raw_data['stock'])
    print("Sector data:", raw_data['sector'])
    print("Market data:", raw_data['market'])

asyncio.run(fetch_raw_data("MINT"))
```

## Data Fields Reference

### Stock/Sector/Market Metrics

All three entities (stock, sector, market) share the same metric structure:

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | `str` | Symbol identifier (stock symbol, sector code, or "SET" for market) |
| `five_day_percent_change` | `float \| None` | Percentage price change over 5 days |
| `one_month_percent_change` | `float \| None` | Percentage price change over 1 month |
| `three_month_percent_change` | `float \| None` | Percentage price change over 3 months |
| `six_month_percent_change` | `float \| None` | Percentage price change over 6 months |
| `ytd_percent_change` | `float \| None` | Year-to-date percentage price change |
| `pe_ratio` | `float \| None` | Price-to-Earnings ratio |
| `pb_ratio` | `float \| None` | Price-to-Book ratio |
| `turnover_ratio` | `float \| None` | Turnover ratio (trading volume / outstanding shares) |

**Sample Data:**
```json
{
  "stock": {
    "symbol": "MINT",
    "fiveDayPercentChange": -1.71,
    "oneMonthPercentChange": -3.36,
    "threeMonthPercentChange": -5.35,
    "sixMonthPercentChange": -14.02,
    "ytdPercentChange": -11.54,
    "peRatio": 17.91,
    "pbRatio": 1.49,
    "turnoverRatio": 0.15
  },
  "sector": {
    "symbol": "TOURISM",
    "fiveDayPercentChange": 1.70,
    "oneMonthPercentChange": -3.74,
    "threeMonthPercentChange": -7.59,
    "sixMonthPercentChange": -7.10,
    "ytdPercentChange": 2.82,
    "peRatio": 22.42,
    "pbRatio": 1.33,
    "turnoverRatio": 0.30
  },
  "market": {
    "symbol": "SET",
    "fiveDayPercentChange": -2.84,
    "oneMonthPercentChange": -5.92,
    "threeMonthPercentChange": -17.52,
    "sixMonthPercentChange": -22.78,
    "ytdPercentChange": -4.25,
    "peRatio": 16.93,
    "pbRatio": 1.23,
    "turnoverRatio": 0.42
  }
}
```

## Performance Considerations

### Session Management

The service uses SessionManager for automatic cookie handling:

- **First Request**: ~2-3 seconds (includes session warmup)
- **Subsequent Requests**: ~100ms (uses cached session) - **25x faster!**
- **Auto-Retry**: Automatically re-warms on HTTP 403/452

### Best Practices

1. **Use Context Manager**: Always use `async with` for proper resource cleanup
2. **Batch Requests**: Use `asyncio.gather()` for multiple stocks
3. **Configure Retries**: Adjust `max_retries` based on network reliability
4. **Handle Exceptions**: Always wrap calls in try/except blocks
5. **Cache Results**: Consider caching if fetching same symbols repeatedly

## Error Handling

### Common Errors

**ValueError**: Empty symbol or invalid language
```python
try:
    data = await get_price_performance("")  # Empty symbol
except ValueError as e:
    print(f"Validation error: {e}")
```

**Exception**: Network error or API failure
```python
try:
    data = await get_price_performance("INVALID")
except Exception as e:
    print(f"Request failed: {e}")
```

### Debug Mode

Use `fetch_price_performance_raw()` for debugging:

```python
service = PricePerformanceService()
raw_data = await service.fetch_price_performance_raw("MINT")
print("Raw response:", raw_data)
```

## Logging

The service uses loguru for logging. Enable debug logging:

```python
from loguru import logger
from settfex.utils.logging import setup_logger

# Enable debug logging
setup_logger(level="DEBUG", log_file="logs/price_performance.log")

# Fetch with detailed logs
data = await get_price_performance("MINT")
```

## See Also

- [Trading Statistics Service](trading_stat.md) - Multi-period trading statistics
- [Stock Highlight Data Service](highlight_data.md) - Key stock metrics
- [Stock Profile Service](profile_stock.md) - Detailed stock information
- [AsyncDataFetcher](../../utils/data_fetcher.md) - HTTP client documentation
