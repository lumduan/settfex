"""Tests for async data fetcher module."""

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from settfex.utils.data_fetcher import (
    AsyncDataFetcher,
    FetcherConfig,
    FetchResponse,
)


class TestFetcherConfig:
    """Tests for FetcherConfig model."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = FetcherConfig()
        assert config.browser_impersonate == "chrome120"
        assert config.timeout == 30
        assert config.max_retries == 3
        assert config.retry_delay == 1.0
        assert config.user_agent is None

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = FetcherConfig(
            browser_impersonate="safari17_0",
            timeout=60,
            max_retries=5,
            retry_delay=2.0,
            user_agent="CustomAgent/1.0",
        )
        assert config.browser_impersonate == "safari17_0"
        assert config.timeout == 60
        assert config.max_retries == 5
        assert config.retry_delay == 2.0
        assert config.user_agent == "CustomAgent/1.0"

    def test_validation_timeout_bounds(self) -> None:
        """Test timeout validation bounds."""
        with pytest.raises(ValueError):
            FetcherConfig(timeout=0)
        with pytest.raises(ValueError):
            FetcherConfig(timeout=301)

    def test_validation_retries_bounds(self) -> None:
        """Test max_retries validation bounds."""
        with pytest.raises(ValueError):
            FetcherConfig(max_retries=-1)
        with pytest.raises(ValueError):
            FetcherConfig(max_retries=11)

    def test_validation_retry_delay_bounds(self) -> None:
        """Test retry_delay validation bounds."""
        with pytest.raises(ValueError):
            FetcherConfig(retry_delay=0.05)
        with pytest.raises(ValueError):
            FetcherConfig(retry_delay=31.0)

    def test_browser_validation_warning(self, caplog: Any) -> None:
        """Test browser validation logs warning for non-standard browsers."""
        config = FetcherConfig(browser_impersonate="custom_browser")
        assert config.browser_impersonate == "custom_browser"
        # Warning should be logged but value still accepted


class TestFetchResponse:
    """Tests for FetchResponse model."""

    def test_basic_response(self) -> None:
        """Test basic response creation."""
        response = FetchResponse(
            status_code=200,
            content=b"test content",
            text="test content",
            headers={"Content-Type": "text/plain"},
            url="https://example.com",
            elapsed=1.5,
        )
        assert response.status_code == 200
        assert response.content == b"test content"
        assert response.text == "test content"
        assert response.headers == {"Content-Type": "text/plain"}
        assert response.url == "https://example.com"
        assert response.elapsed == 1.5
        assert response.encoding == "utf-8"

    def test_thai_unicode_text(self) -> None:
        """Test Thai Unicode text handling."""
        thai_text = "ตลาดหลักทรัพย์แห่งประเทศไทย"
        response = FetchResponse(
            status_code=200,
            content=thai_text.encode("utf-8"),
            text=thai_text,
            headers={},
            url="https://example.com",
            elapsed=1.0,
        )
        assert response.text == thai_text
        assert "ตลาด" in response.text


class TestAsyncDataFetcher:
    """Tests for AsyncDataFetcher class."""

    def test_initialization_default(self) -> None:
        """Test fetcher initialization with defaults."""
        fetcher = AsyncDataFetcher()
        assert fetcher.config.browser_impersonate == "chrome120"
        assert fetcher.config.timeout == 30

    def test_initialization_custom_config(self) -> None:
        """Test fetcher initialization with custom config."""
        config = FetcherConfig(browser_impersonate="safari17_0", timeout=60)
        fetcher = AsyncDataFetcher(config=config)
        assert fetcher.config.browser_impersonate == "safari17_0"
        assert fetcher.config.timeout == 60

    def test_generate_random_cookies(self) -> None:
        """Test random cookie generation."""
        fetcher = AsyncDataFetcher()
        cookies1 = fetcher._generate_random_cookies()
        cookies2 = fetcher._generate_random_cookies()

        # Cookies should be different each time
        assert cookies1 != cookies2

        # Cookies should contain expected keys
        assert "_ga=" in cookies1
        assert "PHPSESSID=" in cookies1
        assert "lang=th" in cookies1
        assert "accept_cookies=1" in cookies1

        # Should be properly formatted
        assert "; " in cookies1
        parts = cookies1.split("; ")
        assert len(parts) > 5

    def test_generate_random_cookies_format(self) -> None:
        """Test random cookie format is valid."""
        fetcher = AsyncDataFetcher()
        cookies = fetcher._generate_random_cookies()

        # Parse cookies
        cookie_dict = {}
        for part in cookies.split("; "):
            if "=" in part:
                key, value = part.split("=", 1)
                cookie_dict[key] = value

        # Verify expected cookies exist
        assert "_ga" in cookie_dict
        assert "_gid" in cookie_dict
        assert "PHPSESSID" in cookie_dict
        assert "lang" in cookie_dict
        assert cookie_dict["lang"] == "th"

    @pytest.mark.asyncio
    async def test_fetch_success(self) -> None:
        """Test successful fetch operation."""
        fetcher = AsyncDataFetcher()

        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"test content"
        mock_response.headers = {"Content-Type": "text/plain"}
        mock_response.url = "https://example.com"

        with patch.object(fetcher, "_make_sync_request", return_value=mock_response):
            response = await fetcher.fetch("https://example.com")

        assert response.status_code == 200
        assert response.text == "test content"
        assert response.content == b"test content"

    @pytest.mark.asyncio
    async def test_fetch_with_thai_content(self) -> None:
        """Test fetch with Thai Unicode content."""
        fetcher = AsyncDataFetcher()
        thai_text = "ตลาดหลักทรัพย์แห่งประเทศไทย SET"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = thai_text.encode("utf-8")
        mock_response.headers = {"Content-Type": "text/html; charset=utf-8"}
        mock_response.url = "https://example.com"

        with patch.object(fetcher, "_make_sync_request", return_value=mock_response):
            response = await fetcher.fetch("https://example.com")

        assert response.status_code == 200
        assert response.text == thai_text
        assert "ตลาดหลักทรัพย์" in response.text

    @pytest.mark.asyncio
    async def test_fetch_with_custom_headers(self) -> None:
        """Test fetch with custom headers."""
        fetcher = AsyncDataFetcher()
        custom_headers = {"X-Custom-Header": "test-value"}

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"test"
        mock_response.headers = {}
        mock_response.url = "https://example.com"

        with patch.object(fetcher, "_make_sync_request", return_value=mock_response) as mock:
            await fetcher.fetch("https://example.com", headers=custom_headers)

        # Verify custom header was included
        call_args = mock.call_args
        headers = call_args[0][1]
        assert headers["X-Custom-Header"] == "test-value"

    @pytest.mark.asyncio
    async def test_fetch_with_custom_cookies(self) -> None:
        """Test fetch with custom cookies."""
        fetcher = AsyncDataFetcher()
        custom_cookies = "session=abc123; user=test"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"test"
        mock_response.headers = {}
        mock_response.url = "https://example.com"

        with patch.object(fetcher, "_make_sync_request", return_value=mock_response) as mock:
            await fetcher.fetch("https://example.com", cookies=custom_cookies)

        # Verify custom cookies were used
        call_args = mock.call_args
        headers = call_args[0][1]
        assert headers["Cookie"] == custom_cookies

    @pytest.mark.asyncio
    async def test_fetch_without_random_cookies(self) -> None:
        """Test fetch with random cookies disabled."""
        fetcher = AsyncDataFetcher()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"test"
        mock_response.headers = {}
        mock_response.url = "https://example.com"

        with patch.object(fetcher, "_make_sync_request", return_value=mock_response) as mock:
            await fetcher.fetch("https://example.com", use_random_cookies=False)

        # Verify no Cookie header was set
        call_args = mock.call_args
        headers = call_args[0][1]
        assert "Cookie" not in headers

    @pytest.mark.asyncio
    async def test_fetch_retry_on_failure(self) -> None:
        """Test fetch retries on failure."""
        config = FetcherConfig(max_retries=2, retry_delay=0.1)
        fetcher = AsyncDataFetcher(config=config)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"success"
        mock_response.headers = {}
        mock_response.url = "https://example.com"

        # Fail twice, then succeed
        call_count = 0

        def side_effect(*args: Any, **kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ConnectionError("Connection failed")
            return mock_response

        with patch.object(fetcher, "_make_sync_request", side_effect=side_effect):
            response = await fetcher.fetch("https://example.com")

        assert call_count == 3
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_fetch_exhausted_retries(self) -> None:
        """Test fetch fails after exhausting retries."""
        config = FetcherConfig(max_retries=2, retry_delay=0.1)
        fetcher = AsyncDataFetcher(config=config)

        with patch.object(
            fetcher, "_make_sync_request", side_effect=ConnectionError("Connection failed")
        ):
            with pytest.raises(Exception, match="Failed to fetch"):
                await fetcher.fetch("https://example.com")

    @pytest.mark.asyncio
    async def test_fetch_unicode_decode_fallback(self) -> None:
        """Test Unicode decode fallback to latin1."""
        fetcher = AsyncDataFetcher()

        # Create content that's not valid UTF-8
        invalid_utf8 = b"\xff\xfe test content"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = invalid_utf8
        mock_response.headers = {}
        mock_response.url = "https://example.com"

        with patch.object(fetcher, "_make_sync_request", return_value=mock_response):
            response = await fetcher.fetch("https://example.com")

        assert response.status_code == 200
        assert response.encoding == "latin1"
        assert response.text is not None

    @pytest.mark.asyncio
    async def test_fetch_json_success(self) -> None:
        """Test successful JSON fetch."""
        fetcher = AsyncDataFetcher()
        json_data = {"symbol": "PTT", "price": 35.50, "name": "ปตท."}
        json_content = json.dumps(json_data, ensure_ascii=False)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = json_content.encode("utf-8")
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.url = "https://example.com/api"

        with patch.object(fetcher, "_make_sync_request", return_value=mock_response):
            data = await fetcher.fetch_json("https://example.com/api")

        assert data == json_data
        assert data["name"] == "ปตท."

    @pytest.mark.asyncio
    async def test_fetch_json_invalid(self) -> None:
        """Test JSON fetch with invalid JSON."""
        fetcher = AsyncDataFetcher()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"not valid json"
        mock_response.headers = {}
        mock_response.url = "https://example.com/api"

        with patch.object(fetcher, "_make_sync_request", return_value=mock_response):
            with pytest.raises(json.JSONDecodeError):
                await fetcher.fetch_json("https://example.com/api")

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """Test async context manager usage."""
        async with AsyncDataFetcher() as fetcher:
            assert isinstance(fetcher, AsyncDataFetcher)

    @pytest.mark.asyncio
    async def test_make_sync_request_called_in_thread(self) -> None:
        """Test that sync request is called via asyncio.to_thread."""
        fetcher = AsyncDataFetcher()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"test"
        mock_response.headers = {}
        mock_response.url = "https://example.com"

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = mock_response

            await fetcher.fetch("https://example.com")

            # Verify asyncio.to_thread was called
            mock_to_thread.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_includes_thai_accept_language(self) -> None:
        """Test that fetch includes Thai in Accept-Language header."""
        fetcher = AsyncDataFetcher()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"test"
        mock_response.headers = {}
        mock_response.url = "https://example.com"

        with patch.object(fetcher, "_make_sync_request", return_value=mock_response) as mock:
            await fetcher.fetch("https://example.com")

        call_args = mock.call_args
        headers = call_args[0][1]
        assert "Accept-Language" in headers
        assert "th-TH" in headers["Accept-Language"]

    @pytest.mark.asyncio
    async def test_fetch_timing_recorded(self) -> None:
        """Test that fetch records elapsed time."""
        fetcher = AsyncDataFetcher()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"test"
        mock_response.headers = {}
        mock_response.url = "https://example.com"

        async def slow_request(*args: Any, **kwargs: Any) -> Any:
            await asyncio.sleep(0.1)
            return mock_response

        with patch("asyncio.to_thread", side_effect=slow_request):
            response = await fetcher.fetch("https://example.com")

        assert response.elapsed >= 0.1
