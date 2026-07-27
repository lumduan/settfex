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

# News search API (market-wide; uses ?lang=). sourceId=company filters to company disclosures —
# unrecognized sourceId values are silently ignored (returns ALL sources). fromDate/toDate are
# dd/MM/yyyy ONLY (ISO dates -> HTTP 400).
SET_NEWS_SEARCH_ENDPOINT = "/api/set/news/search"

# Market holiday calendar. NOTE: this is the ONLY endpoint on the /api/cms/v1/ prefix — every other
# www.set.or.th endpoint here lives under /api/set/. It takes ?lang= (like the stock and news
# endpoints), NOT ?language= (the index endpoints). The API answers anything it does not like —
# an unrecognized lang value, a missing lang, or a year it does not serve — with a bare HTTP 401
# and an empty body, and it also returns 401 transiently on perfectly valid requests.
# Only the CURRENT year is served (live-probed 2026-07-27: 2026 → 200, 2024/2025/2027/2028 → 401).
SET_HOLIDAY_ENDPOINT = "/api/cms/v1/holidays/year/{year}"

# Market index endpoints (note: the index API uses ?language=, not ?lang= like stock endpoints)
SET_INDEX_LIST_ENDPOINT = "/api/set/index/list"
SET_INDEX_INFO_LIST_ENDPOINT = "/api/set/index/info/list"
SET_INDEX_INFO_ENDPOINT = "/api/set/index/{symbol}/info"
SET_INDEX_COMPOSITION_ENDPOINT = "/api/set/index/{symbol}/composition"
SET_INDEX_CHART_QUOTATION_ENDPOINT = "/api/set/index/{symbol}/chart-quotation"

# Earnings Call (Opportunity Day) calendar API.
# Hosted on a separate, stateless backend (no Incapsula/cookies, no auth) — the public page
# is https://opportunity-day.setgroup.or.th/en/earnings-call.
SET_LCP_BASE_URL = "https://api.lcp.setgroup.or.th/api/v1"
SET_EARNINGS_CALL_SEARCH_ENDPOINT = "/investor/search/archive"
SET_EARNINGS_CALL_DETAIL_ENDPOINT = "/investor/vdo/{id}"
SET_EARNINGS_CALL_FILTER_ENDPOINT = "/investor/filter/{name}"
SET_OPPDAY_ORIGIN = "https://opportunity-day.setgroup.or.th"
SET_OPPDAY_REFERER = "https://opportunity-day.setgroup.or.th/"
