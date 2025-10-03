# Corporate Action Service

## Overview

The Corporate Action Service provides async methods to fetch corporate action data for individual stock symbols from the Stock Exchange of Thailand (SET). It retrieves information about dividend announcements (XD), shareholder meetings (XM), and other corporate events.

## Quick Start

```python
import asyncio
from settfex.services.set import get_corporate_actions

async def main():
    # Fetch corporate actions for a stock
    actions = await get_corporate_actions("AOT")

    for action in actions:
        if action.ca_type == "XD":
            print(f"Dividend: {action.dividend} {action.currency}")
            print(f"XD Date: {action.x_date}")
            print(f"Payment Date: {action.payment_date}")
        elif action.ca_type == "XM":
            print(f"Meeting: {action.meeting_type}")
            print(f"Meeting Date: {action.meeting_date}")
            print(f"Agenda: {action.agenda}")

asyncio.run(main())
```

## Features

- **Full Type Safety**: Complete Pydantic models for all corporate action types
- **Dual Language Support**: Fetch data in English ('en') or Thai ('th')
- **Input Normalization**: Automatic symbol uppercase and language validation
- **Async-First**: Built on AsyncDataFetcher for optimal performance
- **Automatic Session Management**: Uses SessionManager for bot detection bypass (25x faster after first request)

## API Reference

### Convenience Function

#### `get_corporate_actions(symbol, lang='en', config=None)`

Quick one-line access to corporate action data.

**Parameters:**
- `symbol: str` - Stock symbol (e.g., "AOT", "PTT", "cpall")
- `lang: str` - Language for response ('en' or 'th', default: 'en')
- `config: FetcherConfig | None` - Optional fetcher configuration

**Returns:**
- `list[CorporateAction]` - List of corporate action objects

**Example:**
```python
from settfex.services.set import get_corporate_actions

# English (default)
actions = await get_corporate_actions("AOT")

# Thai language
actions_th = await get_corporate_actions("AOT", lang="th")

# Custom configuration
from settfex.utils.data_fetcher import FetcherConfig

config = FetcherConfig(timeout=60, max_retries=5)
actions = await get_corporate_actions("AOT", config=config)
```

### CorporateActionService Class

Main service class for fetching corporate action data.

#### Constructor

```python
CorporateActionService(config: FetcherConfig | None = None)
```

**Parameters:**
- `config: FetcherConfig | None` - Optional fetcher configuration (uses defaults if None)

**Example:**
```python
from settfex.services.set.stock import CorporateActionService
from settfex.utils.data_fetcher import FetcherConfig

# Default configuration (uses SessionManager automatically)
service = CorporateActionService()

# Custom configuration
config = FetcherConfig(timeout=60, max_retries=5)
service = CorporateActionService(config=config)
```

#### Methods

##### `fetch_corporate_actions(symbol, lang='en')`

Fetch corporate actions for a specific stock symbol.

**Parameters:**
- `symbol: str` - Stock symbol (e.g., "AOT", "PTT", "cpall")
- `lang: str` - Language for response ('en' or 'th', default: 'en')

**Returns:**
- `list[CorporateAction]` - List of corporate action objects with validated data

**Raises:**
- `ValueError` - If symbol is empty or language is invalid
- `Exception` - If request fails or response cannot be parsed

**Example:**
```python
service = CorporateActionService()

# Fetch corporate actions
actions = await service.fetch_corporate_actions("AOT", lang="en")

for action in actions:
    print(f"Type: {action.ca_type}")
    print(f"XD Date: {action.x_date}")

    # Dividend-specific fields
    if action.ca_type == "XD":
        print(f"Dividend: {action.dividend} {action.currency}")
        print(f"Payment Date: {action.payment_date}")
        print(f"Source: {action.source_of_dividend}")

    # Meeting-specific fields
    if action.ca_type == "XM":
        print(f"Meeting Type: {action.meeting_type}")
        print(f"Meeting Date: {action.meeting_date}")
        print(f"Venue: {action.venue}")
        print(f"Agenda: {action.agenda}")
```

##### `fetch_corporate_actions_raw(symbol, lang='en')`

Fetch corporate actions as raw list of dictionaries without Pydantic validation.

Useful for debugging or when you need the raw API response.

**Parameters:**
- `symbol: str` - Stock symbol (e.g., "AOT", "PTT", "cpall")
- `lang: str` - Language for response ('en' or 'th', default: 'en')

**Returns:**
- `list[dict[str, Any]]` - Raw list of dictionaries from API

**Raises:**
- `ValueError` - If symbol is empty or language is invalid
- `Exception` - If request fails

**Example:**
```python
service = CorporateActionService()

# Fetch raw data
raw_data = await service.fetch_corporate_actions_raw("AOT")
print(f"Found {len(raw_data)} actions")

for action in raw_data:
    print(action.keys())
    print(action)
```

### CorporateAction Model

Pydantic model representing a single corporate action.

#### Common Fields (All Action Types)

- `symbol: str` - Stock symbol/ticker
- `name: str` - Company name (may be empty)
- `ca_type: str` - Corporate action type (e.g., "XD", "XM")
- `type: str` - Action type
- `book_close_date: datetime | None` - Book closure date
- `record_date: datetime | None` - Record date
- `remark: str | None` - Additional remarks or notes
- `x_date: datetime | None` - Ex-date (ex-dividend or ex-rights)
- `x_session: str | None` - Ex-date session

#### Dividend-Specific Fields (XD Type)

- `payment_date: datetime | None` - Dividend payment date
- `begin_operation: datetime | None` - Operation period start date
- `end_operation: datetime | None` - Operation period end date
- `source_of_dividend: str | None` - Source of dividend (e.g., "Net Profit")
- `dividend: float | None` - Dividend amount per share
- `currency: str | None` - Currency code (e.g., "Baht")
- `ratio: str | None` - Dividend ratio (e.g., "15 : 1", "95.1997 : 1")
- `dividend_type: str | None` - Type of dividend (e.g., "Cash Dividend")
- `approximate_payment_date: datetime | None` - Approximate payment date
- `tentative_dividend_flag: bool | None` - Flag for tentative dividend
- `tentative_dividend: float | None` - Tentative dividend amount
- `dividend_payment: str | None` - Dividend payment amount as string

#### Meeting-Specific Fields (XM Type)

- `meeting_date: datetime | None` - Meeting date and time
- `agenda: str | None` - Meeting agenda items
- `venue: str | None` - Meeting venue location
- `meeting_type: str | None` - Type of meeting (e.g., "AGM", "EGM")
- `inquiry_date: datetime | None` - Inquiry date

## Usage Examples

### Example 1: Get All Corporate Actions

```python
import asyncio
from settfex.services.set import get_corporate_actions

async def get_all_actions():
    """Fetch all corporate actions for a stock."""
    actions = await get_corporate_actions("AOT")

    print(f"Found {len(actions)} corporate action(s)")

    for action in actions:
        print(f"\nType: {action.ca_type}")
        print(f"XD Date: {action.x_date}")
        print(f"Record Date: {action.record_date}")

asyncio.run(get_all_actions())
```

### Example 2: Filter Dividend Actions

```python
async def get_dividends():
    """Get only dividend announcements (XD type)."""
    actions = await get_corporate_actions("PTT")

    # Filter for dividend actions
    dividends = [a for a in actions if a.ca_type == "XD"]

    for div in dividends:
        print(f"Dividend: {div.dividend} {div.currency}")
        print(f"XD Date: {div.x_date}")
        print(f"Payment Date: {div.payment_date}")
        print(f"Source: {div.source_of_dividend}")
        print(f"Type: {div.dividend_type}")
        print()
```

### Example 3: Filter Meeting Actions

```python
async def get_meetings():
    """Get only shareholder meetings (XM type)."""
    actions = await get_corporate_actions("CPALL")

    # Filter for meeting actions
    meetings = [a for a in actions if a.ca_type == "XM"]

    for meeting in meetings:
        print(f"Meeting Type: {meeting.meeting_type}")
        print(f"Meeting Date: {meeting.meeting_date}")
        print(f"Agenda: {meeting.agenda}")
        print(f"Venue: {meeting.venue}")
        print()
```

### Example 4: Using Service Class

```python
from settfex.services.set.stock import CorporateActionService
from settfex.utils.data_fetcher import FetcherConfig

async def advanced_usage():
    """Use service class with custom configuration."""
    # Custom config with longer timeout and more retries
    config = FetcherConfig(
        timeout=60,
        max_retries=5,
        retry_delay=2.0
    )

    service = CorporateActionService(config=config)

    # Fetch data
    actions = await service.fetch_corporate_actions("KBANK", lang="en")

    # Group by type
    by_type = {}
    for action in actions:
        if action.ca_type not in by_type:
            by_type[action.ca_type] = []
        by_type[action.ca_type].append(action)

    # Print summary
    for action_type, action_list in by_type.items():
        print(f"{action_type}: {len(action_list)} action(s)")
```

### Example 5: Thai Language Support

```python
async def thai_language():
    """Fetch data in Thai language."""
    # Fetch in Thai
    actions = await get_corporate_actions("BBL", lang="th")

    for action in actions:
        print(f"ประเภท: {action.ca_type}")
        if action.ca_type == "XD":
            print(f"เงินปันผล: {action.dividend} {action.currency}")
        elif action.ca_type == "XM":
            print(f"ประเภทการประชุม: {action.meeting_type}")
            print(f"วาระ: {action.agenda}")
```

### Example 6: Error Handling

```python
async def with_error_handling():
    """Proper error handling."""
    try:
        actions = await get_corporate_actions("AOT")

        if not actions:
            print("No corporate actions found")
            return

        for action in actions:
            print(f"Action: {action.ca_type}")

    except ValueError as e:
        print(f"Invalid input: {e}")
    except Exception as e:
        print(f"Failed to fetch: {e}")
```

### Example 7: Raw Data Access

```python
async def debug_raw_data():
    """Access raw API response for debugging."""
    service = CorporateActionService()

    # Get raw data
    raw_data = await service.fetch_corporate_actions_raw("AOT")

    print(f"Raw response type: {type(raw_data)}")
    print(f"Number of actions: {len(raw_data)}")

    # Inspect first action
    if raw_data:
        print("\nFirst action keys:")
        print(list(raw_data[0].keys()))
        print("\nFirst action data:")
        import json
        print(json.dumps(raw_data[0], indent=2, default=str))
```

### Example 8: Multiple Stocks Concurrently

```python
import asyncio

async def fetch_multiple_stocks():
    """Fetch corporate actions for multiple stocks concurrently."""
    symbols = ["AOT", "PTT", "CPALL", "KBANK", "BBL"]

    # Create tasks for concurrent fetching
    tasks = [get_corporate_actions(symbol) for symbol in symbols]

    # Fetch all concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    for symbol, result in zip(symbols, results):
        if isinstance(result, Exception):
            print(f"{symbol}: Error - {result}")
        else:
            print(f"{symbol}: {len(result)} action(s)")

            # Count by type
            type_counts = {}
            for action in result:
                type_counts[action.ca_type] = type_counts.get(action.ca_type, 0) + 1

            for action_type, count in type_counts.items():
                print(f"  {action_type}: {count}")
```

## Performance

### Session Caching

The service automatically uses SessionManager for cookie handling and caching:

- **First Request**: ~2-3 seconds (session warmup)
- **Subsequent Requests**: ~100ms (25x faster!)
- **Cache Location**: `~/.settfex/cache/`
- **Auto-Retry**: On HTTP 403/452, automatically re-warms and retries

### Best Practices

1. **Use the convenience function** for simple use cases:
   ```python
   actions = await get_corporate_actions("AOT")
   ```

2. **Reuse service instance** for multiple requests:
   ```python
   service = CorporateActionService()
   actions1 = await service.fetch_corporate_actions("AOT")
   actions2 = await service.fetch_corporate_actions("PTT")
   ```

3. **Fetch multiple stocks concurrently** for better performance:
   ```python
   tasks = [get_corporate_actions(s) for s in symbols]
   results = await asyncio.gather(*tasks)
   ```

4. **Handle empty results** gracefully:
   ```python
   actions = await get_corporate_actions("XYZ")
   if not actions:
       print("No corporate actions found")
   ```

## Data Model Details

### Corporate Action Types

Common corporate action types you'll encounter:

- **XD** - Ex-Dividend (dividend announcements)
- **XM** - Ex-Meeting (shareholder meetings)
- **XR** - Ex-Rights (rights offerings)
- **XW** - Ex-Warrant (warrant exercises)

### Date Handling

All datetime fields are properly parsed and timezone-aware (UTC+7 for Thailand):

```python
action = actions[0]
print(f"XD Date: {action.x_date}")  # 2024-12-04 00:00:00+07:00
print(f"Payment Date: {action.payment_date}")  # 2025-02-06 00:00:00+07:00
```

### Optional Fields

Most fields are optional (`None` if not provided):

```python
# Check before using
if action.dividend is not None:
    print(f"Dividend: {action.dividend}")

if action.meeting_date:
    print(f"Meeting: {action.meeting_date}")
```

## Testing

Run the comprehensive test suite:

```bash
# Run all corporate action tests
uv pip run pytest tests/services/set/test_corporate_action.py -v

# Run specific test
uv pip run pytest tests/services/set/test_corporate_action.py::TestCorporateActionService::test_fetch_corporate_actions_success -v

# Run with coverage
uv pip run pytest tests/services/set/test_corporate_action.py --cov=settfex.services.set.stock.corporate_action --cov-report=html
```

## Troubleshooting

### Issue: HTTP 403/452 Errors

**Solution:** The service automatically handles bot detection via SessionManager. If you encounter persistent errors, try clearing the cache:

```bash
rm -rf ~/.settfex/cache/
```

### Issue: Empty Results

**Solution:** Some stocks may not have any corporate actions. This is normal:

```python
actions = await get_corporate_actions("XYZ")
if not actions:
    print("No corporate actions found for this stock")
```

### Issue: Invalid Symbol

**Solution:** Ensure the symbol is valid and listed on SET:

```python
from settfex.services.set import get_stock_list

# Verify symbol exists
stock_list = await get_stock_list()
stock = stock_list.get_symbol("AOT")
if stock:
    actions = await get_corporate_actions("AOT")
```

### Issue: Timeout Errors

**Solution:** Increase timeout and retry settings:

```python
from settfex.utils.data_fetcher import FetcherConfig

config = FetcherConfig(timeout=60, max_retries=5, retry_delay=2.0)
actions = await get_corporate_actions("AOT", config=config)
```

## Related Services

- **[Stock List Service](list.md)** - Get all stocks on SET/mai
- **[Highlight Data Service](highlight_data.md)** - Market metrics and valuations
- **[Stock Profile Service](profile_stock.md)** - Listing details and share structure
- **[Company Profile Service](profile_company.md)** - Full company information
- **[AsyncDataFetcher](../../utils/data_fetcher.md)** - Low-level async HTTP client

## API Endpoint

```
GET https://www.set.or.th/api/set/stock/{symbol}/corporate-action?lang={lang}
```

**Parameters:**
- `{symbol}` - Stock symbol (e.g., "AOT")
- `{lang}` - Language code ("en" or "th")

**Response:** JSON array of corporate action objects

## See Also

- [SET Website - Corporate Actions](https://www.set.or.th/)
- [Project Documentation](../../index.md)
- [Contributing Guide](../../../CONTRIBUTING.md)
