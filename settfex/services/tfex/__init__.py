"""TFEX (Thailand Futures Exchange) services."""

from settfex.services.tfex.constants import (
    TFEX_BASE_URL,
    TFEX_SERIES_LIST_ENDPOINT,
    TFEX_TRADING_STATISTICS_ENDPOINT,
)
from settfex.services.tfex.list import (
    TFEXSeries,
    TFEXSeriesListResponse,
    TFEXSeriesListService,
    get_series_list,
)
from settfex.services.tfex.trading_statistics import (
    TradingStatistics,
    TradingStatisticsService,
    get_trading_statistics,
)

__all__ = [
    # Constants
    "TFEX_BASE_URL",
    "TFEX_SERIES_LIST_ENDPOINT",
    "TFEX_TRADING_STATISTICS_ENDPOINT",
    # Series List Service
    "TFEXSeries",
    "TFEXSeriesListResponse",
    "TFEXSeriesListService",
    "get_series_list",
    # Trading Statistics Service
    "TradingStatistics",
    "TradingStatisticsService",
    "get_trading_statistics",
]
