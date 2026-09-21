"""Tests for the SecCompany facade (delegation + lazy resolve caching)."""

from unittest.mock import AsyncMock, patch

import pytest

from settfex.exceptions import AmbiguousCompanyError, CompanyNotFoundError, FetchError
from settfex.services.sec.company import CompanyMatch
from settfex.services.sec.financial_report import DocumentCategory, SecDocument
from settfex.services.sec.sec import SecCompany

pytestmark = pytest.mark.asyncio

_MATCH = CompanyMatch(
    company_name="CP ALL PUBLIC COMPANY LIMITED", unique_id="0000003875", is_primary=True
)


class TestResolve:
    async def test_resolves_and_caches(self) -> None:
        with patch(
            "settfex.services.sec.sec.resolve_company", new=AsyncMock(return_value=_MATCH)
        ) as mock_resolve:
            sec = SecCompany("cpall")
            a = await sec.resolve()
            b = await sec.resolve()
        assert a is b and a.unique_id == "0000003875"
        mock_resolve.assert_awaited_once()  # cached: resolver called once

    async def test_not_found_raises_an_input_error_not_a_fetch_error(self) -> None:
        """Changed in 0.24.0 — it was ``SymbolNotFoundError``, a ``FetchError`` subclass.

        The identical condition ("the search ran and matched no issuer") was already a
        ``CompanyNotFoundError`` through ``get_sec_documents``, so ``except FetchError`` caught it
        through one entry point and not the other, for the same input. D10's split is between a
        lookup that *failed* and an issuer that does not *exist*; this was on the wrong side of it.
        """
        with (
            patch("settfex.services.sec.sec.resolve_company", new=AsyncMock(return_value=None)),
            pytest.raises(CompanyNotFoundError) as excinfo,
        ):
            await SecCompany("nope").resolve()
        assert not isinstance(excinfo.value, FetchError), "retrying will never help"

    async def test_an_ambiguous_query_propagates(self) -> None:
        """The facade adds nothing here — the resolver's input error reaches the caller intact."""
        with (
            patch(
                "settfex.services.sec.sec.resolve_company",
                new=AsyncMock(side_effect=AmbiguousCompanyError("many", candidates=[])),
            ),
            pytest.raises(AmbiguousCompanyError),
        ):
            await SecCompany("CHINA").resolve()


class TestDelegation:
    async def test_list_documents_delegates(self) -> None:
        doc = SecDocument(
            company_name="CP ALL",
            unique_id="0000003875",
            category=DocumentCategory.FORM_56_1,
            section="Form 56-1",
            file_url="u",
            file_id="dat/f56/x.zip",
            file_kind="zip",
        )
        with patch("settfex.services.sec.sec.resolve_company", new=AsyncMock(return_value=_MATCH)):
            sec = SecCompany("CPALL")
            with patch.object(
                sec.report_service, "fetch_documents", new=AsyncMock(return_value=[doc])
            ) as mock_fetch:
                docs = await sec.list_documents(types="form_56_1")
        assert docs == [doc]
        # facade forwards the resolved unique_id + company_name
        _, kwargs = mock_fetch.call_args
        assert kwargs["company_name"] == "CP ALL PUBLIC COMPANY LIMITED"

    async def test_download_all_delegates(self) -> None:
        with patch("settfex.services.sec.sec.resolve_company", new=AsyncMock(return_value=_MATCH)):
            sec = SecCompany("CPALL")
            with patch.object(
                sec.download_service, "download_all", new=AsyncMock(return_value=[])
            ) as mock_dl:
                await sec.download_all(["dat/news/x.zip"], dest_dir="/tmp/out", max_concurrency=3)
        _, kwargs = mock_dl.call_args
        assert kwargs["dest_dir"] == "/tmp/out" and kwargs["max_concurrency"] == 3


@pytest.mark.asyncio
class TestAllowNameMatchReachesTheResolver:
    """A flag the facade does not forward is a flag that does not exist.

    `SecCompany` and `get_sec_documents` are the tiers people actually call — the resolver is one
    layer down. If `allow_name_match` stopped at the facade, a name lookup would be impossible
    through the documented entry points, which is the whole surface most callers ever touch.
    """

    async def test_sec_company_forwards_it(self) -> None:
        with patch(
            "settfex.services.sec.sec.resolve_company", new=AsyncMock(return_value=_MATCH)
        ) as mock_resolve:
            await SecCompany("CP ALL PUBLIC COMPANY LIMITED", allow_name_match=True).resolve()
        assert mock_resolve.await_args.kwargs["allow_name_match"] is True

    async def test_sec_company_defaults_to_strict(self) -> None:
        with patch(
            "settfex.services.sec.sec.resolve_company", new=AsyncMock(return_value=_MATCH)
        ) as mock_resolve:
            await SecCompany("CPALL").resolve()
        assert mock_resolve.await_args.kwargs["allow_name_match"] is False

    async def test_an_ambiguous_lone_match_propagates_through_the_facade(self) -> None:
        with (
            patch(
                "settfex.services.sec.sec.resolve_company",
                new=AsyncMock(side_effect=AmbiguousCompanyError("one, unflagged", candidates=[])),
            ),
            pytest.raises(AmbiguousCompanyError),
        ):
            await SecCompany("UBOT").resolve()
