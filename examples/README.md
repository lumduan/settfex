# settfex Examples - Interactive Jupyter Notebooks

Comprehensive, beginner-friendly tutorials for the settfex library.

## What's Inside

### SET (Stock Exchange of Thailand) Examples

**Location**: `examples/set/`

Complete tutorial series covering all 11 SET services:

1. **Stock List** - Market universe and symbol validation
2. **Highlight Data** - Key metrics (P/E, P/B, market cap, dividends)
3. **Stock Profile** - Listing details and foreign ownership
4. **Company Profile** - Governance scores and ESG ratings
5. **Corporate Actions** - Dividends and shareholder meetings
6. **Shareholder** - Ownership structure and major holders
7. **NVDR Holder** - Non-voting depositary receipt analysis
8. **Board of Directors** - Management structure
9. **Trading Statistics** - Historical performance (multi-period)
10. **Price Performance** - Stock vs sector vs market comparison
11. **Financial Statements** - Balance sheet, income, cash flow

**Total**: 11 notebooks + comprehensive guide

## Quick Start

### 1. Install Dependencies

```bash
# Install settfex
pip install settfex

# Install Jupyter
pip install jupyter
```

### 2. Launch Jupyter

```bash
# Navigate to examples
cd examples/set

# Start Jupyter
jupyter notebook
```

### 3. Open Any Notebook

Start with `01_stock_list.ipynb` if you're new!

## What You'll Learn

### Beginner Level
- Fetch stock data from SET API
- Work with async/await in Python
- Use Pydantic models for type safety
- Export data to CSV and pandas DataFrames
- Handle errors gracefully

### Intermediate Level
- Build stock screeners (value, dividend, ESG)
- Perform comparative analysis
- Calculate financial ratios
- Create market dashboards
- Analyze ownership structures

### Advanced Level
- Construct sector rotation strategies
- Calculate alpha and relative performance
- Perform fundamental analysis
- Build risk-adjusted portfolios
- Combine multiple data sources

## Notebook Features

Each notebook includes:

✓ **Clear explanations** - No finance jargon, beginner-friendly
✓ **Working code examples** - Copy, paste, run
✓ **Real stock data** - Thai blue chips (PTT, KBANK, CPALL, etc.)
✓ **Financial use cases** - Professional trading scenarios
✓ **Error handling** - Production-ready patterns
✓ **Data export** - CSV, pandas, Excel examples
✓ **Visualization** - Charts and tables where applicable

## Example Use Cases

### 1. Value Stock Screener
Find undervalued stocks using P/E and P/B ratios:
```python
# From 02_highlight_data.ipynb
async def value_stock_screener(symbols, max_pe=15, max_pb=2.0):
    tasks = [get_highlight_data(symbol) for symbol in symbols]
    results = await asyncio.gather(*tasks)

    value_stocks = [
        s for s in results
        if s.pe_ratio <= max_pe and s.pb_ratio <= max_pb
    ]
    return value_stocks
```

### 2. Dividend Portfolio
Build high-yield dividend portfolio:
```python
# From 05_corporate_action.ipynb
async def build_dividend_calendar(symbols):
    actions = await asyncio.gather(*[get_corporate_actions(s) for s in symbols])

    dividends = []
    for symbol, corp_actions in zip(symbols, actions):
        for action in corp_actions:
            if action.ca_type == "XD":
                dividends.append({
                    "symbol": symbol,
                    "dividend": action.dividend,
                    "xd_date": action.x_date
                })
    return dividends
```

### 3. ESG Portfolio
Screen companies by governance and ESG ratings:
```python
# From 04_company_profile.ipynb
async def esg_screener(symbols, min_cg_score=4.0, min_esg="A"):
    profiles = await asyncio.gather(*[get_company_profile(s) for s in symbols])

    esg_stocks = [
        p for p in profiles
        if p.cg_score >= min_cg_score and p.setesg_rating >= min_esg
    ]
    return esg_stocks
```

## Learning Path

### Path 1: Quick Start (30 minutes)
1. Stock List (01)
2. Highlight Data (02)
3. Corporate Actions (05)

Learn to fetch basic data and track dividends.

### Path 2: Fundamental Analysis (2 hours)
1. Stock List (01)
2. Highlight Data (02)
3. Financial Statements (11)
4. Price Performance (10)

Build complete fundamental analysis system.

### Path 3: Portfolio Management (3 hours)
All 11 notebooks in sequence.

Master complete SET data ecosystem.

## Pro Tips

### Performance
- Use `asyncio.gather()` for parallel fetching
- Cache stock lists (they change infrequently)
- Batch requests when analyzing multiple stocks

### Data Quality
- Always validate symbols with Stock List service
- Handle None values (not all stocks have all metrics)
- Check audit status in financial statements

### Production Use
- Implement retry logic for network issues
- Add logging for debugging
- Export data for offline analysis
- Validate data before making decisions

## Common Patterns

### Async Function Call
```python
# In Jupyter, just use await
data = await get_highlight_data("PTT")

# In scripts, use asyncio.run()
asyncio.run(main())
```

### Error Handling
```python
try:
    data = await get_highlight_data(symbol)
except Exception as e:
    print(f"Error fetching {symbol}: {e}")
```

### DataFrame Export
```python
import pandas as pd

df = pd.DataFrame([...])
df.to_csv("output.csv", index=False)
```

## Technical Requirements

- **Python**: 3.11 or higher
- **Libraries**: settfex, pandas, jupyter
- **Optional**: matplotlib, plotly (for visualizations)
- **Internet**: Required for API access

## Troubleshooting

**Can't find settfex?**
```bash
pip install settfex
```

**Jupyter not working?**
```bash
pip install --upgrade jupyter notebook
```

**Async errors?**
Just use `await` in Jupyter cells (no `asyncio.run()`)

**Slow performance?**
Use `asyncio.gather()` for parallel fetching

## What's Next?

After completing these notebooks:

1. **Build Applications**
   - Stock screeners
   - Portfolio trackers
   - Trading signals
   - Risk dashboards

2. **Automate Workflows**
   - Scheduled reports
   - Alert systems
   - Data pipelines
   - Backtesting systems

3. **Advanced Analysis**
   - Machine learning models
   - Factor analysis
   - Options pricing
   - Portfolio optimization

## Additional Resources

- **Documentation**: `/docs/settfex/`
- **Source Code**: `/settfex/`
- **Tests**: `/tests/` (more examples)
- **Debug Scripts**: `/debug/` (quick testing)

## Support

Questions or issues?
1. Check notebook comments and documentation
2. Review similar examples in `/tests/`
3. Open a GitHub issue

## Contributing

Have ideas for new examples?
1. Follow existing notebook structure
2. Include beginner explanations
3. Add professional use cases
4. Submit a pull request

---

**Ready to start?** Open `set/01_stock_list.ipynb` and begin your journey! 🚀
