"""Stock-specific utilities and services for SET stock operations."""

from settfex.services.set.stock.corporate_action import (
    CorporateAction,
    CorporateActionService,
    get_corporate_actions,
)
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
from settfex.services.set.stock.nvdr_holder import (
    NVDRHolderData,
    NVDRHolderService,
    get_nvdr_holder_data,
)
from settfex.services.set.stock.shareholder import (
    ShareholderData,
    ShareholderService,
    get_shareholder_data,
)
from settfex.services.set.stock.board_of_director import (
    Director,
    BoardOfDirectorService,
    get_board_of_directors,
)
from settfex.services.set.stock.trading_stat import (
    TradingStat,
    TradingStatService,
    get_trading_stats,
)
from settfex.services.set.stock.price_performance import (
    PricePerformanceData,
    PricePerformanceService,
    get_price_performance,
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
    # Corporate Action Service
    "CorporateActionService",
    "CorporateAction",
    "get_corporate_actions",
    # Shareholder Service
    "ShareholderService",
    "ShareholderData",
    "get_shareholder_data",
    # NVDR Holder Service
    "NVDRHolderService",
    "NVDRHolderData",
    "get_nvdr_holder_data",
    # Board of Director Service
    "BoardOfDirectorService",
    "Director",
    "get_board_of_directors",
    # Trading Statistics Service
    "TradingStatService",
    "TradingStat",
    "get_trading_stats",
    # Price Performance Service
    "PricePerformanceService",
    "PricePerformanceData",
    "get_price_performance",
]
