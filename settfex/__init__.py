"""settfex - Stock Exchange of Thailand (SET) and Thailand Futures Exchange (TFEX) Data Library.

A modern Python library for fetching real-time and historical data from Thai financial markets.

Usage:
    >>> import asyncio
    >>> from settfex.services.set import SetIndex, Stock, get_stock_list
    >>>
    >>> async def main():
    ...     # Fetch stock list (index memberships included by default)
    ...     stock_list = await get_stock_list()
    ...     print(f"Total stocks: {stock_list.count}")
    ...
    ...     # Fetch stock data
    ...     stock = Stock("CPALL")
    ...     highlight = await stock.get_highlight_data()
    ...     print(f"Market Cap: {highlight.market_cap:,.0f}")
    ...
    ...     # Fetch market index data
    ...     index = SetIndex("SET50")
    ...     info = await index.get_info()
    ...     print(f"SET50: {info.last} ({info.percent_change:+.2f}%)")
    >>>
    >>> asyncio.run(main())
"""

__version__ = "0.8.0"
__author__ = "batt"
__license__ = "MIT"

# Public API exports - import commonly used classes/functions
from settfex.services.set import (
    CompanyProfile,
    IndexCompositionResponse,
    IndexInfo,
    IndexListResponse,
    SetIndex,
    Stock,
    StockHighlightData,
    StockListResponse,
    StockProfile,
    get_company_profile,
    get_highlight_data,
    get_index_composition,
    get_index_info,
    get_index_list,
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
    "SetIndex",
    "get_stock_list",
    "get_highlight_data",
    "get_profile",
    "get_company_profile",
    "get_index_list",
    "get_index_info",
    "get_index_composition",
    # Data Models
    "StockListResponse",
    "StockHighlightData",
    "StockProfile",
    "CompanyProfile",
    "IndexListResponse",
    "IndexInfo",
    "IndexCompositionResponse",
    # Utilities
    "AsyncDataFetcher",
    "FetcherConfig",
    "setup_logger",
]
