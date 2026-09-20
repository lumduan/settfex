"""SEC company resolution — map a symbol/name to the IDISC uniqueIDReference.

The search page identifies an issuer by a 10-digit ``uniqueIDReference`` (e.g. CPALL =
``0000003875``), obtained from a small JSON autocomplete API. This is a clean JSON POST and
reuses the existing ``AsyncDataFetcher.fetch_json`` (stateless — no SessionManager).
"""

from __future__ import annotations

from typing import Any

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from settfex.exceptions import AmbiguousCompanyError
from settfex.services.sec.constants import (
    SEC_BASE_URL,
    SEC_COMPANY_SEARCH_ENDPOINT,
    SEC_REFERER,
)
from settfex.services.sec.utils import build_sec_headers
from settfex.services.set.stock.utils import Language, normalize_language
from settfex.utils.data_fetcher import AsyncDataFetcher, FetcherConfig
from settfex.utils.parsing import ResponseParseError


class CompanyMatch(BaseModel):
    """One issuer match from the SEC company autocomplete."""

    company_name: str = Field(alias="Text", description="Full issuer name")
    unique_id: str = Field(alias="Value", description="10-digit SEC uniqueIDReference")
    is_primary: bool = Field(
        default=False,
        alias="Flag",
        description="True when the query was an identifier the SEC resolved (ticker or uniqueID)",
    )
    """True when the query was an **identifier** the site resolved, not "the best match".

    Live-probed 2026-09-20, and the distinction is load-bearing for :func:`resolve_company`:

    ====================================  ==========================  =======  ======
    query                                 kind                        matches  Flag
    ====================================  ==========================  =======  ======
    ``CPALL`` / ``cpall``                 ticker (case-insensitive)   1        True
    ``0000003875``                        the uniqueIDReference        1        True
    ``CP ALL``                            partial name                 1        False
    ``CP ALL PUBLIC COMPANY LIMITED``     **exact full legal name**    1        False
    ``CHINA`` (a SET ETF, no SEC issuer)  unknown identifier           60       False
    ====================================  ==========================  =======  ======

    So a **name** query never flags a row, not even the exact legal name — the flag says the site
    recognised the *query*, and the search itself is a plain substring match over company names
    returned in alphabetical order. That is why an unflagged multi-candidate result has no
    non-arbitrary winner, and why :func:`resolve_company` raises instead of taking the first row.

    No probed query ever returned more than one flagged row, which is what makes "no primary" a
    safe trigger rather than a tie-break.
    """

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)


def _stateless_config(config: FetcherConfig | None) -> FetcherConfig:
    """Force use_session=False (the SEC host is stateless), preserving other config."""
    base = config or FetcherConfig()
    return base.model_copy(update={"use_session": False})


async def search_companies(
    query: str,
    lang: Language = "en",
    *,
    config: FetcherConfig | None = None,
) -> list[CompanyMatch]:
    """
    Search issuers by name or symbol; returns all matches (primary match flagged).

    Args:
        query: Symbol or (partial) company name, e.g. "CPALL" or "CP ALL".
        lang: Response language ('en' or 'th').
        config: Optional fetcher configuration (use_session is forced off).

    Returns:
        List of CompanyMatch (may be empty). Primary/exact matches have is_primary=True.
    """
    lang = normalize_language(lang)
    url = f"{SEC_BASE_URL}{SEC_COMPANY_SEARCH_ENDPOINT}"
    body = {"lang": lang, "content": query.strip()}
    headers = build_sec_headers(referer=SEC_REFERER, origin=True)

    logger.info(f"Resolving SEC company for query={query!r} (lang={lang})")
    async with AsyncDataFetcher(config=_stateless_config(config)) as fetcher:
        data: Any = await fetcher.fetch_json(url, headers=headers, method="POST", json_body=body)

    if not isinstance(data, list):
        # Returning [] here made a malformed response indistinguishable from "no such company",
        # which is the whole of D10 in three lines.
        error_msg = (
            f"Expected a list response from the SEC company search, got {type(data).__name__}"
        )
        logger.error(error_msg)
        raise ResponseParseError(error_msg)
    matches = [CompanyMatch.model_validate(item) for item in data]
    logger.info(f"Found {len(matches)} company match(es) for {query!r}")
    return matches


async def resolve_company(
    query: str,
    lang: Language = "en",
    *,
    config: FetcherConfig | None = None,
) -> CompanyMatch | None:
    """
    Resolve a symbol/name to a single best CompanyMatch.

    The site flags *the* match for a query with ``Flag`` (:attr:`CompanyMatch.is_primary`), and in
    every live probe a query had **0 or 1** primaries, never more. So:

    * a primary exists         → return it
    * no primary, one match    → return it (there is nothing to be ambiguous between)
    * no primary, many matches → raise :class:`AmbiguousCompanyError` with the candidates
    * nothing at all           → return ``None``

    Args:
        query: Symbol or (partial) company name.
        lang: Response language ('en' or 'th').
        config: Optional fetcher configuration (use_session is forced off).

    Returns:
        The resolved :class:`CompanyMatch`, or ``None`` when the site knows no such issuer.

    Raises:
        AmbiguousCompanyError: Several candidates and none flagged primary.
        FetchError: On a transport failure or a non-listing response.
    """
    matches = await search_companies(query, lang, config=config)
    if not matches:
        return None
    for match in matches:
        if match.is_primary:
            return match
    if len(matches) == 1:
        # One candidate and no flag: nothing to choose between, so this is not the ambiguous
        # case. A full company name typed out ("CP ALL PUBLIC COMPANY LIMITED") lands here.
        logger.info(
            f"Resolved {query!r} to the single unflagged candidate {matches[0].company_name!r}"
        )
        return matches[0]

    # Until 0.24.0 this returned `matches[0]`. The autocomplete does substring matching on the
    # company NAME and returns its candidates alphabetically, not by relevance, so the first row
    # is an arbitrary company -- and when the query is not an SEC-registered issuer at all (a SET
    # ETF, a warrant, a DW), *every* candidate is unrelated. Live-probed 2026-09-20: `CHINA` (an
    # ETF) resolved to "ASEAN CHINA INVESTMENT FUND L.P." out of 60 candidates, and the Thai query
    # `ปตท` resolved to the PTT employees' provident fund while the real issuer sat fifth in the
    # same list.
    #
    # Raising rather than guessing is the whole point: every downstream listing and download would
    # otherwise attach that company's filings to the requested name. This release is about
    # incompleteness that never reaches the return value, and a confident wrong answer is the
    # sharpest form of it.
    names = ", ".join(f"{m.company_name} ({m.unique_id})" for m in matches[:5])
    error_msg = (
        f"{len(matches)} SEC issuers matched {query!r} and the site flagged none of them as the "
        f"match, so there is no non-arbitrary way to choose one. First {min(5, len(matches))}: "
        f"{names}{', …' if len(matches) > 5 else ''}. Call search_companies({query!r}) to see "
        f"every candidate and pass the one you want, or query an exact symbol. Note a SET symbol "
        f"that is not an SEC-registered issuer (an ETF, warrant or DW) will never match one."
    )
    logger.error(error_msg)
    raise AmbiguousCompanyError(error_msg, candidates=matches)
