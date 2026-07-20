"""SEC company resolution — map a symbol/name to the IDISC uniqueIDReference.

The search page identifies an issuer by a 10-digit ``uniqueIDReference`` (e.g. CPALL =
``0000003875``), obtained from a small JSON autocomplete API. This is a clean JSON POST and
reuses the existing ``AsyncDataFetcher.fetch_json`` (stateless — no SessionManager).
"""

from __future__ import annotations

from typing import Any

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from settfex.services.sec.constants import (
    SEC_BASE_URL,
    SEC_COMPANY_SEARCH_ENDPOINT,
    SEC_REFERER,
)
from settfex.services.sec.utils import build_sec_headers
from settfex.services.set.stock.utils import Language, normalize_language
from settfex.utils.data_fetcher import AsyncDataFetcher, FetcherConfig


class CompanyMatch(BaseModel):
    """One issuer match from the SEC company autocomplete."""

    company_name: str = Field(alias="Text", description="Full issuer name")
    unique_id: str = Field(alias="Value", description="10-digit SEC uniqueIDReference")
    is_primary: bool = Field(
        default=False,
        alias="Flag",
        description="True for the primary/exact match (e.g. the symbol's listed company)",
    )

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
        data: Any = await fetcher.fetch_json(
            url, headers=headers, method="POST", json_body=body
        )

    if not isinstance(data, list):
        logger.warning(f"Unexpected company-search payload type: {type(data).__name__}")
        return []
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
    Resolve a symbol/name to a single best CompanyMatch (primary match preferred).

    Returns the ``is_primary`` match if present, else the first match, else None.
    """
    matches = await search_companies(query, lang, config=config)
    if not matches:
        return None
    for match in matches:
        if match.is_primary:
            return match
    return matches[0]
