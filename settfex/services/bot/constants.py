"""Constants for the Bank of Thailand (BOT) API gateway (``gateway.api.bot.or.th``), 1.0.0.

Every endpoint below was live-verified on 2026-11-23 with one token per product, against the
official OpenAPI documents the portal serves (``portal.api.bot.or.th/system/api_details/...``).
Where the two disagreed, the code follows the API (see the BOT service docs).
"""

from __future__ import annotations

from enum import StrEnum

BOT_GATEWAY_URL = "https://gateway.api.bot.or.th"
BOT_PORTAL_URL = "https://portal.api.bot.or.th"
#: The portal's sign-up and token guide, linked from errors and the README.
BOT_MANUAL_URL = "https://portal.api.bot.or.th/manual"

#: The fallback variable, used for any product without its own key.
BOT_TOKEN_ENV = "BANK_OF_THAILAND_TOKEN"
#: The prefix of each product's own variable, e.g. ``BANK_OF_THAILAND_TOKEN_INTEREST_RATES``.
BOT_TOKEN_ENV_PREFIX = "BANK_OF_THAILAND_TOKEN_"


class BotProduct(StrEnum):
    """The six BOT API products. Each portal credential (token) is bound to ONE of them."""

    INTEREST_RATES = "interest_rates"
    STATISTICS = "statistics"
    EXCHANGE_RATES = "exchange_rates"
    DEBT_SECURITIES_AUCTION = "debt_securities_auction"
    OTHERS = "others"
    LICENSE_CHECK = "license_check"

    @property
    def env_key(self) -> str:
        """This product's own token variable, e.g. ``BANK_OF_THAILAND_TOKEN_STATISTICS``."""
        return f"{BOT_TOKEN_ENV_PREFIX}{self.value.upper()}"


# --- Interest Rates ---------------------------------------------------------------------------
POLICY_RATE_PATH = "PolicyRate/v3/policy_rate/"
BIBOR_PATH = "BIBOR/v2/bibor_rate/"
BIBOR_AVERAGE_PATH = "BIBOR/v2/bibor_avg_rate/"
DEPOSIT_RATE_PATH = "DepositRate/v2/deposit_rate/"
DEPOSIT_RATE_RANGE_PATH = "DepositRate/v2/avg_deposit_rate/"
LOAN_RATE_PATH = "LoanRate/v2/loan_rate/"
LOAN_RATE_AVERAGE_PATH = "LoanRate/v2/avg_loan_rate/"
INTERBANK_RATE_PATH = "Stat-InterbankTransactionRate/v2/INTRBNK_TXN_RATE/"
EXTERNAL_RATE_PATH = "Stat-ExternalInterestRate/v2/EXT_INT_RATE/"
SPOT_RATE_PATH = "Stat-SpotRate/v2/SPOTRATE/"
SWAP_POINT_PATH = "Stat-SwapPoint/v2/SWAPPOINT/"
IMPLIED_RATE_PATH = "Stat-ThaiBahtImpliedInterestRate/v2/THB_IMPL_INT_RATE/"

# --- Exchange Rates (one path per frequency) --------------------------------------------------
EXCHANGE_RATE_PATH = "Stat-ExchangeRate/v2/{frequency}_AVG_EXG_RATE/"
REFERENCE_RATE_PATH = "Stat-ReferenceRate/v2/{frequency}_REF_RATE/"

# --- Statistics -------------------------------------------------------------------------------
STAT_CATEGORY_LIST_PATH = "categorylist/category_list/"
STAT_SERIES_LIST_PATH = "categorylist/series_list/"
STAT_SEARCH_PATH = "search-series/"
STAT_OBSERVATIONS_PATH = "observations/"

# --- Debt Securities Auction, Others, License Check -------------------------------------------
BOND_AUCTION_PATH = "BondAuction/bond_auction_v2/"
FI_HOLIDAYS_PATH = "financial-institutions-holidays/"
LICENSE_SEARCH_PATH = "BotLicenseCheckAPI/SearchAuthorized"
LICENSE_DETAIL_PATH = "BotLicenseCheckAPI/AuthorizedDetail"
LICENSE_DOCUMENT_PATH = "BotLicenseCheckAPI/License"

#: Statistics series codes worth knowing, live-verified 2026-11-23. Codes change: the search
#: lists DISCONTINUED ones first (``FMRTINTM00027``-``49`` ended 2025-07; these replace them).
KNOWN_SERIES: dict[str, str] = {
    "thor": "FMRTTHORD00003",  # Thai Overnight Repurchase Rate, daily
    "thor_average_1m": "FMRTTHORAVG1MD00004",  # compounded THOR averages, daily
    "thor_average_3m": "FMRTTHORAVG3MD00005",
    "thor_average_6m": "FMRTTHORAVG6MD00006",
    "government_yield_1m": "FMRTINTM00284",  # T-bill & government bond yields, MONTHLY averages
    "government_yield_3m": "FMRTINTM00285",
    "government_yield_6m": "FMRTINTM00286",
    "government_yield_1y": "FMRTINTM00287",
    "government_yield_10y": "FMRTINTM00296",
}
