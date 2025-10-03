"""Stock-specific utilities and services for SET stock operations."""

from settfex.services.set.stock.highlight_data import (
    StockHighlightData,
    StockHighlightDataService,
    get_highlight_data,
)
from settfex.services.set.stock.profile_company import (
    CompanyProfile,
    CompanyProfileService,
    get_company_profile,
)
from settfex.services.set.stock.profile_stock import (
    StockProfile,
    StockProfileService,
    get_profile,
)
from settfex.services.set.stock.stock import Stock
from settfex.services.set.stock.utils import normalize_language, normalize_symbol

__all__ = [
    # Main Stock Class
    "Stock",
    # Utilities
    "normalize_symbol",
    "normalize_language",
    # Highlight Data Service
    "StockHighlightDataService",
    "StockHighlightData",
    "get_highlight_data",
    # Profile Service
    "StockProfileService",
    "StockProfile",
    "get_profile",
    # Company Profile Service
    "CompanyProfileService",
    "CompanyProfile",
    "get_company_profile",
]
