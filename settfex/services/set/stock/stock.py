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
    ) -> None:
        """
        Initialize Stock instance for a specific symbol.

        Args:
            symbol: Stock symbol (e.g., "CPALL", "PTT", "kbank")
            config: Optional fetcher configuration

        Example:
            >>> # Basic usage - SessionManager handles cookies automatically
            >>> stock = Stock("CPALL")
            >>>
            >>> # With custom configuration
            >>> config = FetcherConfig(timeout=60, max_retries=5)
            >>> stock = Stock("CPALL", config=config)
        """
        self.symbol = normalize_symbol(symbol)
        self.config = config

        # Initialize service instances (lazy initialization for future services)
        self._highlight_data_service: StockHighlightDataService | None = None
        self._profile_service: StockProfileService | None = None
        self._shareholder_service: ShareholderService | None = None

        logger.info(f"Stock instance created for symbol '{self.symbol}'")

    @property
    def highlight_data_service(self) -> StockHighlightDataService:
        """
        Get or create highlight data service instance.

        Returns:
            StockHighlightDataService instance
        """
        if self._highlight_data_service is None:
            self._highlight_data_service = StockHighlightDataService(config=self.config)
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

            self._profile_service = StockProfileService(config=self.config)
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

    @property
    def shareholder_service(self) -> "ShareholderService":
        """
        Get or create shareholder service instance.

        Returns:
            ShareholderService instance
        """
        if self._shareholder_service is None:
            from settfex.services.set.stock.shareholder import ShareholderService

            self._shareholder_service = ShareholderService(config=self.config)
        return self._shareholder_service

    async def get_shareholder_data(self, lang: str = "en") -> "ShareholderData":
        """
        Fetch shareholder data for this stock.

        Args:
            lang: Language for response ('en' or 'th', default: 'en')

        Returns:
            ShareholderData with major shareholders and free float information

        Raises:
            ValueError: If language is invalid
            Exception: If request fails

        Example:
            >>> stock = Stock("MINT")
            >>> data = await stock.get_shareholder_data()
            >>> print(f"Total Shareholders: {data.total_shareholder:,}")
            >>> print(f"Free Float: {data.free_float.percent_free_float:.2f}%")
            >>> for sh in data.major_shareholders[:5]:
            ...     print(f"{sh.sequence}. {sh.name}: {sh.percent_of_share:.2f}%")
        """
        logger.debug(f"Fetching shareholder data for {self.symbol} (lang={lang})")
        return await self.shareholder_service.fetch_shareholder_data(
            symbol=self.symbol, lang=lang
        )

    # Future service methods (placeholders for documentation)
    # async def get_financials(self, lang: str = "en") -> FinancialsData:
    #     """Fetch financial statements for this stock."""
    #     pass

    def __repr__(self) -> str:
        """String representation of Stock instance."""
        return f"Stock(symbol='{self.symbol}')"

    def __str__(self) -> str:
        """String representation of Stock instance."""
        return self.symbol
