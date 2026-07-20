"""Constants for the Thai SEC IDISC (market.sec.or.th) document services.

The SEC information-disclosure system is a separate host from SET/TFEX — an ASP.NET
WebForms app. ``curl_cffi`` browser impersonation passes its (passive) bot wall; no login
or persistent session is required (the WebForms postback needs only fresh VIEWSTATE tokens).
"""

# Base URL for all SEC IDISC endpoints
SEC_BASE_URL = "https://market.sec.or.th"

# Company autocomplete — JSON POST {"lang","content"} -> [{"Text","Value","Flag"}]
SEC_COMPANY_SEARCH_ENDPOINT = "/public/idisc/api/company/valuebyuniqueId"

# Publication-document search page (ASP.NET WebForms). {lang} in {en,th}; {report_type} is a
# ddlReportType code (see SEC_REPORT_TYPE_*). GET returns the form + VIEWSTATE tokens; POST the
# form back to the same URL to run a search.
SEC_FINANCIAL_REPORT_ENDPOINT = "/public/idisc/{lang}/FinancialReport/{report_type}"

# "Display all results" page for a section that truncates inline. {slug} in SEC_VIEWMORE_SLUGS.
# Query params: uniqueIDReference, dateFrom, dateTo (yyyyMMdd).
SEC_VIEWMORE_ENDPOINT = "/public/idisc/{lang}/ViewMore/{slug}"

# Per-file download handler — GET ?FILEID=<path> -> zip/pdf bytes (Content-Disposition names it).
SEC_DOWNLOAD_ENDPOINT = "/public/idisc/Download"

# Page-specific referer (part of the bot-detection posture, mirrors the SET services).
SEC_REFERER = "https://market.sec.or.th/public/idisc/en/FinancialReport/ALL"

# ddlReportType codes accepted by the search form.
SEC_REPORT_TYPE_FINANCIAL_STATEMENT = "FS"  # returns FS + Key Financial Ratio + MD&A sections
SEC_REPORT_TYPE_FORM_56_1 = "R561"
SEC_REPORT_TYPE_FORM_56_2 = "R562"
SEC_REPORT_TYPE_KEY_FINANCIAL_RATIO = "KFR"

# ViewMore slugs (seen live) for the sections a FS search can truncate.
SEC_VIEWMORE_SLUGS: dict[str, str] = {
    "financial_statement": "fs-norm",
    "key_financial_ratio": "fs-kf",
    "mda": "fs-mda",
}

# The SEC search form's field names (ASP.NET control ids).
SEC_FORM_FIELD_REPORT_TYPE = "ctl00$CPH$ddlReportType"
SEC_FORM_FIELD_COMPANY = "ctl00$CPH$BsCompany"
SEC_FORM_FIELD_COMPANY_TEXT = "ctl00$CPH$BsCompany_t"
SEC_FORM_FIELD_COMPANY_VALUE = "ctl00$CPH$BsCompany_v"
SEC_FORM_FIELD_DATE_FROM = "ctl00$CPH$BSDateFrom"
SEC_FORM_FIELD_DATE_TO = "ctl00$CPH$BSDateTo"
SEC_FORM_FIELD_SEARCH = "ctl00$CPH$btSearch"

# Hidden ASP.NET postback tokens that must be echoed back (scraped from the GET page).
SEC_ASPNET_TOKEN_FIELDS = ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION")

# The search form accepts dd/MM/yyyy ONLY; ViewMore uses yyyyMMdd.
SEC_FORM_DATE_FORMAT = "%d/%m/%Y"
SEC_VIEWMORE_DATE_FORMAT = "%Y%m%d"

# Result-panel container id and the Thai "file not found" soft-404 marker (HTTP 200 + text/html).
SEC_RESULT_PANEL_ID = "ctl00_CPH_pnlControl"
SEC_FILE_NOT_FOUND_MARKER = "ไม่พบไฟล์ที่ระบุ"
