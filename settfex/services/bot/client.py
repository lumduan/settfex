"""The Bank of Thailand gateway client: one request, its token, and its errors (1.0.0).

The gateway is stateless (no cookies, no bot wall), so every call runs with ``use_session=False``,
like the other stateless hosts in settfex. The token travels only in the ``Authorization`` header:
it is resolved per request, never kept on the object, never logged and never put in a message.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from loguru import logger

from settfex.exceptions import (
    BotAccessDeniedError,
    BotApiError,
    HTTPStatusError,
    InvalidDateError,
)
from settfex.services.bot.auth import DEFAULT_ENV_FILE, resolve_bot_token
from settfex.services.bot.constants import BOT_GATEWAY_URL, BOT_MANUAL_URL, BotProduct
from settfex.utils.data_fetcher import AsyncDataFetcher, FetcherConfig, FetchResponse
from settfex.utils.parsing import decode_json

BANGKOK = ZoneInfo("Asia/Bangkok")

_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_QUARTER = re.compile(r"^\d{4}-Q[1-4]$")
_YEAR = re.compile(r"^\d{4}$")


def stateless_config(config: FetcherConfig | None) -> FetcherConfig:
    """The caller's fetcher settings, with the cookie session turned off (the host needs none)."""
    return (config or FetcherConfig()).model_copy(update={"use_session": False})


def day_param(value: date | datetime | str, name: str) -> str:
    """A ``YYYY-MM-DD`` period parameter, validated before any request."""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if _DAY.match(text):
        try:
            return date.fromisoformat(text).isoformat()
        except ValueError:
            pass
    raise InvalidDateError(f"Invalid {name} {value!r}: expected YYYY-MM-DD (e.g. '2026-11-20')")


def period_param(value: date | datetime | str | int, name: str, frequency: str) -> str:
    """A period for ``frequency``: ``YYYY-MM-DD``, ``YYYY-MM``, ``YYYY-QN`` or ``YYYY``."""
    if frequency == "daily":
        return day_param(value if not isinstance(value, int) else str(value), name)
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        if frequency == "monthly":
            return f"{value.year:04d}-{value.month:02d}"
        if frequency == "quarterly":
            return f"{value.year:04d}-Q{(value.month - 1) // 3 + 1}"
        return f"{value.year:04d}"
    text = str(value).strip()
    pattern, example = {
        "monthly": (_MONTH, "2026-10"),
        "quarterly": (_QUARTER, "2026-Q3"),
        "annual": (_YEAR, "2025"),
    }[frequency]
    if pattern.match(text):
        return text
    raise InvalidDateError(
        f"Invalid {name} {value!r} for {frequency} data: expected e.g. {example!r}"
    )


def default_day_window(
    start: date | datetime | str | None, end: date | datetime | str | None, *, days: int = 7
) -> tuple[str, str]:
    """``(start, end)`` as ``YYYY-MM-DD``.

    Both missing: the last ``days`` calendar days ending today in Asia/Bangkok. Only ``start``:
    that one day. Only ``end``: ``days`` days ending there.
    """
    if start is None and end is None:
        today = datetime.now(BANGKOK).date()
        return (today - timedelta(days=days)).isoformat(), today.isoformat()
    if start is None:
        end_text = day_param(end, "end_date")  # type: ignore[arg-type]
        return (date.fromisoformat(end_text) - timedelta(days=days)).isoformat(), end_text
    start_text = day_param(start, "start_date")
    return start_text, (day_param(end, "end_date") if end is not None else start_text)


class BotClient:
    """GET one BOT product's endpoints with that product's token.

    Args:
        product: Which product's token to send.
        token: The token itself. Usually left out: it is then read from the environment or
            ``.env`` (see :func:`~settfex.services.bot.auth.resolve_bot_token`).
        env_file: The ``.env`` file to read; ``None`` skips it.
        config: Fetcher settings (timeout, retries). The cookie session is always off.
    """

    def __init__(
        self,
        product: BotProduct | str,
        *,
        token: str | None = None,
        env_file: str | Path | None = DEFAULT_ENV_FILE,
        config: FetcherConfig | None = None,
    ) -> None:
        self.product = BotProduct(product)
        self._token = token
        self.env_file = env_file
        self.config = stateless_config(config)

    def __repr__(self) -> str:  # never show the token
        return f"BotClient(product={self.product.value!r})"

    def _headers(self) -> dict[str, str]:
        token = resolve_bot_token(self.product, self._token, env_file=self.env_file)
        return {"Authorization": token, "Accept": "application/json"}

    def _url(self, path: str, params: dict[str, str] | None) -> str:
        query = {k: v for k, v in (params or {}).items() if v not in (None, "")}
        url = f"{BOT_GATEWAY_URL}/{path.lstrip('/')}"
        return f"{url}?{urlencode(query)}" if query else url

    async def get(
        self, path: str, params: dict[str, str] | None = None, *, decode_text: bool = True
    ) -> FetchResponse:
        """One GET, with the status checked. Returns the response for a 2xx.

        Raises:
            BotTokenMissingError: No token was found (before any request).
            BotAccessDeniedError: HTTP 401/403: the token is not valid for this product.
            HTTPStatusError: Any other non-2xx status. BOT answers a missing required period with
                HTTP 404 "No HTTP resource was found", so the message carries BOT's own words.
        """
        headers = self._headers()
        url = self._url(path, params)
        async with AsyncDataFetcher(config=self.config) as fetcher:
            response = await fetcher.fetch(url, headers=headers, decode_text=decode_text)
        status = response.status_code
        if status in (401, 403):
            raise BotAccessDeniedError(
                f"Bank of Thailand refused the token for '{self.product.value}' (HTTP {status}): "
                f"{_api_message(response)}. Each token works for ONE product: check that "
                f"{self.product.env_key} holds this product's 'Token' (not 'Token Hash'), and "
                f"that your portal app subscribes to it ({BOT_MANUAL_URL}).",
                status_code=status,
                url=url,
                product=self.product.value,
            )
        if not 200 <= status < 300:
            raise HTTPStatusError(
                f"Bank of Thailand {self.product.value} /{path.strip('/')}: HTTP {status}: "
                f"{_api_message(response)}",
                status_code=status,
                url=url,
            )
        logger.debug(f"BOT {self.product.value} /{path.strip('/')} -> HTTP {status}")
        return response

    async def get_json(self, path: str, params: dict[str, str] | None = None) -> Any:
        """One GET, decoded as JSON, with BOT's in-band errors raised.

        Raises:
            BotApiError: HTTP 200 whose ``result`` says ``success: "false"`` or carries errors.
            ResponseParseError: The body is not JSON.
            (and everything :meth:`get` raises)
        """
        response = await self.get(path, params)
        data = decode_json(response.text, context=f"BOT {self.product.value} /{path.strip('/')}")
        result = data.get("result") if isinstance(data, dict) else None
        if isinstance(result, dict):
            errors = result.get("error")
            failed = str(result.get("success", "")).strip().lower() == "false"
            if failed or (isinstance(errors, list) and errors):
                entries = [e for e in (errors or []) if isinstance(e, dict)]
                detail = "; ".join(str(e.get("message", e)) for e in entries) or "no detail"
                raise BotApiError(
                    f"Bank of Thailand {self.product.value} /{path.strip('/')} reported an error "
                    f"under HTTP 200: {detail}",
                    errors=entries,
                )
        return data

    async def fetch_raw(self, path: str, params: dict[str, str] | None = None) -> Any:
        """The decoded JSON of any endpoint of this product: the raw escape hatch."""
        return await self.get_json(path, params)


def _api_message(response: FetchResponse) -> str:
    """BOT's own error text from a body (``error`` / ``Message``), or a short snippet."""
    text = response.text or ""
    try:
        body = decode_json(text, context="BOT error body")
    except Exception:  # noqa: BLE001 - an error body that is not JSON is still worth showing
        body = None
    if isinstance(body, dict):
        for key in ("error", "Message", "message"):
            if body.get(key):
                return str(body[key])
    snippet = " ".join(text.split())[:160]
    return snippet or "(empty body)"


def result_of(data: Any, context: str) -> dict[str, Any]:
    """The ``result`` object most BOT responses wrap their data in."""
    from settfex.utils.parsing import ResponseParseError

    result = data.get("result") if isinstance(data, dict) else None
    if not isinstance(result, dict):
        raise ResponseParseError(f"{context}: expected a JSON object with 'result'")
    return result
