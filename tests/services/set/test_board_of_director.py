"""Tests for SET board of director service."""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from settfex.services.set.stock.board_of_director import (
    BoardOfDirectorService,
    Director,
    get_board_of_directors,
)
from settfex.utils.data_fetcher import FetcherConfig, FetchResponse

# Sample test data based on actual API response
MOCK_BOARD_DATA = [
    {
        "name": "Mr. WILLIAM ELLWOOD HEINECKE",
        "positions": ["CHAIRMAN"],
    },
    {
        "name": "Mr. EMMANUEL JUDE DILLIPRAJ RAJAKARIER",
        "positions": ["GROUP CHIEF EXECUTIVE OFFICER", "DIRECTOR"],
    },
    {
        "name": "Ms. MULLIKA AROONVATANAPORN",
        "positions": ["INDEPENDENT DIRECTOR"],
    },
    {
        "name": "Mr. CHARTSIRI SOPHONPANICH",
        "positions": ["DIRECTOR"],
    },
]

# Sample Thai language data
MOCK_BOARD_DATA_THAI = [
    {
        "name": "นาย วิลเลี่ยม เอลล์วูด ไฮเนเก้",
        "positions": ["ประธานกรรมการ"],
    },
    {
        "name": "นาย เอ็มมานูเอล จูด ดิลลิปราจ ราจากาเรียร์",
        "positions": ["กรรมการผู้จัดการใหญ่กลุ่มบริษัท", "กรรมการ"],
    },
]


@pytest.fixture
def mock_fetcher():
    """Create a mock AsyncDataFetcher."""
    with patch("settfex.services.set.stock.board_of_director.AsyncDataFetcher") as mock:
        # Create async context manager mock
        fetcher_instance = AsyncMock()
        mock.return_value.__aenter__.return_value = fetcher_instance
        mock.return_value.__aexit__.return_value = None

        # Mock the get_set_api_headers static method
        mock.get_set_api_headers = Mock(return_value={"Accept": "application/json"})

        yield fetcher_instance


@pytest.mark.asyncio
class TestBoardOfDirectorService:
    """Tests for BoardOfDirectorService class."""

    async def test_init_default_config(self):
        """Test service initialization with default config."""
        service = BoardOfDirectorService()
        assert service.config is not None
        assert service.base_url == "https://www.set.or.th"

    async def test_init_custom_config(self):
        """Test service initialization with custom config."""
        config = FetcherConfig(timeout=60, max_retries=5)
        service = BoardOfDirectorService(config=config)
        assert service.config.timeout == 60
        assert service.config.max_retries == 5

    async def test_fetch_board_of_directors_success(self, mock_fetcher):
        """Test successful fetch of board of directors."""
        # Mock the fetch response
        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps(MOCK_BOARD_DATA).encode("utf-8"),
            text=json.dumps(MOCK_BOARD_DATA),
            headers={},
            url="https://www.set.or.th/api/set/company/MINT/board-of-director?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = BoardOfDirectorService()
        result = await service.fetch_board_of_directors("MINT", lang="en")

        # Verify result
        assert isinstance(result, list)
        assert len(result) == 4
        assert all(isinstance(d, Director) for d in result)

        # Check first director
        first_director = result[0]
        assert first_director.name == "Mr. WILLIAM ELLWOOD HEINECKE"
        assert first_director.positions == ["CHAIRMAN"]

        # Check second director with multiple positions
        second_director = result[1]
        assert second_director.name == "Mr. EMMANUEL JUDE DILLIPRAJ RAJAKARIER"
        assert len(second_director.positions) == 2
        assert "GROUP CHIEF EXECUTIVE OFFICER" in second_director.positions
        assert "DIRECTOR" in second_director.positions

    async def test_fetch_board_of_directors_symbol_normalization(self, mock_fetcher):
        """Test symbol normalization (lowercase to uppercase)."""
        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps(MOCK_BOARD_DATA).encode("utf-8"),
            text=json.dumps(MOCK_BOARD_DATA),
            headers={},
            url="https://www.set.or.th/api/set/company/MINT/board-of-director?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = BoardOfDirectorService()
        result = await service.fetch_board_of_directors("mint", lang="en")

        assert len(result) == 4
        assert result[0].name == "Mr. WILLIAM ELLWOOD HEINECKE"

    async def test_fetch_board_of_directors_thai_language(self, mock_fetcher):
        """Test fetching board data in Thai language."""
        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps(MOCK_BOARD_DATA_THAI).encode("utf-8"),
            text=json.dumps(MOCK_BOARD_DATA_THAI),
            headers={},
            url="https://www.set.or.th/api/set/company/MINT/board-of-director?lang=th",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = BoardOfDirectorService()
        result = await service.fetch_board_of_directors("MINT", lang="th")

        assert len(result) == 2
        assert result[0].name == "นาย วิลเลี่ยม เอลล์วูด ไฮเนเก้"
        assert result[0].positions == ["ประธานกรรมการ"]

    async def test_fetch_board_of_directors_language_normalization(self, mock_fetcher):
        """Test language normalization."""
        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps(MOCK_BOARD_DATA).encode("utf-8"),
            text=json.dumps(MOCK_BOARD_DATA),
            headers={},
            url="https://www.set.or.th/api/set/company/MINT/board-of-director?lang=th",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = BoardOfDirectorService()

        # Test various language inputs
        for lang_input in ["th", "TH", "thai", "THAI"]:
            result = await service.fetch_board_of_directors("MINT", lang=lang_input)
            assert len(result) == 4

    async def test_fetch_board_of_directors_empty_symbol(self):
        """Test fetch with empty symbol raises ValueError."""
        service = BoardOfDirectorService()

        with pytest.raises(ValueError, match="Stock symbol cannot be empty"):
            await service.fetch_board_of_directors("", lang="en")

    async def test_fetch_board_of_directors_invalid_language(self):
        """Test fetch with invalid language raises ValueError."""
        service = BoardOfDirectorService()

        with pytest.raises(ValueError, match="Invalid language"):
            await service.fetch_board_of_directors("MINT", lang="invalid")

    async def test_fetch_board_of_directors_http_error(self, mock_fetcher):
        """Test handling of HTTP error response."""
        mock_response = FetchResponse(
            status_code=404,
            content=b"Not Found",
            text="Not Found",
            headers={},
            url="https://www.set.or.th/api/set/company/INVALID/board-of-director?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = BoardOfDirectorService()

        with pytest.raises(Exception, match="Failed to fetch board of directors"):
            await service.fetch_board_of_directors("INVALID", lang="en")

    async def test_fetch_board_of_directors_json_decode_error(self, mock_fetcher):
        """Test handling of invalid JSON response."""
        mock_response = FetchResponse(
            status_code=200,
            content=b"Invalid JSON",
            text="Invalid JSON",
            headers={},
            url="https://www.set.or.th/api/set/company/MINT/board-of-director?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = BoardOfDirectorService()

        with pytest.raises(json.JSONDecodeError):
            await service.fetch_board_of_directors("MINT", lang="en")

    async def test_fetch_board_of_directors_non_list_response(self, mock_fetcher):
        """Test handling of non-list response."""
        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps({"error": "Invalid response"}).encode("utf-8"),
            text=json.dumps({"error": "Invalid response"}),
            headers={},
            url="https://www.set.or.th/api/set/company/MINT/board-of-director?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = BoardOfDirectorService()

        with pytest.raises(Exception, match="Expected list response but got dict"):
            await service.fetch_board_of_directors("MINT", lang="en")

    async def test_fetch_board_of_directors_raw_success(self, mock_fetcher):
        """Test successful fetch of raw board data."""
        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps(MOCK_BOARD_DATA).encode("utf-8"),
            text=json.dumps(MOCK_BOARD_DATA),
            headers={},
            url="https://www.set.or.th/api/set/company/MINT/board-of-director?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = BoardOfDirectorService()
        result = await service.fetch_board_of_directors_raw("MINT", lang="en")

        assert isinstance(result, list)
        assert len(result) == 4
        assert result[0]["name"] == "Mr. WILLIAM ELLWOOD HEINECKE"
        assert result[0]["positions"] == ["CHAIRMAN"]


@pytest.mark.asyncio
class TestDirectorModel:
    """Tests for Director Pydantic model."""

    def test_create_director_single_position(self):
        """Test creating a Director model with single position."""
        director_data = MOCK_BOARD_DATA[0]
        director = Director(**director_data)

        assert director.name == "Mr. WILLIAM ELLWOOD HEINECKE"
        assert director.positions == ["CHAIRMAN"]

    def test_create_director_multiple_positions(self):
        """Test creating a Director model with multiple positions."""
        director_data = MOCK_BOARD_DATA[1]
        director = Director(**director_data)

        assert director.name == "Mr. EMMANUEL JUDE DILLIPRAJ RAJAKARIER"
        assert len(director.positions) == 2
        assert "GROUP CHIEF EXECUTIVE OFFICER" in director.positions
        assert "DIRECTOR" in director.positions

    def test_create_director_thai_name(self):
        """Test creating a Director model with Thai name."""
        director_data = MOCK_BOARD_DATA_THAI[0]
        director = Director(**director_data)

        assert director.name == "นาย วิลเลี่ยม เอลล์วูด ไฮเนเก้"
        assert director.positions == ["ประธานกรรมการ"]

    def test_director_whitespace_trimming(self):
        """Test that Director model trims whitespace from strings."""
        director = Director(
            name="  Mr. John Doe  ",
            positions=["  CEO  ", "  DIRECTOR  "],
        )

        assert director.name == "Mr. John Doe"
        # Note: positions list items don't get trimmed automatically, only the name field


@pytest.mark.asyncio
class TestConvenienceFunction:
    """Tests for get_board_of_directors convenience function."""

    async def test_get_board_of_directors_success(self, mock_fetcher):
        """Test convenience function with successful fetch."""
        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps(MOCK_BOARD_DATA).encode("utf-8"),
            text=json.dumps(MOCK_BOARD_DATA),
            headers={},
            url="https://www.set.or.th/api/set/company/MINT/board-of-director?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        result = await get_board_of_directors("MINT", lang="en")

        assert isinstance(result, list)
        assert len(result) == 4
        assert all(isinstance(d, Director) for d in result)

    async def test_get_board_of_directors_custom_config(self, mock_fetcher):
        """Test convenience function with custom config."""
        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps(MOCK_BOARD_DATA).encode("utf-8"),
            text=json.dumps(MOCK_BOARD_DATA),
            headers={},
            url="https://www.set.or.th/api/set/company/MINT/board-of-director?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        config = FetcherConfig(timeout=60, max_retries=5)
        result = await get_board_of_directors("MINT", lang="en", config=config)

        assert len(result) == 4


@pytest.mark.asyncio
class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    async def test_whitespace_in_symbol(self, mock_fetcher):
        """Test handling of whitespace in symbol."""
        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps(MOCK_BOARD_DATA).encode("utf-8"),
            text=json.dumps(MOCK_BOARD_DATA),
            headers={},
            url="https://www.set.or.th/api/set/company/MINT/board-of-director?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = BoardOfDirectorService()
        result = await service.fetch_board_of_directors("  MINT  ", lang="en")

        assert len(result) == 4

    async def test_mixed_case_symbol(self, mock_fetcher):
        """Test handling of mixed case symbol."""
        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps(MOCK_BOARD_DATA).encode("utf-8"),
            text=json.dumps(MOCK_BOARD_DATA),
            headers={},
            url="https://www.set.or.th/api/set/company/MINT/board-of-director?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = BoardOfDirectorService()
        result = await service.fetch_board_of_directors("MiNt", lang="en")

        assert len(result) == 4

    async def test_empty_board_list(self, mock_fetcher):
        """Test handling of company with no board members."""
        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps([]).encode("utf-8"),
            text=json.dumps([]),
            headers={},
            url="https://www.set.or.th/api/set/company/XYZ/board-of-director?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = BoardOfDirectorService()
        result = await service.fetch_board_of_directors("XYZ", lang="en")

        assert isinstance(result, list)
        assert len(result) == 0

    async def test_director_with_empty_positions(self, mock_fetcher):
        """Test handling of director with no positions."""
        data_empty_positions = [
            {
                "name": "Mr. Test Director",
                "positions": [],
            }
        ]

        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps(data_empty_positions).encode("utf-8"),
            text=json.dumps(data_empty_positions),
            headers={},
            url="https://www.set.or.th/api/set/company/TEST/board-of-director?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = BoardOfDirectorService()
        result = await service.fetch_board_of_directors("TEST", lang="en")

        assert len(result) == 1
        assert result[0].name == "Mr. Test Director"
        assert result[0].positions == []

    async def test_director_with_many_positions(self, mock_fetcher):
        """Test handling of director with many positions."""
        data_many_positions = [
            {
                "name": "Mr. Multi-Position Director",
                "positions": [
                    "CHAIRMAN",
                    "CEO",
                    "DIRECTOR",
                    "COMMITTEE MEMBER",
                    "ADVISOR",
                ],
            }
        ]

        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps(data_many_positions).encode("utf-8"),
            text=json.dumps(data_many_positions),
            headers={},
            url="https://www.set.or.th/api/set/company/TEST/board-of-director?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = BoardOfDirectorService()
        result = await service.fetch_board_of_directors("TEST", lang="en")

        assert len(result) == 1
        assert len(result[0].positions) == 5
        assert "CHAIRMAN" in result[0].positions
        assert "ADVISOR" in result[0].positions

    async def test_long_director_name(self, mock_fetcher):
        """Test handling of director with very long name."""
        data_long_name = [
            {
                "name": "Professor Dr. Somchai Pattanapongsakorn Chulalongkorn III",
                "positions": ["INDEPENDENT DIRECTOR"],
            }
        ]

        mock_response = FetchResponse(
            status_code=200,
            content=json.dumps(data_long_name).encode("utf-8"),
            text=json.dumps(data_long_name),
            headers={},
            url="https://www.set.or.th/api/set/company/TEST/board-of-director?lang=en",
            elapsed=0.5,
        )
        mock_fetcher.fetch.return_value = mock_response

        service = BoardOfDirectorService()
        result = await service.fetch_board_of_directors("TEST", lang="en")

        assert len(result) == 1
        assert (
            result[0].name == "Professor Dr. Somchai Pattanapongsakorn Chulalongkorn III"
        )
