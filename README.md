# settfex

> Fetch real-time and historical data from the Stock Exchange of Thailand (SET) and Thailand Futures Exchange (TFEX)

[![PyPI version](https://badge.fury.io/py/settfex.svg)](https://badge.fury.io/py/settfex)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- **SET Data**: Access real-time and historical stock data from the Stock Exchange of Thailand
- **TFEX Data**: Fetch futures and derivatives data from the Thailand Futures Exchange
- **Modern Python**: Built with Python 3.11+ using modern async patterns
- **Type Safe**: Full type hints and runtime validation with Pydantic
- **Easy to Use**: Simple, intuitive API for fetching market data
- **Advanced HTTP**: Built with curl_cffi for browser-like requests with impersonation
- **Smart Logging**: Integrated loguru for beautiful, powerful logging
- **Unicode Support**: Full Thai language support with proper UTF-8 handling
- **Session Caching**: Disk-based session caching with 25x performance boost after first request
- **Auto-Retry**: Automatic session warmup and retry on bot detection

## Installation

```bash
pip install settfex
```

## Quick Start

### Using the Async Data Fetcher (Low-Level)

```python
import asyncio
from settfex.utils.data_fetcher import AsyncDataFetcher

async def main():
    # Basic usage with defaults - SessionManager handles cookies automatically
    async with AsyncDataFetcher() as fetcher:
        # Fetch HTML/text content
        response = await fetcher.fetch("https://www.set.or.th/th/market/product/stock/quote")
        print(f"Status: {response.status_code}")
        print(f"Thai text: {response.text[:200]}")

        # Fetch JSON data with SET-optimized headers
        headers = AsyncDataFetcher.get_set_api_headers()
        data = await fetcher.fetch_json(
            "https://www.set.or.th/api/set/stock/list",
            headers=headers
        )
        print(f"Data: {data}")

asyncio.run(main())
```

### Using SET Stock Services (High-Level)

```python
import asyncio
from settfex.services.set import Stock, get_stock_list
from settfex.utils.logging import setup_logger

# Optional: Configure logging
setup_logger(level="INFO", log_file="logs/settfex.log")

async def main():
    # Fetch complete stock list from SET
    stock_list = await get_stock_list()

    print(f"Total stocks: {stock_list.count}")

    # Filter by market
    set_stocks = stock_list.filter_by_market("SET")
    mai_stocks = stock_list.filter_by_market("mai")
    print(f"SET market: {len(set_stocks)} stocks")
    print(f"mai market: {len(mai_stocks)} stocks")

    # Get specific stock
    ptt = stock_list.get_symbol("PTT")
    if ptt:
        print(f"{ptt.symbol}: {ptt.name_en} ({ptt.name_th})")

    # Fetch highlight data for individual stock
    # SessionManager handles automatic cookie warmup and caching (25x faster after first run!)
    stock = Stock("CPALL")
    highlight = await stock.get_highlight_data()
    print(f"\n{highlight.symbol} Highlight Data:")
    print(f"Market Cap: {highlight.market_cap:,.0f} THB")
    print(f"P/E Ratio: {highlight.pe_ratio}")
    print(f"P/B Ratio: {highlight.pb_ratio}")
    print(f"Dividend Yield: {highlight.dividend_yield}%")

    # Fetch stock profile for detailed listing information
    from settfex.services.set import get_profile

    profile = await get_profile("PTT")
    print(f"\n{profile.name} ({profile.symbol})")
    print(f"Sector: {profile.sector_name}")
    print(f"Industry: {profile.industry_name}")
    print(f"Listed Date: {profile.listed_date}")
    print(f"IPO Price: {profile.ipo} {profile.currency}")

    # Fetch company profile for comprehensive company information
    from settfex.services.set import get_company_profile

    company = await get_company_profile("CPN")
    print(f"\n{company.name} ({company.symbol})")
    print(f"Website: {company.url}")
    print(f"CG Score: {company.cg_score}/5")
    print(f"ESG Rating: {company.setesg_rating}")
    print(f"CAC Certified: {'Yes' if company.cac_flag else 'No'}")
    print(f"Management: {len(company.managements)} executives")

asyncio.run(main())
```

### Using SET/TFEX Clients (High-Level)

```python
from settfex.services.set import SETClient
from settfex.services.tfex import TFEXClient
from settfex.utils.logging import setup_logger

# Optional: Configure logging
setup_logger(level="DEBUG", log_file="logs/settfex.log")

# Fetch SET real-time data
set_client = SETClient()
# Your code here

# Fetch TFEX real-time data
tfex_client = TFEXClient()
# Your code here
```

### Dependencies

settfex uses modern, powerful libraries:

- **curl_cffi**: Advanced HTTP client with browser impersonation for robust API requests
- **loguru**: Beautiful, powerful logging with colors and automatic formatting
- **pydantic**: Runtime validation and settings management with type safety
- **diskcache**: Persistent disk-based caching for 25x performance boost

## Documentation

For detailed documentation, please see:
- [AsyncDataFetcher Guide](docs/settfex/utils/data_fetcher.md) - Low-level async HTTP client with session management
- [Session Caching Guide](docs/session_caching.md) - Understanding session cache for 25x performance boost
- [SET API Protection Note](docs/settfex/services/set/API_PROTECTION_NOTE.md) - Important bot detection bypass information

## Development

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/settfex.git
cd settfex

# Install dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest
```

### Code Quality

```bash
# Run linting
ruff check .

# Run type checking
mypy settfex
```

## Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes with proper type hints and tests
4. Run tests and linting (`pytest` and `ruff check .`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

For detailed development guidelines, see the project structure and architecture notes in `CLAUDE.md`.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This library is not officially affiliated with the Stock Exchange of Thailand or Thailand Futures Exchange. Use at your own risk.
