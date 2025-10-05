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

### 📜 Get NVDR Holder Data

Track Non-Voting Depository Receipt (NVDR) holders and their ownership:

```python
from settfex.services.set import get_nvdr_holder_data

data = await get_nvdr_holder_data("MINT")

print(f"Symbol: {data.symbol}")  # MINT-R
print(f"Total NVDR Holders: {data.total_shareholder:,}")

for holder in data.major_shareholders[:5]:
    print(f"{holder.sequence}. {holder.name}: {holder.percent_of_share:.2f}%")
```

**👉 [Learn more about NVDR Holder Data](docs/settfex/services/set/nvdr_holder.md)**

---

### 👔 Get Board of Directors

See who's running the show! Get board of directors and management information:

```python
from settfex.services.set import get_board_of_directors

directors = await get_board_of_directors("MINT")

for director in directors:
    positions = ", ".join(director.positions)
    print(f"{director.name}: {positions}")

# Find the Chairman
chairman = next((d for d in directors if "CHAIRMAN" in d.positions), None)
if chairman:
    print(f"Chairman: {chairman.name}")
```

**👉 [Learn more about Board of Directors](docs/settfex/services/set/board_of_director.md)**

---

### 📊 Get Trading Statistics

Track historical trading performance with comprehensive statistics across multiple time periods:

```python
from settfex.services.set import get_trading_stats

stats = await get_trading_stats("MINT")

# YTD performance
ytd = next(s for s in stats if s.period == "YTD")
print(f"YTD Performance: {ytd.percent_change:.2f}%")
print(f"Current Price: {ytd.close:.2f} THB")
print(f"P/E Ratio: {ytd.pe}, Market Cap: {ytd.market_cap:,.0f} THB")

# Compare different periods
for stat in stats:
    print(f"{stat.period}: {stat.close:.2f} THB ({stat.percent_change:+.2f}%)")
```

**👉 [Learn more about Trading Statistics](docs/settfex/services/set/trading_stat.md)**

---

### 📈 Get Price Performance

Compare stock performance against sector and market with comprehensive price change data:

```python
from settfex.services.set import get_price_performance

data = await get_price_performance("MINT")

# Stock performance
print(f"Stock: {data.stock.symbol}")
print(f"  YTD: {data.stock.ytd_percent_change:+.2f}%")
print(f"  P/E: {data.stock.pe_ratio}, P/B: {data.stock.pb_ratio}")

# Sector comparison
print(f"Sector ({data.sector.symbol}): {data.sector.ytd_percent_change:+.2f}%")

# Market comparison
print(f"Market ({data.market.symbol}): {data.market.ytd_percent_change:+.2f}%")
```

**👉 [Learn more about Price Performance](docs/settfex/services/set/price_performance.md)**

---

### 💰 Get Financial Statements

Fetch comprehensive financial data including balance sheet, income statement, and cash flow:

```python
from settfex.services.set import (
    get_balance_sheet,
    get_income_statement,
    get_cash_flow
)

# Balance sheet
balance_sheets = await get_balance_sheet("CPALL")
latest = balance_sheets[0]
print(f"Period: {latest.quarter} {latest.year}")
print(f"Total Assets: {latest.accounts[0].amount:,.0f}K")

# Income statement
income_statements = await get_income_statement("CPALL")
for stmt in income_statements[:3]:
    print(f"{stmt.quarter} {stmt.year}: {stmt.status}")

# Cash flow
cash_flows = await get_cash_flow("CPALL")
```

**👉 [Learn more about Financial Service](docs/settfex/services/set/financial.md)**

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
- **[Shareholder Service](docs/settfex/services/set/shareholder.md)** - Major shareholders and ownership data
- **[NVDR Holder Service](docs/settfex/services/set/nvdr_holder.md)** - NVDR holder information and ownership
- **[Board of Director Service](docs/settfex/services/set/board_of_director.md)** - Board of directors and management structure
- **[Trading Statistics Service](docs/settfex/services/set/trading_stat.md)** - Historical trading performance and metrics
- **[Price Performance Service](docs/settfex/services/set/price_performance.md)** - Stock, sector, and market price performance comparison
- **[Financial Service](docs/settfex/services/set/financial.md)** - Balance sheet, income statement, and cash flow data

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
    get_board_of_directors,
    get_trading_stats,
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

    # Get board of directors
    directors = await get_board_of_directors(symbol)
    print(f"\n👔 Board of Directors: {len(directors)}")
    chairman = next((d for d in directors if "CHAIRMAN" in d.positions), None)
    if chairman:
        print(f"  Chairman: {chairman.name}")

    # Get trading statistics
    stats = await get_trading_stats(symbol)
    ytd = next((s for s in stats if s.period == "YTD"), None)
    if ytd:
        print(f"\n📊 Trading Statistics (YTD):")
        print(f"  Performance: {ytd.percent_change:+.2f}%")
        print(f"  Volume: {ytd.total_volume:,.0f} shares")
        print(f"  Turnover: {ytd.turnover_ratio:.2f}%")

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
