"""SET Stock List Service - Fetch list of stock details from SET API."""

from typing import Any

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from settfex.services.set.constants import SET_BASE_URL, SET_STOCK_LIST_ENDPOINT
from settfex.utils.data_fetcher import AsyncDataFetcher, FetcherConfig


class StockSymbol(BaseModel):
    """Model for individual stock symbol information."""

    symbol: str = Field(description="Stock symbol/ticker")
    name_th: str = Field(alias="nameTH", description="Company name in Thai")
    name_en: str = Field(alias="nameEN", description="Company name in English")
    market: str = Field(description="Market type (SET, mai, etc.)")
    security_type: str = Field(alias="securityType", description="Security type")
    type_sequence: int = Field(alias="typeSequence", description="Type sequence number")
    industry: str = Field(description="Industry classification")
    sector: str = Field(description="Sector classification")
    query_sector: str = Field(alias="querySector", description="Queryable sector name")
    is_iff: bool = Field(alias="isIFF", description="Is Infrastructure Fund Flag")
    is_foreign_listing: bool = Field(
        alias="isForeignListing", description="Is foreign listing flag"
    )
    remark: str = Field(default="", description="Additional remarks")

    model_config = ConfigDict(
        populate_by_name=True,  # Allow both field name and alias
        str_strip_whitespace=True,  # Strip whitespace from strings
    )


class StockListResponse(BaseModel):
    """Response model for stock list API."""

    security_symbols: list[StockSymbol] = Field(
        alias="securitySymbols", description="List of stock symbols"
    )

    model_config = ConfigDict(
        populate_by_name=True,  # Allow both field name and alias
    )

    @property
    def count(self) -> int:
        """Get total count of securities."""
        return len(self.security_symbols)

    def filter_by_market(self, market: str) -> list[StockSymbol]:
        """
        Filter securities by market type.

        Args:
            market: Market type (e.g., 'SET', 'mai')

        Returns:
            List of stock symbols for the specified market
        """
        return [s for s in self.security_symbols if s.market.upper() == market.upper()]

    def filter_by_industry(self, industry: str) -> list[StockSymbol]:
        """
        Filter securities by industry.

        Args:
            industry: Industry classification

        Returns:
            List of stock symbols in the specified industry
        """
        return [s for s in self.security_symbols if s.industry.upper() == industry.upper()]

    def get_symbol(self, symbol: str) -> StockSymbol | None:
        """
        Get a specific stock symbol.

        Args:
            symbol: Stock symbol to find

        Returns:
            StockSymbol if found, None otherwise
        """
        for s in self.security_symbols:
            if s.symbol.upper() == symbol.upper():
                return s
        return None


class StockListService:
    """
    Service for fetching stock list from SET API.

    This service provides async methods to fetch the complete list of stocks
    traded on the Stock Exchange of Thailand (SET), including company names,
    market classifications, and industry sectors.
    """

    def __init__(
        self, config: FetcherConfig | None = None, session_cookies: str | None = None
    ) -> None:
        """
        Initialize the stock list service.

        Args:
            config: Optional fetcher configuration (uses defaults if None)
            session_cookies: Optional browser session cookies for authenticated requests.
                           When None, generated Incapsula cookies are used.
                           For production use with real API access, provide actual
                           browser session cookies from an authenticated session.

        Example:
            >>> # Using generated cookies (may be blocked by Incapsula)
            >>> service = StockListService()
            >>>
            >>> # Using real browser session cookies (recommended)
            >>> cookies = "charlot=abc123; incap_ses_357_2046605=xyz789; ..."
            >>> service = StockListService(session_cookies=cookies)
        """
        self.config = config or FetcherConfig()
        self.base_url = SET_BASE_URL
        self.session_cookies = session_cookies
        logger.info(f"StockListService initialized with base_url={self.base_url}")
        if session_cookies:
            logger.debug("Using provided session cookies for authentication")

    async def fetch_stock_list(self) -> StockListResponse:
        """
        Fetch the complete list of stocks from SET API.

        Returns:
            StockListResponse containing all stock symbols and details

        Raises:
            Exception: If request fails or response cannot be parsed

        Example:
            >>> service = StockListService()
            >>> response = await service.fetch_stock_list()
            >>> print(f"Total stocks: {response.count}")
            >>> print(f"SET stocks: {len(response.filter_by_market('SET'))}")
        """
        url = f"{self.base_url}{SET_STOCK_LIST_ENDPOINT}"

        logger.info(f"Fetching stock list from {url}")

        async with AsyncDataFetcher(config=self.config) as fetcher:
            # Get optimized headers for SET API (includes all Incapsula bypass headers)
            headers = AsyncDataFetcher.get_set_api_headers()

            # Use provided session cookies or generate Incapsula-aware cookies
            cookies = self.session_cookies or AsyncDataFetcher.generate_incapsula_cookies()

            # Fetch JSON data from API
            data = await fetcher.fetch_json(
                url, headers=headers, cookies=cookies, use_random_cookies=False
            )

            # Parse and validate response using Pydantic
            response = StockListResponse(**data)

            logger.info(
                f"Successfully fetched {response.count} stock symbols from SET API"
            )

            return response

    async def fetch_stock_list_raw(self) -> dict[str, Any]:
        """
        Fetch stock list as raw dictionary without Pydantic validation.

        Useful for debugging or when you need the raw API response.

        Returns:
            Raw dictionary from API

        Raises:
            Exception: If request fails

        Example:
            >>> service = StockListService()
            >>> raw_data = await service.fetch_stock_list_raw()
            >>> print(raw_data.keys())
        """
        url = f"{self.base_url}{SET_STOCK_LIST_ENDPOINT}"

        logger.info(f"Fetching raw stock list from {url}")

        async with AsyncDataFetcher(config=self.config) as fetcher:
            # Get optimized headers for SET API
            headers = AsyncDataFetcher.get_set_api_headers()

            # Use provided session cookies or generate Incapsula-aware cookies
            cookies = self.session_cookies or AsyncDataFetcher.generate_incapsula_cookies()

            # Fetch JSON data
            data = await fetcher.fetch_json(
                url, headers=headers, cookies=cookies, use_random_cookies=False
            )
            logger.debug(f"Raw response keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")  # noqa: E501
            return data


# Convenience function for quick access
async def get_stock_list(
    config: FetcherConfig | None = None, session_cookies: str | None = None
) -> StockListResponse:
    """
    Convenience function to fetch stock list.

    Args:
        config: Optional fetcher configuration
        session_cookies: Optional browser session cookies for authenticated requests

    Returns:
        StockListResponse with all stock symbols

    Example:
        >>> from settfex.services.set import get_stock_list
        >>> # Using generated cookies
        >>> response = await get_stock_list()
        >>> # Or with real browser session cookies (recommended)
        >>> cookies = "charlot=abc123; incap_ses_357_2046605=xyz789; ..."
        >>> response = await get_stock_list(session_cookies=cookies)
        >>> for stock in response.security_symbols[:5]:
        ...     print(f"{stock.symbol}: {stock.name_en}")
    """
    service = StockListService(config=config, session_cookies=session_cookies)
    return await service.fetch_stock_list()
