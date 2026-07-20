"""Tests for async data fetcher module."""

import asyncio
import json
from typing import Any
from unittest.mock import Mock, patch

import pytest

from settfex.utils.data_fetcher import (
    AsyncDataFetcher,
    FetcherConfig,
    FetchResponse,
)
from settfex.utils.parsing import ResponseParseError


class TestFetcherConfig:
    """Tests for FetcherConfig model."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = FetcherConfig()
        assert config.browser_impersonate == "chrome120"
        assert config.timeout == 30
        assert config.max_retries == 3
        assert config.retry_delay == 1.0
        assert config.rate_limit_delay == 0.0
        assert config.use_session is True
        assert config.user_agent is None

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = FetcherConfig(
            browser_impersonate="safari17_0",
            timeout=60,
            max_retries=5,
            retry_delay=2.0,
            rate_limit_delay=0.5,
            use_session=False,
            user_agent="CustomAgent/1.0",
        )
        assert config.browser_impersonate == "safari17_0"
        assert config.timeout == 60
        assert config.max_retries == 5
        assert config.retry_delay == 2.0
        assert config.rate_limit_delay == 0.5
        assert config.use_session is False
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

    def test_validation_rate_limit_delay_bounds(self) -> None:
        """Test rate_limit_delay validation bounds."""
        with pytest.raises(ValueError):
            FetcherConfig(rate_limit_delay=-0.1)
        with pytest.raises(ValueError):
            FetcherConfig(rate_limit_delay=11.0)

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
        assert fetcher.config.use_session is True
        assert fetcher.config.rate_limit_delay == 0.0

    def test_initialization_custom_config(self) -> None:
        """Test fetcher initialization with custom config."""
        config = FetcherConfig(
            browser_impersonate="safari17_0",
            timeout=60,
            use_session=False,
            rate_limit_delay=0.5,
        )
        fetcher = AsyncDataFetcher(config=config)
        assert fetcher.config.browser_impersonate == "safari17_0"
        assert fetcher.config.timeout == 60
        assert fetcher.config.use_session is False
        assert fetcher.config.rate_limit_delay == 0.5

    def test_get_set_api_headers(self) -> None:
        """Test SET API headers generation."""
        headers = AsyncDataFetcher.get_set_api_headers()

        # Verify essential headers are present
        assert "Accept" in headers
        assert "application/json" in headers["Accept"]
        assert "Accept-Language" in headers
        assert "th-TH" in headers["Accept-Language"]
        assert "User-Agent" in headers
        assert "Chrome" in headers["User-Agent"]
        assert "Referer" in headers
        assert "set.or.th" in headers["Referer"]

        # Verify bot detection headers
        assert "Sec-Ch-Ua" in headers
        assert "Sec-Fetch-Dest" in headers
        assert "Sec-Fetch-Mode" in headers

    def test_get_set_api_headers_custom_referer(self) -> None:
        """Test SET API headers with custom referer."""
        custom_referer = "https://example.com"
        headers = AsyncDataFetcher.get_set_api_headers(referer=custom_referer)
        assert headers["Referer"] == custom_referer

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

        with patch.object(fetcher, "_make_request", return_value=mock_response):
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

        with patch.object(fetcher, "_make_request", return_value=mock_response):
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

        with patch.object(fetcher, "_make_request", return_value=mock_response) as mock:
            await fetcher.fetch("https://example.com", headers=custom_headers)

        # Verify custom header was included
        call_args = mock.call_args
        headers = call_args[0][1]
        assert headers["X-Custom-Header"] == "test-value"

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

        with patch.object(fetcher, "_make_request", side_effect=side_effect):
            response = await fetcher.fetch("https://example.com")

        assert call_count == 3
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_fetch_exhausted_retries(self) -> None:
        """Test fetch fails after exhausting retries."""
        config = FetcherConfig(max_retries=2, retry_delay=0.1)
        fetcher = AsyncDataFetcher(config=config)

        with (
            patch.object(
                fetcher, "_make_request", side_effect=ConnectionError("Connection failed")
            ),
            pytest.raises(Exception, match="Failed to fetch"),
        ):
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

        with patch.object(fetcher, "_make_request", return_value=mock_response):
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

        with patch.object(fetcher, "_make_request", return_value=mock_response):
            data = await fetcher.fetch_json("https://example.com/api")

        assert data == json_data
        assert data["name"] == "ปตท."

    @pytest.mark.asyncio
    async def test_fetch_json_invalid(self) -> None:
        """Test JSON fetch with invalid JSON raises a context-rich error."""
        fetcher = AsyncDataFetcher()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"not valid json"
        mock_response.headers = {}
        mock_response.url = "https://example.com/api"

        with (
            patch.object(fetcher, "_make_request", return_value=mock_response),
            pytest.raises(ResponseParseError, match="example.com"),
        ):
            await fetcher.fetch_json("https://example.com/api")

    @pytest.mark.asyncio
    async def test_fetch_json_rejects_nonfinite(self) -> None:
        """NaN/Infinity in a numeric response must be rejected, not silently accepted."""
        fetcher = AsyncDataFetcher()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"pe": NaN}'
        mock_response.headers = {}
        mock_response.url = "https://example.com/api"

        with (
            patch.object(fetcher, "_make_request", return_value=mock_response),
            pytest.raises(ResponseParseError),
        ):
            await fetcher.fetch_json("https://example.com/api")

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """Test async context manager usage."""
        async with AsyncDataFetcher() as fetcher:
            assert isinstance(fetcher, AsyncDataFetcher)

    @pytest.mark.asyncio
    async def test_rate_limiting_delay(self) -> None:
        """Test rate limiting behavior."""
        config = FetcherConfig(rate_limit_delay=0.1)
        fetcher = AsyncDataFetcher(config=config)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"test"
        mock_response.headers = {}
        mock_response.url = "https://example.com"

        with patch.object(fetcher, "_make_request", return_value=mock_response):
            # First request
            start_time = asyncio.get_event_loop().time()
            await fetcher.fetch("https://example.com")

            # Second request should be delayed
            await fetcher.fetch("https://example.com")
            elapsed = asyncio.get_event_loop().time() - start_time

            # Should take at least the rate limit delay
            assert elapsed >= 0.1

    @pytest.mark.asyncio
    async def test_session_vs_standalone_mode(self) -> None:
        """Test difference between session and standalone mode."""
        # Test with session disabled
        config = FetcherConfig(use_session=False)
        fetcher = AsyncDataFetcher(config=config)
        assert fetcher.config.use_session is False

        # Test with session enabled (default)
        fetcher_with_session = AsyncDataFetcher()
        assert fetcher_with_session.config.use_session is True

    @pytest.mark.asyncio
    async def test_fetch_includes_thai_accept_language(self) -> None:
        """Test that fetch includes Thai in Accept-Language header."""
        fetcher = AsyncDataFetcher()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"test"
        mock_response.headers = {}
        mock_response.url = "https://example.com"

        with patch.object(fetcher, "_make_request", return_value=mock_response) as mock:
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

        # Mock a slow response
        async def slow_request(*args: Any, **kwargs: Any) -> Any:
            await asyncio.sleep(0.1)
            return mock_response

        with patch.object(fetcher, "_make_request", side_effect=slow_request):
            response = await fetcher.fetch("https://example.com")

        assert response.elapsed >= 0.1


class TestAsyncDataFetcherPost:
    """Tests for the POST support added to AsyncDataFetcher (backward-compatible)."""

    @pytest.mark.asyncio
    async def test_fetch_defaults_to_get(self) -> None:
        """fetch() defaults to GET and forwards method/json_body to _make_request."""
        fetcher = AsyncDataFetcher()
        mock_response = Mock(status_code=200, content=b"ok", headers={}, url="https://example.com")

        with patch.object(fetcher, "_make_request", return_value=mock_response) as mock:
            await fetcher.fetch("https://example.com")

        assert mock.call_args.kwargs["method"] == "GET"
        assert mock.call_args.kwargs["json_body"] is None

    @pytest.mark.asyncio
    async def test_fetch_post_forwards_method_and_body(self) -> None:
        """fetch(method='POST', json_body=...) forwards both onward."""
        fetcher = AsyncDataFetcher()
        body = {"start": 1, "page_size": 12, "type_id": 1}
        mock_response = Mock(status_code=200, content=b"{}", headers={}, url="https://api.x/search")

        with patch.object(fetcher, "_make_request", return_value=mock_response) as mock:
            await fetcher.fetch("https://api.x/search", method="POST", json_body=body)

        assert mock.call_args.kwargs["method"] == "POST"
        assert mock.call_args.kwargs["json_body"] == body

    @pytest.mark.asyncio
    async def test_fetch_json_post_returns_parsed_body(self) -> None:
        """fetch_json supports POST and still routes through the hardened decoder."""
        fetcher = AsyncDataFetcher()
        payload = {"no_records": 2, "items": []}
        mock_response = Mock(
            status_code=200,
            content=json.dumps(payload).encode("utf-8"),
            headers={},
            url="https://api.x/search",
        )

        with patch.object(fetcher, "_make_request", return_value=mock_response) as mock:
            data = await fetcher.fetch_json(
                "https://api.x/search", method="POST", json_body={"start": 1}
            )

        assert data == payload
        assert mock.call_args.kwargs["method"] == "POST"
        assert mock.call_args.kwargs["json_body"] == {"start": 1}

    @pytest.mark.asyncio
    async def test_post_via_session_raises(self) -> None:
        """POST via a persistent session is unsupported and must fail loudly."""
        fetcher = AsyncDataFetcher()  # default use_session=True
        with pytest.raises(NotImplementedError, match="POST"):
            await fetcher._make_request(
                "https://api.x/search", {}, method="POST", json_body={"a": 1}
            )

    @pytest.mark.asyncio
    async def test_standalone_post_calls_requests_post(self) -> None:
        """Standalone POST issues a curl_cffi POST carrying the JSON body."""
        fetcher = AsyncDataFetcher(config=FetcherConfig(use_session=False))
        body = {"start": 1, "type_id": 1}
        mock_resp = Mock(status_code=200)

        with patch("settfex.utils.data_fetcher.requests") as mock_requests:
            mock_requests.post.return_value = mock_resp
            result = await fetcher._make_request(
                "https://api.x/search",
                {"Origin": "https://opportunity-day.setgroup.or.th"},
                method="POST",
                json_body=body,
            )

        assert result is mock_resp
        assert mock_requests.post.called
        assert mock_requests.get.called is False
        kwargs = mock_requests.post.call_args.kwargs
        assert kwargs["json"] == body
        assert kwargs["headers"]["Origin"] == "https://opportunity-day.setgroup.or.th"

    @pytest.mark.asyncio
    async def test_standalone_get_unchanged(self) -> None:
        """Standalone GET still uses requests.get (no regression)."""
        fetcher = AsyncDataFetcher(config=FetcherConfig(use_session=False))
        mock_resp = Mock(status_code=200)

        with patch("settfex.utils.data_fetcher.requests") as mock_requests:
            mock_requests.get.return_value = mock_resp
            result = await fetcher._make_request("https://example.com", {})

        assert result is mock_resp
        assert mock_requests.get.called
        assert mock_requests.post.called is False

    @pytest.mark.asyncio
    async def test_standalone_post_form_data(self) -> None:
        """Standalone POST with data= issues a form-encoded curl_cffi POST (not JSON)."""
        fetcher = AsyncDataFetcher(config=FetcherConfig(use_session=False))
        form = {"__VIEWSTATE": "abc", "ctl00$CPH$btSearch": "Search"}
        mock_resp = Mock(status_code=200)

        with patch("settfex.utils.data_fetcher.requests") as mock_requests:
            mock_requests.post.return_value = mock_resp
            result = await fetcher._make_request(
                "https://market.sec.or.th/x", {"Referer": "https://market.sec.or.th/x"},
                method="POST", data=form,
            )

        assert result is mock_resp
        assert mock_requests.post.called
        kwargs = mock_requests.post.call_args.kwargs
        assert kwargs["data"] == form
        assert "json" not in kwargs  # form path must not send a JSON body

    @pytest.mark.asyncio
    async def test_fetch_forwards_data(self) -> None:
        """fetch(method='POST', data=...) forwards the form body to _make_request."""
        fetcher = AsyncDataFetcher()
        form = {"a": "1"}
        mock_response = Mock(status_code=200, content=b"ok", headers={}, url="https://x/y")

        with patch.object(fetcher, "_make_request", return_value=mock_response) as mock:
            await fetcher.fetch("https://x/y", method="POST", data=form)

        assert mock.call_args.kwargs["data"] == form

    @pytest.mark.asyncio
    async def test_fetch_binary_skips_text_decode(self) -> None:
        """decode_text=False returns raw bytes on .content and leaves .text empty."""
        fetcher = AsyncDataFetcher()
        raw = b"PK\x03\x04\x14\x00\x00\x08"  # zip magic + junk (invalid UTF-8)
        mock_response = Mock(status_code=200, content=raw, headers={}, url="https://x/f.zip")

        with patch.object(fetcher, "_make_request", return_value=mock_response):
            resp = await fetcher.fetch("https://x/f.zip", decode_text=False)

        assert resp.content == raw
        assert resp.text == ""
        assert resp.encoding == "binary"

    @pytest.mark.asyncio
    async def test_fetch_binary_bytes_would_break_text_decode(self) -> None:
        """The same non-UTF-8 bytes with default decode_text still succeed (latin1 fallback)."""
        fetcher = AsyncDataFetcher()
        raw = b"\xff\xfe\x00\x01"  # not valid UTF-8
        mock_response = Mock(status_code=200, content=raw, headers={}, url="https://x/f.bin")

        with patch.object(fetcher, "_make_request", return_value=mock_response):
            resp = await fetcher.fetch("https://x/f.bin")  # decode_text defaults True

        assert resp.content == raw
        assert resp.encoding == "latin1"
