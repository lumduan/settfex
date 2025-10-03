"""SET (Stock Exchange of Thailand) services."""

from settfex.services.set.constants import (
    SET_BASE_URL,
    SET_COMPANY_PROFILE_ENDPOINT,
    SET_CORPORATE_ACTION_ENDPOINT,
    SET_STOCK_HIGHLIGHT_DATA_ENDPOINT,
    SET_STOCK_LIST_ENDPOINT,
    SET_STOCK_PROFILE_ENDPOINT,
    SET_STOCK_SHAREHOLDER_ENDPOINT,
)
from settfex.services.set.list import (
    StockListResponse,
    StockListService,
    StockSymbol,
    get_stock_list,
)
from settfex.services.set.stock import (
    CompanyProfile,
    CompanyProfileService,
    CorporateAction,
    CorporateActionService,
    ShareholderData,
    ShareholderService,
    Stock,
    StockHighlightData,
    StockHighlightDataService,
    StockProfile,
    StockProfileService,
    get_company_profile,
    get_corporate_actions,
    get_highlight_data,
    get_profile,
    get_shareholder_data,
    normalize_language,
    normalize_symbol,
)

__all__ = [
    # Constants
    "SET_BASE_URL",
    "SET_STOCK_LIST_ENDPOINT",
    "SET_STOCK_HIGHLIGHT_DATA_ENDPOINT",
    "SET_STOCK_PROFILE_ENDPOINT",
    "SET_COMPANY_PROFILE_ENDPOINT",
    "SET_CORPORATE_ACTION_ENDPOINT",
    "SET_STOCK_SHAREHOLDER_ENDPOINT",
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
    "CompanyProfileService",
    "CompanyProfile",
    "get_company_profile",
    "CorporateActionService",
    "CorporateAction",
    "get_corporate_actions",
    "ShareholderService",
    "ShareholderData",
    "get_shareholder_data",
    # Stock Utilities
    "normalize_symbol",
    "normalize_language",
]
