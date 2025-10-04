"""Constants and configuration for SET (Stock Exchange of Thailand) services."""

# Base URL for all SET API endpoints
SET_BASE_URL = "https://www.set.or.th"

# API endpoints
SET_STOCK_LIST_ENDPOINT = "/api/set/stock/list"
SET_STOCK_HIGHLIGHT_DATA_ENDPOINT = "/api/set/stock/{symbol}/highlight-data"
SET_STOCK_PROFILE_ENDPOINT = "/api/set/stock/{symbol}/profile"
SET_COMPANY_PROFILE_ENDPOINT = "/api/set/company/{symbol}/profile"
SET_CORPORATE_ACTION_ENDPOINT = "/api/set/stock/{symbol}/corporate-action"
SET_STOCK_SHAREHOLDER_ENDPOINT = "/api/set/stock/{symbol}/shareholder"
SET_NVDR_HOLDER_ENDPOINT = "/api/set/stock/{symbol}/nvdr-holder"
SET_BOARD_OF_DIRECTOR_ENDPOINT = "/api/set/company/{symbol}/board-of-director"
SET_TRADING_STAT_ENDPOINT = "/api/set/factsheet/{symbol}/trading-stat"
SET_PRICE_PERFORMANCE_ENDPOINT = "/api/set/factsheet/{symbol}/price-performance"
