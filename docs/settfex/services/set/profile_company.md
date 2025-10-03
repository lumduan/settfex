# Company Profile Service

## Overview

The Company Profile Service provides comprehensive company information for individual stock symbols from the Stock Exchange of Thailand (SET). This service fetches detailed company data including business information, contact details, governance scores, auditors, management structure, and capital information.

## Features

- **Comprehensive Company Data**: Complete company profile with 30+ fields
- **Dual Language Support**: Fetch data in English ('en') or Thai ('th')
- **Full Type Safety**: Complete Pydantic models for all data structures
- **Async-First**: Built on AsyncDataFetcher for optimal performance
- **Input Normalization**: Automatic symbol uppercase and language validation
- **Session Management**: Automatic cookie handling via SessionManager (25x faster after first request)

## Installation

The service is included with `settfex`:

```bash
pip install settfex
```

## Quick Start

### Using Convenience Function

```python
import asyncio
from settfex.services.set import get_company_profile

async def main():
    # Fetch company profile (SessionManager handles cookies automatically)
    profile = await get_company_profile("CPN")

    print(f"Company: {profile.name}")
    print(f"Sector: {profile.sector_name}")
    print(f"Website: {profile.url}")
    print(f"CG Score: {profile.cg_score}")
    print(f"ESG Rating: {profile.setesg_rating}")
    print(f"Management: {len(profile.managements)} executives")
    print(f"Auditors: {len(profile.auditors)}")

asyncio.run(main())
```

### Using Service Class

```python
from settfex.services.set.stock import CompanyProfileService

async def main():
    service = CompanyProfileService()

    # Fetch company profile
    profile = await service.fetch_company_profile("PTT", lang="en")

    print(f"{profile.symbol}: {profile.name}")
    print(f"Industry: {profile.industry_name}")
    print(f"Address: {profile.address}")
    print(f"Phone: {profile.telephone}")

asyncio.run(main())
```

## API Reference

### CompanyProfile Model

Complete company profile data model.

**Fields:**

#### Basic Information
- `symbol: str` - Stock symbol/ticker
- `name: str` - Company name
- `name_remark: str` - Additional name remarks
- `market: str` - Market (SET, mai, etc.)
- `industry: str` - Industry code
- `industry_name: str` - Industry name
- `sector: str` - Sector code
- `sector_name: str` - Sector name
- `logo_url: str` - Company logo URL

#### Business Information
- `business_type: str` - Business type description
- `url: str` - Company website URL
- `established_date: str` - Company established date
- `dividend_policy: str` - Dividend policy details

#### Contact Information
- `address: str` - Company address
- `telephone: str` - Contact telephone
- `fax: str` - Contact fax
- `email: str` - Contact email

#### Governance & Ratings
- `cg_score: int | None` - Corporate Governance score (0-5)
- `cg_remark: str` - CG score remarks
- `cac_flag: bool` - CAC (anti-corruption) certification
- `setesg_rating: str | None` - SET ESG rating (AAA, AA, A, BBB, etc.)
- `setesg_rating_remark: str` - ESG rating remarks

#### Audit Information
- `audit_end: datetime` - Audit period end date
- `audit_choice: str` - Audit opinion type
- `auditors: list[Auditor]` - List of auditors

#### Management
- `managements: list[Management]` - List of executives

#### Capital Structure
- `common_capital: Capital` - Common stock capital information
- `commons_share: ShareStructure` - Common share structure
- `preferred_capital: Capital` - Preferred stock capital
- `preferred_share: ShareStructure` - Preferred share structure

### Nested Models

#### Auditor

**Fields:**
- `name: str` - Auditor's name
- `company: str` - Audit firm name
- `audit_end_date: datetime` - Audit period end date

#### Management

**Fields:**
- `position_code: int` - Position code
- `position: str` - Position title
- `name: str` - Executive's name
- `start_date: datetime` - Start date in position

#### Capital

**Fields:**
- `authorized_capital: float | None` - Authorized capital amount
- `paidup_capital: float | None` - Paid-up capital amount
- `par: float` - Par value per share
- `currency: str` - Currency code

#### ShareStructure

**Fields:**
- `listed_share: int | None` - Number of listed shares
- `voting_rights: list[VotingRight]` - Voting rights information
- `treasury_shares: int | None` - Treasury shares
- `voting_shares: list[VotingShare] | None` - Voting shares by date

#### VotingRight

**Fields:**
- `symbol: str` - Stock symbol
- `paidup_share: int` - Number of paid-up shares
- `ratio: str | None` - Voting ratio (e.g., "1 : 1")

#### VotingShare

**Fields:**
- `as_of_date: datetime` - Data as of date
- `share: int` - Number of voting shares

### CompanyProfileService

Service class for fetching company profile data.

#### Methods

##### `__init__(config: FetcherConfig | None = None)`

Initialize the company profile service.

**Parameters:**
- `config` - Optional fetcher configuration (uses defaults if None)

**Example:**
```python
from settfex.utils.data_fetcher import FetcherConfig

config = FetcherConfig(timeout=60, max_retries=5)
service = CompanyProfileService(config=config)
```

##### `async fetch_company_profile(symbol: str, lang: str = "en") -> CompanyProfile`

Fetch company profile data for a specific stock symbol.

**Parameters:**
- `symbol: str` - Stock symbol (e.g., "PTT", "CPALL", "kbank")
- `lang: str` - Language for response ('en' or 'th', default: 'en')

**Returns:**
- `CompanyProfile` - Complete company profile data

**Raises:**
- `ValueError` - If symbol is empty or language is invalid
- `Exception` - If request fails or response cannot be parsed

**Example:**
```python
service = CompanyProfileService()
profile = await service.fetch_company_profile("CPN", lang="en")
```

##### `async fetch_company_profile_raw(symbol: str, lang: str = "en") -> dict[str, Any]`

Fetch raw company profile data without Pydantic validation.

**Parameters:**
- Same as `fetch_company_profile()`

**Returns:**
- `dict[str, Any]` - Raw API response

**Example:**
```python
service = CompanyProfileService()
raw_data = await service.fetch_company_profile_raw("CPN")
print(raw_data.keys())
```

### Convenience Function

#### `async get_company_profile(symbol: str, lang: str = "en", config: FetcherConfig | None = None) -> CompanyProfile`

Quick one-line access to company profile data.

**Parameters:**
- `symbol: str` - Stock symbol
- `lang: str` - Language ('en' or 'th')
- `config: FetcherConfig | None` - Optional configuration

**Returns:**
- `CompanyProfile` - Complete company profile

**Example:**
```python
from settfex.services.set import get_company_profile

profile = await get_company_profile("PTT")
print(f"{profile.name} - ESG: {profile.setesg_rating}")
```

## Usage Examples

### Example 1: Basic Company Information

```python
import asyncio
from settfex.services.set import get_company_profile

async def main():
    profile = await get_company_profile("CPN")

    print(f"Company: {profile.name}")
    print(f"Symbol: {profile.symbol}")
    print(f"Market: {profile.market}")
    print(f"Sector: {profile.sector_name} ({profile.sector})")
    print(f"Industry: {profile.industry_name} ({profile.industry})")
    print(f"Website: {profile.url}")
    print(f"Established: {profile.established_date}")

asyncio.run(main())
```

### Example 2: Governance & ESG Ratings

```python
async def check_governance():
    profile = await get_company_profile("PTT")

    print(f"Corporate Governance Score: {profile.cg_score}/5")
    print(f"ESG Rating: {profile.setesg_rating}")
    print(f"CAC Certified: {'Yes' if profile.cac_flag else 'No'}")

    if profile.cg_remark:
        print(f"CG Remarks: {profile.cg_remark}")
    if profile.setesg_rating_remark:
        print(f"ESG Remarks: {profile.setesg_rating_remark}")

asyncio.run(check_governance())
```

### Example 3: Management Structure

```python
async def show_management():
    profile = await get_company_profile("CPALL")

    print(f"Management Team ({len(profile.managements)} executives):")
    for mgmt in profile.managements[:5]:  # Show top 5
        print(f"  {mgmt.position}: {mgmt.name}")
        print(f"    Since: {mgmt.start_date.strftime('%Y-%m-%d')}")

asyncio.run(show_management())
```

### Example 4: Auditor Information

```python
async def show_auditors():
    profile = await get_company_profile("KBANK")

    print(f"Audit Information:")
    print(f"  Audit End: {profile.audit_end.strftime('%Y-%m-%d')}")
    print(f"  Audit Opinion: {profile.audit_choice}")
    print(f"\nAuditors ({len(profile.auditors)}):")
    for auditor in profile.auditors:
        print(f"  {auditor.name}")
        print(f"    Firm: {auditor.company}")
        print(f"    Period: {auditor.audit_end_date.strftime('%Y-%m-%d')}")

asyncio.run(show_auditors())
```

### Example 5: Capital Structure

```python
async def show_capital():
    profile = await get_company_profile("AOT")

    # Common stock
    print("Common Stock:")
    print(f"  Authorized: {profile.common_capital.authorized_capital:,.2f} {profile.common_capital.currency}")
    print(f"  Paid-up: {profile.common_capital.paidup_capital:,.2f} {profile.common_capital.currency}")
    print(f"  Par Value: {profile.common_capital.par} {profile.common_capital.currency}")
    print(f"  Listed Shares: {profile.commons_share.listed_share:,}")

    # Voting rights
    if profile.commons_share.voting_rights:
        print("\nVoting Rights:")
        for vr in profile.commons_share.voting_rights:
            print(f"  {vr.symbol}: {vr.paidup_share:,} shares, Ratio: {vr.ratio}")

asyncio.run(show_capital())
```

### Example 6: Thai Language Support

```python
async def fetch_thai():
    # Fetch in Thai language
    profile = await get_company_profile("BBL", lang="th")

    print(f"บริษัท: {profile.name}")
    print(f"ธุรกิจ: {profile.business_type}")
    print(f"นโยบายเงินปันผล: {profile.dividend_policy}")

asyncio.run(fetch_thai())
```

### Example 7: Multiple Companies

```python
async def compare_companies():
    symbols = ["PTT", "KBANK", "CPALL", "AOT"]

    from settfex.services.set.stock import CompanyProfileService

    service = CompanyProfileService()

    tasks = [
        service.fetch_company_profile(symbol)
        for symbol in symbols
    ]

    profiles = await asyncio.gather(*tasks)

    print("Company Comparison:")
    for profile in profiles:
        print(f"{profile.symbol}: CG={profile.cg_score}, ESG={profile.setesg_rating}, CAC={'✓' if profile.cac_flag else '✗'}")

asyncio.run(compare_companies())
```

### Example 8: Custom Configuration

```python
from settfex.utils.data_fetcher import FetcherConfig

async def fetch_with_config():
    config = FetcherConfig(
        timeout=60,
        max_retries=5,
        retry_delay=2.0
    )

    profile = await get_company_profile("CPN", config=config)
    print(f"Fetched: {profile.name}")

asyncio.run(fetch_with_config())
```

## Data Fields Detail

### Corporate Governance (CG) Score

The CG score ranges from 1-5:
- **5**: Excellent
- **4**: Very Good
- **3**: Good
- **2**: Satisfactory
- **1**: Pass

### SET ESG Rating

The SET ESG rating scale:
- **AAA**: Leader
- **AA**: Outstanding
- **A**: Advanced
- **BBB**: Good
- **BB**: Average
- **B**: Below Average
- **CCC**: Poor

### CAC Certification

CAC (Collective Action Against Corruption) is Thailand's private sector anti-corruption initiative. Companies with `cac_flag=True` are certified participants.

## Error Handling

```python
async def safe_fetch():
    try:
        profile = await get_company_profile("INVALID")
        print(profile.name)
    except ValueError as e:
        print(f"Validation error: {e}")
    except Exception as e:
        print(f"Request failed: {e}")

asyncio.run(safe_fetch())
```

## Performance

### Session Caching

The service uses SessionManager for automatic cookie handling:

1. **First Request**: ~2-3 seconds (includes session warmup)
2. **Subsequent Requests**: ~100ms (25x faster with cached session)

```python
# First run: ~2-3s
profile1 = await get_company_profile("PTT")

# Second run: ~100ms (uses cached session)
profile2 = await get_company_profile("CPALL")
```

### Concurrent Requests

Fetch multiple profiles concurrently:

```python
symbols = ["PTT", "KBANK", "AOT", "CPALL", "BBL"]

tasks = [get_company_profile(symbol) for symbol in symbols]
profiles = await asyncio.gather(*tasks)

# ~3s total vs ~15s sequential
```

## Integration with Other Services

### Combine with Stock Profile

```python
from settfex.services.set import get_company_profile, get_profile

async def full_analysis():
    symbol = "PTT"

    # Get both company and stock profiles
    company, stock = await asyncio.gather(
        get_company_profile(symbol),
        get_profile(symbol)
    )

    print(f"Company: {company.name}")
    print(f"ESG Rating: {company.setesg_rating}")
    print(f"Market: {stock.market}")
    print(f"IPO Price: {stock.ipo}")

asyncio.run(full_analysis())
```

### Use with Stock Class

```python
from settfex.services.set import Stock, get_company_profile

async def comprehensive_data():
    symbol = "CPALL"

    stock = Stock(symbol)

    # Fetch all data concurrently
    highlight, company = await asyncio.gather(
        stock.get_highlight_data(),
        get_company_profile(symbol)
    )

    print(f"{company.name} ({symbol})")
    print(f"Market Cap: {highlight.market_cap:,.0f}")
    print(f"CG Score: {company.cg_score}")
    print(f"ESG Rating: {company.setesg_rating}")

asyncio.run(comprehensive_data())
```

## Logging

Enable detailed logging for debugging:

```python
from loguru import logger
from settfex.utils.logging import setup_logger

setup_logger(level="DEBUG", log_file="logs/company_profile.log")

profile = await get_company_profile("PTT")
```

## API Endpoint

The service fetches data from:

```
https://www.set.or.th/api/set/company/{symbol}/profile?lang={lang}
```

Example:
```
https://www.set.or.th/api/set/company/CPN/profile?lang=en
```

## Testing

Run the verification script:

```bash
uv run python scripts/settfex/services/set/verify_profile_company.py
```

## Best Practices

1. **Use convenience function** for simple cases
2. **Reuse service instance** when fetching multiple profiles
3. **Enable logging** during development
4. **Handle exceptions** gracefully
5. **Use concurrent fetching** for multiple symbols
6. **Trust SessionManager** for cookie handling (no manual configuration needed)
7. **Validate symbol** before fetching (use normalize_symbol)

## See Also

- [Stock Profile Service](profile_stock.md) - Stock-specific profile data
- [Highlight Data Service](highlight_data.md) - Market metrics and valuations
- [Stock List Service](list.md) - Complete stock list from SET
- [AsyncDataFetcher](../../utils/data_fetcher.md) - Low-level HTTP client
- [Stock Class](stock.md) - Unified stock data interface
