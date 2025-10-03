# Board of Director Service

## Overview

The Board of Director Service provides async methods to fetch board of directors and management information for individual stock symbols from the Stock Exchange of Thailand (SET). It retrieves information about directors, their positions, and management structure.

## Quick Start

```python
import asyncio
from settfex.services.set import get_board_of_directors

async def main():
    # Fetch board of directors for a stock
    directors = await get_board_of_directors("MINT")

    # Display directors and their positions
    for director in directors:
        positions = ", ".join(director.positions)
        print(f"{director.name}: {positions}")

asyncio.run(main())
```

## Features

- **Full Type Safety**: Complete Pydantic models for director information
- **Dual Language Support**: Fetch data in English ('en') or Thai ('th')
- **Input Normalization**: Automatic symbol uppercase and language validation
- **Async-First**: Built on AsyncDataFetcher for optimal performance
- **Automatic Session Management**: Uses SessionManager for bot detection bypass (25x faster after first request)
- **Thai/Unicode Support**: Proper handling of Thai director names

## API Reference

### Convenience Function

#### `get_board_of_directors(symbol, lang='en', config=None)`

Quick one-line access to board of directors data.

**Parameters:**
- `symbol: str` - Stock symbol (e.g., "MINT", "PTT", "cpall")
- `lang: str` - Language for response ('en' or 'th', default: 'en')
- `config: FetcherConfig | None` - Optional fetcher configuration

**Returns:**
- `list[Director]` - List of Director objects with name and positions

**Example:**
```python
from settfex.services.set import get_board_of_directors

# English (default)
directors = await get_board_of_directors("MINT")

# Thai language
directors_th = await get_board_of_directors("MINT", lang="th")

# Custom configuration
from settfex.utils.data_fetcher import FetcherConfig

config = FetcherConfig(timeout=60, max_retries=5)
directors = await get_board_of_directors("MINT", config=config)
```

### BoardOfDirectorService Class

Main service class for fetching board of directors data.

#### Constructor

```python
BoardOfDirectorService(config: FetcherConfig | None = None)
```

**Parameters:**
- `config: FetcherConfig | None` - Optional fetcher configuration (uses defaults if None)

**Example:**
```python
from settfex.services.set.stock import BoardOfDirectorService
from settfex.utils.data_fetcher import FetcherConfig

# Default configuration (uses SessionManager automatically)
service = BoardOfDirectorService()

# Custom configuration
config = FetcherConfig(timeout=60, max_retries=5)
service = BoardOfDirectorService(config=config)
```

#### Methods

##### `fetch_board_of_directors(symbol, lang='en')`

Fetch board of directors for a specific stock symbol.

**Parameters:**
- `symbol: str` - Stock symbol (e.g., "MINT", "PTT", "cpall")
- `lang: str` - Language for response ('en' or 'th', default: 'en')

**Returns:**
- `list[Director]` - List of Director objects with validated data

**Raises:**
- `ValueError` - If symbol is empty or language is invalid
- `Exception` - If request fails or response cannot be parsed

**Example:**
```python
service = BoardOfDirectorService()

# Fetch board of directors
directors = await service.fetch_board_of_directors("MINT", lang="en")

for director in directors:
    print(f"Name: {director.name}")
    print(f"Positions: {', '.join(director.positions)}")
    print()
```

##### `fetch_board_of_directors_raw(symbol, lang='en')`

Fetch board of directors as raw list of dictionaries without Pydantic validation.

Useful for debugging or when you need the raw API response.

**Parameters:**
- `symbol: str` - Stock symbol (e.g., "MINT", "PTT", "cpall")
- `lang: str` - Language for response ('en' or 'th', default: 'en')

**Returns:**
- `list[dict[str, Any]]` - Raw list of dictionaries from API

**Example:**
```python
service = BoardOfDirectorService()

raw_data = await service.fetch_board_of_directors_raw("MINT")
print(f"Found {len(raw_data)} directors")
for director in raw_data:
    print(director.keys())  # dict_keys(['name', 'positions'])
```

## Data Models

### Director

Model for individual board member/director information.

**Fields:**
- `name: str` - Director's full name
- `positions: list[str]` - List of positions held by the director

**Example:**
```python
directors = await get_board_of_directors("MINT")

for director in directors:
    print(f"Director: {director.name}")

    if len(director.positions) == 1:
        print(f"Position: {director.positions[0]}")
    else:
        print(f"Positions: {', '.join(director.positions)}")

    # Check for specific positions
    if "CHAIRMAN" in director.positions:
        print("  → This is the Chairman")
    if "CEO" in director.positions or "CHIEF EXECUTIVE OFFICER" in director.positions:
        print("  → This is the CEO")
```

## Usage Examples

### Basic Usage

```python
from settfex.services.set import get_board_of_directors

# Fetch board of directors
directors = await get_board_of_directors("MINT")

print(f"Total Directors: {len(directors)}")
for i, director in enumerate(directors, 1):
    positions = ", ".join(director.positions)
    print(f"{i}. {director.name}")
    print(f"   {positions}")
```

### Analyzing Board Structure

```python
directors = await get_board_of_directors("MINT")

# Find chairman
chairman = next(
    (d for d in directors if "CHAIRMAN" in d.positions),
    None
)
if chairman:
    print(f"Chairman: {chairman.name}")

# Find CEO
ceo = next(
    (d for d in directors
     if any("CEO" in pos or "CHIEF EXECUTIVE" in pos for pos in d.positions)),
    None
)
if ceo:
    print(f"CEO: {ceo.name}")

# Find independent directors
independent_directors = [
    d for d in directors
    if any("INDEPENDENT" in pos for pos in d.positions)
]
print(f"Independent Directors: {len(independent_directors)}")

# Directors with multiple positions
multi_position_directors = [d for d in directors if len(d.positions) > 1]
print(f"Directors with multiple positions: {len(multi_position_directors)}")
```

### Thai Language Support

```python
# Fetch in Thai
directors_th = await get_board_of_directors("MINT", lang="th")

print("กรรมการบริษัท:")
for director in directors_th:
    print(f"ชื่อ: {director.name}")
    print(f"ตำแหน่ง: {', '.join(director.positions)}")
    print()
```

### Comparing Multiple Companies

```python
from settfex.services.set import get_board_of_directors

symbols = ["PTT", "CPALL", "AOT", "KBANK", "MINT"]

for symbol in symbols:
    directors = await get_board_of_directors(symbol)

    # Find chairman
    chairman = next(
        (d for d in directors if "CHAIRMAN" in d.positions),
        None
    )

    print(f"\n{symbol}:")
    print(f"  Board Size: {len(directors)}")
    if chairman:
        print(f"  Chairman: {chairman.name[:50]}")  # Truncate long names

    # Count independent directors
    independent_count = sum(
        1 for d in directors
        if any("INDEPENDENT" in pos for pos in d.positions)
    )
    print(f"  Independent Directors: {independent_count}")
```

### Finding Specific Positions

```python
directors = await get_board_of_directors("MINT")

# Group directors by position type
position_groups = {}
for director in directors:
    for position in director.positions:
        if position not in position_groups:
            position_groups[position] = []
        position_groups[position].append(director.name)

# Display results
for position, names in sorted(position_groups.items()):
    print(f"\n{position}:")
    for name in names:
        print(f"  - {name}")
```

### Error Handling

```python
from settfex.services.set import get_board_of_directors

try:
    # Fetch board of directors
    directors = await get_board_of_directors("MINT")
    print(f"Successfully fetched {len(directors)} directors")

except ValueError as e:
    # Handle invalid input
    print(f"Invalid input: {e}")

except Exception as e:
    # Handle API errors
    print(f"Failed to fetch data: {e}")
```

## Performance Notes

The board of director service uses SessionManager for automatic cookie handling and bot detection bypass:

- **First request**: ~3-5 seconds (includes session warmup)
- **Subsequent requests**: ~100-200ms (25x faster with cached session)
- **Session cache TTL**: 1 hour (automatically refreshed)

No manual cookie management required - SessionManager handles everything automatically.

## Language Support

The service supports both English and Thai languages:

```python
# English (default)
directors_en = await get_board_of_directors("MINT", lang="en")

# Thai
directors_th = await get_board_of_directors("MINT", lang="th")

# Alternative Thai inputs (all normalized to 'th')
directors = await get_board_of_directors("MINT", lang="thai")
directors = await get_board_of_directors("MINT", lang="tha")
```

## Symbol Normalization

Stock symbols are automatically normalized to uppercase:

```python
# All of these work identically
directors1 = await get_board_of_directors("MINT")
directors2 = await get_board_of_directors("mint")
directors3 = await get_board_of_directors("MiNt")
directors4 = await get_board_of_directors("  mint  ")  # Whitespace trimmed

# All return the same data for "MINT"
```

## Common Position Titles

The API returns various position titles. Here are some common ones:

**English:**
- `CHAIRMAN` - Chairman of the Board
- `DIRECTOR` - Board Director
- `INDEPENDENT DIRECTOR` - Independent Board Director
- `CEO` / `CHIEF EXECUTIVE OFFICER` - Chief Executive Officer
- `GROUP CHIEF EXECUTIVE OFFICER` - Group CEO
- `EXECUTIVE DIRECTOR` - Executive Director
- `NON-EXECUTIVE DIRECTOR` - Non-Executive Director

**Thai:**
- `ประธานกรรมการ` - Chairman
- `กรรมการ` - Director
- `กรรมการอิสระ` - Independent Director
- `กรรมการผู้จัดการใหญ่` - Managing Director/CEO
- `กรรมการผู้จัดการใหญ่กลุ่มบริษัท` - Group CEO

## Related Services

- **[Company Profile Service](profile_company.md)**: Detailed company information including governance
- **[Shareholder Service](shareholder.md)**: Major shareholders and ownership data
- **[Stock Profile Service](profile_stock.md)**: Stock and listing information

## API Endpoint

```
GET https://www.set.or.th/api/set/company/{symbol}/board-of-director?lang={lang}
```

**Parameters:**
- `symbol`: Stock symbol (uppercase)
- `lang`: Language code ('en' or 'th')

**Response:** JSON array of director objects

**Example Response:**
```json
[
    {
        "name": "Mr. WILLIAM ELLWOOD HEINECKE",
        "positions": ["CHAIRMAN"]
    },
    {
        "name": "Mr. EMMANUEL JUDE DILLIPRAJ RAJAKARIER",
        "positions": ["GROUP CHIEF EXECUTIVE OFFICER", "DIRECTOR"]
    }
]
```

## See Also

- [Stock List Service](list.md) - Complete list of all SET stocks
- [Data Fetcher Utilities](../../utils/data_fetcher.md) - HTTP client and configuration
- [Session Manager](../../utils/session_manager.md) - Automatic session and cookie management
