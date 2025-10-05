# TFEX Trading Statistics Service

## Overview

The TFEX Trading Statistics Service provides async methods to fetch trading statistics for individual TFEX series. This includes settlement prices, margin requirements, theoretical pricing, days to maturity, and other key trading metrics.

## Quick Start

```python
import asyncio
from settfex.services.tfex import get_trading_statistics

async def main():
    # Fetch trading statistics for a specific series
    stats = await get_trading_statistics("S50Z25")

    print(f"Symbol: {stats.symbol}")
    print(f"Settlement Price: {stats.settlement_price:.5f}")
    print(f"Days to Maturity: {stats.day_to_maturity}")
    print(f"Initial Margin: {stats.im:,.2f}")
    print(f"Maintenance Margin: {stats.mm:,.2f}")

asyncio.run(main())
```

## Features

- **Full Type Safety**: Complete Pydantic models with all fields validated
- **Async-First**: Built on AsyncDataFetcher for optimal performance
- **Session Management**: Uses SessionManager for 25x faster subsequent requests
- **Symbol Normalization**: Automatic uppercase conversion for symbols
- **Comprehensive Data**: Settlement prices, margins, theoretical prices, and maturity info
- **DateTime Support**: Automatic parsing of market time and trading dates

## Models

### TradingStatistics

Individual TFEX series trading statistics.

**Fields:**
- `symbol: str` - Series symbol/ticker (e.g., "S50Z25")
- `market_time: datetime` - Market time when data was captured
- `last_trading_date: datetime` - Last trading date of the series
- `day_to_maturity: int` - Number of days until maturity/expiration
- `settlement_pattern: str` - Number format pattern for settlement price (e.g., "#,##0.00000")
- `is_options: bool` - Whether series is an options contract
- `theoretical_price: float | None` - Theoretical price of the series
- `prior_settlement_price: float | None` - Previous settlement price
- `settlement_price: float | None` - Current settlement price
- `im: float | None` - Initial margin requirement
- `mm: float | None` - Maintenance margin requirement
- `has_theoretical_price: bool` - Whether theoretical price is available

## Service Class

### TradingStatisticsService

Main service class for fetching TFEX trading statistics.

#### Constructor

```python
from settfex.services.tfex import TradingStatisticsService
from settfex.utils.data_fetcher import FetcherConfig

# Default configuration
service = TradingStatisticsService()

# Custom configuration
config = FetcherConfig(timeout=60, max_retries=5)
service = TradingStatisticsService(config=config)
```

#### Methods

##### `fetch_trading_statistics(symbol: str) -> TradingStatistics`

Fetch trading statistics for a specific TFEX series.

```python
service = TradingStatisticsService()
stats = await service.fetch_trading_statistics("S50Z25")

print(f"Settlement Price: {stats.settlement_price:.5f}")
print(f"Days to Maturity: {stats.day_to_maturity}")
print(f"Margins: IM={stats.im:,.2f}, MM={stats.mm:,.2f}")
```

##### `fetch_trading_statistics_raw(symbol: str) -> dict[str, Any]`

Fetch trading statistics as raw dictionary without Pydantic validation. Useful for debugging.

```python
service = TradingStatisticsService()
raw_data = await service.fetch_trading_statistics_raw("S50Z25")
print(raw_data.keys())
```

## Convenience Function

### `get_trading_statistics(symbol: str, config: FetcherConfig | None = None)`

Quick one-line access to fetch TFEX trading statistics.

```python
from settfex.services.tfex import get_trading_statistics

# Simple usage
stats = await get_trading_statistics("S50Z25")

# With custom config
from settfex.utils.data_fetcher import FetcherConfig
config = FetcherConfig(timeout=60)
stats = await get_trading_statistics("S50Z25", config=config)
```

## Usage Examples

### Example 1: Basic Trading Statistics

```python
from settfex.services.tfex import get_trading_statistics

async def check_series_stats():
    """Get basic trading statistics for a series."""
    stats = await get_trading_statistics("S50Z25")

    print(f"Symbol: {stats.symbol}")
    print(f"Market Time: {stats.market_time}")
    print(f"Last Trading Date: {stats.last_trading_date}")
    print(f"Days to Maturity: {stats.day_to_maturity}")
    print(f"\nPricing:")
    print(f"  Settlement Price: {stats.settlement_price:.5f}")
    print(f"  Prior Settlement: {stats.prior_settlement_price:.5f}")

    if stats.has_theoretical_price:
        print(f"  Theoretical Price: {stats.theoretical_price:.5f}")

    print(f"\nMargin Requirements:")
    print(f"  Initial Margin (IM): {stats.im:,.2f}")
    print(f"  Maintenance Margin (MM): {stats.mm:,.2f}")

await check_series_stats()
```

### Example 2: Monitor Multiple Series

```python
from settfex.services.tfex import get_trading_statistics

async def monitor_series(symbols: list[str]):
    """Monitor trading statistics for multiple series."""
    print("Symbol".ljust(10), "Settlement".rjust(12), "Days Left".rjust(10),
          "IM".rjust(12), "MM".rjust(12))
    print("-" * 60)

    for symbol in symbols:
        try:
            stats = await get_trading_statistics(symbol)
            print(
                f"{stats.symbol.ljust(10)} "
                f"{stats.settlement_price:12.5f} "
                f"{stats.day_to_maturity:10d} "
                f"{stats.im:12,.2f} "
                f"{stats.mm:12,.2f}"
            )
        except Exception as e:
            print(f"{symbol.ljust(10)} Error: {e}")

# Monitor SET50 futures series
symbols = ["S50Z25", "S50V25", "S50X25"]
await monitor_series(symbols)
```

### Example 3: Calculate Margin Coverage

```python
from settfex.services.tfex import get_trading_statistics

async def calculate_margin_coverage(symbol: str, capital: float):
    """Calculate how many contracts can be traded with available capital."""
    stats = await get_trading_statistics(symbol)

    # Calculate number of contracts based on initial margin
    max_contracts = int(capital / stats.im)

    # Calculate maintenance margin requirement
    mm_required = max_contracts * stats.mm

    print(f"Symbol: {stats.symbol}")
    print(f"Available Capital: {capital:,.2f} THB")
    print(f"\nMargin Requirements per Contract:")
    print(f"  Initial Margin (IM): {stats.im:,.2f} THB")
    print(f"  Maintenance Margin (MM): {stats.mm:,.2f} THB")
    print(f"\nMaximum Contracts: {max_contracts}")
    print(f"Total IM Required: {max_contracts * stats.im:,.2f} THB")
    print(f"Total MM Required: {mm_required:,.2f} THB")
    print(f"Remaining Capital: {capital - (max_contracts * stats.im):,.2f} THB")

await calculate_margin_coverage("S50Z25", 500000)
```

### Example 4: Check Days to Expiration

```python
from settfex.services.tfex import get_trading_statistics

async def check_expiration(symbol: str):
    """Check days to expiration and alert if close to maturity."""
    stats = await get_trading_statistics(symbol)

    print(f"Symbol: {stats.symbol}")
    print(f"Last Trading Date: {stats.last_trading_date.date()}")
    print(f"Days to Maturity: {stats.day_to_maturity}")

    if stats.day_to_maturity <= 7:
        print(f"⚠️  WARNING: Less than 1 week to expiration!")
    elif stats.day_to_maturity <= 30:
        print(f"⚠️  NOTICE: Less than 1 month to expiration")
    else:
        print(f"✓ More than 1 month remaining")

await check_expiration("S50Z25")
```

### Example 5: Compare Settlement Prices

```python
from settfex.services.tfex import get_trading_statistics

async def compare_settlements(symbol: str):
    """Compare current and prior settlement prices."""
    stats = await get_trading_statistics(symbol)

    # Calculate change
    price_change = stats.settlement_price - stats.prior_settlement_price
    percent_change = (price_change / stats.prior_settlement_price) * 100

    print(f"Symbol: {stats.symbol}")
    print(f"Prior Settlement: {stats.prior_settlement_price:.5f}")
    print(f"Current Settlement: {stats.settlement_price:.5f}")
    print(f"Change: {price_change:+.5f} ({percent_change:+.2f}%)")

    # Show trend
    if price_change > 0:
        print("Trend: 📈 Upward")
    elif price_change < 0:
        print("Trend: 📉 Downward")
    else:
        print("Trend: ➡️  Unchanged")

await compare_settlements("S50Z25")
```

### Example 6: Theoretical vs Settlement Price

```python
from settfex.services.tfex import get_trading_statistics

async def analyze_pricing(symbol: str):
    """Analyze theoretical vs settlement price."""
    stats = await get_trading_statistics(symbol)

    print(f"Symbol: {stats.symbol}")
    print(f"Settlement Price: {stats.settlement_price:.5f}")

    if stats.has_theoretical_price:
        print(f"Theoretical Price: {stats.theoretical_price:.5f}")

        # Calculate difference
        diff = stats.settlement_price - stats.theoretical_price
        percent_diff = (diff / stats.theoretical_price) * 100

        print(f"Difference: {diff:+.5f} ({percent_diff:+.2f}%)")

        if abs(percent_diff) > 1.0:
            print("⚠️  Significant deviation from theoretical price!")
        else:
            print("✓ Price aligned with theoretical value")
    else:
        print("Theoretical price not available")

await analyze_pricing("S50Z25")
```

### Example 7: Margin Ratio Analysis

```python
from settfex.services.tfex import get_trading_statistics

async def analyze_margin_ratio(symbol: str):
    """Analyze the margin ratio (MM/IM)."""
    stats = await get_trading_statistics(symbol)

    # Calculate margin ratio
    margin_ratio = (stats.mm / stats.im) * 100

    print(f"Symbol: {stats.symbol}")
    print(f"Initial Margin (IM): {stats.im:,.2f} THB")
    print(f"Maintenance Margin (MM): {stats.mm:,.2f} THB")
    print(f"Margin Ratio (MM/IM): {margin_ratio:.2f}%")
    print(f"\nBuffer: {stats.im - stats.mm:,.2f} THB ({100 - margin_ratio:.2f}%)")

    # Interpret ratio
    if margin_ratio > 80:
        print("⚠️  High margin ratio - smaller cushion")
    elif margin_ratio > 60:
        print("Moderate margin ratio")
    else:
        print("✓ Good margin cushion")

await analyze_margin_ratio("S50Z25")
```

### Example 8: Series Type Detection

```python
from settfex.services.tfex import get_trading_statistics

async def check_series_type(symbol: str):
    """Check if series is futures or options."""
    stats = await get_trading_statistics(symbol)

    series_type = "Options" if stats.is_options else "Futures"

    print(f"Symbol: {stats.symbol}")
    print(f"Type: {series_type}")
    print(f"Settlement Pattern: {stats.settlement_pattern}")
    print(f"Days to Maturity: {stats.day_to_maturity}")

    if stats.is_options:
        print("\nOptions Contract Details:")
        print(f"  Settlement Price: {stats.settlement_price:.5f}")
        if stats.has_theoretical_price:
            print(f"  Theoretical Price: {stats.theoretical_price:.5f}")
    else:
        print("\nFutures Contract Details:")
        print(f"  Settlement Price: {stats.settlement_price:.5f}")
        print(f"  Prior Settlement: {stats.prior_settlement_price:.5f}")

await check_series_type("S50Z25")
```

## Performance

### Session Caching

The service uses SessionManager for automatic cookie handling and caching:

- **First request**: ~2-3 seconds (warmup + request)
- **Subsequent requests**: ~100ms (25x faster!)
- **Cache location**: `~/.settfex/cache/`
- **Auto-retry**: Automatically re-warms on HTTP 403/452

### Best Practices

1. **Use convenience function** for quick access: `get_trading_statistics(symbol)`
2. **Reuse service instance** when fetching multiple symbols
3. **Cache results** in your application if querying frequently
4. **Monitor margin requirements** before trading
5. **Check days to maturity** for contract rollover planning

## Error Handling

The service includes comprehensive error handling:

```python
from settfex.services.tfex import get_trading_statistics

async def safe_fetch(symbol: str):
    """Fetch trading statistics with error handling."""
    try:
        stats = await get_trading_statistics(symbol)
        return stats
    except Exception as e:
        print(f"Failed to fetch statistics for {symbol}: {e}")
        return None

stats = await safe_fetch("S50Z25")
if stats:
    print(f"Settlement Price: {stats.settlement_price:.5f}")
```

## Common Use Cases

### Risk Management

```python
# Check margin requirements before opening position
stats = await get_trading_statistics("S50Z25")
if capital >= stats.im:
    print(f"Sufficient capital for position (IM: {stats.im:,.2f})")
else:
    print(f"Insufficient capital. Need: {stats.im:,.2f}, Have: {capital:,.2f}")
```

### Contract Rollover Planning

```python
# Monitor days to maturity for rollover
stats = await get_trading_statistics("S50Z25")
if stats.day_to_maturity <= 5:
    print(f"Time to roll position! Only {stats.day_to_maturity} days left")
```

### Settlement Price Monitoring

```python
# Track settlement price changes
stats = await get_trading_statistics("S50Z25")
change = stats.settlement_price - stats.prior_settlement_price
print(f"Settlement change: {change:+.5f}")
```

## API Endpoint

The service fetches data from:

```
https://www.tfex.co.th/api/set/tfex/series/{symbol}/trading-statistics
```

Example: `https://www.tfex.co.th/api/set/tfex/series/S50Z25/trading-statistics`

Response format:
```json
{
    "symbol": "S50Z25",
    "marketTime": "2025-10-04T03:05:08.070566685+07:00",
    "lastTradingDate": "2025-12-29T16:30:00+07:00",
    "dayToMaturity": 86,
    "settlementPattern": "#,##0.00000",
    "isOptions": false,
    "theoreticalPrice": 831.8776,
    "priorSettlementPrice": 825.9,
    "settlementPrice": 830.3,
    "im": 10080.0,
    "mm": 7084.8,
    "hasTheoreticalPrice": true
}
```

## Related Services

- [TFEX Series List Service](list.md) - List all TFEX futures and options series
- [AsyncDataFetcher](../../utils/data_fetcher.md) - Low-level HTTP client
- [Session Caching](../../utils/session_caching.md) - Session management and caching

## Troubleshooting

### Issue: Symbol not found

**Solution**: Verify the symbol exists using the Series List service:
```python
from settfex.services.tfex import get_series_list

series_list = await get_series_list()
series = series_list.get_symbol("S50Z25")
if series:
    print(f"Found: {series.symbol}")
else:
    print("Symbol not found")
```

### Issue: None values for prices/margins

**Solution**: Some fields may be None for inactive or newly listed series. Always check before using:
```python
stats = await get_trading_statistics("S50Z25")
if stats.settlement_price is not None:
    print(f"Settlement: {stats.settlement_price:.5f}")
else:
    print("Settlement price not available")
```

### Issue: Slow first request

**Solution**: This is normal (warmup). Subsequent requests are 25x faster due to caching.

## See Also

- [TFEX Series List Service](list.md) - Get list of all TFEX series
- [TFEX Constants](../../../services/tfex/constants.md) - TFEX API configuration
