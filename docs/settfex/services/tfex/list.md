# TFEX Series List Service

## Overview

The TFEX Series List Service provides async methods to fetch the complete list of futures and options series traded on the Thailand Futures Exchange (TFEX). This includes detailed information about contract specifications, trading dates, underlying assets, and market classifications.

## Quick Start

```python
import asyncio
from settfex.services.tfex import get_series_list

async def main():
    # Fetch all TFEX series
    series_list = await get_series_list()

    print(f"Total series: {series_list.count}")
    print(f"Active series: {len(series_list.filter_active_only())}")
    print(f"Futures only: {len(series_list.get_futures())}")
    print(f"Options only: {len(series_list.get_options())}")

asyncio.run(main())
```

## Features

- **Full Type Safety**: Complete Pydantic models with all fields validated
- **Async-First**: Built on AsyncDataFetcher for optimal performance
- **Session Management**: Uses SessionManager for 25x faster subsequent requests
- **Rich Filtering**: Filter by instrument, market, underlying, active status, futures/options
- **DateTime Support**: Automatic parsing of trading dates
- **Comprehensive Data**: Instrument details, contract months, strike prices, night sessions

## Models

### TFEXSeries

Individual TFEX series information.

**Fields:**
- `symbol: str` - Series symbol/ticker (e.g., "S50V25")
- `instrument_id: str` - Instrument identifier (e.g., "SET50_FC")
- `instrument_name: str` - Instrument name (e.g., "SET50 Futures")
- `market_list_id: str` - Market list identifier (e.g., "TXI_F")
- `market_list_name: str` - Market list name (e.g., "Equity Index Futures")
- `first_trading_date: datetime` - First trading date of the series
- `last_trading_date: datetime` - Last trading date of the series
- `contract_month: str` - Contract month (e.g., "10/2025")
- `options_type: str` - Options type (empty for futures, "C"/"P" for options)
- `strike_price: float | None` - Strike price (for options only)
- `has_night_session: bool` - Whether series has night trading session
- `underlying: str` - Underlying asset (e.g., "SET50", "GOLD")
- `active: bool` - Whether series is currently active for trading

### TFEXSeriesListResponse

Complete response containing all series.

**Properties:**
- `series: list[TFEXSeries]` - List of all TFEX series
- `count: int` - Total number of series (property)

**Filter Methods:**
- `filter_by_instrument(instrument_id: str)` - Filter by instrument ID
- `filter_by_market(market_list_id: str)` - Filter by market list ID
- `filter_by_underlying(underlying: str)` - Filter by underlying asset
- `filter_active_only()` - Get only active series
- `get_futures()` - Get only futures contracts
- `get_options()` - Get only options contracts
- `get_symbol(symbol: str)` - Lookup specific series by symbol

## Service Class

### TFEXSeriesListService

Main service class for fetching TFEX series list.

#### Constructor

```python
from settfex.services.tfex import TFEXSeriesListService
from settfex.utils.data_fetcher import FetcherConfig

# Default configuration
service = TFEXSeriesListService()

# Custom configuration
config = FetcherConfig(timeout=60, max_retries=5)
service = TFEXSeriesListService(config=config)
```

#### Methods

##### `fetch_series_list() -> TFEXSeriesListResponse`

Fetch the complete list of TFEX series from TFEX API.

```python
service = TFEXSeriesListService()
response = await service.fetch_series_list()

print(f"Total series: {response.count}")
print(f"Active series: {len(response.filter_active_only())}")
```

##### `fetch_series_list_raw() -> dict[str, Any]`

Fetch series list as raw dictionary without Pydantic validation. Useful for debugging.

```python
service = TFEXSeriesListService()
raw_data = await service.fetch_series_list_raw()
print(raw_data.keys())
```

## Convenience Function

### `get_series_list(config: FetcherConfig | None = None)`

Quick one-line access to fetch TFEX series list.

```python
from settfex.services.tfex import get_series_list

# Simple usage
response = await get_series_list()

# With custom config
from settfex.utils.data_fetcher import FetcherConfig
config = FetcherConfig(timeout=60)
response = await get_series_list(config=config)
```

## Usage Examples

### Example 1: Get All Series

```python
from settfex.services.tfex import get_series_list

async def list_all_series():
    """List all TFEX series."""
    series_list = await get_series_list()

    print(f"Total series: {series_list.count}")

    for series in series_list.series[:10]:  # First 10
        print(f"{series.symbol}: {series.instrument_name}")
        print(f"  Contract: {series.contract_month}")
        print(f"  Active: {series.active}")
        print(f"  Last Trading: {series.last_trading_date.date()}")
        print()

await list_all_series()
```

### Example 2: Filter Active Futures

```python
from settfex.services.tfex import get_series_list

async def get_active_futures():
    """Get only active futures contracts."""
    series_list = await get_series_list()

    # Get active futures (not options)
    active_futures = [s for s in series_list.get_futures() if s.active]

    print(f"Active futures: {len(active_futures)}")

    for series in active_futures[:5]:
        print(f"{series.symbol}: {series.instrument_name}")
        print(f"  Underlying: {series.underlying}")
        print(f"  Expires: {series.last_trading_date.date()}")
        print()

await get_active_futures()
```

### Example 3: Filter by Instrument

```python
from settfex.services.tfex import get_series_list

async def get_set50_contracts():
    """Get all SET50 futures contracts."""
    series_list = await get_series_list()

    # Filter SET50 futures
    set50_series = series_list.filter_by_instrument("SET50_FC")

    print(f"SET50 Futures contracts: {len(set50_series)}")

    # Show active contracts sorted by expiry
    active = [s for s in set50_series if s.active]
    active.sort(key=lambda x: x.last_trading_date)

    for series in active:
        print(f"{series.symbol}: {series.contract_month}")
        print(f"  Expires: {series.last_trading_date.date()}")
        print(f"  Night Session: {series.has_night_session}")
        print()

await get_set50_contracts()
```

### Example 4: Filter by Underlying Asset

```python
from settfex.services.tfex import get_series_list

async def get_gold_contracts():
    """Get all GOLD futures contracts."""
    series_list = await get_series_list()

    # Filter by underlying
    gold_series = series_list.filter_by_underlying("GOLD")

    print(f"GOLD contracts: {len(gold_series)}")

    for series in gold_series:
        status = "Active" if series.active else "Inactive"
        print(f"{series.symbol} ({status}): {series.contract_month}")

await get_gold_contracts()
```

### Example 5: Filter Options

```python
from settfex.services.tfex import get_series_list

async def get_options_by_underlying():
    """Get all options contracts grouped by underlying."""
    series_list = await get_series_list()

    # Get all options
    options = series_list.get_options()

    print(f"Total options: {len(options)}")

    # Group by underlying
    from collections import defaultdict
    by_underlying = defaultdict(list)

    for option in options:
        if option.active:
            by_underlying[option.underlying].append(option)

    for underlying, opts in by_underlying.items():
        print(f"\n{underlying} Options: {len(opts)}")

        # Show sample
        for opt in opts[:3]:
            opt_type = "Call" if opt.options_type == "C" else "Put"
            print(f"  {opt.symbol} ({opt_type}, Strike: {opt.strike_price})")

await get_options_by_underlying()
```

### Example 6: Filter by Market

```python
from settfex.services.tfex import get_series_list

async def list_by_market():
    """List series grouped by market."""
    series_list = await get_series_list()

    # Get unique markets
    markets = set(s.market_list_id for s in series_list.series)

    for market_id in sorted(markets):
        market_series = series_list.filter_by_market(market_id)
        active_count = len([s for s in market_series if s.active])

        # Get market name from first series
        market_name = market_series[0].market_list_name if market_series else "Unknown"

        print(f"\n{market_id}: {market_name}")
        print(f"  Total: {len(market_series)}, Active: {active_count}")

await list_by_market()
```

### Example 7: Lookup Specific Series

```python
from settfex.services.tfex import get_series_list

async def get_series_details(symbol: str):
    """Get detailed information for a specific series."""
    series_list = await get_series_list()

    series = series_list.get_symbol(symbol)

    if not series:
        print(f"Series {symbol} not found!")
        return

    print(f"Symbol: {series.symbol}")
    print(f"Instrument: {series.instrument_name}")
    print(f"Underlying: {series.underlying}")
    print(f"Contract Month: {series.contract_month}")
    print(f"First Trading: {series.first_trading_date.date()}")
    print(f"Last Trading: {series.last_trading_date.date()}")
    print(f"Active: {series.active}")
    print(f"Night Session: {series.has_night_session}")

    if series.options_type:
        opt_type = "Call" if series.options_type == "C" else "Put"
        print(f"Option Type: {opt_type}")
        print(f"Strike Price: {series.strike_price}")

await get_series_details("S50V25")
```

### Example 8: Advanced Filtering

```python
from settfex.services.tfex import get_series_list
from datetime import datetime, timedelta

async def find_near_expiry_contracts():
    """Find contracts expiring in the next 30 days."""
    series_list = await get_series_list()

    now = datetime.now(series_list.series[0].last_trading_date.tzinfo)
    thirty_days = now + timedelta(days=30)

    near_expiry = [
        s for s in series_list.filter_active_only()
        if now <= s.last_trading_date <= thirty_days
    ]

    near_expiry.sort(key=lambda x: x.last_trading_date)

    print(f"Contracts expiring in next 30 days: {len(near_expiry)}")

    for series in near_expiry:
        days_left = (series.last_trading_date - now).days
        print(f"{series.symbol}: {series.instrument_name}")
        print(f"  Expires in {days_left} days ({series.last_trading_date.date()})")
        print()

await find_near_expiry_contracts()
```

## Performance

### Session Caching

The service uses SessionManager for automatic cookie handling and caching:

- **First request**: ~2-3 seconds (warmup + request)
- **Subsequent requests**: ~100ms (25x faster!)
- **Cache location**: `~/.settfex/cache/`
- **Auto-retry**: Automatically re-warms on HTTP 403/452

### Best Practices

1. **Use convenience function** for quick access: `get_series_list()`
2. **Filter after fetching** rather than making multiple API calls
3. **Cache results** in your application if querying frequently
4. **Use filter methods** for efficient data access
5. **Check active status** before using series data

## Error Handling

The service includes comprehensive error handling:

```python
from settfex.services.tfex import get_series_list

async def safe_fetch():
    """Fetch series list with error handling."""
    try:
        series_list = await get_series_list()
        return series_list
    except Exception as e:
        print(f"Failed to fetch series list: {e}")
        return None

series_list = await safe_fetch()
if series_list:
    print(f"Successfully fetched {series_list.count} series")
```

## Common Use Cases

### Investment Research

```python
# Find all active SET50 futures
series_list = await get_series_list()
set50_futures = [
    s for s in series_list.filter_by_underlying("SET50")
    if s.active and not s.options_type
]
```

### Options Chain Analysis

```python
# Get all options for a specific underlying
series_list = await get_series_list()
underlying_options = [
    s for s in series_list.filter_by_underlying("SET50")
    if s.active and s.options_type
]

# Separate calls and puts
calls = [o for o in underlying_options if o.options_type == "C"]
puts = [o for o in underlying_options if o.options_type == "P"]
```

### Contract Roll Monitoring

```python
# Find next contract month for rollover
from datetime import datetime

series_list = await get_series_list()
set50_futures = [
    s for s in series_list.filter_by_instrument("SET50_FC")
    if s.active
]

# Sort by expiry
set50_futures.sort(key=lambda x: x.last_trading_date)

front_month = set50_futures[0]
next_month = set50_futures[1] if len(set50_futures) > 1 else None

print(f"Front month: {front_month.symbol} (expires {front_month.last_trading_date.date()})")
if next_month:
    print(f"Next month: {next_month.symbol} (expires {next_month.last_trading_date.date()})")
```

## API Endpoint

The service fetches data from:

```
https://www.tfex.co.th/api/set/tfex/series/list
```

Response format:
```json
{
  "series": [
    {
      "symbol": "S50V25",
      "instrumentId": "SET50_FC",
      "instrumentName": "SET50 Futures",
      "marketListId": "TXI_F",
      "marketListName": "Equity Index Futures",
      "firstTradingDate": "2025-07-30T00:00:00+07:00",
      "lastTradingDate": "2025-10-30T16:30:00+07:00",
      "contractMonth": "10/2025",
      "optionsType": "",
      "strikePrice": null,
      "hasNightSession": false,
      "underlying": "SET50",
      "active": true
    }
  ]
}
```

## Related Services

- [AsyncDataFetcher](../../utils/data_fetcher.md) - Low-level HTTP client
- [Session Caching](../../utils/session_caching.md) - Session management and caching

## Troubleshooting

### Issue: No series returned

**Solution**: Check API availability and network connection:
```python
raw = await service.fetch_series_list_raw()
print(raw)  # Inspect raw response
```

### Issue: DateTime parsing errors

**Solution**: Ensure you're using Python 3.11+ with proper datetime support

### Issue: Slow first request

**Solution**: This is normal (warmup). Subsequent requests are 25x faster due to caching.

## See Also

- [SET Stock List Service](../../set/list.md) - Similar service for SET stocks
- [TFEX Constants](../../../services/tfex/constants.md) - TFEX API configuration
