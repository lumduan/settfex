# Financial Service - Balance Sheet, Income Statement, and Cash Flow Data

## Overview

The Financial Service provides async methods to fetch comprehensive financial statement data from the Stock Exchange of Thailand (SET) for individual stock symbols. This service retrieves balance sheet, income statement, and cash flow data for multiple reporting periods.

## Features

- **Full Type Safety**: Complete Pydantic models with field validation
- **Dual Language Support**: Fetch data in English ('en') or Thai ('th')
- **Multiple Statements**: Balance sheet, income statement, and cash flow
- **Historical Data**: Returns multiple periods for trend analysis
- **Quarter Codes**: Supports '6M' (half year) and 'Q9' (full year) periods
- **Input Normalization**: Automatic symbol uppercase and language validation
- **Async-First**: Built on AsyncDataFetcher for optimal performance
- **Raw Data Access**: Methods to return both structured and raw JSON data

## Installation

The Financial Service is included with `settfex`:

```bash
pip install settfex
```

## Quick Start

### Fetch Balance Sheet

```python
import asyncio
from settfex.services.set import get_balance_sheet

async def main():
    # Fetch balance sheet data
    statements = await get_balance_sheet("CPALL")

    # Get latest period
    latest = statements[0]
    print(f"Period: {latest.quarter} {latest.year}")
    print(f"Status: {latest.status}")
    print(f"Accounts: {len(latest.accounts)}")

    # Find total assets
    total_assets = next(
        (acc for acc in latest.accounts if acc.account_code == "607"),
        None
    )
    if total_assets:
        print(f"Total Assets: {total_assets.amount:,.0f} (thousands)")

asyncio.run(main())
```

### Fetch Income Statement

```python
from settfex.services.set import get_income_statement

async def analyze_income():
    statements = await get_income_statement("CPALL", lang="en")

    for stmt in statements[:3]:  # Last 3 periods
        # Find revenue
        revenue = next(
            (acc for acc in stmt.accounts if "Revenue" in acc.account_name),
            None
        )
        # Find net profit
        net_profit = next(
            (acc for acc in stmt.accounts if "Net Profit" in acc.account_name),
            None
        )

        print(f"{stmt.quarter} {stmt.year}:")
        if revenue:
            print(f"  Revenue: {revenue.amount:,.0f}")
        if net_profit:
            print(f"  Net Profit: {net_profit.amount:,.0f}")

asyncio.run(analyze_income())
```

### Fetch Cash Flow

```python
from settfex.services.set import get_cash_flow

async def analyze_cash_flow():
    statements = await get_cash_flow("PTT")

    latest = statements[0]
    print(f"Cash Flow - {latest.quarter} {latest.year}")

    # List all cash flow accounts
    for account in latest.accounts:
        if account.amount:
            print(f"{account.account_name}: {account.amount:,.0f}")

asyncio.run(analyze_cash_flow())
```

## API Reference

### Models

#### Account

Individual financial account line item.

**Fields:**
- `account_code: str` - Account code/identifier
- `account_name: str` - Account name/description
- `amount: float | None` - Account amount in thousands (can be null)
- `adjusted: bool` - Whether account has been adjusted
- `level: int` - Hierarchy level (-1 for totals, 0+ for details)
- `divider: int` - Divider for amount scaling (usually 1000)
- `format: str` - Display format hint (e.g., 'BU' for bold underline)

**Example:**
```python
account = Account(
    accountCode="607",
    accountName="Total Assets",
    amount=931772208.0,
    adjusted=False,
    level=-1,
    divider=1000,
    format="BU"
)
print(f"{account.account_name}: {account.amount:,.0f}")
```

#### FinancialStatement

Base model for all financial statements.

**Fields:**
- `symbol: str` - Stock symbol/ticker
- `quarter: str` - Quarter code ('6M' for half year, 'Q9' for full year)
- `year: int` - Fiscal year
- `begin_date: datetime` - Statement period begin date
- `end_date: datetime` - Statement period end date
- `fs_type: str` - Financial statement type (C=Consolidated)
- `account_form_id: str` - Account form identifier
- `download_url: str` - URL to download full statement
- `fs_type_description: str` - Financial statement type description
- `status: str` - Statement status (Audited/Reviewed/Unaudited)
- `is_fs_comp: bool` - Is comparison financial statement
- `has_adjusted_account: bool` - Whether statement has adjusted accounts
- `accounts: list[Account]` - List of financial account line items
- `is_restatement: bool` - Whether this is a restated statement
- `restatement_date: datetime | None` - Restatement date if applicable

#### BalanceSheet

Balance sheet financial statement (inherits from FinancialStatement).

#### IncomeStatement

Income statement financial statement (inherits from FinancialStatement).

#### CashFlow

Cash flow financial statement (inherits from FinancialStatement).

### FinancialService

Main service class for fetching financial data.

#### `__init__(config: FetcherConfig | None = None)`

Initialize the financial service.

**Parameters:**
- `config` - Optional fetcher configuration (uses defaults if None)

**Example:**
```python
from settfex.services.set.stock.financial import FinancialService
from settfex.utils.data_fetcher import FetcherConfig

# Default config
service = FinancialService()

# Custom config
config = FetcherConfig(timeout=60, max_retries=5)
service = FinancialService(config=config)
```

#### `async fetch_balance_sheet(symbol: str, lang: str = "en") -> list[BalanceSheet]`

Fetch balance sheet data for a stock symbol.

**Parameters:**
- `symbol: str` - Stock symbol (e.g., "CPALL", "PTT", case-insensitive)
- `lang: str` - Language ('en' or 'th', default: 'en')

**Returns:**
- `list[BalanceSheet]` - List of balance sheet statements (multiple periods)

**Raises:**
- `ValueError` - If symbol is empty or language is invalid
- `Exception` - If request fails or response cannot be parsed

**Example:**
```python
service = FinancialService()
statements = await service.fetch_balance_sheet("CPALL", lang="en")

for stmt in statements:
    print(f"{stmt.quarter} {stmt.year}: {len(stmt.accounts)} accounts")
```

#### `async fetch_balance_sheet_raw(symbol: str, lang: str = "en") -> list[dict[str, Any]]`

Fetch balance sheet data as raw dictionary.

Useful for debugging or when you need the raw API response.

**Parameters:**
- Same as `fetch_balance_sheet()`

**Returns:**
- `list[dict[str, Any]]` - List of raw dictionaries from API

**Example:**
```python
raw_data = await service.fetch_balance_sheet_raw("CPALL")
print(f"Periods: {len(raw_data)}")
print(f"Keys: {raw_data[0].keys()}")
```

#### `async fetch_income_statement(symbol: str, lang: str = "en") -> list[IncomeStatement]`

Fetch income statement data for a stock symbol.

**Parameters:**
- `symbol: str` - Stock symbol (e.g., "CPALL", "PTT", case-insensitive)
- `lang: str` - Language ('en' or 'th', default: 'en')

**Returns:**
- `list[IncomeStatement]` - List of income statement statements

**Example:**
```python
statements = await service.fetch_income_statement("PTT", lang="en")
latest = statements[0]
print(f"Status: {latest.status}")
```

#### `async fetch_income_statement_raw(symbol: str, lang: str = "en") -> list[dict[str, Any]]`

Fetch income statement data as raw dictionary.

#### `async fetch_cash_flow(symbol: str, lang: str = "en") -> list[CashFlow]`

Fetch cash flow data for a stock symbol.

**Parameters:**
- `symbol: str` - Stock symbol (e.g., "CPALL", "PTT", case-insensitive)
- `lang: str` - Language ('en' or 'th', default: 'en')

**Returns:**
- `list[CashFlow]` - List of cash flow statements

**Example:**
```python
statements = await service.fetch_cash_flow("KBANK")
for stmt in statements:
    print(f"{stmt.quarter} {stmt.year}: {stmt.status}")
```

#### `async fetch_cash_flow_raw(symbol: str, lang: str = "en") -> list[dict[str, Any]]`

Fetch cash flow data as raw dictionary.

### Convenience Functions

#### `async get_balance_sheet(symbol: str, lang: str = "en", config: FetcherConfig | None = None) -> list[BalanceSheet]`

Quick access to balance sheet data.

**Example:**
```python
from settfex.services.set import get_balance_sheet

statements = await get_balance_sheet("CPALL")
```

#### `async get_income_statement(symbol: str, lang: str = "en", config: FetcherConfig | None = None) -> list[IncomeStatement]`

Quick access to income statement data.

**Example:**
```python
from settfex.services.set import get_income_statement

statements = await get_income_statement("PTT")
```

#### `async get_cash_flow(symbol: str, lang: str = "en", config: FetcherConfig | None = None) -> list[CashFlow]`

Quick access to cash flow data.

**Example:**
```python
from settfex.services.set import get_cash_flow

statements = await get_cash_flow("KBANK")
```

## Usage Examples

### Example 1: Comprehensive Financial Analysis

```python
import asyncio
from settfex.services.set import (
    get_balance_sheet,
    get_income_statement,
    get_cash_flow
)

async def analyze_company(symbol: str):
    """Comprehensive financial analysis."""

    # Fetch all financial statements
    balance_sheets = await get_balance_sheet(symbol)
    income_statements = await get_income_statement(symbol)
    cash_flows = await get_cash_flow(symbol)

    print(f"Financial Analysis for {symbol}")
    print(f"=" * 50)

    # Balance sheet analysis
    latest_bs = balance_sheets[0]
    print(f"\nBalance Sheet ({latest_bs.quarter} {latest_bs.year}):")
    print(f"  Status: {latest_bs.status}")

    total_assets = next(
        (acc for acc in latest_bs.accounts if "Total Assets" in acc.account_name),
        None
    )
    if total_assets:
        print(f"  Total Assets: {total_assets.amount:,.0f}K")

    # Income statement analysis
    latest_is = income_statements[0]
    print(f"\nIncome Statement ({latest_is.quarter} {latest_is.year}):")

    revenue = next(
        (acc for acc in latest_is.accounts if "Revenue" in acc.account_name),
        None
    )
    net_profit = next(
        (acc for acc in latest_is.accounts if "Net Profit" in acc.account_name),
        None
    )

    if revenue and net_profit:
        print(f"  Revenue: {revenue.amount:,.0f}K")
        print(f"  Net Profit: {net_profit.amount:,.0f}K")
        margin = (net_profit.amount / revenue.amount * 100)
        print(f"  Profit Margin: {margin:.2f}%")

    # Cash flow analysis
    latest_cf = cash_flows[0]
    print(f"\nCash Flow ({latest_cf.quarter} {latest_cf.year}):")
    print(f"  Status: {latest_cf.status}")

asyncio.run(analyze_company("CPALL"))
```

### Example 2: Trend Analysis

```python
async def analyze_trends(symbol: str):
    """Analyze financial trends over time."""

    income_statements = await get_income_statement(symbol)

    print(f"Revenue Trend for {symbol}")
    print(f"-" * 40)

    for stmt in income_statements[:5]:  # Last 5 periods
        revenue = next(
            (acc for acc in stmt.accounts if "Revenue" in acc.account_name),
            None
        )
        if revenue:
            print(f"{stmt.quarter} {stmt.year}: {revenue.amount:,.0f}K")

asyncio.run(analyze_trends("PTT"))
```

### Example 3: Find Specific Accounts

```python
async def find_account(symbol: str, account_name_pattern: str):
    """Find specific accounts in balance sheet."""

    balance_sheets = await get_balance_sheet(symbol)
    latest = balance_sheets[0]

    print(f"Accounts matching '{account_name_pattern}':")

    for account in latest.accounts:
        if account_name_pattern.lower() in account.account_name.lower():
            print(f"  {account.account_code}: {account.account_name}")
            if account.amount:
                print(f"    Amount: {account.amount:,.0f}K")
            print(f"    Level: {account.level}, Format: {account.format or 'None'}")

asyncio.run(find_account("CPALL", "Cash"))
```

### Example 4: Quarter Code Handling

```python
async def analyze_by_quarter():
    """Analyze financial data by quarter type."""

    statements = await get_balance_sheet("CPALL")

    # Group by quarter type
    half_year = [s for s in statements if s.quarter == "6M"]
    full_year = [s for s in statements if s.quarter == "Q9"]

    print(f"Half-Year Reports: {len(half_year)}")
    print(f"Full-Year Reports: {len(full_year)}")

    # Show latest full year
    if full_year:
        latest = full_year[0]
        print(f"\nLatest Full Year: {latest.year}")
        print(f"Status: {latest.status}")
        print(f"Period: {latest.begin_date.date()} to {latest.end_date.date()}")

asyncio.run(analyze_by_quarter())
```

### Example 5: Thai Language Support

```python
async def fetch_thai_financials():
    """Fetch financial data in Thai language."""

    statements = await get_balance_sheet("CPALL", lang="th")
    latest = statements[0]

    print(f"งบการเงิน {latest.symbol}")
    print(f"ไตรมาส: {latest.quarter} ปี: {latest.year}")

    # Thai account names
    for account in latest.accounts[:5]:
        print(f"{account.account_code}: {account.account_name}")
        if account.amount:
            print(f"  จำนวน: {account.amount:,.0f}K")

asyncio.run(fetch_thai_financials())
```

### Example 6: Compare Multiple Periods

```python
async def compare_periods(symbol: str):
    """Compare financial performance across periods."""

    statements = await get_income_statement(symbol)

    print(f"Income Statement Comparison - {symbol}")
    print(f"{'Period':<15} {'Revenue':>15} {'Net Profit':>15} {'Margin %':>10}")
    print(f"-" * 60)

    for stmt in statements[:4]:  # Last 4 periods
        revenue = next(
            (acc for acc in stmt.accounts if "Revenue" in acc.account_name),
            None
        )
        net_profit = next(
            (acc for acc in stmt.accounts if "Net Profit" in acc.account_name),
            None
        )

        period = f"{stmt.quarter} {stmt.year}"
        if revenue and net_profit:
            margin = (net_profit.amount / revenue.amount * 100)
            print(f"{period:<15} {revenue.amount:>15,.0f} {net_profit.amount:>15,.0f} {margin:>10.2f}")

asyncio.run(compare_periods("CPALL"))
```

### Example 7: Error Handling

```python
async def safe_fetch_financials(symbol: str):
    """Fetch financial data with error handling."""

    try:
        statements = await get_balance_sheet(symbol)

        if not statements:
            print(f"No financial data found for {symbol}")
            return

        latest = statements[0]
        print(f"Successfully fetched {len(statements)} periods")
        print(f"Latest: {latest.quarter} {latest.year} ({latest.status})")

    except ValueError as e:
        print(f"Validation error: {e}")
    except Exception as e:
        print(f"Failed to fetch data: {e}")

# Test with valid and invalid symbols
asyncio.run(safe_fetch_financials("CPALL"))
asyncio.run(safe_fetch_financials(""))  # Will raise ValueError
```

## Quarter Codes

The service uses specific quarter codes to identify reporting periods:

- **`6M`** - Half year report (6 months)
- **`Q9`** - Full year report (12 months)

These codes are returned in the `quarter` field of each financial statement.

## Data Fields

### Account Hierarchy

Accounts are organized hierarchically using the `level` field:

- **`level = -1`** - Total/summary accounts (e.g., "Total Assets", "Total Liabilities")
- **`level = 0`** - Main category accounts
- **`level = 1+`** - Sub-category accounts

### Amount Scaling

Amounts are typically in thousands (divider=1000). To get the actual value:

```python
actual_amount = account.amount  # Already in thousands
# For display in millions
millions = account.amount / 1000
```

### Display Format

The `format` field provides display hints:

- **`"BU"`** - Bold and underlined (usually for totals)
- **`""`** - Normal display

## Performance Tips

1. **Batch Requests**: Fetch multiple statement types concurrently:
   ```python
   balance_sheets, income_statements, cash_flows = await asyncio.gather(
       get_balance_sheet("CPALL"),
       get_income_statement("CPALL"),
       get_cash_flow("CPALL")
   )
   ```

2. **Use Raw Methods for Debugging**: When troubleshooting, use `_raw()` methods to see actual API response

3. **Cache Results**: Store fetched data to avoid repeated API calls

## Error Handling

The service raises these exceptions:

- **`ValueError`** - Invalid symbol or language parameter
- **`Exception`** - HTTP errors, JSON parsing errors, or API failures

Always wrap calls in try-except blocks for production use.

## See Also

- [Stock Highlight Data Service](highlight_data.md) - Market metrics and valuations
- [Trading Statistics Service](trading_stat.md) - Historical trading performance
- [AsyncDataFetcher](../../utils/data_fetcher.md) - Low-level HTTP client
- [Stock Class](stock.md) - Unified stock data interface
