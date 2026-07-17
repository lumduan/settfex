"""Tests for the SET market index list service (index directory)."""

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from settfex.services.set.index.list import (
    IndexListResponse,
    IndexListService,
    IndexSymbol,
    get_index_list,
)
from settfex.utils.data_fetcher import FetcherConfig

# Representative slice of the live /api/set/index/list payload: headline indices for both
# markets, the SET/mai 'AGRO' industry pair (same symbol, different querySymbol), one sector.
SAMPLE_INDEX_LIST: list[dict[str, Any]] = [
    {
        "symbol": "SET",
        "market": "SET",
        "level": "INDEX",
        "parentIndex": None,
        "querySymbol": "SET",
        "nameEN": "SET",
        "nameTH": "SET",
    },
    {
        "symbol": "SET50",
        "market": "SET",
        "level": "INDEX",
        "parentIndex": None,
        "querySymbol": "SET50",
        "nameEN": "SET50",
        "nameTH": "SET50",
    },
    {
        "symbol": "sSET",
        "market": "SET",
        "level": "INDEX",
        "parentIndex": None,
        "querySymbol": "sSET",
        "nameEN": "sSET",
        "nameTH": "sSET",
    },
    {
        "symbol": "mai",
        "market": "mai",
        "level": "INDEX",
        "parentIndex": None,
        "querySymbol": "mai",
        "nameEN": "mai",
        "nameTH": "mai",
    },
    {
        "symbol": "AGRO",
        "market": "SET",
        "level": "INDUSTRY",
        "parentIndex": "SET",
        "querySymbol": "AGRO",
        "nameEN": "Agro & Food Industry",
        "nameTH": "เกษตรและอุตสาหกรรมอาหาร",
    },
    {
        "symbol": "AGRO",
        "market": "mai",
        "level": "INDUSTRY",
        "parentIndex": "mai",
        "querySymbol": "AGRO-m",
        "nameEN": "Agro & Food Industry",
        "nameTH": "เกษตรและอุตสาหกรรมอาหาร",
    },
    {
        "symbol": "AGRI",
        "market": "SET",
        "level": "SECTOR",
        "parentIndex": "AGRO",
        "querySymbol": "AGRI",
        "nameEN": "Agribusiness",
        "nameTH": "ธุรกิจการเกษตร",
    },
]


def _index_list() -> IndexListResponse:
    """Build an IndexListResponse from the sample payload."""
    return IndexListResponse(
        indices=[IndexSymbol.model_validate(item) for item in SAMPLE_INDEX_LIST]
    )


@pytest.fixture
def mock_fetcher():
    """Patch AsyncDataFetcher inside the index list module; yield its async instance."""
    with patch("settfex.services.set.index.list.AsyncDataFetcher") as mock:
        fetcher_instance = AsyncMock()
        mock.return_value.__aenter__.return_value = fetcher_instance
        mock.return_value.__aexit__.return_value = None
        mock.get_set_api_headers = Mock(return_value={"Accept": "application/json"})
        fetcher_instance.cls = mock
        yield fetcher_instance


class TestIndexSymbolModel:
    """Pydantic parsing: camelCase aliases, null parent, populate_by_name."""

    def test_aliases(self):
        ix = IndexSymbol.model_validate(SAMPLE_INDEX_LIST[5])
        assert ix.symbol == "AGRO"
        assert ix.market == "mai"
        assert ix.level == "INDUSTRY"
        assert ix.parent_index == "mai"
        assert ix.query_symbol == "AGRO-m"
        assert ix.name_en == "Agro & Food Industry"
        assert ix.name_th == "เกษตรและอุตสาหกรรมอาหาร"

    def test_null_parent_index(self):
        ix = IndexSymbol.model_validate(SAMPLE_INDEX_LIST[0])
        assert ix.parent_index is None

    def test_populate_by_name(self):
        ix = IndexSymbol(
            symbol="SET50",
            market="SET",
            level="INDEX",
            parent_index=None,
            query_symbol="SET50",
        )
        assert ix.query_symbol == "SET50"
        assert ix.name_en == ""


class TestIndexListResponse:
    """Filtering, level properties, and index lookup incl. the AGRO ambiguity."""

    def test_count(self):
        assert _index_list().count == 7

    def test_level_properties(self):
        response = _index_list()
        assert [ix.symbol for ix in response.market_indices] == ["SET", "SET50", "sSET", "mai"]
        assert len(response.industries) == 2
        assert [ix.symbol for ix in response.sectors] == ["AGRI"]

    def test_filter_by_market_case_insensitive(self):
        response = _index_list()
        mai_entries = response.filter_by_market("MAI")
        assert {ix.query_symbol for ix in mai_entries} == {"mai", "AGRO-m"}

    def test_filter_by_level_case_insensitive(self):
        assert [ix.symbol for ix in _index_list().filter_by_level("sector")] == ["AGRI"]

    def test_get_index_by_symbol(self):
        ix = _index_list().get_index("SET50")
        assert ix is not None
        assert ix.symbol == "SET50"

    def test_get_index_case_insensitive_sset(self):
        ix = _index_list().get_index("sset")
        assert ix is not None
        assert ix.symbol == "sSET"

    def test_get_index_query_symbol_pins_mai_industry(self):
        ix = _index_list().get_index("agro-m")
        assert ix is not None
        assert ix.market == "mai"
        assert ix.query_symbol == "AGRO-m"

    def test_get_index_with_market_disambiguates(self):
        set_agro = _index_list().get_index("AGRO", market="SET")
        assert set_agro is not None
        assert set_agro.market == "SET"
        mai_agro = _index_list().get_index("AGRO", market="mai")
        assert mai_agro is not None
        assert mai_agro.query_symbol == "AGRO-m"

    def test_get_index_bare_agro_resolves_via_query_symbol(self):
        # 'AGRO' is the SET industry's exact query_symbol, so it wins deterministically.
        ix = _index_list().get_index("AGRO")
        assert ix is not None
        assert ix.market == "SET"

    def test_get_index_not_found(self):
        assert _index_list().get_index("NOPE") is None
        assert _index_list().get_index("AGRI", market="mai") is None


@pytest.mark.asyncio
class TestIndexListService:
    """Service I/O: fetch, raw fetch, URL/language construction, header defaults."""

    async def test_init_default_and_custom_config(self):
        assert IndexListService().base_url == "https://www.set.or.th"
        service = IndexListService(config=FetcherConfig(timeout=60, max_retries=5))
        assert service.config.timeout == 60
        assert service.config.max_retries == 5

    async def test_fetch_success(self, mock_fetcher):
        mock_fetcher.fetch_json.return_value = SAMPLE_INDEX_LIST
        response = await IndexListService().fetch_index_list()
        assert isinstance(response, IndexListResponse)
        assert response.count == 7
        assert response.get_index("sSET") is not None

    async def test_fetch_url_and_default_language(self, mock_fetcher):
        mock_fetcher.fetch_json.return_value = SAMPLE_INDEX_LIST
        await IndexListService().fetch_index_list()
        url = mock_fetcher.fetch_json.call_args.args[0]
        assert "/api/set/index/list" in url
        assert "language=en" in url

    async def test_fetch_thai_language(self, mock_fetcher):
        mock_fetcher.fetch_json.return_value = SAMPLE_INDEX_LIST
        await IndexListService().fetch_index_list(lang="th")
        assert "language=th" in mock_fetcher.fetch_json.call_args.args[0]

    async def test_fetch_invalid_language_raises(self):
        with pytest.raises(ValueError, match="Invalid language"):
            await IndexListService().fetch_index_list(lang="fr")  # type: ignore[arg-type]  # intentional: runtime-permissive language

    async def test_fetch_uses_default_referer(self, mock_fetcher):
        mock_fetcher.fetch_json.return_value = SAMPLE_INDEX_LIST
        await IndexListService().fetch_index_list()
        # Market-wide list endpoint uses the default SET headers (no per-index referer)
        assert mock_fetcher.cls.get_set_api_headers.call_args.args == ()
        assert mock_fetcher.cls.get_set_api_headers.call_args.kwargs == {}

    async def test_fetch_raw_returns_bare_list(self, mock_fetcher):
        mock_fetcher.fetch_json.return_value = SAMPLE_INDEX_LIST
        raw = await IndexListService().fetch_index_list_raw()
        assert isinstance(raw, list)
        assert raw[0]["symbol"] == "SET"


@pytest.mark.asyncio
class TestConvenienceFunctions:
    """Top-level get_index_list."""

    async def test_get_index_list(self, mock_fetcher):
        mock_fetcher.fetch_json.return_value = SAMPLE_INDEX_LIST
        response = await get_index_list()
        assert isinstance(response, IndexListResponse)
        assert len(response.market_indices) == 4

    async def test_get_index_list_thai(self, mock_fetcher):
        mock_fetcher.fetch_json.return_value = SAMPLE_INDEX_LIST
        await get_index_list(lang="thai")  # type: ignore[arg-type]  # intentional: runtime-permissive language
        assert "language=th" in mock_fetcher.fetch_json.call_args.args[0]
