"""Unified Stock class for accessing multiple stock-related services."""

from loguru import logger

from settfex.services.set.stock.highlight_data import (
    StockHighlightData,
    StockHighlightDataService,
)
from settfex.services.set.stock.utils import normalize_symbol
from settfex.utils.data_fetcher import FetcherConfig


class Stock:
    """
    Unified class for accessing all stock-related services for a single symbol.

    This class provides a clean interface to fetch various types of data
    for a stock symbol, including highlight data, shareholders, financials, etc.

    Example:
        >>> stock = Stock("CPALL")
        >>> highlight = await stock.get_highlight_data()
        >>> print(f"Market Cap: {highlight.market_cap:,.0f}")
        >>>
        >>> # Future services (planned)
        >>> # shareholders = await stock.get_shareholders()
        >>> # financials = await stock.get_financials()
    """

    def __init__(
        self,
        symbol: str,
        config: FetcherConfig | None = None,
        session_cookies: str | None = None,
    ) -> None:
        """
        Initialize Stock instance for a specific symbol.

        Args:
            symbol: Stock symbol (e.g., "CPALL", "PTT", "kbank")
            config: Optional fetcher configuration
            session_cookies: Optional browser session cookies

        Example:
            >>> # Basic usage
            >>> stock = Stock("CPALL")
            >>>
            >>> # With custom config
            >>> config = FetcherConfig(timeout=60, max_retries=5)
            >>> stock = Stock("CPALL", config=config)
            >>>
            >>> # With session cookies
            >>> cookies = "charlot=abc123; incap_ses_357_2046605=xyz789; ..."
            >>> stock = Stock("CPALL", session_cookies=cookies)
        """
        self.symbol = normalize_symbol(symbol)
        self.config = config
        self.session_cookies = session_cookies

        # Initialize service instances (lazy initialization for future services)
        self._highlight_data_service: StockHighlightDataService | None = None

        logger.info(f"Stock instance created for symbol '{self.symbol}'")

    @property
    def highlight_data_service(self) -> StockHighlightDataService:
        """
        Get or create highlight data service instance.

        Returns:
            StockHighlightDataService instance
        """
        if self._highlight_data_service is None:
            self._highlight_data_service = StockHighlightDataService(
                config=self.config, session_cookies=self.session_cookies
            )
        return self._highlight_data_service

    async def get_highlight_data(self, lang: str = "en") -> StockHighlightData:
        """
        Fetch highlight data for this stock.

        Args:
            lang: Language for response ('en' or 'th', default: 'en')

        Returns:
            StockHighlightData with metrics and statistics

        Raises:
            ValueError: If language is invalid
            Exception: If request fails

        Example:
            >>> stock = Stock("CPALL")
            >>> data = await stock.get_highlight_data()
            >>> print(f"P/E: {data.pe_ratio}, P/B: {data.pb_ratio}")
            >>>
            >>> # In Thai
            >>> data = await stock.get_highlight_data(lang="th")
        """
        logger.debug(f"Fetching highlight data for {self.symbol} (lang={lang})")
        return await self.highlight_data_service.fetch_highlight_data(
            symbol=self.symbol, lang=lang
        )

    # Future service methods (placeholders for documentation)
    # async def get_shareholders(self, lang: str = "en") -> ShareholdersData:
    #     """Fetch shareholder information for this stock."""
    #     pass
    #
    # async def get_financials(self, lang: str = "en") -> FinancialsData:
    #     """Fetch financial statements for this stock."""
    #     pass
    #
    # async def get_company_profile(self, lang: str = "en") -> CompanyProfile:
    #     """Fetch company profile information."""
    #     pass

    def __repr__(self) -> str:
        """String representation of Stock instance."""
        return f"Stock(symbol='{self.symbol}')"

    def __str__(self) -> str:
        """String representation of Stock instance."""
        return self.symbol
