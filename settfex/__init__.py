"""settfex - Stock Exchange of Thailand (SET) and Thailand Futures Exchange (TFEX) Data Library.

A modern Python library for fetching real-time and historical data from Thai financial markets.

Designed for both humans and AI/LLM agents. Every service exposes three tiers:

- ``get_*()`` — flat, one-call convenience functions (e.g. ``get_highlight_data("CPALL")``);
  the intended entry point for LLM tool-calling.
- ``fetch_*()`` — return validated Pydantic models, giving structured, schema-checked output
  that lowers hallucination risk for agents.
- ``fetch_*_raw()`` — return the raw API ``dict`` as an escape hatch.

All I/O is async. Language arguments accept ``en``/``th`` (plus ``english``/``thai`` aliases);
symbols are auto-normalized (uppercased).

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

__version__ = "0.11.0"
__author__ = "batt"
__license__ = "MIT"

# Public API exports - import commonly used classes/functions
from settfex.exceptions import (
    FetchError,
    InvalidDateError,
    InvalidLanguageError,
    InvalidSymbolError,
    SymbolNotFoundError,
)
from settfex.services.set import (
    CompanyProfile,
    IndexCompositionResponse,
    IndexInfo,
    IndexListResponse,
    Language,
    NewsSearchResponse,
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
    get_news,
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
    "get_news",
    # Data Models
    "StockListResponse",
    "StockHighlightData",
    "StockProfile",
    "CompanyProfile",
    "IndexListResponse",
    "IndexInfo",
    "IndexCompositionResponse",
    "NewsSearchResponse",
    # Utilities
    "AsyncDataFetcher",
    "FetcherConfig",
    "setup_logger",
    # Exceptions
    "FetchError",
    "SymbolNotFoundError",
    "InvalidSymbolError",
    "InvalidLanguageError",
    "InvalidDateError",
    # Types
    "Language",
]
