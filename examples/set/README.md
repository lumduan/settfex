# SET Services - Jupyter Notebook Examples

Complete, beginner-friendly tutorials for all SET (Stock Exchange of Thailand) services in the settfex library.

## Quick Start

### Prerequisites

1. **Python 3.11+** installed
2. **Jupyter Notebook** or **JupyterLab**:
   ```bash
   pip install jupyter
   ```
3. **settfex library**:
   ```bash
   pip install settfex
   ```

### Running the Notebooks

1. Start Jupyter:
   ```bash
   cd examples/set
   jupyter notebook
   ```

2. Open any notebook and run cells sequentially (Shift+Enter)

3. All notebooks are self-contained with explanations and examples

## Notebook Overview

### 1. Stock List Service (`01_stock_list.ipynb`)
**What it does**: Fetch all stocks traded on SET and mai markets

**Learn how to**:
- Get complete stock universe
- Filter by market (SET vs mai)
- Filter by industry/sector
- Validate stock symbols
- Export to CSV/DataFrame

**Use cases**:
- Symbol validation for trading systems
- Market composition analysis
- Sector rotation strategies
- Universe definition for screeners

---

### 2. Highlight Data Service (`02_highlight_data.ipynb`)
**What it does**: Get key market metrics for individual stocks

**Learn how to**:
- Fetch P/E, P/B, market cap
- Get dividend yield and beta
- Monitor 52-week high/low
- Track YTD performance
- Analyze NVDR trading

**Use cases**:
- Value stock screening (low P/E, P/B)
- Dividend portfolio construction
- Risk-adjusted portfolio building
- Market dashboards

---

### 3. Stock Profile Service (`03_stock_profile.ipynb`)
**What it does**: Detailed listing information and foreign ownership limits

**Learn how to**:
- Get IPO price and listing dates
- Check foreign ownership limits
- Monitor free float percentage
- Access ISIN codes
- Track warrant details

**Use cases**:
- Foreign investor compliance
- IPO analysis
- Free float calculations
- Trading system setup

---

### 4. Company Profile Service (`04_company_profile.ipynb`)
**What it does**: Corporate information, governance, and ESG ratings

**Learn how to**:
- Access CG scores (0-5 scale)
- Get SET ESG ratings (AAA-CCC)
- Track CAC certification
- Monitor management and auditors
- Analyze capital structure

**Use cases**:
- ESG portfolio construction
- Governance screening
- Management continuity tracking
- Anti-corruption compliance

---

### 5. Corporate Action Service (`05_corporate_action.ipynb`)
**What it does**: Track dividends and shareholder meetings

**Learn how to**:
- Monitor dividend announcements
- Track ex-dividend dates
- Get AGM/EGM meeting details
- Build dividend calendars
- Plan dividend capture strategies

**Use cases**:
- Dividend income strategies
- Meeting participation planning
- Corporate event tracking
- Ex-dividend date monitoring

---

### 6. Shareholder Service (`06_shareholder.ipynb`)
**What it does**: Ownership structure and major shareholders

**Learn how to**:
- Track major shareholders
- Monitor ownership concentration
- Analyze free float
- Identify NVDR holders
- Compare foreign vs local ownership

**Use cases**:
- Liquidity analysis
- Control analysis (M&A potential)
- Corporate governance research
- Shareholder activism tracking

---

### 7. NVDR Holder Service (`07_nvdr_holder.ipynb`)
**What it does**: Non-Voting Depositary Receipt holder analysis

**Learn how to**:
- Track NVDR holders
- Compare with ordinary shareholders
- Analyze Thai vs foreign NVDR
- Understand NVDR mechanics

**Use cases**:
- Foreign investor analysis
- Liquidity assessment
- Ownership structure comparison

**Note**: NVDRs have same rights as ordinary shares except voting rights

---

### 8. Board of Director Service (`08_board_of_director.ipynb`)
**What it does**: Board composition and management structure

**Learn how to**:
- Track directors and positions
- Identify independent directors
- Analyze board size
- Monitor management changes

**Use cases**:
- Corporate governance analysis
- Independent director tracking
- Management continuity assessment
- ESG compliance monitoring

---

### 9. Trading Statistics Service (`09_trading_statistics.ipynb`)
**What it does**: Historical trading data across multiple periods

**Learn how to**:
- Get multi-period statistics (YTD, 1M, 3M, 6M, 1Y)
- Track OHLC price data
- Analyze volume and liquidity
- Monitor valuation changes
- Assess volatility (beta)

**Use cases**:
- Historical performance analysis
- Trend identification
- Volatility assessment
- Technical analysis

---

### 10. Price Performance Service (`10_price_performance.ipynb`)
**What it does**: Compare stock vs sector vs market performance

**Learn how to**:
- Compare across 5 time periods
- Calculate relative performance
- Identify sector leaders
- Compute alpha (excess return)
- Analyze momentum

**Use cases**:
- Sector rotation strategies
- Alpha calculation
- Performance attribution
- Market timing decisions

---

### 11. Financial Service (`11_financial.ipynb`)
**What it does**: Balance sheet, income statement, and cash flow data

**Learn how to**:
- Fetch financial statements
- Calculate financial ratios
- Perform trend analysis
- Compare companies
- Export to Excel/CSV

**Use cases**:
- Fundamental analysis
- Financial ratio calculations
- Credit analysis
- DCF modeling
- Trend analysis

## Learning Path

### Beginners
Start here:
1. **Stock List** (01) - Get familiar with available stocks
2. **Highlight Data** (02) - Learn key metrics
3. **Stock Profile** (03) - Understand listing details

### Intermediate
Continue with:
4. **Corporate Actions** (05) - Track dividends
5. **Trading Statistics** (09) - Historical analysis
6. **Price Performance** (10) - Relative performance

### Advanced
Master with:
7. **Financial Statements** (11) - Deep fundamental analysis
8. **Shareholder** (06) + **NVDR** (07) - Ownership analysis
9. **Company Profile** (04) + **Board** (08) - Governance

## Common Patterns

### Fetch Single Stock Data
```python
from settfex.services.set import get_highlight_data

# Simple fetch
data = await get_highlight_data("PTT")
print(f"P/E: {data.pe_ratio}")
```

### Fetch Multiple Stocks (Parallel)
```python
import asyncio

symbols = ["PTT", "KBANK", "CPALL"]
tasks = [get_highlight_data(symbol) for symbol in symbols]
results = await asyncio.gather(*tasks)
```

### Error Handling
```python
try:
    data = await get_highlight_data("SYMBOL")
    print("Success!")
except Exception as e:
    print(f"Error: {e}")
```

### Export to pandas
```python
import pandas as pd

# Convert to DataFrame
df = pd.DataFrame([
    {"symbol": d.symbol, "pe": d.pe_ratio}
    for d in results
])
```

## Pro Tips

1. **Use asyncio.gather()** for parallel fetching - much faster!
2. **Cache stock lists** - They don't change frequently
3. **Handle errors gracefully** - Always use try/except in production
4. **Export to CSV** - Easy to share and analyze in Excel
5. **Combine services** - Most powerful when used together

## Example: Complete Stock Analysis

```python
import asyncio
from settfex.services.set import (
    get_highlight_data,
    get_profile,
    get_corporate_actions,
    get_shareholder_data,
    get_balance_sheet
)

async def analyze_stock(symbol: str):
    """Complete stock analysis combining multiple services."""

    # Fetch all data in parallel
    highlight, profile, actions, shareholders, financials = await asyncio.gather(
        get_highlight_data(symbol),
        get_profile(symbol),
        get_corporate_actions(symbol),
        get_shareholder_data(symbol),
        get_balance_sheet(symbol)
    )

    # Create comprehensive report
    print(f"Complete Analysis: {symbol}")
    print(f"Market Cap: {highlight.market_cap:,.0f} THB")
    print(f"P/E: {highlight.pe_ratio}, P/B: {highlight.pb_ratio}")
    print(f"Dividend Yield: {highlight.dividend_yield}%")
    print(f"Foreign Limit: {profile.foreign_limit}%")
    print(f"Recent Dividends: {len([a for a in actions if a.ca_type == 'XD'])}")
    print(f"Major Shareholders: {len(shareholders.major_shareholders)}")
    print(f"Financial Periods: {len(financials)}")

# Run analysis
await analyze_stock("PTT")
```

## Financial Firm Use Cases

Each notebook includes professional use cases:

- **Portfolio Construction**: Value, dividend, ESG portfolios
- **Risk Management**: Beta analysis, concentration metrics
- **Compliance**: Foreign limits, CAC certification
- **Trading Systems**: Symbol validation, liquidity checks
- **Research**: Fundamental analysis, sector comparisons
- **Reporting**: Market dashboards, compliance reports

## Troubleshooting

### "ModuleNotFoundError: No module named 'settfex'"
```bash
pip install settfex
```

### "This event loop is already running"
In Jupyter, just use `await` directly (no `asyncio.run()` needed)

### Slow performance
Use `asyncio.gather()` for parallel fetching instead of sequential

### Data looks incorrect
- Check symbol is valid using Stock List service
- Verify you're using correct language ('en' or 'th')
- Some metrics may be None for certain stocks

## Additional Resources

- **Main Documentation**: `/docs/settfex/services/set/`
- **Source Code**: `/settfex/services/set/`
- **Test Examples**: `/tests/services/set/`
- **Debug Scripts**: `/debug/set/`

## Support

Found an issue or have questions?
1. Check the documentation in `/docs/`
2. Review test examples in `/tests/`
3. Open a GitHub issue

## Next Steps

After completing these notebooks:

1. **Build a stock screener** combining multiple services
2. **Create automated reports** with scheduling
3. **Develop trading strategies** with backtesting
4. **Build dashboards** with Streamlit or Plotly Dash
5. **Integrate with databases** for historical tracking

Happy analyzing! 📊
