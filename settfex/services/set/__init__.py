"""SET (Stock Exchange of Thailand) services."""

from settfex.services.set.constants import (
    SET_BASE_URL,
    SET_STOCK_HIGHLIGHT_DATA_ENDPOINT,
    SET_STOCK_LIST_ENDPOINT,
    SET_STOCK_PROFILE_ENDPOINT,
)
from settfex.services.set.list import (
    StockListResponse,
    StockListService,
    StockSymbol,
    get_stock_list,
)
from settfex.services.set.stock import (
    Stock,
    StockHighlightData,
    StockHighlightDataService,
    StockProfile,
    StockProfileService,
    get_highlight_data,
    get_profile,
    normalize_language,
    normalize_symbol,
)

__all__ = [
    # Constants
    "SET_BASE_URL",
    "SET_STOCK_LIST_ENDPOINT",
    "SET_STOCK_HIGHLIGHT_DATA_ENDPOINT",
    "SET_STOCK_PROFILE_ENDPOINT",
    # Stock List Service
    "StockListService",
    "StockListResponse",
    "StockSymbol",
    "get_stock_list",
    # Stock Class and Services
    "Stock",
    "StockHighlightDataService",
    "StockHighlightData",
    "get_highlight_data",
    "StockProfileService",
    "StockProfile",
    "get_profile",
    # Stock Utilities
    "normalize_symbol",
    "normalize_language",
]
