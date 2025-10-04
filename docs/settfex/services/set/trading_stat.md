# Trading Statistics Service

## Overview

The Trading Statistics Service provides async methods to fetch comprehensive trading statistics for individual stock symbols from the Stock Exchange of Thailand (SET). It retrieves historical trading data including price movements, volume, valuation metrics, and financial ratios across multiple time periods (YTD, 1M, 3M, 6M, 1Y).

## Quick Start

```python
import asyncio
from settfex.services.set import get_trading_stats

async def main():
    # Fetch trading statistics for a stock
    stats = await get_trading_stats("MINT")

    # Display statistics for each period
    for stat in stats:
        print(f"\n{stat.period} Performance:")
        print(f"  Close: {stat.close:.2f} THB")
        print(f"  Change: {stat.percent_change:.2f}%")
        print(f"  Volume: {stat.total_volume:,.0f}")
        print(f"  P/E: {stat.pe}, P/B: {stat.pbv}")
        print(f"  Market Cap: {stat.market_cap:,.0f} THB")

asyncio.run(main())
```

## Features

- **Full Type Safety**: Complete Pydantic model with 30+ trading statistics fields
- **Dual Language Support**: Fetch data in English ('en') or Thai ('th')
- **Input Normalization**: Automatic symbol uppercase and language validation
- **Async-First**: Built on AsyncDataFetcher for optimal performance
- **Automatic Session Management**: Uses SessionManager for bot detection bypass (25x faster after first request)
- **Multi-Period Data**: Returns statistics for YTD, 1M, 3M, 6M, and 1Y periods
- **Comprehensive Metrics**: Price, volume, valuation ratios, financial data, and volatility measures

## API Reference

### Convenience Function

#### `get_trading_stats(symbol, lang='en', config=None)`

Quick one-line access to trading statistics.

**Parameters:**
- `symbol: str` - Stock symbol (e.g., "MINT", "PTT", "cpall")
- `lang: str` - Language for response ('en' or 'th', default: 'en')
- `config: FetcherConfig | None` - Optional fetcher configuration

**Returns:**
- `list[TradingStat]` - List of trading statistics for different time periods

**Example:**
```python
from settfex.services.set import get_trading_stats

# English (default)
stats = await get_trading_stats("MINT")

# Thai language
stats_th = await get_trading_stats("MINT", lang="th")

# Custom configuration
from settfex.utils.data_fetcher import FetcherConfig

config = FetcherConfig(timeout=60, max_retries=5)
stats = await get_trading_stats("MINT", config=config)

# Get specific period
ytd_stat = next(s for s in stats if s.period == "YTD")
print(f"YTD Performance: {ytd_stat.percent_change:.2f}%")
```

### TradingStatService Class

Main service class for fetching trading statistics.

#### Constructor

```python
TradingStatService(config: FetcherConfig | None = None)
```

**Parameters:**
- `config: FetcherConfig | None` - Optional fetcher configuration (uses defaults if None)

**Example:**
```python
from settfex.services.set.stock import TradingStatService
from settfex.utils.data_fetcher import FetcherConfig

# Default configuration (uses SessionManager automatically)
service = TradingStatService()

# Custom configuration
config = FetcherConfig(timeout=60, max_retries=5)
service = TradingStatService(config=config)
```

#### Methods

##### `fetch_trading_stats(symbol, lang='en')`

Fetch trading statistics for a specific stock symbol.

**Parameters:**
- `symbol: str` - Stock symbol (e.g., "MINT", "PTT", "cpall")
- `lang: str` - Language for response ('en' or 'th', default: 'en')

**Returns:**
- `list[TradingStat]` - List of trading statistics records

**Raises:**
- `ValueError` - If symbol is empty or language is invalid
- `Exception` - If request fails or response cannot be parsed

**Example:**
```python
service = TradingStatService()
stats = await service.fetch_trading_stats("MINT", lang="en")

for stat in stats:
    print(f"{stat.period}: {stat.close} ({stat.percent_change:.2f}%)")
```

##### `fetch_trading_stats_raw(symbol, lang='en')`

Fetch trading statistics as raw list of dictionaries without Pydantic validation.

**Parameters:**
- `symbol: str` - Stock symbol (e.g., "MINT", "PTT", "cpall")
- `lang: str` - Language for response ('en' or 'th', default: 'en')

**Returns:**
- `list[dict[str, Any]]` - Raw list of dictionaries from API

**Raises:**
- `ValueError` - If symbol is empty or language is invalid
- `Exception` - If request fails

**Example:**
```python
service = TradingStatService()
raw_stats = await service.fetch_trading_stats_raw("MINT")
print(f"Found {len(raw_stats)} periods")
print(raw_stats[0].keys())
```

### TradingStat Model

Pydantic model representing individual trading statistics record.

#### Fields

**Period & Identification:**
- `date: datetime` - Trading statistics date
- `period: str` - Trading period (e.g., 'YTD', '1M', '3M', '6M', '1Y')
- `symbol: str` - Stock symbol/ticker
- `market: str` - Market (e.g., 'SET', 'mai')
- `industry: str` - Industry classification
- `sector: str` - Sector classification

**Price Data:**
- `prior: float | None` - Prior closing price
- `open: float | None` - Opening price for the period
- `high: float | None` - Highest price during the period
- `low: float | None` - Lowest price during the period
- `average: float | None` - Average price during the period
- `close: float | None` - Closing price for the period
- `change: float | None` - Price change (absolute)
- `percent_change: float | None` - Percentage price change

**Volume & Value:**
- `total_volume: float | None` - Total trading volume (shares)
- `total_value: float | None` - Total trading value (THB)
- `average_value: float | None` - Average trading value per day (THB)
- `turnover_ratio: float | None` - Turnover ratio (%)

**Valuation Metrics:**
- `pe: float | None` - Price-to-Earnings ratio
- `pbv: float | None` - Price-to-Book Value ratio
- `market_cap: float | None` - Market capitalization (THB)
- `book_value_per_share: float | None` - Book value per share (THB)

**Share Data:**
- `listed_share: float | None` - Number of listed shares
- `par: float | None` - Par value per share (THB)

**Financial Metrics:**
- `dividend_yield: float | None` - Dividend yield (%)
- `dividend_payout_ratio: float | None` - Dividend payout ratio
- `financial_date: datetime | None` - Financial data reference date

**Risk Metrics:**
- `beta: float | None` - Beta coefficient (volatility measure)

## Data Structure

The service returns a list of `TradingStat` objects, typically one for each time period:

```python
[
    TradingStat(period="YTD", close=23.0, percent_change=-11.54, ...),
    TradingStat(period="1M", close=23.0, percent_change=-8.0, ...),
    TradingStat(period="3M", close=23.0, percent_change=-15.0, ...),
    TradingStat(period="6M", close=23.0, percent_change=-19.3, ...),
    TradingStat(period="1Y", close=23.0, percent_change=-11.54, ...)
]
```

## Usage Examples

### Example 1: Basic Trading Statistics

```python
import asyncio
from settfex.services.set import get_trading_stats

async def show_trading_stats(symbol: str):
    """Display trading statistics for a stock."""
    stats = await get_trading_stats(symbol)

    print(f"\n📊 Trading Statistics for {symbol}")
    print("=" * 60)

    for stat in stats:
        print(f"\n{stat.period} Period:")
        print(f"  Price: {stat.close:.2f} THB ({stat.percent_change:+.2f}%)")
        print(f"  Range: {stat.low:.2f} - {stat.high:.2f}")
        print(f"  Volume: {stat.total_volume:,.0f} shares")
        print(f"  Value: {stat.total_value:,.0f} THB")

asyncio.run(show_trading_stats("MINT"))
```

### Example 2: YTD Performance Analysis

```python
import asyncio
from settfex.services.set import get_trading_stats

async def analyze_ytd_performance(symbol: str):
    """Analyze year-to-date performance."""
    stats = await get_trading_stats(symbol)

    # Get YTD statistics
    ytd = next(s for s in stats if s.period == "YTD")

    print(f"\n📈 {symbol} - YTD Performance")
    print(f"Current Price: {ytd.close:.2f} THB")
    print(f"YTD Change: {ytd.percent_change:+.2f}%")
    print(f"52-Week High: {ytd.high:.2f}")
    print(f"52-Week Low: {ytd.low:.2f}")
    print(f"\nValuation:")
    print(f"  P/E Ratio: {ytd.pe:.2f}")
    print(f"  P/B Ratio: {ytd.pbv:.2f}")
    print(f"  Market Cap: {ytd.market_cap:,.0f} THB")
    print(f"  Dividend Yield: {ytd.dividend_yield:.2f}%")
    print(f"\nRisk:")
    print(f"  Beta: {ytd.beta:.2f}")

asyncio.run(analyze_ytd_performance("MINT"))
```

### Example 3: Compare Multiple Periods

```python
import asyncio
from settfex.services.set import get_trading_stats

async def compare_periods(symbol: str):
    """Compare performance across different periods."""
    stats = await get_trading_stats(symbol)

    print(f"\n📊 {symbol} - Performance Comparison")
    print(f"{'Period':<8} {'Close':>10} {'Change %':>10} {'Volume':>15}")
    print("-" * 48)

    for stat in stats:
        print(
            f"{stat.period:<8} "
            f"{stat.close:>10.2f} "
            f"{stat.percent_change:>10.2f} "
            f"{stat.total_volume:>15,.0f}"
        )

asyncio.run(compare_periods("MINT"))
```

### Example 4: Thai Language Support

```python
import asyncio
from settfex.services.set import get_trading_stats

async def fetch_thai_data(symbol: str):
    """Fetch trading statistics in Thai language."""
    stats_th = await get_trading_stats(symbol, lang="th")

    for stat in stats_th:
        print(f"\nช่วงเวลา: {stat.period}")
        print(f"ตลาด: {stat.market}")
        print(f"อุตสาหกรรม: {stat.industry}")
        print(f"ภาคธุรกิจ: {stat.sector}")
        print(f"ราคาปิด: {stat.close:.2f} บาท")

asyncio.run(fetch_thai_data("MINT"))
```

### Example 5: Valuation Analysis

```python
import asyncio
from settfex.services.set import get_trading_stats

async def analyze_valuation(symbol: str):
    """Analyze stock valuation metrics."""
    stats = await get_trading_stats(symbol)
    ytd = next(s for s in stats if s.period == "YTD")

    print(f"\n💰 {symbol} - Valuation Analysis")
    print(f"\nPrice Metrics:")
    print(f"  Current Price: {ytd.close:.2f} THB")
    print(f"  Book Value/Share: {ytd.book_value_per_share:.2f} THB")
    print(f"  Par Value: {ytd.par:.2f} THB")

    print(f"\nValuation Ratios:")
    print(f"  P/E Ratio: {ytd.pe:.2f}x")
    print(f"  P/B Ratio: {ytd.pbv:.2f}x")

    print(f"\nMarket Data:")
    print(f"  Market Cap: {ytd.market_cap:,.0f} THB")
    print(f"  Listed Shares: {ytd.listed_share:,.0f}")

    print(f"\nDividend:")
    print(f"  Yield: {ytd.dividend_yield:.2f}%")
    print(f"  Payout Ratio: {ytd.dividend_payout_ratio:.2%}")

asyncio.run(analyze_valuation("MINT"))
```

### Example 6: Trading Activity Analysis

```python
import asyncio
from settfex.services.set import get_trading_stats

async def analyze_trading_activity(symbol: str):
    """Analyze trading volume and liquidity."""
    stats = await get_trading_stats(symbol)
    ytd = next(s for s in stats if s.period == "YTD")

    print(f"\n📊 {symbol} - Trading Activity (YTD)")
    print(f"\nVolume:")
    print(f"  Total Volume: {ytd.total_volume:,.0f} shares")
    print(f"  Total Value: {ytd.total_value:,.0f} THB")
    print(f"  Avg Daily Value: {ytd.average_value:,.0f} THB")

    print(f"\nLiquidity:")
    print(f"  Turnover Ratio: {ytd.turnover_ratio:.2f}%")

    print(f"\nVolatility:")
    print(f"  Beta: {ytd.beta:.2f}")
    print(f"  52W High: {ytd.high:.2f} THB")
    print(f"  52W Low: {ytd.low:.2f} THB")
    price_range = ((ytd.high - ytd.low) / ytd.low) * 100
    print(f"  52W Range: {price_range:.2f}%")

asyncio.run(analyze_trading_activity("MINT"))
```

### Example 7: Multiple Stocks Comparison

```python
import asyncio
from settfex.services.set import get_trading_stats

async def compare_stocks(symbols: list[str]):
    """Compare trading statistics across multiple stocks."""
    print(f"\n📊 Stock Comparison - YTD Performance")
    print(f"{'Symbol':<8} {'Close':>10} {'Change %':>10} {'P/E':>8} {'Mkt Cap':>15}")
    print("-" * 60)

    for symbol in symbols:
        stats = await get_trading_stats(symbol)
        ytd = next(s for s in stats if s.period == "YTD")

        print(
            f"{symbol:<8} "
            f"{ytd.close:>10.2f} "
            f"{ytd.percent_change:>10.2f} "
            f"{ytd.pe:>8.2f} "
            f"{ytd.market_cap/1e9:>14.2f}B"
        )

asyncio.run(compare_stocks(["MINT", "AOT", "CPALL", "PTT"]))
```

### Example 8: Using the Service Class

```python
import asyncio
from settfex.services.set.stock import TradingStatService
from settfex.utils.data_fetcher import FetcherConfig

async def use_service_class():
    """Example using the service class directly."""
    # Custom configuration
    config = FetcherConfig(
        timeout=60,
        max_retries=5,
        browser_impersonate="chrome120"
    )

    # Create service
    service = TradingStatService(config=config)

    # Fetch trading statistics
    stats = await service.fetch_trading_stats("MINT", lang="en")

    print(f"Fetched {len(stats)} periods of data")
    for stat in stats:
        print(f"{stat.period}: {stat.close:.2f} THB")

    # Fetch raw data for debugging
    raw_stats = await service.fetch_trading_stats_raw("MINT")
    print(f"\nRaw data keys: {raw_stats[0].keys()}")

asyncio.run(use_service_class())
```

## Error Handling

```python
import asyncio
from settfex.services.set import get_trading_stats

async def safe_fetch(symbol: str):
    """Fetch with proper error handling."""
    try:
        stats = await get_trading_stats(symbol)
        return stats
    except ValueError as e:
        print(f"Validation error: {e}")
    except Exception as e:
        print(f"Failed to fetch trading stats: {e}")
    return None

asyncio.run(safe_fetch("MINT"))
```

## Performance Tips

1. **Reuse Service Instance**: Create one service instance and reuse it for multiple requests
2. **Concurrent Requests**: Use `asyncio.gather()` for fetching multiple stocks in parallel
3. **Session Caching**: SessionManager automatically caches cookies (25x speedup after first request)
4. **Filter Periods**: If you only need specific periods, filter the results client-side

```python
import asyncio
from settfex.services.set import get_trading_stats

async def efficient_batch_fetch(symbols: list[str]):
    """Efficiently fetch multiple stocks in parallel."""
    # Fetch all stocks concurrently
    results = await asyncio.gather(
        *[get_trading_stats(symbol) for symbol in symbols],
        return_exceptions=True
    )

    # Process results
    for symbol, result in zip(symbols, results):
        if isinstance(result, Exception):
            print(f"{symbol}: Error - {result}")
        else:
            ytd = next(s for s in result if s.period == "YTD")
            print(f"{symbol}: {ytd.close:.2f} ({ytd.percent_change:+.2f}%)")

asyncio.run(efficient_batch_fetch(["MINT", "AOT", "CPALL", "PTT"]))
```

## Troubleshooting

### Issue: Empty or missing data

**Solution:** Some fields may be `None` depending on the stock and data availability. Always check for `None` before using values:

```python
stats = await get_trading_stats("MINT")
ytd = next(s for s in stats if s.period == "YTD")

if ytd.pe is not None:
    print(f"P/E Ratio: {ytd.pe:.2f}")
else:
    print("P/E Ratio: N/A")
```

### Issue: Request timeout

**Solution:** Increase timeout in configuration:

```python
from settfex.utils.data_fetcher import FetcherConfig

config = FetcherConfig(timeout=60, max_retries=5)
stats = await get_trading_stats("MINT", config=config)
```

### Issue: Symbol not found

**Solution:** Verify the symbol exists using the stock list service:

```python
from settfex.services.set import get_stock_list

stock_list = await get_stock_list()
stock = stock_list.get_symbol("MINT")
if stock:
    stats = await get_trading_stats(stock.symbol)
```

## See Also

- [Stock Highlight Data Service](highlight_data.md) - Real-time stock metrics
- [Stock Profile Service](profile_stock.md) - Stock listing details
- [AsyncDataFetcher](../../utils/data_fetcher.md) - Low-level data fetcher
- [Session Caching](../../utils/session_caching.md) - Performance optimization
