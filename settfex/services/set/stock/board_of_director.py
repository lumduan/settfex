"""SET Board of Director Service - Fetch board of directors for individual stock symbols."""

from typing import Any

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from settfex.services.set.constants import SET_BASE_URL, SET_BOARD_OF_DIRECTOR_ENDPOINT
from settfex.services.set.stock.utils import normalize_language, normalize_symbol
from settfex.utils.data_fetcher import AsyncDataFetcher, FetcherConfig


class Director(BaseModel):
    """Model for individual board member/director information."""

    name: str = Field(description="Director's full name")
    positions: list[str] = Field(description="List of positions held by the director")

    model_config = ConfigDict(
        str_strip_whitespace=True,  # Strip whitespace from strings
    )


class BoardOfDirectorService:
    """
    Service for fetching board of directors data from SET API.

    This service provides async methods to fetch board of directors and management
    information for individual stock symbols from the Stock Exchange of Thailand (SET).
    """

    def __init__(self, config: FetcherConfig | None = None) -> None:
        """
        Initialize the board of director service.

        Args:
            config: Optional fetcher configuration (uses defaults if None)

        Example:
            >>> # Default: Uses SessionManager for automatic cookie handling
            >>> service = BoardOfDirectorService()
        """
        self.config = config or FetcherConfig()
        self.base_url = SET_BASE_URL
        logger.info(f"BoardOfDirectorService initialized with base_url={self.base_url}")

    async def fetch_board_of_directors(
        self, symbol: str, lang: str = "en"
    ) -> list[Director]:
        """
        Fetch board of directors for a specific stock symbol.

        Args:
            symbol: Stock symbol (e.g., "CPALL", "PTT", "mint")
            lang: Language for response ('en' or 'th', default: 'en')

        Returns:
            List of Director objects containing name and positions

        Raises:
            ValueError: If symbol is empty or language is invalid
            Exception: If request fails or response cannot be parsed

        Example:
            >>> service = BoardOfDirectorService()
            >>> directors = await service.fetch_board_of_directors("MINT", lang="en")
            >>> for director in directors:
            ...     print(f"{director.name}: {', '.join(director.positions)}")
        """
        # Normalize and validate inputs
        symbol = normalize_symbol(symbol)
        lang = normalize_language(lang)

        if not symbol:
            error_msg = "Stock symbol cannot be empty"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Build URL with symbol and language parameters
        endpoint = SET_BOARD_OF_DIRECTOR_ENDPOINT.format(symbol=symbol)
        url = f"{self.base_url}{endpoint}?lang={lang}"

        logger.info(
            f"Fetching board of directors for symbol '{symbol}' (lang={lang}) from {url}"
        )

        async with AsyncDataFetcher(config=self.config) as fetcher:
            # Get optimized headers for SET API with symbol-specific referer
            # This is critical for bypassing Incapsula bot detection
            referer = f"https://www.set.or.th/en/market/product/stock/quote/{symbol}/overview"
            headers = AsyncDataFetcher.get_set_api_headers(referer=referer)

            # Fetch raw response - SessionManager handles cookies automatically
            response = await fetcher.fetch(url, headers=headers)

            # Check for errors
            if response.status_code != 200:
                error_msg = (
                    f"Failed to fetch board of directors for {symbol}: "
                    f"HTTP {response.status_code}"
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

            # Validate that data is a list
            if not isinstance(data, list):
                error_msg = (
                    f"Expected list response but got {type(data).__name__}: "
                    f"{str(data)[:200]}"
                )
                logger.error(error_msg)
                raise Exception(error_msg)

            # Parse and validate response using Pydantic
            directors = [Director(**director_data) for director_data in data]

            logger.info(
                f"Successfully fetched {len(directors)} board members for {symbol}"
            )

            return directors

    async def fetch_board_of_directors_raw(
        self, symbol: str, lang: str = "en"
    ) -> list[dict[str, Any]]:
        """
        Fetch board of directors as raw list of dictionaries without Pydantic validation.

        Useful for debugging or when you need the raw API response.

        Args:
            symbol: Stock symbol (e.g., "CPALL", "PTT", "mint")
            lang: Language for response ('en' or 'th', default: 'en')

        Returns:
            Raw list of dictionaries from API

        Raises:
            ValueError: If symbol is empty or language is invalid
            Exception: If request fails

        Example:
            >>> service = BoardOfDirectorService()
            >>> raw_data = await service.fetch_board_of_directors_raw("MINT")
            >>> print(f"Found {len(raw_data)} directors")
            >>> print(raw_data[0].keys())
        """
        # Normalize and validate inputs
        symbol = normalize_symbol(symbol)
        lang = normalize_language(lang)

        if not symbol:
            error_msg = "Stock symbol cannot be empty"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Build URL with symbol and language parameters
        endpoint = SET_BOARD_OF_DIRECTOR_ENDPOINT.format(symbol=symbol)
        url = f"{self.base_url}{endpoint}?lang={lang}"

        logger.info(
            f"Fetching raw board of directors for '{symbol}' (lang={lang}) from {url}"
        )

        async with AsyncDataFetcher(config=self.config) as fetcher:
            # Get optimized headers for SET API with symbol-specific referer
            referer = f"https://www.set.or.th/en/market/product/stock/quote/{symbol}/overview"
            headers = AsyncDataFetcher.get_set_api_headers(referer=referer)

            # Fetch raw response - SessionManager handles cookies automatically
            response = await fetcher.fetch(url, headers=headers)

            # Check for errors
            if response.status_code != 200:
                error_msg = (
                    f"Failed to fetch board of directors for {symbol}: "
                    f"HTTP {response.status_code}"
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

            # Validate that data is a list
            if not isinstance(data, list):
                error_msg = (
                    f"Expected list response but got {type(data).__name__}: "
                    f"{str(data)[:200]}"
                )
                logger.error(error_msg)
                raise Exception(error_msg)

            logger.debug(f"Raw response: {len(data)} directors")
            return data


# Convenience function for quick access
async def get_board_of_directors(
    symbol: str,
    lang: str = "en",
    config: FetcherConfig | None = None,
) -> list[Director]:
    """
    Convenience function to fetch board of directors.

    Args:
        symbol: Stock symbol (e.g., "CPALL", "PTT", "mint")
        lang: Language for response ('en' or 'th', default: 'en')
        config: Optional fetcher configuration

    Returns:
        List of Director objects with name and positions

    Example:
        >>> from settfex.services.set.stock import get_board_of_directors
        >>> # Uses SessionManager for automatic cookie handling
        >>> directors = await get_board_of_directors("MINT")
        >>> for director in directors[:5]:
        ...     print(f"{director.name}: {', '.join(director.positions)}")
    """
    service = BoardOfDirectorService(config=config)
    return await service.fetch_board_of_directors(symbol=symbol, lang=lang)
