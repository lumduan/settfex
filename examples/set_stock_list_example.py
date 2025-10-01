#!/usr/bin/env python3
"""
Example: Fetching SET Stock List

This example demonstrates how to use the SET Stock List Service to fetch
the complete list of stocks from the Stock Exchange of Thailand.

The service supports two modes:
1. Generated cookies (may be blocked by Incapsula protection)
2. Real browser session cookies (recommended for production)
"""

import asyncio

from settfex.services.set import StockListService, get_stock_list
from settfex.utils.logging import setup_logger


async def example_basic():
    """Basic usage with generated cookies."""
    print("=" * 80)
    print("Example 1: Basic Usage with Generated Cookies")
    print("=" * 80)

    # Fetch stock list using convenience function
    try:
        stock_list = await get_stock_list()

        print(f"\n✓ Successfully fetched {stock_list.count} stocks")

        # Display first 10 stocks
        print("\nFirst 10 stocks:")
        for stock in stock_list.security_symbols[:10]:
            print(f"  {stock.symbol:8} {stock.name_en:50} {stock.market}")

    except Exception as e:
        print(f"\n✗ Failed: {e}")
        print("Note: This may fail due to Incapsula protection.")
        print("      Use real browser session cookies for production.")


async def example_with_session_cookies():
    """Usage with real browser session cookies (recommended)."""
    print("\n" + "=" * 80)
    print("Example 2: Using Real Browser Session Cookies")
    print("=" * 80)

    # Real browser session cookies from an authenticated session
    # To get these:
    # 1. Open https://www.set.or.th in your browser
    # 2. Open Developer Tools (F12)
    # 3. Go to Network tab
    # 4. Reload the page and find any API request
    # 5. Copy the Cookie header value
    session_cookies = (
        # Replace with your actual browser session cookies
        "charlot=your-session-id; "
        "incap_ses_357_2046605=your-session-token; "
        "visid_incap_2046605=your-visitor-id; "
        # ... add all your cookies here
    )

    # Note: The above cookies are placeholders
    # For the example to work, you need real cookies from your browser
    print("\nNote: This example requires real browser session cookies.")
    print("      Replace the placeholder cookies with actual values from your browser.")
    print("      See the code comments for instructions.")

    # Uncomment the following lines when you have real cookies:
    # try:
    #     stock_list = await get_stock_list(session_cookies=session_cookies)
    #     print(f"\n✓ Successfully fetched {stock_list.count} stocks")
    # except Exception as e:
    #     print(f"\n✗ Failed: {e}")


async def example_filtering():
    """Filtering and searching stocks."""
    print("\n" + "=" * 80)
    print("Example 3: Filtering and Searching")
    print("=" * 80)

    try:
        stock_list = await get_stock_list()

        # Filter by market
        set_stocks = stock_list.filter_by_market("SET")
        mai_stocks = stock_list.filter_by_market("mai")

        print(f"\nMarket Distribution:")
        print(f"  SET market: {len(set_stocks)} stocks")
        print(f"  mai market: {len(mai_stocks)} stocks")

        # Filter by industry
        bank_stocks = stock_list.filter_by_industry("BANK")
        if bank_stocks:
            print(f"\n  BANK industry: {len(bank_stocks)} stocks")
            print("  First 5 banks:")
            for stock in bank_stocks[:5]:
                print(f"    {stock.symbol:8} {stock.name_en}")

        # Lookup specific stock
        ptt = stock_list.get_symbol("PTT")
        if ptt:
            print(f"\nStock Details for PTT:")
            print(f"  Symbol: {ptt.symbol}")
            print(f"  English Name: {ptt.name_en}")
            print(f"  Thai Name: {ptt.name_th}")
            print(f"  Market: {ptt.market}")
            print(f"  Industry: {ptt.industry}")
            print(f"  Sector: {ptt.sector}")

    except Exception as e:
        print(f"\n✗ Failed: {e}")


async def example_with_service_class():
    """Using the service class directly for more control."""
    print("\n" + "=" * 80)
    print("Example 4: Using StockListService Class")
    print("=" * 80)

    from settfex.utils.data_fetcher import FetcherConfig

    # Create custom configuration
    config = FetcherConfig(
        browser_impersonate="chrome120",
        timeout=60,
        max_retries=3,
    )

    # Initialize service with custom config
    service = StockListService(config=config)

    try:
        # Fetch stock list
        response = await service.fetch_stock_list()

        print(f"\n✓ Successfully fetched {response.count} stocks")

        # Analyze by market
        markets = {}
        for stock in response.security_symbols:
            market = stock.market
            if market not in markets:
                markets[market] = 0
            markets[market] += 1

        print("\nMarket Distribution:")
        for market, count in sorted(markets.items()):
            print(f"  {market}: {count} stocks")

    except Exception as e:
        print(f"\n✗ Failed: {e}")


async def main():
    """Run all examples."""
    # Setup logging (optional)
    setup_logger(level="INFO")

    print("\nSET Stock List Service Examples")
    print("=" * 80)

    # Run examples
    await example_basic()
    await example_with_session_cookies()
    await example_filtering()
    await example_with_service_class()

    print("\n" + "=" * 80)
    print("Examples completed!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
