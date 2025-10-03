"""Tests for SET corporate action service."""

import json
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from settfex.services.set.stock.corporate_action import (
    CorporateAction,
    CorporateActionService,
    get_corporate_actions,
)
from settfex.utils.data_fetcher import FetchResponse, FetcherConfig


# Sample test data based on actual API response
MOCK_CORPORATE_ACTION_DATA = [
    {
        "symbol": "AOT",
        "name": "",
        "caType": "XD",
        "type": "XD",
        "bookCloseDate": None,
        "recordDate": "2024-12-06T00:00:00+07:00",
        "remark": None,
        "paymentDate": "2025-02-06T00:00:00+07:00",
        "beginOperation": "2023-10-01T00:00:00+07:00",
        "endOperation": "2024-09-30T00:00:00+07:00",
        "sourceOfDividend": "Net Profit",
        "dividend": 0.79,
        "currency": "Baht",
        "ratio": None,
        "dividendType": "Cash Dividend",
        "approximatePaymentDate": None,
        "tentativeDividendFlag": None,
        "tentativeDividend": None,
        "dividendPayment": "0.79",
        "xdate": "2024-12-04T00:00:00+07:00",
        "xSession": "",
    },
    {
        "symbol": "AOT",
        "name": "",
        "caType": "XM",
        "type": "XM",
        "bookCloseDate": None,
        "recordDate": "2024-12-06T00:00:00+07:00",
        "remark": "",
        "meetingDate": "2025-01-24T14:00:00+07:00",
        "agenda": "Cash dividend payment,Changing The director(s)",
        "venue": "Broadcasting via electronic means from the Auditorium",
        "meetingType": "AGM",
        "inquiryDate": None,
        "xdate": "2024-12-04T00:00:00+07:00",
        "xSession": "",
    },
]


@pytest.fixture
def mock_fetcher():
    """Create a mock AsyncDataFetcher."""
    with patch("settfex.services.set.stock.corporate_action.AsyncDataFetcher") as mock:
        # Create async context manager mock
        fetcher_instance = AsyncMock()
        mock.return_value.__aenter__.return_value = fetcher_instance
        mock.return_value.__aexit__.return_value = None

        # Mock the get_set_api_headers static method
        mock.get_set_api_headers = Mock(return_value={"Accept": "application/json"})

        yield fetcher_instance


@pytest.mark.asyncio
class TestCorporateActionService:
    """Tests for CorporateActionService class."""

    async def test_init_default_config(self):
        """Test service initialization with default config."""
        service = CorporateActionService()
        assert service.config is not None
        assert service.base_url == "https://www.set.or.th"

    async def test_init_custom_config(self):
        """Test service initialization with custom config."""
        config = FetcherConfig(timeout=60, max_retries=5)
        service = CorporateActionService(config=config)
        assert service.config.timeout == 60
        assert service.config.max_retries == 5

    async def test_fetch_corporate_actions_success(self, mock_fetcher):
        """Test successful fetch of corporate actions."""
        # Mock the fetch response
        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps(MOCK_CORPORATE_ACTION_DATA).encode("utf-8"),
            text=json.dumps(MOCK_CORPORATE_ACTION_DATA),
            headers={},
            url="https://www.set.or.th/api/set/stock/AOT/corporate-action?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = CorporateActionService()
        result = await service.fetch_corporate_actions("AOT", lang="en")

        # Verify result
        assert isinstance(result, list)
        assert len(result) == 2

        # Check first action (XD)
        xd_action = result[0]
        assert isinstance(xd_action, CorporateAction)
        assert xd_action.symbol == "AOT"
        assert xd_action.ca_type == "XD"
        assert xd_action.dividend == 0.79
        assert xd_action.currency == "Baht"
        assert xd_action.source_of_dividend == "Net Profit"

        # Check second action (XM)
        xm_action = result[1]
        assert xm_action.ca_type == "XM"
        assert xm_action.meeting_type == "AGM"
        assert "Cash dividend payment" in xm_action.agenda

    async def test_fetch_corporate_actions_symbol_normalization(self, mock_fetcher):
        """Test symbol normalization (lowercase to uppercase)."""
        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps(MOCK_CORPORATE_ACTION_DATA).encode("utf-8"),
            text=json.dumps(MOCK_CORPORATE_ACTION_DATA),
            headers={},
            url="https://www.set.or.th/api/set/stock/AOT/corporate-action?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = CorporateActionService()
        result = await service.fetch_corporate_actions("aot", lang="en")

        assert len(result) == 2
        assert result[0].symbol == "AOT"

    async def test_fetch_corporate_actions_language_normalization(self, mock_fetcher):
        """Test language normalization."""
        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps(MOCK_CORPORATE_ACTION_DATA).encode("utf-8"),
            text=json.dumps(MOCK_CORPORATE_ACTION_DATA),
            headers={},
            url="https://www.set.or.th/api/set/stock/AOT/corporate-action?lang=th",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = CorporateActionService()

        # Test various language inputs
        for lang_input in ["th", "TH", "thai", "THAI"]:
            result = await service.fetch_corporate_actions("AOT", lang=lang_input)
            assert len(result) == 2

    async def test_fetch_corporate_actions_empty_symbol(self):
        """Test fetch with empty symbol raises ValueError."""
        service = CorporateActionService()

        with pytest.raises(ValueError, match="Stock symbol cannot be empty"):
            await service.fetch_corporate_actions("", lang="en")

    async def test_fetch_corporate_actions_invalid_language(self):
        """Test fetch with invalid language raises ValueError."""
        service = CorporateActionService()

        with pytest.raises(ValueError, match="Invalid language"):
            await service.fetch_corporate_actions("AOT", lang="invalid")

    async def test_fetch_corporate_actions_http_error(self, mock_fetcher):
        """Test handling of HTTP error response."""
        mock_response = FetchResponse(
            status_code=404,
            content=b"Not Found",
            text="Not Found",
            headers={},
            url="https://www.set.or.th/api/set/stock/INVALID/corporate-action?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = CorporateActionService()

        with pytest.raises(Exception, match="Failed to fetch corporate actions"):
            await service.fetch_corporate_actions("INVALID", lang="en")

    async def test_fetch_corporate_actions_json_decode_error(self, mock_fetcher):
        """Test handling of invalid JSON response."""
        mock_response = FetchResponse(
            status_code=200,
            content=b"Invalid JSON",
            text="Invalid JSON",
            headers={},
            url="https://www.set.or.th/api/set/stock/AOT/corporate-action?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = CorporateActionService()

        with pytest.raises(json.JSONDecodeError):
            await service.fetch_corporate_actions("AOT", lang="en")

    async def test_fetch_corporate_actions_non_list_response(self, mock_fetcher):
        """Test handling of non-list JSON response."""
        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps({"error": "Invalid format"}).encode("utf-8"),
            text=json.dumps({"error": "Invalid format"}),
            headers={},
            url="https://www.set.or.th/api/set/stock/AOT/corporate-action?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = CorporateActionService()

        with pytest.raises(ValueError, match="Expected list response"):
            await service.fetch_corporate_actions("AOT", lang="en")

    async def test_fetch_corporate_actions_empty_list(self, mock_fetcher):
        """Test handling of empty corporate action list."""
        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps([]).encode("utf-8"),
            text=json.dumps([]),
            headers={},
            url="https://www.set.or.th/api/set/stock/XYZ/corporate-action?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = CorporateActionService()
        result = await service.fetch_corporate_actions("XYZ", lang="en")

        assert isinstance(result, list)
        assert len(result) == 0

    async def test_fetch_corporate_actions_raw_success(self, mock_fetcher):
        """Test successful fetch of raw corporate actions."""
        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps(MOCK_CORPORATE_ACTION_DATA).encode("utf-8"),
            text=json.dumps(MOCK_CORPORATE_ACTION_DATA),
            headers={},
            url="https://www.set.or.th/api/set/stock/AOT/corporate-action?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = CorporateActionService()
        result = await service.fetch_corporate_actions_raw("AOT", lang="en")

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["symbol"] == "AOT"
        assert result[0]["caType"] == "XD"


@pytest.mark.asyncio
class TestCorporateActionModel:
    """Tests for CorporateAction Pydantic model."""

    def test_create_dividend_action(self):
        """Test creating a dividend corporate action model."""
        action_data = MOCK_CORPORATE_ACTION_DATA[0]
        action = CorporateAction(**action_data)

        assert action.symbol == "AOT"
        assert action.ca_type == "XD"
        assert action.dividend == 0.79
        assert action.currency == "Baht"
        assert action.source_of_dividend == "Net Profit"
        assert isinstance(action.x_date, datetime)
        assert isinstance(action.record_date, datetime)

    def test_create_meeting_action(self):
        """Test creating a meeting corporate action model."""
        action_data = MOCK_CORPORATE_ACTION_DATA[1]
        action = CorporateAction(**action_data)

        assert action.symbol == "AOT"
        assert action.ca_type == "XM"
        assert action.meeting_type == "AGM"
        assert "Cash dividend payment" in action.agenda
        assert isinstance(action.meeting_date, datetime)

    def test_model_alias_support(self):
        """Test that model supports both field names and aliases."""
        # Test with alias (camelCase)
        action1 = CorporateAction(
            symbol="TEST",
            name="Test Company",
            caType="XD",
            type="XD",
            recordDate="2024-12-01T00:00:00+07:00",
            xdate="2024-11-29T00:00:00+07:00",
            xSession="",
        )
        assert action1.ca_type == "XD"
        assert action1.record_date is not None

        # Test with field name (snake_case)
        action2 = CorporateAction(
            symbol="TEST",
            name="Test Company",
            ca_type="XD",
            type="XD",
            record_date="2024-12-01T00:00:00+07:00",
            x_date="2024-11-29T00:00:00+07:00",
            x_session="",
        )
        assert action2.ca_type == "XD"
        assert action2.record_date is not None

    def test_model_optional_fields(self):
        """Test that optional fields can be None."""
        action = CorporateAction(
            symbol="TEST",
            name="",
            caType="XD",
            type="XD",
            recordDate="2024-12-01T00:00:00+07:00",
            xdate="2024-11-29T00:00:00+07:00",
            xSession="",
            # All other fields are optional
        )
        assert action.symbol == "TEST"
        assert action.dividend is None
        assert action.meeting_date is None


@pytest.mark.asyncio
class TestConvenienceFunction:
    """Tests for get_corporate_actions convenience function."""

    async def test_get_corporate_actions_success(self, mock_fetcher):
        """Test convenience function with successful fetch."""
        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps(MOCK_CORPORATE_ACTION_DATA).encode("utf-8"),
            text=json.dumps(MOCK_CORPORATE_ACTION_DATA),
            headers={},
            url="https://www.set.or.th/api/set/stock/AOT/corporate-action?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        result = await get_corporate_actions("AOT", lang="en")

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(action, CorporateAction) for action in result)

    async def test_get_corporate_actions_custom_config(self, mock_fetcher):
        """Test convenience function with custom config."""
        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps(MOCK_CORPORATE_ACTION_DATA).encode("utf-8"),
            text=json.dumps(MOCK_CORPORATE_ACTION_DATA),
            headers={},
            url="https://www.set.or.th/api/set/stock/AOT/corporate-action?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        config = FetcherConfig(timeout=60, max_retries=5)
        result = await get_corporate_actions("AOT", lang="en", config=config)

        assert len(result) == 2


@pytest.mark.asyncio
class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    async def test_whitespace_in_symbol(self, mock_fetcher):
        """Test handling of whitespace in symbol."""
        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps(MOCK_CORPORATE_ACTION_DATA).encode("utf-8"),
            text=json.dumps(MOCK_CORPORATE_ACTION_DATA),
            headers={},
            url="https://www.set.or.th/api/set/stock/AOT/corporate-action?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = CorporateActionService()
        result = await service.fetch_corporate_actions("  AOT  ", lang="en")

        assert len(result) == 2
        assert result[0].symbol == "AOT"

    async def test_mixed_case_symbol(self, mock_fetcher):
        """Test handling of mixed case symbol."""
        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps(MOCK_CORPORATE_ACTION_DATA).encode("utf-8"),
            text=json.dumps(MOCK_CORPORATE_ACTION_DATA),
            headers={},
            url="https://www.set.or.th/api/set/stock/AOT/corporate-action?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = CorporateActionService()
        result = await service.fetch_corporate_actions("AoT", lang="en")

        assert len(result) == 2

    async def test_multiple_action_types(self, mock_fetcher):
        """Test handling of multiple corporate action types."""
        # Create data with various action types
        multi_type_data = [
            {**MOCK_CORPORATE_ACTION_DATA[0], "caType": "XD"},
            {**MOCK_CORPORATE_ACTION_DATA[1], "caType": "XM"},
            {**MOCK_CORPORATE_ACTION_DATA[0], "caType": "XR", "symbol": "AOT"},
        ]

        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps(multi_type_data).encode("utf-8"),
            text=json.dumps(multi_type_data),
            headers={},
            url="https://www.set.or.th/api/set/stock/AOT/corporate-action?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = CorporateActionService()
        result = await service.fetch_corporate_actions("AOT", lang="en")

        assert len(result) == 3
        action_types = {action.ca_type for action in result}
        assert "XD" in action_types
        assert "XM" in action_types
        assert "XR" in action_types
