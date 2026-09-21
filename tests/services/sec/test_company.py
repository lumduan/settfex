"""Tests for SEC company resolution (mocked JSON POST)."""

from unittest.mock import AsyncMock, patch

import pytest

from settfex.exceptions import AmbiguousCompanyError, CompanyNotFoundError
from settfex.services.sec.company import CompanyMatch, resolve_company, search_companies
from settfex.utils.parsing import ResponseParseError
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
        # Constructed by alias (as the API payload arrives) — model_validate rather than
        # CompanyMatch(Text=...) so the alias path stays exercised AND type-checks: the
        # pydantic mypy plugin types __init__ by field name, not by alias.
        m = CompanyMatch.model_validate({"Text": "CP ALL", "Value": "0000003875", "Flag": True})
        assert m.company_name == "CP ALL"
        assert m.unique_id == "0000003875"
        assert m.is_primary is True

    def test_flag_defaults_false(self) -> None:
        m = CompanyMatch.model_validate({"Text": "X", "Value": "1"})
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
    async def test_non_list_payload_raises_rather_than_returning_empty(self) -> None:
        """Changed in 0.24.0 (D10): a malformed payload is no longer "no matches".

        Returning [] for a shape the search never produces made a broken response
        indistinguishable from "no such issuer" — and `resolve_company` turns [] into None, so the
        confusion propagated all the way to an empty document list.
        """
        _patch_company_fetcher({"unexpected": "shape"})
        try:
            with pytest.raises(ResponseParseError):
                await search_companies("CPALL")
        finally:
            patch.stopall()


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


class TestAmbiguityIsRaisedNotGuessed:
    """0.24.0: several candidates and no primary used to resolve to ``matches[0]``.

    The evidence that made this a defect rather than a rough edge (live-probed 2026-09-20):

    * ``CHINA`` — a SET **ETF**, so no SEC-registered issuer exists at all — returned 60
      name-substring candidates, none flagged, and resolved to ``ASEAN CHINA INVESTMENT FUND L.P.``
    * ``UBOT`` — also an ETF — returned 13 and resolved to ``KUBOTA AYUTTHAYA (HUAHENGLEE)``
    * the Thai query ``ปตท`` (PTT) returned 17 and resolved to
      ``กองทุนสำรองเลี้ยงชีพพนักงานบริษัท ปตท.`` (the PTT employees' provident fund) — while the
      real issuer ``บริษัท ปตท. จำกัด (มหาชน)`` sat **fifth in the same list**

    The candidate list is alphabetical, not ranked, so ``matches[0]`` is arbitrary. Every
    downstream listing and download then attached that company's filings to the requested name:
    not missing data, but confidently wrong data.

    Rate over the sampled domain: 2 of 156 symbols spanning all nine ``securityType`` codes, and
    0 of 156 ever returned more than one primary — which is what makes "no primary" a safe
    trigger rather than a tie-break.
    """

    AMBIGUOUS = [
        {"Text": "ASEAN CHINA INVESTMENT FUND L.P.", "Value": "0000022213", "Flag": False},
        {"Text": "BANGKOK BANK CHINA SHANGHAI", "Value": "0000004168", "Flag": False},
        {"Text": "BANK OF CHINA LIMITED BANGOKOK BRANCH", "Value": "0000007608", "Flag": False},
    ]

    @pytest.mark.asyncio
    async def test_several_candidates_and_no_primary_raises(self) -> None:
        _patch_company_fetcher(self.AMBIGUOUS)
        try:
            with pytest.raises(AmbiguousCompanyError) as excinfo:
                await resolve_company("CHINA")
        finally:
            patch.stopall()
        assert "CHINA" in str(excinfo.value)
        assert "3 SEC issuers matched" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_it_carries_the_candidates_so_the_caller_can_choose(self) -> None:
        """Data, not prose: recovering must not mean re-running the search or parsing a message."""
        _patch_company_fetcher(self.AMBIGUOUS)
        try:
            with pytest.raises(AmbiguousCompanyError) as excinfo:
                await resolve_company("CHINA")
        finally:
            patch.stopall()
        candidates = excinfo.value.candidates
        assert len(candidates) == 3
        assert [c.unique_id for c in candidates][0] == "0000022213"
        assert all(isinstance(c, CompanyMatch) for c in candidates)

    @pytest.mark.asyncio
    async def test_it_is_an_input_error_not_a_fetch_error(self) -> None:
        """Retrying returns the same candidates forever, so `except FetchError: retry` must miss it.

        The same split as ``CompanyNotFoundError``: the request succeeded, and what failed was the
        caller's ability to name one issuer. This is the row #135 records as "invalid input is
        misclassified" — an input problem wearing a transport exception is what makes a retry loop
        spin on a typo.
        """
        from settfex.exceptions import FetchError

        _patch_company_fetcher(self.AMBIGUOUS)
        try:
            with pytest.raises(ValueError) as excinfo:
                await resolve_company("CHINA")
        finally:
            patch.stopall()
        assert not isinstance(excinfo.value, FetchError)

    @pytest.mark.asyncio
    async def test_a_primary_among_many_is_unchanged(self) -> None:
        """The discipline: the new signal must not fire on the healthy majority.

        13 of the 156 sampled symbols returned many candidates *with* a primary — the normal case
        for any real issuer, because the site flags the row the query names.
        """
        _patch_company_fetcher([*self.AMBIGUOUS, {"Text": "REAL", "Value": "9", "Flag": True}])
        try:
            match = await resolve_company("CHINA")
        finally:
            patch.stopall()
        assert match is not None and match.unique_id == "9"

    @pytest.mark.asyncio
    async def test_no_matches_at_all_is_still_none_not_ambiguous(self) -> None:
        """ "Nothing matched" and "several matched" are different answers and stay so."""
        _patch_company_fetcher([])
        try:
            assert await resolve_company("NOPE") is None
        finally:
            patch.stopall()


class TestALoneUnflaggedCandidateIsAmbiguousToo:
    """Changed after the archive validated 0.24.0rc1: one unflagged candidate no longer resolves.

    0.24.0rc1 returned it, reasoning that a single candidate leaves nothing to be ambiguous
    *between*. True of the candidates; false of the question. An unflagged row means the site did
    not resolve the query as an **identifier**, so the row is a substring match on a company
    **name** — which is:

    * exactly right when the caller typed a name (``CP ALL PUBLIC COMPANY LIMITED``), and
    * an unrelated company when they typed a ticker the SEC does not know — the ``UBOT`` →
      ``KUBOTA`` failure with one candidate instead of thirteen.

    The library cannot tell those apart, so the caller declares intent with ``allow_name_match``.

    ⚠️ **The evidence did not decide this; the severity did.** Of 156 sampled symbols across all
    nine ``securityType`` codes exactly **one** hit this case, and that probe recorded aggregates
    only — the symbol and whether it was wrong are unrecoverable. Name-shaped queries were 3/3
    correct. What justifies a breaking default is the cost of being wrong (a whole issuer's filings
    attached to the wrong company), not a measured rate.
    """

    LONE_UNFLAGGED = [
        {"Text": "CP ALL PUBLIC COMPANY LIMITED", "Value": "0000003875", "Flag": False}
    ]

    @pytest.mark.asyncio
    async def test_it_raises_by_default(self) -> None:
        _patch_company_fetcher(self.LONE_UNFLAGGED)
        try:
            with pytest.raises(AmbiguousCompanyError):
                await resolve_company("CP ALL PUBLIC COMPANY LIMITED")
        finally:
            patch.stopall()

    @pytest.mark.asyncio
    async def test_the_error_carries_the_one_candidate(self) -> None:
        """So an agent can inspect and decide **without a second request** — the whole point."""
        _patch_company_fetcher(self.LONE_UNFLAGGED)
        try:
            with pytest.raises(AmbiguousCompanyError) as excinfo:
                await resolve_company("UBOT")
        finally:
            patch.stopall()
        assert len(excinfo.value.candidates) == 1
        assert excinfo.value.candidates[0].unique_id == "0000003875"
        assert isinstance(excinfo.value.candidates[0], CompanyMatch)

    @pytest.mark.asyncio
    async def test_the_message_names_the_opt_in(self) -> None:
        """An opt-in nobody can discover from the error is not an opt-in."""
        _patch_company_fetcher(self.LONE_UNFLAGGED)
        try:
            with pytest.raises(AmbiguousCompanyError) as excinfo:
                await resolve_company("UBOT")
        finally:
            patch.stopall()
        assert "allow_name_match=True" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_the_opt_in_returns_it(self) -> None:
        """A deliberate name lookup is the case this flag exists for."""
        _patch_company_fetcher(self.LONE_UNFLAGGED)
        try:
            match = await resolve_company("CP ALL PUBLIC COMPANY LIMITED", allow_name_match=True)
        finally:
            patch.stopall()
        assert match is not None and match.unique_id == "0000003875"

    @pytest.mark.asyncio
    async def test_the_flag_never_rescues_multiple_unflagged_candidates(self) -> None:
        """`allow_name_match` is about ONE row. CHINA/UBOT stay ambiguous whatever was intended."""
        _patch_company_fetcher(TestAmbiguityIsRaisedNotGuessed.AMBIGUOUS)
        try:
            with pytest.raises(AmbiguousCompanyError) as excinfo:
                await resolve_company("CHINA", allow_name_match=True)
        finally:
            patch.stopall()
        assert len(excinfo.value.candidates) == 3

    @pytest.mark.asyncio
    async def test_a_flagged_single_candidate_is_unaffected(self) -> None:
        """The healthy majority: a real ticker flags, and the flag changes nothing for it."""
        _patch_company_fetcher(
            [{"Text": "CP ALL PUBLIC COMPANY LIMITED", "Value": "0000003875", "Flag": True}]
        )
        try:
            match = await resolve_company("CPALL")
        finally:
            patch.stopall()
        assert match is not None and match.unique_id == "0000003875"


class TestWhatTheFlagActuallyMeans:
    """``Flag`` says the site resolved your *query*, not that the row is the best match.

    Live-probed 2026-09-20 (the table is reproduced on ``CompanyMatch.is_primary``):

    * ``CPALL`` and ``cpall`` → 1 match, flagged — tickers resolve, case-insensitively
    * ``0000003875`` → 1 match, flagged — the uniqueIDReference resolves too
    * ``CP ALL PUBLIC COMPANY LIMITED`` → 1 match, **not** flagged — the *exact legal name* does
      not resolve, because the search is a substring match over names, not a lookup

    That last row is the one worth pinning: it rules out the natural reading ("the flag marks the
    exact match"), and it is what makes an unflagged multi-candidate result genuinely arbitrary
    rather than merely unranked.
    """

    @pytest.mark.asyncio
    async def test_an_exact_full_company_name_is_not_flagged(self) -> None:
        _patch_company_fetcher(
            [{"Text": "CP ALL PUBLIC COMPANY LIMITED", "Value": "0000003875", "Flag": False}]
        )
        try:
            matches = await search_companies("CP ALL PUBLIC COMPANY LIMITED")
        finally:
            patch.stopall()
        assert len(matches) == 1
        assert matches[0].is_primary is False, "a name query never flags, even when exact"

    @pytest.mark.asyncio
    async def test_a_ticker_is_flagged(self) -> None:
        _patch_company_fetcher(
            [{"Text": "CP ALL PUBLIC COMPANY LIMITED", "Value": "0000003875", "Flag": True}]
        )
        try:
            matches = await search_companies("CPALL")
        finally:
            patch.stopall()
        assert matches[0].is_primary is True


class TestGetSecDocumentsForwardsTheFlag:
    """The `get_*` tier is the LLM tool-calling entry point, so its passthrough is load-bearing."""

    @pytest.mark.asyncio
    async def test_it_is_forwarded(self) -> None:
        from settfex.services.sec.financial_report import get_sec_documents

        with (
            patch(
                "settfex.services.sec.financial_report.resolve_company",
                new=AsyncMock(return_value=None),
            ) as mock_resolve,
            pytest.raises(CompanyNotFoundError),
        ):
            await get_sec_documents("CP ALL PUBLIC COMPANY LIMITED", allow_name_match=True)
        assert mock_resolve.await_args.kwargs["allow_name_match"] is True

    @pytest.mark.asyncio
    async def test_it_defaults_to_strict(self) -> None:
        from settfex.services.sec.financial_report import get_sec_documents

        with (
            patch(
                "settfex.services.sec.financial_report.resolve_company",
                new=AsyncMock(return_value=None),
            ) as mock_resolve,
            pytest.raises(CompanyNotFoundError),
        ):
            await get_sec_documents("CPALL")
        assert mock_resolve.await_args.kwargs["allow_name_match"] is False
