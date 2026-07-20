"""Tests for SEC company resolution (mocked JSON POST)."""

from unittest.mock import AsyncMock, patch

import pytest

from settfex.services.sec.company import CompanyMatch, resolve_company, search_companies
from tests.services.sec.fixtures import COMPANY_SEARCH_JSON, COMPANY_SEARCH_MULTI_JSON


def _patch_company_fetcher(payload):
    """Patch AsyncDataFetcher in the company module; fetch_json returns ``payload``."""
    cls = patch("settfex.services.sec.company.AsyncDataFetcher").start()
    instance = AsyncMock()
    instance.fetch_json = AsyncMock(return_value=payload)
    cls.return_value.__aenter__.return_value = instance
    cls.return_value.__aexit__.return_value = None
    return cls, instance


class TestCompanyMatchModel:
    def test_aliases(self) -> None:
        m = CompanyMatch(Text="CP ALL", Value="0000003875", Flag=True)
        assert m.company_name == "CP ALL"
        assert m.unique_id == "0000003875"
        assert m.is_primary is True

    def test_flag_defaults_false(self) -> None:
        m = CompanyMatch(Text="X", Value="1")
        assert m.is_primary is False


class TestSearchCompanies:
    @pytest.mark.asyncio
    async def test_returns_matches(self) -> None:
        cls, instance = _patch_company_fetcher(COMPANY_SEARCH_JSON)
        try:
            matches = await search_companies("CPALL")
        finally:
            patch.stopall()
        assert len(matches) == 1
        assert matches[0].unique_id == "0000003875"
        # POST with JSON body {lang, content}
        _, kwargs = instance.fetch_json.call_args
        assert kwargs["method"] == "POST"
        assert kwargs["json_body"] == {"lang": "en", "content": "CPALL"}

    @pytest.mark.asyncio
    async def test_non_list_payload_returns_empty(self) -> None:
        _patch_company_fetcher({"unexpected": "shape"})
        try:
            matches = await search_companies("CPALL")
        finally:
            patch.stopall()
        assert matches == []


class TestResolveCompany:
    @pytest.mark.asyncio
    async def test_prefers_primary_flag(self) -> None:
        _patch_company_fetcher(COMPANY_SEARCH_MULTI_JSON)
        try:
            match = await resolve_company("PTT")
        finally:
            patch.stopall()
        assert match is not None
        assert match.is_primary is True
        assert match.unique_id == "0000001111"

    @pytest.mark.asyncio
    async def test_empty_returns_none(self) -> None:
        _patch_company_fetcher([])
        try:
            match = await resolve_company("NOPE")
        finally:
            patch.stopall()
        assert match is None
