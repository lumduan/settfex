# AsyncDataFetcher - Unicode/Thai Data Fetcher

## Overview

`AsyncDataFetcher` is a specialized async HTTP client designed for fetching data from SET (Stock Exchange of Thailand) and TFEX (Thailand Futures Exchange) APIs. It provides robust Unicode/Thai language support, browser impersonation for bot detection bypass, and randomized session management.

## Key Features

- **Async-First Design**: Built on `asyncio` with proper async/await patterns
- **Unicode/Thai Support**: Proper encoding handling for Thai characters (UTF-8 with latin1 fallback)
- **Browser Impersonation**: Uses curl_cffi to impersonate modern browsers (Chrome, Safari, Edge)
- **Randomized Cookies**: Generates realistic cookie strings to avoid bot detection
- **Automatic Retries**: Exponential backoff retry mechanism for failed requests
- **Type Safety**: Full type hints and Pydantic validation for all data structures
- **Comprehensive Logging**: Detailed logging via loguru for debugging and monitoring

## Architecture

The module consists of three main components:

1. **FetcherConfig**: Pydantic model for configuration management
2. **FetchResponse**: Pydantic model for response data
3. **AsyncDataFetcher**: Main async client class

### Design Principles

- **Async Compliance**: Synchronous curl_cffi requests wrapped with `asyncio.to_thread`
- **Session Management**: Proper resource cleanup via context managers
- **Error Handling**: Graceful degradation with detailed error logging
- **Unicode First**: UTF-8 encoding by default with fallback mechanisms

## Installation

The module is included with `settfex` and requires the following dependencies:

```bash
uv pip install curl-cffi>=0.6.0 pydantic>=2.0.0 loguru>=0.7.0
```

## Quick Start

### Basic Usage

```python
import asyncio
from settfex.utils.data_fetcher import AsyncDataFetcher

async def main():
    async with AsyncDataFetcher() as fetcher:
        # Fetch HTML/text content
        response = await fetcher.fetch("https://www.set.or.th/th/market/product/stock/quote")
        print(f"Status: {response.status_code}")
        print(f"Content: {response.text[:200]}")  # First 200 chars

asyncio.run(main())
```

### Fetch JSON Data

```python
async def fetch_stock_data():
    async with AsyncDataFetcher() as fetcher:
        data = await fetcher.fetch_json(
            "https://api.example.com/stocks/PTT"
        )
        print(f"Symbol: {data['symbol']}")
        print(f"Price: {data['price']}")
```

### Custom Configuration

```python
from settfex.utils.data_fetcher import AsyncDataFetcher, FetcherConfig

config = FetcherConfig(
    browser_impersonate="safari17_0",  # Use Safari instead of Chrome
    timeout=60,                        # 60 second timeout
    max_retries=5,                     # Retry up to 5 times
    retry_delay=2.0,                   # 2 second base delay
    user_agent="MyApp/1.0"            # Custom user agent
)

async with AsyncDataFetcher(config=config) as fetcher:
    response = await fetcher.fetch("https://example.com")
```

## API Reference

### Static Methods for SET Services

#### `get_set_api_headers(referer: str = "https://www.set.or.th/en/home") -> dict[str, str]`

Get optimized headers for SET (Stock Exchange of Thailand) API requests.

These headers are based on successful browser requests and include all necessary Incapsula/Imperva bot detection bypass headers.

**Parameters:**
- `referer: str` - Referer URL (default: SET home page)

**Returns:**
- `dict[str, str]` - Dictionary of HTTP headers optimized for SET API

**Example:**
```python
from settfex.utils.data_fetcher import AsyncDataFetcher

# Get SET API headers (can be used by any SET service)
headers = AsyncDataFetcher.get_set_api_headers()

async with AsyncDataFetcher() as fetcher:
    response = await fetcher.fetch(url, headers=headers)
```

#### `generate_incapsula_cookies() -> str`

Generate Incapsula-aware randomized cookies for SET API requests.

Creates cookies that mimic legitimate browser sessions with Incapsula bot protection, including visitor IDs, session tokens, and load balancer identifiers.

**Returns:**
- `str` - Cookie string with Incapsula-compatible randomized values

**Example:**
```python
from settfex.utils.data_fetcher import AsyncDataFetcher

# Generate Incapsula cookies
cookies = AsyncDataFetcher.generate_incapsula_cookies()

# Use with headers
headers = AsyncDataFetcher.get_set_api_headers()

async with AsyncDataFetcher() as fetcher:
    response = await fetcher.fetch(
        url,
        headers=headers,
        cookies=cookies,
        use_random_cookies=False
    )
```

**Note:**
Generated cookies may be blocked by Incapsula. For production use, real authenticated browser session cookies are recommended.

### FetcherConfig

Configuration model for `AsyncDataFetcher`.

**Fields:**
- `browser_impersonate: str = "chrome120"` - Browser to impersonate
- `timeout: int = 30` - Request timeout in seconds (1-300)
- `max_retries: int = 3` - Maximum retry attempts (0-10)
- `retry_delay: float = 1.0` - Base retry delay in seconds (0.1-30.0)
- `user_agent: Optional[str] = None` - Custom User-Agent (auto-generated if None)

**Supported Browsers:**
- Chrome: `chrome99`, `chrome100`, `chrome101`, `chrome104`, `chrome107`, `chrome110`, `chrome116`, `chrome119`, `chrome120`
- Safari: `safari15_3`, `safari15_5`, `safari17_0`, `safari17_2_1`
- Edge: `edge99`, `edge101`

**Example:**
```python
config = FetcherConfig(
    browser_impersonate="chrome120",
    timeout=30,
    max_retries=3,
    retry_delay=1.0
)
```

### FetchResponse

Response model containing fetched data and metadata.

**Fields:**
- `status_code: int` - HTTP status code
- `content: bytes` - Raw response content
- `text: str` - Response text decoded as UTF-8
- `headers: dict[str, str]` - Response headers
- `url: str` - Final URL after redirects
- `elapsed: float` - Request duration in seconds
- `encoding: str = "utf-8"` - Response encoding used

**Example:**
```python
response = await fetcher.fetch("https://example.com")
print(f"Status: {response.status_code}")
print(f"Size: {len(response.content)} bytes")
print(f"Time: {response.elapsed:.2f}s")
```

### AsyncDataFetcher

Main async client for fetching data.

#### Methods

##### `__init__(config: Optional[FetcherConfig] = None)`

Initialize the fetcher.

**Parameters:**
- `config` - Optional configuration (uses defaults if None)

**Example:**
```python
fetcher = AsyncDataFetcher()
# or with custom config
fetcher = AsyncDataFetcher(config=FetcherConfig(timeout=60))
```

##### `async fetch(url: str, headers: Optional[dict[str, str]] = None, cookies: Optional[str] = None, use_random_cookies: bool = True) -> FetchResponse`

Fetch data from a URL asynchronously.

**Parameters:**
- `url` - URL to fetch
- `headers` - Optional custom headers (merged with defaults)
- `cookies` - Optional custom cookies (overrides random cookies)
- `use_random_cookies` - Generate random cookies (default: True)

**Returns:**
- `FetchResponse` with status, content, and metadata

**Raises:**
- `Exception` if request fails after all retries

**Example:**
```python
# Basic fetch
response = await fetcher.fetch("https://www.set.or.th")

# With custom headers
response = await fetcher.fetch(
    "https://api.example.com",
    headers={"X-API-Key": "secret"}
)

# With custom cookies
response = await fetcher.fetch(
    "https://example.com",
    cookies="session=abc123; user=test"
)

# Disable random cookies
response = await fetcher.fetch(
    "https://example.com",
    use_random_cookies=False
)
```

##### `async fetch_json(url: str, headers: Optional[dict[str, str]] = None, cookies: Optional[str] = None, use_random_cookies: bool = True) -> Any`

Fetch and parse JSON data.

**Parameters:**
- Same as `fetch()`

**Returns:**
- Parsed JSON data (dict, list, or primitive)

**Raises:**
- `Exception` if request fails
- `json.JSONDecodeError` if response is not valid JSON

**Example:**
```python
data = await fetcher.fetch_json("https://api.example.com/stocks")
for stock in data["stocks"]:
    print(f"{stock['symbol']}: {stock['price']}")
```

##### `_generate_random_cookies() -> str`

Generate randomized cookies for session management.

**Returns:**
- Cookie string in format "key1=value1; key2=value2; ..."

**Generated Cookies:**
- `_ga`, `_gid`, `_gat` - Google Analytics
- `PHPSESSID` - PHP session ID
- `_fbp` - Facebook pixel
- `tracking_id` - Custom tracking
- `user_pref` - User preferences
- `lang=th` - Thai language preference
- `accept_cookies=1` - Cookie consent

**Example:**
```python
cookies = fetcher._generate_random_cookies()
# "_ga=GA1.2.123456789.1234567890; PHPSESSID=abc123...; lang=th; ..."
```

##### `_make_sync_request(url: str, headers: dict[str, str]) -> Any`

Internal method to make synchronous HTTP request.

**Note:** This method is wrapped by `asyncio.to_thread` for async compliance.

**Parameters:**
- `url` - URL to fetch
- `headers` - HTTP headers

**Returns:**
- Response object from curl_cffi

**Raises:**
- `Exception` if request fails

## Usage Examples

### Example 1: Fetch SET Stock Quote Page

```python
import asyncio
from settfex.utils.data_fetcher import AsyncDataFetcher

async def fetch_set_quote():
    """Fetch SET stock quote page with Thai content."""
    async with AsyncDataFetcher() as fetcher:
        response = await fetcher.fetch(
            "https://www.set.or.th/th/market/product/stock/quote"
        )

        # Check if Thai text is present
        if "ตลาดหลักทรัพย์" in response.text:
            print("✓ Thai text decoded correctly")

        print(f"Status: {response.status_code}")
        print(f"Size: {len(response.content):,} bytes")
        print(f"Time: {response.elapsed:.2f}s")

asyncio.run(fetch_set_quote())
```

### Example 2: Fetch JSON Data with Retry

```python
async def fetch_with_retry():
    """Fetch JSON data with custom retry settings."""
    from settfex.utils.data_fetcher import FetcherConfig

    config = FetcherConfig(
        max_retries=5,
        retry_delay=2.0,
        timeout=30
    )

    async with AsyncDataFetcher(config=config) as fetcher:
        try:
            data = await fetcher.fetch_json(
                "https://api.example.com/market/data"
            )
            print(f"Received {len(data)} items")
        except Exception as e:
            print(f"Failed after retries: {e}")

asyncio.run(fetch_with_retry())
```

### Example 3: Custom Headers and Cookies

```python
async def fetch_with_auth():
    """Fetch data with authentication."""
    async with AsyncDataFetcher() as fetcher:
        response = await fetcher.fetch(
            "https://api.example.com/private/data",
            headers={
                "Authorization": "Bearer token123",
                "X-API-Version": "v2"
            },
            cookies="session=abc123; auth=xyz789"
        )

        print(f"Authenticated request: {response.status_code}")

asyncio.run(fetch_with_auth())
```

### Example 4: Handle Thai Language JSON

```python
async def fetch_thai_json():
    """Fetch and parse JSON with Thai characters."""
    async with AsyncDataFetcher() as fetcher:
        data = await fetcher.fetch_json(
            "https://api.example.com/stocks/th"
        )

        # Thai characters are properly decoded
        for stock in data:
            symbol = stock["symbol"]
            name_th = stock["name_th"]  # Thai name
            print(f"{symbol}: {name_th}")

asyncio.run(fetch_thai_json())
```

### Example 5: Multiple Concurrent Requests

```python
async def fetch_multiple_stocks():
    """Fetch data for multiple stocks concurrently."""
    symbols = ["PTT", "KBANK", "AOT", "CPALL", "BBL"]

    async with AsyncDataFetcher() as fetcher:
        tasks = [
            fetcher.fetch_json(f"https://api.example.com/stocks/{symbol}")
            for symbol in symbols
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                print(f"{symbol}: Error - {result}")
            else:
                print(f"{symbol}: {result['price']}")

asyncio.run(fetch_multiple_stocks())
```

## Error Handling

The fetcher implements comprehensive error handling:

### Automatic Retries

Failed requests are automatically retried with exponential backoff:

```python
# Configure retry behavior
config = FetcherConfig(
    max_retries=3,      # Try up to 4 times total (1 + 3 retries)
    retry_delay=1.0     # Start with 1s, then 2s, then 4s
)

async with AsyncDataFetcher(config=config) as fetcher:
    # Will retry automatically on failure
    response = await fetcher.fetch("https://example.com")
```

**Retry delays:**
- Attempt 1: Immediate
- Attempt 2: 1.0s delay (retry_delay × 2^0)
- Attempt 3: 2.0s delay (retry_delay × 2^1)
- Attempt 4: 4.0s delay (retry_delay × 2^2)

### Unicode Decode Fallback

If UTF-8 decoding fails, the fetcher automatically tries latin1:

```python
# Handles both UTF-8 and problematic encodings
response = await fetcher.fetch("https://example.com")
print(f"Encoding used: {response.encoding}")  # "utf-8" or "latin1"
```

### Exception Handling

```python
async def safe_fetch():
    async with AsyncDataFetcher() as fetcher:
        try:
            response = await fetcher.fetch("https://example.com")
            return response.text
        except Exception as e:
            print(f"Fetch failed: {e}")
            return None
```

## Logging

The module uses loguru for comprehensive logging:

### Configure Logging

```python
from loguru import logger
from settfex.utils.logging import setup_logger

# Configure logging level and output
setup_logger(level="DEBUG", log_file="logs/fetcher.log")

# Use the fetcher (logs will be captured)
async with AsyncDataFetcher() as fetcher:
    response = await fetcher.fetch("https://example.com")
```

### Log Levels

- **DEBUG**: Detailed request/response information
- **INFO**: Successful operations with timing
- **WARNING**: Retry attempts and fallback behavior
- **ERROR**: Failed requests and exceptions

### Example Log Output

```
2025-10-01 10:30:15.123 | INFO     | AsyncDataFetcher initialized with browser=chrome120, timeout=30s
2025-10-01 10:30:15.124 | DEBUG    | Generated cookies: 245 chars
2025-10-01 10:30:15.125 | DEBUG    | Making sync request to https://www.set.or.th
2025-10-01 10:30:15.789 | INFO     | Fetch successful: url=https://www.set.or.th, status=200, elapsed=0.66s, size=45123 bytes
```

## Performance Considerations

### Async Operations

All I/O operations are async-compliant:

```python
# Run multiple fetches concurrently
async def fetch_all():
    async with AsyncDataFetcher() as fetcher:
        results = await asyncio.gather(
            fetcher.fetch("https://www.set.or.th"),
            fetcher.fetch("https://www.tfex.co.th"),
            fetcher.fetch("https://api.example.com")
        )
        return results
```

### Connection Reuse

Use context manager for efficient resource management:

```python
# Good: Context manager handles cleanup
async with AsyncDataFetcher() as fetcher:
    for url in urls:
        response = await fetcher.fetch(url)
        process(response)

# Avoid: Creates new fetcher for each request
for url in urls:
    async with AsyncDataFetcher() as fetcher:
        response = await fetcher.fetch(url)
```

### Timeout Configuration

Set appropriate timeouts based on your use case:

```python
# Fast requests (APIs)
fast_config = FetcherConfig(timeout=10)

# Slow requests (full pages)
slow_config = FetcherConfig(timeout=60)

# Very slow requests (large downloads)
large_config = FetcherConfig(timeout=300)
```

## Testing

The module includes comprehensive test coverage:

```bash
# Run all tests
uv pip run python -m pytest tests/utils/test_data_fetcher.py -v

# Run specific test
uv pip run python -m pytest tests/utils/test_data_fetcher.py::TestAsyncDataFetcher::test_fetch_with_thai_content -v

# Run with coverage
uv pip run python -m pytest tests/utils/test_data_fetcher.py --cov=settfex.utils.data_fetcher
```

## Integration with SET/TFEX Services

The fetcher is designed to be used by SET and TFEX service modules:

```python
from settfex.utils.data_fetcher import AsyncDataFetcher, FetcherConfig

class SETClient:
    """SET API client using AsyncDataFetcher."""

    def __init__(self):
        self.config = FetcherConfig(
            browser_impersonate="chrome120",
            timeout=30
        )

    async def get_stock_quote(self, symbol: str):
        """Get stock quote for a symbol."""
        async with AsyncDataFetcher(self.config) as fetcher:
            data = await fetcher.fetch_json(
                f"https://api.set.or.th/stock/{symbol}"
            )
            return data
```

## Troubleshooting

### Issue: Thai characters appear as ��

**Solution:** Ensure you're using the `text` field, not manually decoding `content`:

```python
# Correct
response = await fetcher.fetch(url)
thai_text = response.text  # Properly decoded

# Incorrect
thai_text = response.content.decode("ascii")  # Will fail
```

### Issue: Requests getting blocked

**Solution:** Try different browser impersonation:

```python
config = FetcherConfig(browser_impersonate="safari17_0")
```

### Issue: Timeout errors

**Solution:** Increase timeout and retries:

```python
config = FetcherConfig(
    timeout=60,
    max_retries=5,
    retry_delay=2.0
)
```

### Issue: JSON parsing fails

**Solution:** Verify the response is actually JSON:

```python
try:
    data = await fetcher.fetch_json(url)
except json.JSONDecodeError:
    # Fallback to text
    response = await fetcher.fetch(url)
    print(f"Response is not JSON: {response.text[:200]}")
```

## Best Practices

1. **Always use context manager** for proper resource cleanup
2. **Configure retries** based on API reliability
3. **Use fetch_json()** for JSON endpoints instead of manual parsing
4. **Enable logging** during development for debugging
5. **Set appropriate timeouts** based on expected response times
6. **Handle exceptions** gracefully with try/except blocks
7. **Use concurrent fetching** with asyncio.gather() for multiple requests
8. **Test Thai/Unicode** handling with sample data

## See Also

- [HTTP Utilities](http.md) - Lower-level HTTP client
- [Logging Utilities](logging.md) - Logging configuration
- [SET Client](../../services/set/client.md) - SET API client implementation
- [TFEX Client](../../services/tfex/client.md) - TFEX API client implementation
