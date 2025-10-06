"""settfex - Stock Exchange of Thailand (SET) and Thailand Futures Exchange (TFEX) Data Library.

A modern Python library for fetching real-time and historical data from Thai financial markets.

Usage:
    >>> import asyncio
    >>> from settfex.services.set import Stock, get_stock_list
    >>>
    >>> async def main():
    ...     # Fetch stock list
    ...     stock_list = await get_stock_list()
    ...     print(f"Total stocks: {stock_list.count}")
    ...
    ...     # Fetch stock data
    ...     stock = Stock("CPALL")
    ...     highlight = await stock.get_highlight_data()
    ...     print(f"Market Cap: {highlight.market_cap:,.0f}")
    >>>
    >>> asyncio.run(main())
"""

__version__ = "0.1.0"
__author__ = "batt"
__license__ = "MIT"

# Public API exports - import commonly used classes/functions
from settfex.services.set import (
    CompanyProfile,
    Stock,
    StockHighlightData,
    StockListResponse,
    StockProfile,
    get_company_profile,
    get_highlight_data,
    get_profile,
    get_stock_list,
)

# Utility exports
from settfex.utils.data_fetcher import AsyncDataFetcher, FetcherConfig
from settfex.utils.logging import setup_logger

__all__ = [
    # Version info
    "__version__",
    "__author__",
    "__license__",
    # SET Services - Most commonly used
    "Stock",
    "get_stock_list",
    "get_highlight_data",
    "get_profile",
    "get_company_profile",
    # Data Models
    "StockListResponse",
    "StockHighlightData",
    "StockProfile",
    "CompanyProfile",
    # Utilities
    "AsyncDataFetcher",
    "FetcherConfig",
    "setup_logger",
]
