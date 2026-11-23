"""Bank of Thailand License Check product: who is licensed, and the licence documents (1.0.0).

Its official spec documents no response schema, so these models follow the live answers of
2026-11-23. The document endpoint returns a file (a PDF), not JSON.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from settfex.services.bot.auth import DEFAULT_ENV_FILE
from settfex.services.bot.client import BotClient
from settfex.services.bot.constants import (
    LICENSE_DETAIL_PATH,
    LICENSE_DOCUMENT_PATH,
    LICENSE_SEARCH_PATH,
    BotProduct,
)
from settfex.services.bot.models import (
    License,
    LicensedEntity,
    LicensedEntityDetail,
    LicenseDocument,
    LicenseSearchResult,
)
from settfex.utils.data_fetcher import FetcherConfig
from settfex.utils.parsing import ResponseParseError, decode_json, validate_or_raise


class LicenseCheckService:
    """The BOT License Check product (token: ``BANK_OF_THAILAND_TOKEN_LICENSE_CHECK``)."""

    def __init__(
        self,
        *,
        token: str | None = None,
        env_file: str | Path | None = DEFAULT_ENV_FILE,
        config: FetcherConfig | None = None,
    ) -> None:
        self.client = BotClient(
            BotProduct.LICENSE_CHECK, token=token, env_file=env_file, config=config
        )

    async def search(self, keyword: str, *, page: int = 1, limit: int = 20) -> LicenseSearchResult:
        """Licensed or registered businesses matching ``keyword`` (Thai or English names)."""
        if not keyword or not keyword.strip():
            raise ValueError("keyword must not be empty")
        params = {"keyword": keyword.strip(), "page": str(page), "limit": str(limit)}
        data = await self.client.get_json(LICENSE_SEARCH_PATH, params)
        if not isinstance(data, dict) or not isinstance(data.get("ResultSet"), list):
            raise ResponseParseError("BOT license search: expected a JSON object with 'ResultSet'")
        info = data.get("ResultSetInfo") or {}
        return LicenseSearchResult(
            entities=[
                validate_or_raise(LicensedEntity, e, context="BOT license search")
                for e in data.get("ResultSet") or []
            ],
            total=info.get("QueryTotalRecord"),
            page=info.get("QueryCurrentPage"),
            per_page=info.get("QueryRecordPerPage"),
            groups=list(data.get("GroupInfo") or []),
        )

    async def fetch_entity(self, entity_id: str | int) -> LicensedEntityDetail:
        """One entity's record and licences (``entity_id`` is ``LicensedEntity.id``)."""
        data = await self.client.get_json(LICENSE_DETAIL_PATH, {"id": str(entity_id)})
        if not isinstance(data, dict) or not isinstance(data.get("AuthorizationInfo"), dict):
            raise ResponseParseError(f"BOT license detail {entity_id}: no AuthorizationInfo")
        return LicensedEntityDetail(
            entity=validate_or_raise(
                LicensedEntity, data["AuthorizationInfo"], context="BOT license detail"
            ),
            licenses=[
                validate_or_raise(License, x, context="BOT licence")
                for x in data.get("LicenseInformations") or []
            ],
            branches=list(data.get("Branches") or []),
        )

    async def fetch_document(self, auth_id: str | int, doc_id: str | int) -> LicenseDocument:
        """A licence document file (``doc_id``: a :class:`License` id from :meth:`fetch_entity`)."""
        params = {"authId": str(auth_id), "docId": str(doc_id)}
        response = await self.client.get(LICENSE_DOCUMENT_PATH, params, decode_text=False)
        content_type = (
            response.headers.get("content-type") or response.headers.get("Content-Type") or ""
        )
        if "json" in content_type.lower():
            body = decode_json(
                response.content.decode("utf-8", "replace"), context="BOT license document"
            )
            raise ResponseParseError(
                f"BOT license document {auth_id}/{doc_id}: got JSON, not a file: {body!r}"[:300]
            )
        return LicenseDocument(
            content=response.content,
            content_type=content_type,
            size=len(response.content),
            auth_id=str(auth_id),
            doc_id=str(doc_id),
        )

    async def fetch_raw(self, path: str, params: dict[str, str] | None = None) -> Any:
        """Any endpoint of this product, as decoded JSON (escape hatch)."""
        return await self.client.fetch_raw(path, params)


async def search_licensed_entities(
    keyword: str,
    *,
    page: int = 1,
    limit: int = 20,
    token: str | None = None,
    env_file: str | Path | None = DEFAULT_ENV_FILE,
    config: FetcherConfig | None = None,
) -> LicenseSearchResult:
    """Search the businesses the Bank of Thailand has licensed or registered."""
    service = LicenseCheckService(token=token, env_file=env_file, config=config)
    return await service.search(keyword, page=page, limit=limit)


async def get_licensed_entity(
    entity_id: str | int,
    *,
    token: str | None = None,
    env_file: str | Path | None = DEFAULT_ENV_FILE,
    config: FetcherConfig | None = None,
) -> LicensedEntityDetail:
    """One licensed entity's record and licences."""
    return await LicenseCheckService(token=token, env_file=env_file, config=config).fetch_entity(
        entity_id
    )


async def get_license_document(
    auth_id: str | int,
    doc_id: str | int,
    *,
    token: str | None = None,
    env_file: str | Path | None = DEFAULT_ENV_FILE,
    config: FetcherConfig | None = None,
) -> LicenseDocument:
    """A licence document file (BOT served a PDF), e.g. ``get_license_document(55, 1)``."""
    service = LicenseCheckService(token=token, env_file=env_file, config=config)
    return await service.fetch_document(auth_id, doc_id)
