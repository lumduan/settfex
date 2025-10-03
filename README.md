# settfex

> Your friendly Python library for fetching Thai stock market data 🇹🇭

[![PyPI version](https://badge.fury.io/py/settfex.svg)](https://badge.fury.io/py/settfex)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**settfex** makes it super easy to get stock market data from the Stock Exchange of Thailand (SET) and Thailand Futures Exchange (TFEX). Whether you're building a trading bot, doing market analysis, or just curious about Thai stocks, we've got you covered!

## ⚡ Quick Install

```bash
pip install settfex
```

## 🎯 What Can You Do?

### 📋 Get Stock List

Want to see all stocks trading on SET? Easy!

```python
from settfex.services.set import get_stock_list

stock_list = await get_stock_list()
print(f"Found {stock_list.count} stocks!")

# Filter by market
set_stocks = stock_list.filter_by_market("SET")
mai_stocks = stock_list.filter_by_market("mai")
```

**👉 [Learn more about Stock Lists](docs/settfex/services/set/list.md)**

---

### 💰 Get Stock Highlight Data

Need market cap, P/E ratio, dividend yield? We got you!

```python
from settfex.services.set import Stock

stock = Stock("CPALL")
data = await stock.get_highlight_data()

print(f"Market Cap: {data.market_cap:,.0f} THB")
print(f"P/E Ratio: {data.pe_ratio}")
print(f"Dividend Yield: {data.dividend_yield}%")
```

**👉 [Learn more about Highlight Data](docs/settfex/services/set/highlight_data.md)**

---

### 📊 Get Stock Profile

Want to know when a company was listed? Its IPO price? Foreign ownership limits?

```python
from settfex.services.set import get_profile

profile = await get_profile("PTT")

print(f"Listed: {profile.listed_date}")
print(f"IPO Price: {profile.ipo} {profile.currency}")
print(f"Foreign Limit: {profile.percent_foreign_limit}%")
```

**👉 [Learn more about Stock Profiles](docs/settfex/services/set/profile_stock.md)**

---

### 🏢 Get Company Profile

Curious about company details, management, auditors, or ESG ratings?

```python
from settfex.services.set import get_company_profile

company = await get_company_profile("CPN")

print(f"Company: {company.name}")
print(f"Website: {company.url}")
print(f"CG Score: {company.cg_score}/5")
print(f"ESG Rating: {company.setesg_rating}")
print(f"Executives: {len(company.managements)}")
```

**👉 [Learn more about Company Profiles](docs/settfex/services/set/profile_company.md)**

---

### 📅 Get Corporate Actions

Track dividends, shareholder meetings, and other corporate events:

```python
from settfex.services.set import get_corporate_actions

actions = await get_corporate_actions("AOT")

for action in actions:
    if action.ca_type == "XD":
        print(f"Dividend: {action.dividend} {action.currency}")
        print(f"XD Date: {action.x_date}")
        print(f"Payment Date: {action.payment_date}")
    elif action.ca_type == "XM":
        print(f"Meeting: {action.meeting_type}")
        print(f"Agenda: {action.agenda}")
```

**👉 [Learn more about Corporate Actions](docs/settfex/services/set/corporate_action.md)**

---

### 👥 Get Shareholder Data

See who owns what! Get major shareholders, free float, and ownership distribution:

```python
from settfex.services.set import get_shareholder_data

data = await get_shareholder_data("MINT")

print(f"Total Shareholders: {data.total_shareholder:,}")
print(f"Free Float: {data.free_float.percent_free_float:.2f}%")

for sh in data.major_shareholders[:5]:
    print(f"{sh.sequence}. {sh.name}: {sh.percent_of_share:.2f}%")
```

**👉 [Learn more about Shareholder Data](docs/settfex/services/set/shareholder.md)**

---

## 🚀 Why settfex?

### ⚡ Blazing Fast

First request takes ~2 seconds (warming up). After that? **100ms!** That's 25x faster thanks to smart session caching.

**👉 [Learn about Session Caching](docs/settfex/utils/session_caching.md)**

### 🇹🇭 Thai Language Support

Full UTF-8 support for Thai characters. Company names, sectors, everything just works!

### 🔒 Type Safe

Everything is type-hinted and validated with Pydantic. Your IDE will love it!

### 🪵 Smart Logging

Beautiful logs with loguru. Debug issues easily or turn them off in production.

## 📚 Full Documentation

Want to dig deeper? Check out our detailed guides:

### Services

- **[Stock List Service](docs/settfex/services/set/list.md)** - Get all stocks on SET/mai
- **[Highlight Data Service](docs/settfex/services/set/highlight_data.md)** - Market metrics and valuations
- **[Stock Profile Service](docs/settfex/services/set/profile_stock.md)** - Listing details and share structure
- **[Company Profile Service](docs/settfex/services/set/profile_company.md)** - Full company information
- **[Corporate Action Service](docs/settfex/services/set/corporate_action.md)** - Dividends, meetings, and events

### Utilities

- **[AsyncDataFetcher](docs/settfex/utils/data_fetcher.md)** - Low-level async HTTP client
- **[Session Caching](docs/settfex/utils/session_caching.md)** - How we make things 25x faster

## 💡 Quick Example

Here's everything in action:

```python
import asyncio
from settfex.services.set import (
    get_stock_list,
    get_profile,
    get_company_profile,
    get_corporate_actions,
    Stock
)

async def analyze_stock(symbol: str):
    # Get basic info from stock list
    stock_list = await get_stock_list()
    stock_info = stock_list.get_symbol(symbol)

    if not stock_info:
        print(f"Stock {symbol} not found!")
        return

    print(f"📊 {stock_info.name_en} ({symbol})")
    print(f"Market: {stock_info.market}")
    print(f"Sector: {stock_info.sector}")

    # Get detailed metrics
    stock = Stock(symbol)
    highlight = await stock.get_highlight_data()

    print(f"\n💰 Valuation:")
    print(f"Market Cap: {highlight.market_cap:,.0f} THB")
    print(f"P/E Ratio: {highlight.pe_ratio}")
    print(f"Dividend Yield: {highlight.dividend_yield}%")

    # Get listing details
    profile = await get_profile(symbol)
    print(f"\n📅 Listed: {profile.listed_date}")
    print(f"IPO: {profile.ipo} {profile.currency}")

    # Get company info
    company = await get_company_profile(symbol)
    print(f"\n🏢 {company.name}")
    print(f"Website: {company.url}")
    print(f"ESG Rating: {company.setesg_rating}")

    # Get corporate actions
    actions = await get_corporate_actions(symbol)
    print(f"\n📅 Corporate Actions: {len(actions)}")
    for action in actions[:3]:  # Show first 3
        if action.ca_type == "XD":
            print(f"  Dividend: {action.dividend} {action.currency}")
        elif action.ca_type == "XM":
            print(f"  Meeting: {action.meeting_type}")

# Run it!
asyncio.run(analyze_stock("PTT"))
```

## 🛠️ Advanced Usage

Need more control? We've got you covered!

```python
from settfex.utils.data_fetcher import AsyncDataFetcher, FetcherConfig

# Custom configuration
config = FetcherConfig(
    timeout=60,           # Longer timeout
    max_retries=5,        # More retries
    browser_impersonate="safari17_0"  # Different browser
)

# Use with any service
from settfex.services.set.stock import StockHighlightDataService

service = StockHighlightDataService(config=config)
data = await service.fetch_highlight_data("CPALL")
```

**👉 [Learn more about AsyncDataFetcher](docs/settfex/utils/data_fetcher.md)**

## 🧪 Optional: Configure Logging

Want to see what's happening under the hood?

```python
from settfex.utils.logging import setup_logger

# Turn on detailed logs
setup_logger(level="DEBUG", log_file="logs/settfex.log")

# Now run your code - you'll see everything!
stock_list = await get_stock_list()
```

Great for debugging or monitoring in production.

## 🤝 Contributing

We'd love your help making settfex better! Here's how:

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/cool-new-thing`
3. Make your changes with proper type hints and tests
4. Run tests: `pytest`
5. Run linting: `ruff check .`
6. Commit: `git commit -m 'Add cool new thing'`
7. Push: `git push origin feature/cool-new-thing`
8. Open a Pull Request

## 📜 License

MIT License - feel free to use this in your projects!

## ⚠️ Disclaimer

This library is not officially affiliated with the Stock Exchange of Thailand or Thailand Futures Exchange. Use at your own risk for educational and informational purposes.

## 🙋 Need Help?

- 📖 Check the [detailed documentation](docs/settfex/)
- 🐛 Found a bug? [Open an issue](https://github.com/lumduan/settfex/issues)
- 💬 Have questions? Start a [discussion](https://github.com/lumduan/settfex/discussions)

---

Made with ❤️ for the Thai stock market community
