"""SET Stock Profile Service - Fetch profile data for individual stock symbols."""

from datetime import datetime
from typing import Any

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from settfex.services.set.constants import SET_BASE_URL, SET_STOCK_PROFILE_ENDPOINT
from settfex.services.set.stock.utils import normalize_language, normalize_symbol
from settfex.utils.data_fetcher import AsyncDataFetcher, FetcherConfig


class StockProfile(BaseModel):
    """Model for stock profile data."""

    symbol: str = Field(description="Stock symbol/ticker")
    name: str = Field(description="Company name")
    market: str = Field(description="Market (SET, mai, etc.)")
    industry: str = Field(description="Industry code")
    industry_name: str = Field(
        alias="industryName", description="Industry name in readable format"
    )
    sector: str = Field(description="Sector code")
    sector_name: str = Field(alias="sectorName", description="Sector name in readable format")
    security_type: str = Field(alias="securityType", description="Security type code")
    security_type_name: str = Field(
        alias="securityTypeName", description="Security type name in readable format"
    )
    status: str = Field(description="Listing status (Listed, Delisted, etc.)")
    listed_date: datetime | None = Field(
        alias="listedDate", description="Date when the stock was listed"
    )
    first_trade_date: datetime | None = Field(
        alias="firstTradeDate", description="Date of first trade"
    )
    last_trade_date: datetime | None = Field(
        alias="lastTradeDate", description="Date of last trade (if delisted)"
    )
    maturity_date: datetime | None = Field(
        alias="maturityDate", description="Maturity date (for bonds/warrants)"
    )
    fiscal_year_end: str | None = Field(
        alias="fiscalYearEnd", description="Fiscal year end date (DD/MM format)"
    )
    fiscal_year_end_display: str | None = Field(
        alias="fiscalYearEndDisplay", description="Fiscal year end date in display format"
    )
    account_form: str | None = Field(
        alias="accountForm", description="Accounting form type"
    )
    par: float | None = Field(description="Par value per share")
    currency: str | None = Field(description="Currency code (THB, USD, etc.)")
    listed_share: int | None = Field(
        alias="listedShare", description="Number of listed shares"
    )
    ipo: float | None = Field(description="Initial Public Offering price")
    isin_local: str | None = Field(alias="isinLocal", description="ISIN code for local trading")
    isin_foreign: str | None = Field(
        alias="isinForeign", description="ISIN code for foreign trading"
    )
    isin_nvdr: str | None = Field(alias="isinNVDR", description="ISIN code for NVDR")
    percent_free_float: float | None = Field(
        alias="percentFreeFloat", description="Percentage of free float shares"
    )
    foreign_limit_as_of: datetime | None = Field(
        alias="foreignLimitAsOf", description="Foreign limit data as of date"
    )
    percent_foreign_room: float | None = Field(
        alias="percentForeignRoom", description="Percentage of foreign room available"
    )
    percent_foreign_limit: float | None = Field(
        alias="percentForeignLimit", description="Percentage of foreign ownership limit"
    )
    foreign_available: int | None = Field(
        alias="foreignAvailable", description="Number of shares available for foreign ownership"
    )
    underlying: str | None = Field(description="Underlying security (for derivatives)")
    exercise_price: float | None = Field(
        alias="exercisePrice", description="Exercise price (for warrants)"
    )
    exercise_ratio: str | None = Field(
        alias="exerciseRatio", description="Exercise ratio (for warrants)"
    )
    reserved_share: int | None = Field(
        alias="reservedShare", description="Number of reserved shares"
    )
    converted_share: int | None = Field(
        alias="convertedShare", description="Number of converted shares"
    )
    last_exercise_date: datetime | None = Field(
        alias="lastExerciseDate", description="Last exercise date (for warrants)"
    )
    issued_share: int | None = Field(
        alias="issuedShare", description="Number of issued shares"
    )

    model_config = ConfigDict(
        populate_by_name=True,  # Allow both field name and alias
        str_strip_whitespace=True,  # Strip whitespace from strings
    )


class StockProfileService:
    """
    Service for fetching stock profile data from SET API.

    This service provides async methods to fetch comprehensive profile information
    for individual stock symbols from the Stock Exchange of Thailand (SET), including
    company details, listing information, share structure, and foreign ownership limits.
    """

    def __init__(
        self, config: FetcherConfig | None = None, session_cookies: str | None = None
    ) -> None:
        """
        Initialize the stock profile service.

        Args:
            config: Optional fetcher configuration (uses defaults if None)
            session_cookies: Optional browser session cookies for authenticated requests.
                           When None, generated Incapsula cookies are used.
                           For production use with real API access, provide actual
                           browser session cookies from an authenticated session.

        Example:
            >>> # Using generated cookies (may be blocked by Incapsula)
            >>> service = StockProfileService()
            >>>
            >>> # Using real browser session cookies (recommended)
            >>> cookies = "charlot=abc123; incap_ses_357_2046605=xyz789; ..."
            >>> service = StockProfileService(session_cookies=cookies)
        """
        self.config = config or FetcherConfig()
        self.base_url = SET_BASE_URL
        self.session_cookies = session_cookies
        logger.info(f"StockProfileService initialized with base_url={self.base_url}")
        if session_cookies:
            logger.debug("Using provided session cookies for authentication")

    async def fetch_profile(
        self, symbol: str, lang: str = "en"
    ) -> StockProfile:
        """
        Fetch profile data for a specific stock symbol.

        Args:
            symbol: Stock symbol (e.g., "PTT", "CPALL", "kbank")
            lang: Language for response ('en' or 'th', default: 'en')

        Returns:
            StockProfile containing comprehensive company and listing information

        Raises:
            ValueError: If symbol is empty or language is invalid
            Exception: If request fails or response cannot be parsed

        Example:
            >>> service = StockProfileService()
            >>> profile = await service.fetch_profile("PTT", lang="en")
            >>> print(f"Company: {profile.name}")
            >>> print(f"Market: {profile.market}, Sector: {profile.sector_name}")
            >>> print(f"Listed Date: {profile.listed_date}")
            >>> print(f"IPO Price: {profile.ipo} {profile.currency}")
        """
        # Normalize and validate inputs
        symbol = normalize_symbol(symbol)
        lang = normalize_language(lang)

        if not symbol:
            error_msg = "Stock symbol cannot be empty"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Build URL with symbol and language parameters
        endpoint = SET_STOCK_PROFILE_ENDPOINT.format(symbol=symbol)
        url = f"{self.base_url}{endpoint}?lang={lang}"

        logger.info(f"Fetching profile data for symbol '{symbol}' (lang={lang}) from {url}")

        async with AsyncDataFetcher(config=self.config) as fetcher:
            # Get optimized headers for SET API (includes all Incapsula bypass headers)
            headers = AsyncDataFetcher.get_set_api_headers()

            # Use provided session cookies or generate Incapsula-aware cookies
            cookies = self.session_cookies or AsyncDataFetcher.generate_incapsula_cookies()

            # Fetch raw response first to check status
            response = await fetcher.fetch(
                url, headers=headers, cookies=cookies, use_random_cookies=False
            )

            # Check for Incapsula/bot detection errors
            if response.status_code != 200:
                error_msg = (
                    f"Failed to fetch profile for {symbol}: "
                    f"HTTP {response.status_code}. "
                    f"This may be due to Incapsula bot detection. "
                    f"Try using real browser session cookies."
                )
                logger.error(error_msg)
                raise Exception(error_msg)

            # Parse JSON
            import json
            try:
                data = json.loads(response.text)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.debug(f"Response text: {response.text[:500]}")
                raise

            # Parse and validate response using Pydantic
            profile = StockProfile(**data)

            logger.info(
                f"Successfully fetched profile for {symbol}: "
                f"Name={profile.name}, Market={profile.market}, "
                f"Sector={profile.sector_name}, Status={profile.status}"
            )

            return profile

    async def fetch_profile_raw(
        self, symbol: str, lang: str = "en"
    ) -> dict[str, Any]:
        """
        Fetch profile data as raw dictionary without Pydantic validation.

        Useful for debugging or when you need the raw API response.

        Args:
            symbol: Stock symbol (e.g., "PTT", "CPALL", "kbank")
            lang: Language for response ('en' or 'th', default: 'en')

        Returns:
            Raw dictionary from API

        Raises:
            ValueError: If symbol is empty or language is invalid
            Exception: If request fails

        Example:
            >>> service = StockProfileService()
            >>> raw_data = await service.fetch_profile_raw("PTT")
            >>> print(raw_data.keys())
        """
        # Normalize and validate inputs
        symbol = normalize_symbol(symbol)
        lang = normalize_language(lang)

        if not symbol:
            error_msg = "Stock symbol cannot be empty"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Build URL with symbol and language parameters
        endpoint = SET_STOCK_PROFILE_ENDPOINT.format(symbol=symbol)
        url = f"{self.base_url}{endpoint}?lang={lang}"

        logger.info(f"Fetching raw profile data for '{symbol}' (lang={lang}) from {url}")

        async with AsyncDataFetcher(config=self.config) as fetcher:
            # Get optimized headers for SET API
            headers = AsyncDataFetcher.get_set_api_headers()

            # Use provided session cookies or generate Incapsula-aware cookies
            cookies = self.session_cookies or AsyncDataFetcher.generate_incapsula_cookies()

            # Fetch JSON data
            data = await fetcher.fetch_json(
                url, headers=headers, cookies=cookies, use_random_cookies=False
            )
            logger.debug(
                f"Raw response keys: {list(data.keys()) if isinstance(data, dict) else type(data)}"
            )
            return data


# Convenience function for quick access
async def get_profile(
    symbol: str,
    lang: str = "en",
    config: FetcherConfig | None = None,
    session_cookies: str | None = None,
) -> StockProfile:
    """
    Convenience function to fetch stock profile data.

    Args:
        symbol: Stock symbol (e.g., "PTT", "CPALL", "kbank")
        lang: Language for response ('en' or 'th', default: 'en')
        config: Optional fetcher configuration
        session_cookies: Optional browser session cookies for authenticated requests

    Returns:
        StockProfile with comprehensive company and listing information

    Example:
        >>> from settfex.services.set.stock import get_profile
        >>> # Using generated cookies
        >>> profile = await get_profile("PTT")
        >>> print(f"{profile.symbol}: {profile.name}")
        >>> print(f"Sector: {profile.sector_name}, Industry: {profile.industry_name}")
        >>>
        >>> # Or with real browser session cookies (recommended)
        >>> cookies = "charlot=abc123; incap_ses_357_2046605=xyz789; ..."
        >>> profile = await get_profile("PTT", lang="th", session_cookies=cookies)
    """
    service = StockProfileService(config=config, session_cookies=session_cookies)
    return await service.fetch_profile(symbol=symbol, lang=lang)
