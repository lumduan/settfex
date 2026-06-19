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
SET_FINANCIAL_BALANCE_SHEET_ENDPOINT = "/api/set/factsheet/{symbol}/financialstatement"
SET_FINANCIAL_INCOME_STATEMENT_ENDPOINT = "/api/set/factsheet/{symbol}/financialstatement"
SET_FINANCIAL_CASH_FLOW_ENDPOINT = "/api/set/factsheet/{symbol}/financialstatement"
SET_STOCK_CHART_QUOTATION_ENDPOINT = "/api/set/stock/{symbol}/chart-quotation"
SET_STOCK_LATEST_HISTORICAL_TRADING_ENDPOINT = "/api/set/stock/{symbol}/latest-historical-trading"

# Earnings Call (Opportunity Day) calendar API.
# Hosted on a separate, stateless backend (no Incapsula/cookies, no auth) — the public page
# is https://opportunity-day.setgroup.or.th/en/earnings-call.
SET_LCP_BASE_URL = "https://api.lcp.setgroup.or.th/api/v1"
SET_EARNINGS_CALL_SEARCH_ENDPOINT = "/investor/search/archive"
SET_EARNINGS_CALL_DETAIL_ENDPOINT = "/investor/vdo/{id}"
SET_EARNINGS_CALL_FILTER_ENDPOINT = "/investor/filter/{name}"
SET_OPPDAY_ORIGIN = "https://opportunity-day.setgroup.or.th"
SET_OPPDAY_REFERER = "https://opportunity-day.setgroup.or.th/"
