"""Async data fetcher with Unicode/Thai language support for SET and TFEX APIs."""

import asyncio
import base64
import random
import secrets
import time
import uuid
from typing import Any

from curl_cffi import requests
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, field_validator


class FetcherConfig(BaseModel):
    """Configuration for the data fetcher."""

    browser_impersonate: str = Field(
        default="chrome120",
        description="Browser version to impersonate (e.g., 'chrome120', 'safari17')",
    )
    timeout: int = Field(default=30, ge=1, le=300, description="Request timeout in seconds")
    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum retry attempts")
    retry_delay: float = Field(
        default=1.0, ge=0.1, le=30.0, description="Base delay between retries in seconds"
    )
    rate_limit_delay: float = Field(
        default=0.0,
        ge=0.0,
        le=10.0,
        description="Delay between consecutive requests in seconds (0 = no rate limiting)",
    )
    use_session: bool = Field(
        default=True,
        description=(
            "Use persistent session with automatic cookie handling "
            "(recommended for ~100% success)"
        ),
    )
    user_agent: str | None = Field(
        default=None, description="Custom User-Agent header (auto-generated if None)"
    )

    @field_validator("browser_impersonate")
    @classmethod
    def validate_browser(cls, v: str) -> str:
        """Validate browser impersonation value."""
        valid_browsers = [
            "chrome99",
            "chrome100",
            "chrome101",
            "chrome104",
            "chrome107",
            "chrome110",
            "chrome116",
            "chrome119",
            "chrome120",
            "safari15_3",
            "safari15_5",
            "safari17_0",
            "safari17_2_1",
            "edge99",
            "edge101",
        ]
        if v not in valid_browsers:
            logger.warning(
                f"Browser '{v}' not in validated list, using anyway. "
                f"Valid options: {', '.join(valid_browsers)}"
            )
        return v


class FetchResponse(BaseModel):
    """Response from a fetch operation."""

    status_code: int = Field(description="HTTP status code")
    content: bytes = Field(description="Raw response content")
    text: str = Field(description="Response text decoded as UTF-8")
    headers: dict[str, str] = Field(default_factory=dict, description="Response headers")
    url: str = Field(description="Final URL after redirects")
    elapsed: float = Field(description="Request duration in seconds")
    encoding: str = Field(default="utf-8", description="Response encoding")

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator("text")
    @classmethod
    def ensure_unicode(cls, v: str) -> str:
        """Ensure text is properly decoded Unicode."""
        # This validator ensures the text field is always valid Unicode
        # If there are encoding issues, they should be caught during initialization
        return v


class AsyncDataFetcher:
    """
    Async data fetcher with Unicode/Thai language support.

    This fetcher is specifically designed for SET and TFEX APIs, providing:
    - Browser impersonation to bypass bot detection
    - Proper Unicode/Thai character handling
    - Randomized cookies for session management
    - Async-first design with sync fallback
    - Automatic retries with exponential backoff
    """

    def __init__(self, config: FetcherConfig | None = None) -> None:
        """
        Initialize the async data fetcher.

        Args:
            config: Configuration for the fetcher (uses defaults if None)
        """
        self.config = config or FetcherConfig()
        self._last_request_time: float = 0.0  # Track last request time for rate limiting
        logger.info(
            f"AsyncDataFetcher initialized with browser={self.config.browser_impersonate}, "
            f"timeout={self.config.timeout}s, rate_limit={self.config.rate_limit_delay}s"
        )

    @staticmethod
    def get_set_api_headers(referer: str = "https://www.set.or.th/en/home") -> dict[str, str]:
        """
        Get optimized headers for SET (Stock Exchange of Thailand) API requests.

        These headers are based on successful browser requests and include all
        necessary Incapsula/Imperva bot detection bypass headers.

        Args:
            referer: Referer URL (default: SET home page)

        Returns:
            Dictionary of HTTP headers optimized for SET API

        Example:
            >>> fetcher = AsyncDataFetcher()
            >>> headers = fetcher.get_set_api_headers()
            >>> response = await fetcher.fetch(url, headers=headers)
        """
        return {
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-US,en;q=0.9,th-TH;q=0.8,th;q=0.7",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Priority": "u=1, i",
            "Referer": referer,
            "Sec-Ch-Ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
            ),
        }

    @staticmethod
    def generate_incapsula_cookies(landing_url: str | None = None) -> str:
        """
        Generate Incapsula-aware randomized cookies for SET API requests.

        This method creates cookies that mimic legitimate browser sessions
        with Incapsula bot protection, including visitor IDs, session tokens,
        load balancer identifiers, and analytics tracking cookies.

        Enhanced to include Google Analytics, Facebook Pixel, and other
        tracking cookies that indicate a legitimate browser session.

        Useful for all SET services that need to bypass Incapsula protection.
        For production use, real authenticated browser session cookies are
        recommended over generated cookies.

        Args:
            landing_url: Optional landing URL to include in cookies (e.g., the referer page).
                        This is critical for some symbols that check the landing_url cookie.

        Returns:
            Cookie string with Incapsula-compatible randomized values

        Example:
            >>> cookies = AsyncDataFetcher.generate_incapsula_cookies()
            >>> response = await fetcher.fetch(url, cookies=cookies)
            >>>
            >>> # With landing URL for better bot detection bypass
            >>> landing = "https://www.set.or.th/en/market/product/stock/quote/CPN/price"
            >>> cookies = AsyncDataFetcher.generate_incapsula_cookies(landing_url=landing)

        Note:
            Generated cookies may be blocked by Incapsula. For best results,
            use real browser session cookies from an authenticated session.
        """
        import time

        # Current timestamp for realistic session cookies
        now = int(time.time() * 1000)  # Milliseconds
        now_seconds = int(time.time())

        # Random charlot session token (UUID format)
        charlot: str = str(uuid.uuid4())

        # Random LiveChat customer ID (UUID format)
        lt_cid: str = str(uuid.uuid4())

        # Random Incapsula load balancer ID (base64-like format)
        nlbi_id: str = base64.b64encode(secrets.token_bytes(32)).decode("utf-8")[:40]

        # Random visitor IDs (Incapsula format - base64-like)
        visid_1: str = base64.b64encode(secrets.token_bytes(48)).decode("utf-8")[:64]
        visid_2: str = base64.b64encode(secrets.token_bytes(48)).decode("utf-8")[:64]

        # Random session IDs (Incapsula format - base64-like)
        session_1: str = base64.b64encode(secrets.token_bytes(32)).decode("utf-8")[:48]
        session_2: str = base64.b64encode(secrets.token_bytes(32)).decode("utf-8")[:48]

        # Random site IDs (7-8 digit numbers matching real SET site IDs)
        site_id_1: int = 2046605  # Real SET Incapsula site ID
        site_id_2: int = 2771851  # Real SET alternate site ID

        # Random visit time and API counter
        visit_time: int = random.randint(10, 300)  # 10 seconds to 5 minutes
        api_counter: int = random.randint(1, 10)  # 1-10 API calls

        # Google Analytics client ID (GA1.1.{random}.{timestamp})
        ga_client_id: int = random.randint(1000000000, 9999999999)
        ga_timestamp: int = now_seconds - random.randint(3600, 86400)  # 1-24 hours ago
        ga_cookie: str = f"GA1.1.{ga_client_id}.{ga_timestamp}"

        # Facebook Pixel (fb.{version}.{timestamp}.{random})
        fbp_random: str = str(random.randint(100000000000000000, 999999999999999999))
        fbp_cookie: str = f"fb.2.{now - random.randint(3600000, 86400000)}.{fbp_random}"

        # Google Ads conversion tracking (version.subversion.{random}.{timestamp})
        gcl_random: int = random.randint(1000000000, 9999999999)
        gcl_timestamp: int = now_seconds - random.randint(3600, 86400)
        gcl_cookie: str = f"1.1.{gcl_random}.{gcl_timestamp}"

        # GA4 session cookies
        # Format: GS{version}.{version}.s{timestamp}$o{seq}$g{engaged}$t{timestamp}$j{seq}$l0$h0
        # $g1$ = user engaged (clicked/scrolled), $g0$ = not engaged
        # AOT requires $g1$ to prove active interaction!
        ga4_session_time: int = now_seconds - random.randint(60, 3600)
        ga4_seq: int = random.randint(60, 99)
        ga4_cookie_1: str = (
            f"GS2.1.s{ga4_session_time}$o{ga4_seq}$g1$t{ga4_session_time}"
            f"$j{ga4_seq}$l0$h0"
        )
        ga4_cookie_2: str = (
            f"GS2.1.s{ga4_session_time}$o{ga4_seq}$g1$t{ga4_session_time}"
            f"$j{ga4_seq}$l0$h0"
        )

        # SET Cookie Policy (date format: YYYYMMDDHHMMSS)
        policy_date: str = "20231111093657"

        # UID tracking cookie (8 hex chars . 2 hex digits)
        uid_hex: str = secrets.token_hex(4).upper()
        uid_suffix: str = secrets.token_hex(1).upper()[:2]
        uid_cookie: str = f"{uid_hex}.{uid_suffix}"

        # LiveChat Session ID (__lt__sid) - Critical for AOT and other Tier 4 symbols
        # Format: {uuid}-{short_hash}
        lt_sid: str = f"{str(uuid.uuid4())[:23]}-{secrets.token_hex(4)}"

        # Hotjar Active Session (_hjSession_3931504) - Critical for AOT
        # Base64 encoded JSON with active session data
        import json
        hj_session_data = {
            "id": str(uuid.uuid4()),
            "c": now,  # created timestamp (ms)
            "s": 0,    # session count
            "r": 0,    # recording
            "sb": 0,   # session buffer
            "sr": 0,   # session recording
            "se": 0,   # session events
            "fs": 0,   # first session
            "sp": 0    # session ping
        }
        hj_session_json = json.dumps(hj_session_data, separators=(',', ':'))
        hj_session_cookie = base64.b64encode(hj_session_json.encode()).decode()

        # Build comprehensive cookie string
        # Order matters - start with analytics/tracking for legitimacy
        cookie_string: str = (
            # Analytics & Tracking (signals legitimate browser)
            f"__lt__cid={lt_cid}; "
            f"_fbp={fbp_cookie}; "
            f"_ga={ga_cookie}; "
            f"_tt_enable_cookie=1; "
            f"_gcl_au={gcl_cookie}; "
            f"SET_COOKIE_POLICY={policy_date}; "
            f"_cbclose=1; "
            f"_cbclose23453=1; "
            f"_uid23453={uid_cookie}; "
            f"_ctout23453=1; "
            # Active Session Cookies (Critical for AOT/Tier 4)
            f"__lt__sid={lt_sid}; "
            f"_hjSession_3931504={hj_session_cookie}; "
            # Incapsula Core (required for bot detection bypass)
            f"charlot={charlot}; "
            f"nlbi_{site_id_1}={nlbi_id}; "
            f"visid_incap_{site_id_1}={visid_1}; "
            f"incap_ses_357_{site_id_1}={session_1}; "
            f"visid_incap_{site_id_2}={visid_2}; "
            f"incap_ses_357_{site_id_2}={session_2}; "
            # Session Management
            f"visit_time={visit_time}; "
            f"_ga_6WS2P0P25V={ga4_cookie_1}; "
            f"_ga_ET2H60H2CB={ga4_cookie_2}; "
            f"api_call_counter={api_counter}"
        )

        # Add landing_url if provided (critical for some symbols like CPN, 2S)
        if landing_url:
            cookie_string += f"; landing_url={landing_url}"
            logger.debug(f"Added landing_url to cookies: {landing_url}")

        logger.debug(f"Generated enhanced Incapsula cookies: {len(cookie_string)} chars")
        return cookie_string

    def _generate_random_cookies(self) -> str:
        """
        Generate randomized cookies for session management.

        This method creates realistic-looking cookies to simulate browser behavior
        and avoid detection as a bot. Cookies include session identifiers and
        tracking parameters commonly used by Thai financial websites.

        Returns:
            Cookie string in the format "key1=value1; key2=value2; ..."
        """
        # Generate session ID (32 hex chars)
        session_id = "".join(random.choices("0123456789abcdef", k=32))

        # Generate tracking ID (mix of timestamp and random)
        timestamp = int(time.time() * 1000)
        tracking_id = f"{timestamp}_{random.randint(1000000, 9999999)}"

        # Generate user preference ID
        user_pref = "".join(random.choices("0123456789ABCDEF", k=16))

        # Common cookie names used by Thai financial sites
        cookies = {
            "_ga": f"GA1.2.{random.randint(100000000, 999999999)}.{int(time.time())}",
            "_gid": f"GA1.2.{random.randint(100000000, 999999999)}.{int(time.time())}",
            "_gat": "1",
            "PHPSESSID": session_id,
            "_fbp": f"fb.1.{timestamp}.{random.randint(1000000000, 9999999999)}",
            "tracking_id": tracking_id,
            "user_pref": user_pref,
            "lang": "th",  # Thai language preference
            "accept_cookies": "1",
        }

        cookie_string = "; ".join([f"{key}={value}" for key, value in cookies.items()])
        logger.debug(f"Generated cookies: {len(cookie_string)} chars")
        return cookie_string

    async def _make_request(self, url: str, headers: dict[str, str]) -> Any:
        """
        Make HTTP GET request using either persistent session or standalone request.

        Uses SessionManager for automatic cookie handling if use_session=True,
        otherwise makes standalone request.

        Args:
            url: URL to fetch
            headers: HTTP headers to include

        Returns:
            Response object from curl_cffi

        Raises:
            Exception: If request fails
        """
        if self.config.use_session:
            # Use persistent session with automatic cookie handling
            from settfex.utils.session_manager import get_shared_session

            session = await get_shared_session(browser=self.config.browser_impersonate)
            response = await session.get(url, headers=headers, timeout=self.config.timeout)
            logger.debug(
                f"Request via session: status={response.status_code}, url={url}"
            )
            return response
        else:
            # Make standalone request (no cookie persistence)
            logger.debug(f"Making standalone request to {url}")

            def do_request():
                return requests.get(
                    url,
                    headers=headers,
                    timeout=self.config.timeout,
                    impersonate=self.config.browser_impersonate,  # type: ignore
                )

            try:
                response = await asyncio.to_thread(do_request)
                logger.debug(f"Request completed: status={response.status_code}, url={url}")
                return response
            except Exception as e:
                logger.error(f"Request failed: {e}", exc_info=True)
                raise

    async def fetch(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        cookies: str | None = None,
        use_random_cookies: bool = True,
    ) -> FetchResponse:
        """
        Fetch data from a URL asynchronously with proper Unicode handling.

        This is the main entry point for fetching data. It automatically:
        - Generates randomized cookies (unless disabled)
        - Handles Unicode/Thai characters correctly
        - Retries on failure with exponential backoff
        - Logs all operations for debugging

        Args:
            url: URL to fetch
            headers: Optional custom headers (merged with defaults)
            cookies: Optional custom cookies (overrides random cookies if provided)
            use_random_cookies: Whether to generate random cookies (default: True)

        Returns:
            FetchResponse with status, content, and metadata

        Raises:
            Exception: If request fails after all retries

        Example:
            >>> async with AsyncDataFetcher() as fetcher:
            ...     response = await fetcher.fetch("https://api.set.or.th/data")
            ...     print(response.text)  # Properly decoded Thai text
        """
        # Prepare headers
        default_headers = {
            "Accept": "text/html,application/json,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",  # noqa: E501
            "Accept-Language": "th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7",
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

        # Add custom user agent if provided
        if self.config.user_agent:
            default_headers["User-Agent"] = self.config.user_agent

        # Merge custom headers
        if headers:
            default_headers.update(headers)

        # Handle cookies
        if cookies:
            default_headers["Cookie"] = cookies
        elif use_random_cookies:
            default_headers["Cookie"] = self._generate_random_cookies()

        # Rate limiting: Wait if needed to respect rate_limit_delay
        if self.config.rate_limit_delay > 0:
            elapsed_since_last = time.time() - self._last_request_time
            if elapsed_since_last < self.config.rate_limit_delay:
                delay = self.config.rate_limit_delay - elapsed_since_last
                logger.debug(f"Rate limiting: sleeping {delay:.3f}s")
                await asyncio.sleep(delay)

        # Retry loop with exponential backoff
        last_exception: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                start_time = time.time()

                # Update last request time for rate limiting
                self._last_request_time = start_time

                # Make request (either via persistent session or standalone)
                response = await self._make_request(url, default_headers)

                elapsed = time.time() - start_time

                # Decode content with UTF-8 for Thai/Unicode support
                try:
                    text = response.content.decode("utf-8")
                except UnicodeDecodeError:
                    # Fallback to latin1 if UTF-8 fails
                    logger.warning(f"UTF-8 decode failed for {url}, trying latin1")
                    text = response.content.decode("latin1")
                    encoding = "latin1"
                else:
                    encoding = "utf-8"

                # Create response object
                fetch_response = FetchResponse(
                    status_code=response.status_code,
                    content=response.content,
                    text=text,
                    headers=dict(response.headers),
                    url=str(response.url),
                    elapsed=elapsed,
                    encoding=encoding,
                )

                logger.info(
                    f"Fetch successful: url={url}, status={response.status_code}, "
                    f"elapsed={elapsed:.2f}s, size={len(response.content)} bytes"
                )

                return fetch_response

            except Exception as e:
                last_exception = e
                logger.warning(
                    f"Fetch attempt {attempt + 1}/{self.config.max_retries + 1} failed: {e}"
                )

                # Don't sleep after the last attempt
                if attempt < self.config.max_retries:
                    # Exponential backoff
                    delay = self.config.retry_delay * (2**attempt)
                    logger.debug(f"Retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)

        # All retries exhausted
        logger.error(f"All fetch attempts failed for {url}")
        raise Exception(
            f"Failed to fetch {url} after {self.config.max_retries + 1} attempts"
        ) from last_exception  # noqa: E501

    async def fetch_json(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        cookies: str | None = None,
        use_random_cookies: bool = True,
    ) -> Any:
        """
        Fetch JSON data from a URL.

        Convenience method that fetches data and parses it as JSON.
        Handles Thai/Unicode characters in JSON responses.

        Args:
            url: URL to fetch
            headers: Optional custom headers
            cookies: Optional custom cookies
            use_random_cookies: Whether to generate random cookies

        Returns:
            Parsed JSON data (dict, list, or primitive)

        Raises:
            Exception: If request fails or response is not valid JSON
        """
        # Add JSON accept header
        json_headers = {"Accept": "application/json"}
        if headers:
            json_headers.update(headers)

        response = await self.fetch(
            url, headers=json_headers, cookies=cookies, use_random_cookies=use_random_cookies
        )

        try:
            # Use standard json parsing which handles Unicode correctly
            import json

            data = json.loads(response.text)
            logger.debug(f"Parsed JSON response from {url}")
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from {url}: {e}")
            logger.debug(f"Response text: {response.text[:500]}")
            raise

    async def __aenter__(self) -> "AsyncDataFetcher":
        """Enter async context manager."""
        logger.debug("AsyncDataFetcher context entered")
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Exit async context manager."""
        logger.debug("AsyncDataFetcher context exited")
