"""Tests for the SecCompany facade (delegation + lazy resolve caching)."""

from unittest.mock import AsyncMock, patch

import pytest

from settfex.exceptions import SymbolNotFoundError
from settfex.services.sec.company import CompanyMatch
from settfex.services.sec.financial_report import DocumentCategory, SecDocument
from settfex.services.sec.sec import SecCompany

pytestmark = pytest.mark.asyncio

_MATCH = CompanyMatch(Text="CP ALL PUBLIC COMPANY LIMITED", Value="0000003875", Flag=True)


class TestResolve:
    async def test_resolves_and_caches(self) -> None:
        with patch("settfex.services.sec.sec.resolve_company",
                   new=AsyncMock(return_value=_MATCH)) as mock_resolve:
            sec = SecCompany("cpall")
            a = await sec.resolve()
            b = await sec.resolve()
        assert a is b and a.unique_id == "0000003875"
        mock_resolve.assert_awaited_once()  # cached: resolver called once

    async def test_not_found_raises(self) -> None:
        with patch("settfex.services.sec.sec.resolve_company",
                   new=AsyncMock(return_value=None)), pytest.raises(SymbolNotFoundError):
            await SecCompany("nope").resolve()


class TestDelegation:
    async def test_list_documents_delegates(self) -> None:
        doc = SecDocument(
            company_name="CP ALL", unique_id="0000003875",
            category=DocumentCategory.FORM_56_1, section="Form 56-1",
            file_url="u", file_id="dat/f56/x.zip", file_kind="zip",
        )
        with patch("settfex.services.sec.sec.resolve_company",
                   new=AsyncMock(return_value=_MATCH)):
            sec = SecCompany("CPALL")
            with patch.object(sec.report_service, "fetch_documents",
                              new=AsyncMock(return_value=[doc])) as mock_fetch:
                docs = await sec.list_documents(types="form_56_1")
        assert docs == [doc]
        # facade forwards the resolved unique_id + company_name
        _, kwargs = mock_fetch.call_args
        assert kwargs["company_name"] == "CP ALL PUBLIC COMPANY LIMITED"

    async def test_download_all_delegates(self) -> None:
        with patch("settfex.services.sec.sec.resolve_company",
                   new=AsyncMock(return_value=_MATCH)):
            sec = SecCompany("CPALL")
            with patch.object(sec.download_service, "download_all",
                              new=AsyncMock(return_value=[])) as mock_dl:
                await sec.download_all(["dat/news/x.zip"], dest_dir="/tmp/out", max_concurrency=3)
        _, kwargs = mock_dl.call_args
        assert kwargs["dest_dir"] == "/tmp/out" and kwargs["max_concurrency"] == 3
