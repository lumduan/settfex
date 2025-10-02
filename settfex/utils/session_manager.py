"""
Session manager for persistent curl_cffi sessions with automatic cookie handling.

This module provides a singleton session that mimics real browser behavior by:
1. Storing cookies automatically across requests
2. Making initial "warm-up" requests to get Incapsula cookies
3. Reusing the same session for all API calls
"""

import asyncio
import time
from typing import ClassVar

from curl_cffi import requests
from loguru import logger


class SessionManager:
    """
    Singleton session manager for curl_cffi with automatic cookie persistence.

    This class maintains a single curl_cffi session that automatically stores
    and reuses cookies, just like a real browser. This eliminates the need to
    manually capture Chrome cookies.

    Key features:
    - Automatic cookie storage and reuse
    - Session warm-up (visits SET homepage to get Incapsula cookies)
    - Thread-safe singleton pattern
    - Configurable browser impersonation

    Example:
        >>> manager = SessionManager.get_instance()
        >>> await manager.ensure_initialized()
        >>> response = await manager.get("https://www.set.or.th/api/set/stock/PTT/highlight-data")
    """

    _instance: ClassVar["SessionManager | None"] = None
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    def __init__(self, browser: str = "chrome120") -> None:
        """
        Initialize session manager.

        Args:
            browser: Browser to impersonate (default: chrome120)
        """
        self.browser = browser
        self._session: requests.Session | None = None
        self._initialized = False
        self._last_warmup_time = 0.0
        self._warmup_interval = 3600.0  # Re-warm every hour
        logger.info(f"SessionManager created with browser={browser}")

    @classmethod
    async def get_instance(cls, browser: str = "chrome120") -> "SessionManager":
        """
        Get singleton instance of SessionManager.

        Args:
            browser: Browser to impersonate (default: chrome120)

        Returns:
            SessionManager instance
        """
        async with cls._lock:
            if cls._instance is None:
                cls._instance = cls(browser=browser)
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (useful for testing)."""
        if cls._instance and cls._instance._session:
            cls._instance._session.close()
        cls._instance = None
        logger.debug("SessionManager instance reset")

    async def ensure_initialized(self, force_warmup: bool = False) -> None:
        """
        Ensure session is initialized and warmed up.

        This performs a "warm-up" request to SET's homepage to get Incapsula
        cookies, just like a real browser visiting the site.

        Args:
            force_warmup: Force a new warm-up even if recently done
        """
        # Check if warmup needed
        now = time.time()
        needs_warmup = (
            force_warmup
            or not self._initialized
            or (now - self._last_warmup_time) > self._warmup_interval
        )

        if not needs_warmup:
            return

        logger.info("Warming up session with SET homepage visit...")

        try:
            # Create session if needed
            if self._session is None:
                self._session = requests.Session()
                logger.debug("Created new curl_cffi Session")

            # Warm-up: Visit SET homepage to get Incapsula cookies
            warmup_url = "https://www.set.or.th/en/home"
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/140.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Cache-Control": "max-age=0",
            }

            # Run in thread since curl_cffi Session is sync
            def do_warmup():
                response = self._session.get(
                    warmup_url,
                    headers=headers,
                    impersonate=self.browser,  # type: ignore
                    timeout=30,
                )
                return response

            response = await asyncio.to_thread(do_warmup)

            if response.status_code == 200:
                # Check if we got cookies
                cookie_count = len(response.cookies)
                logger.success(
                    f"✓ Session warmed up successfully (got {cookie_count} cookies)"
                )
                self._initialized = True
                self._last_warmup_time = now
            else:
                logger.warning(
                    f"Warmup request returned {response.status_code}, continuing anyway"
                )
                self._initialized = True
                self._last_warmup_time = now

        except Exception as e:
            logger.error(f"Failed to warm up session: {e}")
            # Don't fail - continue with unwarmed session
            self._initialized = True

    async def get(
        self, url: str, headers: dict[str, str] | None = None, timeout: int = 30
    ) -> requests.Response:
        """
        Make GET request using persistent session.

        Args:
            url: URL to fetch
            headers: Optional headers to include
            timeout: Request timeout in seconds

        Returns:
            Response object from curl_cffi

        Raises:
            Exception: If session not initialized or request fails
        """
        await self.ensure_initialized()

        if self._session is None:
            raise RuntimeError("Session not initialized")

        logger.debug(f"GET {url} (using persistent session with cookies)")

        def do_request():
            return self._session.get(
                url,
                headers=headers or {},
                impersonate=self.browser,  # type: ignore
                timeout=timeout,
            )

        response = await asyncio.to_thread(do_request)
        logger.debug(
            f"Response: {response.status_code}, cookies in session: {len(self._session.cookies)}"
        )

        return response

    def close(self) -> None:
        """Close the session."""
        if self._session:
            self._session.close()
            self._session = None
            self._initialized = False
            logger.debug("Session closed")


# Convenience function for quick access
async def get_shared_session(browser: str = "chrome120") -> SessionManager:
    """
    Get the shared SessionManager instance.

    This is the recommended way to get a session with automatic cookie handling.

    Args:
        browser: Browser to impersonate (default: chrome120)

    Returns:
        Initialized SessionManager instance

    Example:
        >>> session = await get_shared_session()
        >>> response = await session.get("https://www.set.or.th/api/...")
    """
    manager = await SessionManager.get_instance(browser=browser)
    await manager.ensure_initialized()
    return manager
