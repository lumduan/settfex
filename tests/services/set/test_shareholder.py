"""Tests for SET shareholder service."""

import json
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from settfex.services.set.stock.shareholder import (
    FreeFloat,
    MajorShareholder,
    ShareholderData,
    ShareholderService,
    get_shareholder_data,
)
from settfex.utils.data_fetcher import FetcherConfig, FetchResponse

# Sample test data based on actual API response
MOCK_SHAREHOLDER_DATA = {
    "symbol": "MINT",
    "bookCloseDate": "2025-09-02T00:00:00+07:00",
    "caType": "XD",
    "totalShareholder": 48794,
    "percentScriptless": 81.27,
    "majorShareholders": [
        {
            "sequence": 1,
            "name": "บริษัท  ไมเนอร์ โฮลดิ้ง (ไทย) จำกัด",
            "nationality": None,
            "numberOfShare": 916556730,
            "percentOfShare": 16.17,
            "isThaiNVDR": False,
        },
        {
            "sequence": 2,
            "name": "นาย นิติ โอสถานุเคราะห์",
            "nationality": None,
            "numberOfShare": 558134428,
            "percentOfShare": 9.84,
            "isThaiNVDR": False,
        },
        {
            "sequence": 3,
            "name": "UBS AG SINGAPORE BRANCH",
            "nationality": None,
            "numberOfShare": 475893748,
            "percentOfShare": 8.39,
            "isThaiNVDR": False,
        },
        {
            "sequence": 4,
            "name": "Thai NVDR Company Limited",
            "nationality": None,
            "numberOfShare": 465082581,
            "percentOfShare": 8.2,
            "isThaiNVDR": True,
        },
    ],
    "freeFloat": {
        "bookCloseDate": "2025-03-05T00:00:00+07:00",
        "caType": "XM",
        "percentFreeFloat": 59.5099983215332,
        "numberOfHolder": 41108,
    },
}


@pytest.fixture
def mock_fetcher():
    """Create a mock AsyncDataFetcher."""
    with patch("settfex.services.set.stock.shareholder.AsyncDataFetcher") as mock:
        # Create async context manager mock
        fetcher_instance = AsyncMock()
        mock.return_value.__aenter__.return_value = fetcher_instance
        mock.return_value.__aexit__.return_value = None

        # Mock the get_set_api_headers static method
        mock.get_set_api_headers = Mock(return_value={"Accept": "application/json"})

        yield fetcher_instance


@pytest.mark.asyncio
class TestShareholderService:
    """Tests for ShareholderService class."""

    async def test_init_default_config(self):
        """Test service initialization with default config."""
        service = ShareholderService()
        assert service.config is not None
        assert service.base_url == "https://www.set.or.th"

    async def test_init_custom_config(self):
        """Test service initialization with custom config."""
        config = FetcherConfig(timeout=60, max_retries=5)
        service = ShareholderService(config=config)
        assert service.config.timeout == 60
        assert service.config.max_retries == 5

    async def test_fetch_shareholder_data_success(self, mock_fetcher):
        """Test successful fetch of shareholder data."""
        # Mock the fetch response
        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps(MOCK_SHAREHOLDER_DATA).encode("utf-8"),
            text=json.dumps(MOCK_SHAREHOLDER_DATA),
            headers={},
            url="https://www.set.or.th/api/set/stock/MINT/shareholder?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = ShareholderService()
        result = await service.fetch_shareholder_data("MINT", lang="en")

        # Verify result
        assert isinstance(result, ShareholderData)
        assert result.symbol == "MINT"
        assert result.total_shareholder == 48794
        assert result.percent_scriptless == 81.27
        assert len(result.major_shareholders) == 4

        # Check first major shareholder
        first_sh = result.major_shareholders[0]
        assert isinstance(first_sh, MajorShareholder)
        assert first_sh.sequence == 1
        assert first_sh.number_of_share == 916556730
        assert first_sh.percent_of_share == 16.17
        assert first_sh.is_thai_nvdr is False

        # Check free float
        assert isinstance(result.free_float, FreeFloat)
        assert result.free_float.percent_free_float == 59.5099983215332
        assert result.free_float.number_of_holder == 41108

    async def test_fetch_shareholder_data_symbol_normalization(self, mock_fetcher):
        """Test symbol normalization (lowercase to uppercase)."""
        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps(MOCK_SHAREHOLDER_DATA).encode("utf-8"),
            text=json.dumps(MOCK_SHAREHOLDER_DATA),
            headers={},
            url="https://www.set.or.th/api/set/stock/MINT/shareholder?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = ShareholderService()
        result = await service.fetch_shareholder_data("mint", lang="en")

        assert result.symbol == "MINT"
        assert len(result.major_shareholders) == 4

    async def test_fetch_shareholder_data_language_normalization(self, mock_fetcher):
        """Test language normalization."""
        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps(MOCK_SHAREHOLDER_DATA).encode("utf-8"),
            text=json.dumps(MOCK_SHAREHOLDER_DATA),
            headers={},
            url="https://www.set.or.th/api/set/stock/MINT/shareholder?lang=th",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = ShareholderService()

        # Test various language inputs
        for lang_input in ["th", "TH", "thai", "THAI"]:
            result = await service.fetch_shareholder_data("MINT", lang=lang_input)
            assert result.symbol == "MINT"

    async def test_fetch_shareholder_data_empty_symbol(self):
        """Test fetch with empty symbol raises ValueError."""
        service = ShareholderService()

        with pytest.raises(ValueError, match="Stock symbol cannot be empty"):
            await service.fetch_shareholder_data("", lang="en")

    async def test_fetch_shareholder_data_invalid_language(self):
        """Test fetch with invalid language raises ValueError."""
        service = ShareholderService()

        with pytest.raises(ValueError, match="Invalid language"):
            await service.fetch_shareholder_data("MINT", lang="invalid")

    async def test_fetch_shareholder_data_http_error(self, mock_fetcher):
        """Test handling of HTTP error response."""
        mock_response = FetchResponse(
            status_code=404,
            content=b"Not Found",
            text="Not Found",
            headers={},
            url="https://www.set.or.th/api/set/stock/INVALID/shareholder?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = ShareholderService()

        with pytest.raises(Exception, match="Failed to fetch shareholder data"):
            await service.fetch_shareholder_data("INVALID", lang="en")

    async def test_fetch_shareholder_data_json_decode_error(self, mock_fetcher):
        """Test handling of invalid JSON response."""
        mock_response = FetchResponse(
            status_code=200,
            content=b"Invalid JSON",
            text="Invalid JSON",
            headers={},
            url="https://www.set.or.th/api/set/stock/MINT/shareholder?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = ShareholderService()

        with pytest.raises(json.JSONDecodeError):
            await service.fetch_shareholder_data("MINT", lang="en")

    async def test_fetch_shareholder_data_raw_success(self, mock_fetcher):
        """Test successful fetch of raw shareholder data."""
        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps(MOCK_SHAREHOLDER_DATA).encode("utf-8"),
            text=json.dumps(MOCK_SHAREHOLDER_DATA),
            headers={},
            url="https://www.set.or.th/api/set/stock/MINT/shareholder?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = ShareholderService()
        result = await service.fetch_shareholder_data_raw("MINT", lang="en")

        assert isinstance(result, dict)
        assert result["symbol"] == "MINT"
        assert result["totalShareholder"] == 48794
        assert len(result["majorShareholders"]) == 4


@pytest.mark.asyncio
class TestShareholderModels:
    """Tests for Shareholder Pydantic models."""

    def test_create_major_shareholder(self):
        """Test creating a MajorShareholder model."""
        sh_data = MOCK_SHAREHOLDER_DATA["majorShareholders"][0]
        shareholder = MajorShareholder(**sh_data)

        assert shareholder.sequence == 1
        assert shareholder.name == "บริษัท  ไมเนอร์ โฮลดิ้ง (ไทย) จำกัด"
        assert shareholder.number_of_share == 916556730
        assert shareholder.percent_of_share == 16.17
        assert shareholder.is_thai_nvdr is False
        assert shareholder.nationality is None

    def test_create_free_float(self):
        """Test creating a FreeFloat model."""
        ff_data = MOCK_SHAREHOLDER_DATA["freeFloat"]
        free_float = FreeFloat(**ff_data)

        assert isinstance(free_float.book_close_date, datetime)
        assert free_float.ca_type == "XM"
        assert free_float.percent_free_float == 59.5099983215332
        assert free_float.number_of_holder == 41108

    def test_create_shareholder_data(self):
        """Test creating a ShareholderData model."""
        data = ShareholderData(**MOCK_SHAREHOLDER_DATA)

        assert data.symbol == "MINT"
        assert isinstance(data.book_close_date, datetime)
        assert data.ca_type == "XD"
        assert data.total_shareholder == 48794
        assert data.percent_scriptless == 81.27
        assert len(data.major_shareholders) == 4
        assert isinstance(data.free_float, FreeFloat)

    def test_model_alias_support(self):
        """Test that models support both field names and aliases."""
        # Test MajorShareholder with alias (camelCase)
        sh1 = MajorShareholder(
            sequence=1,
            name="Test Company",
            nationality=None,
            numberOfShare=1000000,
            percentOfShare=10.5,
            isThaiNVDR=True,
        )
        assert sh1.number_of_share == 1000000
        assert sh1.percent_of_share == 10.5
        assert sh1.is_thai_nvdr is True

        # Test with field name (snake_case)
        sh2 = MajorShareholder(
            sequence=2,
            name="Test Person",
            nationality="TH",
            number_of_share=2000000,
            percent_of_share=20.5,
            is_thai_nvdr=False,
        )
        assert sh2.number_of_share == 2000000
        assert sh2.percent_of_share == 20.5
        assert sh2.is_thai_nvdr is False

    def test_thai_nvdr_identification(self):
        """Test identification of Thai NVDR shareholders."""
        # Thai NVDR Company
        nvdr_sh = MOCK_SHAREHOLDER_DATA["majorShareholders"][3]
        shareholder = MajorShareholder(**nvdr_sh)
        assert shareholder.is_thai_nvdr is True
        assert shareholder.name == "Thai NVDR Company Limited"

        # Non-NVDR
        regular_sh = MOCK_SHAREHOLDER_DATA["majorShareholders"][0]
        shareholder2 = MajorShareholder(**regular_sh)
        assert shareholder2.is_thai_nvdr is False


@pytest.mark.asyncio
class TestConvenienceFunction:
    """Tests for get_shareholder_data convenience function."""

    async def test_get_shareholder_data_success(self, mock_fetcher):
        """Test convenience function with successful fetch."""
        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps(MOCK_SHAREHOLDER_DATA).encode("utf-8"),
            text=json.dumps(MOCK_SHAREHOLDER_DATA),
            headers={},
            url="https://www.set.or.th/api/set/stock/MINT/shareholder?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        result = await get_shareholder_data("MINT", lang="en")

        assert isinstance(result, ShareholderData)
        assert result.symbol == "MINT"
        assert len(result.major_shareholders) == 4

    async def test_get_shareholder_data_custom_config(self, mock_fetcher):
        """Test convenience function with custom config."""
        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps(MOCK_SHAREHOLDER_DATA).encode("utf-8"),
            text=json.dumps(MOCK_SHAREHOLDER_DATA),
            headers={},
            url="https://www.set.or.th/api/set/stock/MINT/shareholder?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        config = FetcherConfig(timeout=60, max_retries=5)
        result = await get_shareholder_data("MINT", lang="en", config=config)

        assert result.symbol == "MINT"


@pytest.mark.asyncio
class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    async def test_whitespace_in_symbol(self, mock_fetcher):
        """Test handling of whitespace in symbol."""
        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps(MOCK_SHAREHOLDER_DATA).encode("utf-8"),
            text=json.dumps(MOCK_SHAREHOLDER_DATA),
            headers={},
            url="https://www.set.or.th/api/set/stock/MINT/shareholder?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = ShareholderService()
        result = await service.fetch_shareholder_data("  MINT  ", lang="en")

        assert result.symbol == "MINT"

    async def test_mixed_case_symbol(self, mock_fetcher):
        """Test handling of mixed case symbol."""
        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps(MOCK_SHAREHOLDER_DATA).encode("utf-8"),
            text=json.dumps(MOCK_SHAREHOLDER_DATA),
            headers={},
            url="https://www.set.or.th/api/set/stock/MINT/shareholder?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = ShareholderService()
        result = await service.fetch_shareholder_data("MiNt", lang="en")

        assert result.symbol == "MINT"

    async def test_empty_major_shareholders(self, mock_fetcher):
        """Test handling of stock with no major shareholders."""
        data_no_major = {
            **MOCK_SHAREHOLDER_DATA,
            "majorShareholders": [],
        }

        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps(data_no_major).encode("utf-8"),
            text=json.dumps(data_no_major),
            headers={},
            url="https://www.set.or.th/api/set/stock/XYZ/shareholder?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = ShareholderService()
        result = await service.fetch_shareholder_data("XYZ", lang="en")

        assert isinstance(result.major_shareholders, list)
        assert len(result.major_shareholders) == 0

    async def test_multiple_nvdr_shareholders(self, mock_fetcher):
        """Test handling of multiple NVDR shareholders."""
        data_multi_nvdr = {
            **MOCK_SHAREHOLDER_DATA,
            "majorShareholders": [
                {
                    "sequence": 1,
                    "name": "Thai NVDR Company Limited",
                    "nationality": None,
                    "numberOfShare": 1000000,
                    "percentOfShare": 10.0,
                    "isThaiNVDR": True,
                },
                {
                    "sequence": 2,
                    "name": "Another NVDR",
                    "nationality": None,
                    "numberOfShare": 500000,
                    "percentOfShare": 5.0,
                    "isThaiNVDR": True,
                },
            ],
        }

        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps(data_multi_nvdr).encode("utf-8"),
            text=json.dumps(data_multi_nvdr),
            headers={},
            url="https://www.set.or.th/api/set/stock/TEST/shareholder?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = ShareholderService()
        result = await service.fetch_shareholder_data("TEST", lang="en")

        nvdr_count = sum(1 for sh in result.major_shareholders if sh.is_thai_nvdr)
        assert nvdr_count == 2

    async def test_high_ownership_percentage(self, mock_fetcher):
        """Test handling of shareholder with high ownership percentage."""
        data_high_ownership = {
            **MOCK_SHAREHOLDER_DATA,
            "majorShareholders": [
                {
                    "sequence": 1,
                    "name": "Majority Owner",
                    "nationality": "TH",
                    "numberOfShare": 9000000000,
                    "percentOfShare": 75.5,
                    "isThaiNVDR": False,
                }
            ],
        }

        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps(data_high_ownership).encode("utf-8"),
            text=json.dumps(data_high_ownership),
            headers={},
            url="https://www.set.or.th/api/set/stock/TEST/shareholder?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = ShareholderService()
        result = await service.fetch_shareholder_data("TEST", lang="en")

        assert result.major_shareholders[0].percent_of_share == 75.5
