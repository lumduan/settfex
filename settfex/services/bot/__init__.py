"""Bank of Thailand API services (``gateway.api.bot.or.th``), new in 1.0.0.

Every user registers at https://portal.api.bot.or.th and gets one free token per product (see the
README). settfex only connects. It reads each token from the ``token=`` argument, from the
environment, or from a ``.env`` file, and never logs it.

Products and their token variables:
- Interest Rates: ``BANK_OF_THAILAND_TOKEN_INTEREST_RATES``
- Statistics: ``BANK_OF_THAILAND_TOKEN_STATISTICS``
- Exchange Rates: ``BANK_OF_THAILAND_TOKEN_EXCHANGE_RATES``
- Debt Securities Auction: ``BANK_OF_THAILAND_TOKEN_DEBT_SECURITIES_AUCTION``
- Others (financial institutions' holidays): ``BANK_OF_THAILAND_TOKEN_OTHERS``
- License Check: ``BANK_OF_THAILAND_TOKEN_LICENSE_CHECK``

``BANK_OF_THAILAND_TOKEN`` is the fallback for any of them.
"""

from settfex.services.bot.auth import read_env_file, resolve_bot_token
from settfex.services.bot.bank_of_thailand import BankOfThailand
from settfex.services.bot.client import BotClient
from settfex.services.bot.constants import (
    BOT_GATEWAY_URL,
    BOT_MANUAL_URL,
    BOT_PORTAL_URL,
    BOT_TOKEN_ENV,
    KNOWN_SERIES,
    BotProduct,
)
from settfex.services.bot.debt_securities import (
    DebtSecuritiesAuctionService,
    get_bond_auction_results,
)
from settfex.services.bot.exchange_rates import (
    ExchangeRatesService,
    get_exchange_rates,
    get_reference_rates,
)
from settfex.services.bot.holidays import HolidaysService, get_financial_institution_holidays
from settfex.services.bot.interest_rates import (
    InterestRatesService,
    get_bibor,
    get_deposit_rates,
    get_interbank_rates,
    get_loan_rates,
    get_policy_rate,
)
from settfex.services.bot.license_check import (
    LicenseCheckService,
    get_license_document,
    get_licensed_entity,
    search_licensed_entities,
)
from settfex.services.bot.models import (
    BiborRate,
    BondAuctionResult,
    BotReport,
    DepositRate,
    ExchangeRate,
    FinancialInstitutionHoliday,
    InterbankRate,
    License,
    LicensedEntity,
    LicensedEntityDetail,
    LicenseDocument,
    LicenseSearchResult,
    LoanRate,
    PolicyRate,
    RateTypeQuote,
    ReferenceRate,
    ReportHeader,
    SpotRate,
    StatCategory,
    StatObservation,
    StatSeries,
    StatSeriesInfo,
    SwapPoint,
)
from settfex.services.bot.statistics import (
    StatisticsService,
    get_stat_categories,
    get_stat_observations,
    get_stat_series_list,
    search_stat_series,
)

__all__ = [
    # facade, client, tokens
    "BankOfThailand",
    "BotClient",
    "BotProduct",
    "resolve_bot_token",
    "read_env_file",
    "BOT_GATEWAY_URL",
    "BOT_PORTAL_URL",
    "BOT_MANUAL_URL",
    "BOT_TOKEN_ENV",
    "KNOWN_SERIES",
    # services
    "InterestRatesService",
    "StatisticsService",
    "ExchangeRatesService",
    "DebtSecuritiesAuctionService",
    "HolidaysService",
    "LicenseCheckService",
    # convenience functions
    "get_policy_rate",
    "get_bibor",
    "get_deposit_rates",
    "get_loan_rates",
    "get_interbank_rates",
    "get_stat_categories",
    "get_stat_series_list",
    "search_stat_series",
    "get_stat_observations",
    "get_exchange_rates",
    "get_reference_rates",
    "get_bond_auction_results",
    "get_financial_institution_holidays",
    "search_licensed_entities",
    "get_licensed_entity",
    "get_license_document",
    # models
    "BotReport",
    "ReportHeader",
    "PolicyRate",
    "BiborRate",
    "DepositRate",
    "LoanRate",
    "InterbankRate",
    "RateTypeQuote",
    "SpotRate",
    "SwapPoint",
    "ExchangeRate",
    "ReferenceRate",
    "BondAuctionResult",
    "FinancialInstitutionHoliday",
    "StatCategory",
    "StatSeriesInfo",
    "StatSeries",
    "StatObservation",
    "LicensedEntity",
    "LicensedEntityDetail",
    "License",
    "LicenseSearchResult",
    "LicenseDocument",
]
