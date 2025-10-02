"""SET Stock Highlight Data Service - Fetch highlight data for individual stock symbols."""

from datetime import datetime
from typing import Any

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from settfex.services.set.constants import SET_BASE_URL, SET_STOCK_HIGHLIGHT_DATA_ENDPOINT
from settfex.services.set.stock.utils import normalize_language, normalize_symbol
from settfex.utils.data_fetcher import AsyncDataFetcher, FetcherConfig


class StockHighlightData(BaseModel):
    """Model for stock highlight data."""

    symbol: str = Field(description="Stock symbol/ticker")
    as_of_date: datetime = Field(alias="asOfDate", description="Data as of date")
    market_cap: float | None = Field(alias="marketCap", description="Market capitalization")
    pe_ratio: float | None = Field(alias="peRatio", description="Price to Earnings ratio")
    pb_ratio: float | None = Field(alias="pbRatio", description="Price to Book ratio")
    dividend_yield: float | None = Field(
        alias="dividendYield", description="Dividend yield percentage"
    )
    beta: float | None = Field(description="Beta coefficient")
    ytd_percent_change: float | None = Field(
        alias="ytdPercentChange", description="Year-to-date percent change"
    )
    xd_date: datetime | None = Field(alias="xdDate", description="Ex-dividend date")
    xd_session: str | None = Field(alias="xdSession", description="Ex-dividend session")
    dividend: float | None = Field(description="Dividend amount")
    dividend_ratio: float | None = Field(alias="dividendRatio", description="Dividend ratio")
    free_float_as_of_date: datetime | None = Field(
        alias="freeFloatAsOfDate", description="Free float data as of date"
    )
    percent_free_float: float | None = Field(
        alias="percentFreeFloat", description="Percentage of free float"
    )
    year_high_price: float | None = Field(
        alias="yearHighPrice", description="52-week high price"
    )
    year_low_price: float | None = Field(alias="yearLowPrice", description="52-week low price")
    listed_share: int | None = Field(alias="listedShare", description="Number of listed shares")
    par: float | None = Field(description="Par value")
    currency: str | None = Field(description="Currency code")
    nvdr_buy_volume: float | None = Field(
        alias="nvdrBuyVolume", description="NVDR buy volume"
    )
    nvdr_sell_volume: float | None = Field(
        alias="nvdrSellVolume", description="NVDR sell volume"
    )
    nvdr_buy_value: float | None = Field(alias="nvdrBuyValue", description="NVDR buy value")
    nvdr_sell_value: float | None = Field(alias="nvdrSellValue", description="NVDR sell value")
    outstanding_date: datetime | None = Field(
        alias="outstandingDate", description="Outstanding shares date"
    )
    outstanding_share: int | None = Field(
        alias="outstandingShare", description="Number of outstanding shares"
    )
    dividend_yield_12m: float | None = Field(
        alias="dividendYield12M", description="12-month dividend yield"
    )
    turnover_ratio: float | None = Field(
        alias="turnoverRatio", description="Turnover ratio"
    )
    nvdr_net_volume: float | None = Field(
        alias="nvdrNetVolume", description="NVDR net volume"
    )
    nvdr_net_value: float | None = Field(alias="nvdrNetValue", description="NVDR net value")

    model_config = ConfigDict(
        populate_by_name=True,  # Allow both field name and alias
        str_strip_whitespace=True,  # Strip whitespace from strings
    )


class StockHighlightDataResponse(BaseModel):
    """Response model for stock highlight data API."""

    data: StockHighlightData = Field(description="Stock highlight data")

    model_config = ConfigDict(
        populate_by_name=True,  # Allow both field name and alias
    )


class StockHighlightDataService:
    """
    Service for fetching stock highlight data from SET API.

    This service provides async methods to fetch highlight data for individual
    stock symbols from the Stock Exchange of Thailand (SET), including metrics
    like market cap, P/E ratio, dividend yield, and trading statistics.
    """

    def __init__(
        self, config: FetcherConfig | None = None, session_cookies: str | None = None
    ) -> None:
        """
        Initialize the stock highlight data service.

        Args:
            config: Optional fetcher configuration (uses defaults if None)
            session_cookies: Optional browser session cookies for authenticated requests.
                           When None, generated Incapsula cookies are used.
                           For production use with real API access, provide actual
                           browser session cookies from an authenticated session.

        Example:
            >>> # Using generated cookies (may be blocked by Incapsula)
            >>> service = StockHighlightDataService()
            >>>
            >>> # Using real browser session cookies (recommended)
            >>> cookies = "charlot=abc123; incap_ses_357_2046605=xyz789; ..."
            >>> service = StockHighlightDataService(session_cookies=cookies)
        """
        self.config = config or FetcherConfig()
        self.base_url = SET_BASE_URL
        self.session_cookies = session_cookies
        logger.info(f"StockHighlightDataService initialized with base_url={self.base_url}")
        if session_cookies:
            logger.debug("Using provided session cookies for authentication")

    async def fetch_highlight_data(
        self, symbol: str, lang: str = "en"
    ) -> StockHighlightData:
        """
        Fetch highlight data for a specific stock symbol.

        Args:
            symbol: Stock symbol (e.g., "CPALL", "PTT", "kbank")
            lang: Language for response ('en' or 'th', default: 'en')

        Returns:
            StockHighlightData containing highlight metrics and statistics

        Raises:
            ValueError: If symbol is empty or language is invalid
            Exception: If request fails or response cannot be parsed

        Example:
            >>> service = StockHighlightDataService()
            >>> data = await service.fetch_highlight_data("CPALL", lang="en")
            >>> print(f"Market Cap: {data.market_cap:,.0f}")
            >>> print(f"P/E Ratio: {data.pe_ratio}")
            >>> print(f"Dividend Yield: {data.dividend_yield}%")
        """
        # Normalize and validate inputs
        symbol = normalize_symbol(symbol)
        lang = normalize_language(lang)

        if not symbol:
            error_msg = "Stock symbol cannot be empty"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Build URL with symbol and language parameters
        endpoint = SET_STOCK_HIGHLIGHT_DATA_ENDPOINT.format(symbol=symbol)
        url = f"{self.base_url}{endpoint}?lang={lang}"

        logger.info(f"Fetching highlight data for symbol '{symbol}' (lang={lang}) from {url}")

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
            highlight_data = StockHighlightData(**data)

            logger.info(
                f"Successfully fetched highlight data for {symbol}: "
                f"Market Cap={highlight_data.market_cap}, "
                f"P/E={highlight_data.pe_ratio}, "
                f"P/B={highlight_data.pb_ratio}"
            )

            return highlight_data

    async def fetch_highlight_data_raw(
        self, symbol: str, lang: str = "en"
    ) -> dict[str, Any]:
        """
        Fetch highlight data as raw dictionary without Pydantic validation.

        Useful for debugging or when you need the raw API response.

        Args:
            symbol: Stock symbol (e.g., "CPALL", "PTT", "kbank")
            lang: Language for response ('en' or 'th', default: 'en')

        Returns:
            Raw dictionary from API

        Raises:
            ValueError: If symbol is empty or language is invalid
            Exception: If request fails

        Example:
            >>> service = StockHighlightDataService()
            >>> raw_data = await service.fetch_highlight_data_raw("CPALL")
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
        endpoint = SET_STOCK_HIGHLIGHT_DATA_ENDPOINT.format(symbol=symbol)
        url = f"{self.base_url}{endpoint}?lang={lang}"

        logger.info(f"Fetching raw highlight data for '{symbol}' (lang={lang}) from {url}")

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
async def get_highlight_data(
    symbol: str,
    lang: str = "en",
    config: FetcherConfig | None = None,
    session_cookies: str | None = None,
) -> StockHighlightData:
    """
    Convenience function to fetch stock highlight data.

    Args:
        symbol: Stock symbol (e.g., "CPALL", "PTT", "kbank")
        lang: Language for response ('en' or 'th', default: 'en')
        config: Optional fetcher configuration
        session_cookies: Optional browser session cookies for authenticated requests

    Returns:
        StockHighlightData with highlight metrics and statistics

    Example:
        >>> from settfex.services.set.stock import get_highlight_data
        >>> # Using generated cookies
        >>> data = await get_highlight_data("CPALL")
        >>> print(f"{data.symbol}: Market Cap = {data.market_cap:,.0f}")
        >>>
        >>> # Or with real browser session cookies (recommended)
        >>> cookies = "charlot=abc123; incap_ses_357_2046605=xyz789; ..."
        >>> data = await get_highlight_data("CPALL", lang="th", session_cookies=cookies)
    """
    service = StockHighlightDataService(config=config, session_cookies=session_cookies)
    return await service.fetch_highlight_data(symbol=symbol, lang=lang)
