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
        use_cookies: bool = True,
    ) -> None:
        """
        Initialize Stock instance for a specific symbol.

        Args:
            symbol: Stock symbol (e.g., "CPALL", "PTT", "kbank")
            config: Optional fetcher configuration
            session_cookies: Optional browser session cookies
            use_cookies: Whether to generate cookies automatically. Default True (recommended
                        for compatibility). Set to False only if providing session_cookies.

        Example:
            >>> # Basic usage (auto-generated cookies - recommended)
            >>> stock = Stock("CPALL")
            >>>
            >>> # With rate limiting to avoid HTTP 452
            >>> config = FetcherConfig(rate_limit_delay=0.2)
            >>> stock = Stock("CPALL", config=config)
            >>>
            >>> # With real browser session cookies (most reliable)
            >>> cookies = "charlot=abc123; incap_ses_357_2046605=xyz789; ..."
            >>> stock = Stock("CPALL", session_cookies=cookies)
            >>>
            >>> # No cookies mode (may get HTTP 403)
            >>> stock = Stock("CPALL", use_cookies=False)
        """
        self.symbol = normalize_symbol(symbol)
        self.config = config
        self.session_cookies = session_cookies
        self.use_cookies = use_cookies

        # Initialize service instances (lazy initialization for future services)
        self._highlight_data_service: StockHighlightDataService | None = None
        self._profile_service: StockProfileService | None = None

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
                config=self.config,
                session_cookies=self.session_cookies,
                use_cookies=self.use_cookies,
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

    @property
    def profile_service(self) -> "StockProfileService":
        """
        Get or create profile service instance.

        Returns:
            StockProfileService instance
        """
        if self._profile_service is None:
            from settfex.services.set.stock.profile_stock import StockProfileService

            self._profile_service = StockProfileService(
                config=self.config,
                session_cookies=self.session_cookies,
                use_cookies=self.use_cookies,
            )
        return self._profile_service

    async def get_profile(self, lang: str = "en") -> "StockProfile":
        """
        Fetch profile data for this stock.

        Args:
            lang: Language for response ('en' or 'th', default: 'en')

        Returns:
            StockProfile with company and listing information

        Raises:
            ValueError: If language is invalid
            Exception: If request fails

        Example:
            >>> stock = Stock("PTT")
            >>> profile = await stock.get_profile()
            >>> print(f"Company: {profile.name}")
            >>> print(f"Sector: {profile.sector_name}")
        """
        logger.debug(f"Fetching profile for {self.symbol} (lang={lang})")
        return await self.profile_service.fetch_profile(symbol=self.symbol, lang=lang)

    # Future service methods (placeholders for documentation)
    # async def get_shareholders(self, lang: str = "en") -> ShareholdersData:
    #     """Fetch shareholder information for this stock."""
    #     pass
    #
    # async def get_financials(self, lang: str = "en") -> FinancialsData:
    #     """Fetch financial statements for this stock."""
    #     pass

    def __repr__(self) -> str:
        """String representation of Stock instance."""
        return f"Stock(symbol='{self.symbol}')"

    def __str__(self) -> str:
        """String representation of Stock instance."""
        return self.symbol
