"""Typed exceptions for settfex.

Input-validation errors subclass :class:`ValueError` so existing ``except ValueError`` handlers
keep working; fetch/HTTP errors subclass :class:`Exception` and are still caught by
``except Exception``. All are therefore backward-compatible with pre-0.9 callers.

Example:
    >>> from settfex import get_highlight_data
    >>> from settfex.exceptions import SymbolNotFoundError
    >>> try:
    ...     await get_highlight_data("NOSUCH")
    ... except SymbolNotFoundError as exc:
    ...     print(exc.status_code, exc.symbol)
    404 NOSUCH
"""

from __future__ import annotations

from typing import NoReturn

__all__ = [
    "FetchError",
    "SymbolNotFoundError",
    "InvalidSymbolError",
    "InvalidLanguageError",
    "raise_for_status",
]


class FetchError(Exception):
    """A data fetch failed.

    ``status_code`` is the HTTP status for non-2xx responses, or ``None`` for transport-level
    failures (timeouts, connection errors, retries exhausted). ``symbol`` is the stock/index
    symbol involved, when known.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        symbol: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.symbol = symbol


class SymbolNotFoundError(FetchError):
    """A symbol or index was not found (HTTP 404)."""


class InvalidSymbolError(ValueError):
    """A symbol was empty or invalid."""


class InvalidLanguageError(ValueError):
    """A language string was not recognized (not ``en``/``th`` or an accepted alias)."""


def raise_for_status(status_code: int, message: str, *, symbol: str | None = None) -> NoReturn:
    """Raise :class:`SymbolNotFoundError` for HTTP 404, otherwise :class:`FetchError`.

    Args:
        status_code: The non-2xx HTTP status code from the response.
        message: The error message to attach.
        symbol: The stock/index symbol involved, when known.

    Raises:
        SymbolNotFoundError: If ``status_code`` is 404.
        FetchError: For any other non-2xx status.
    """
    if status_code == 404:
        raise SymbolNotFoundError(message, status_code=status_code, symbol=symbol)
    raise FetchError(message, status_code=status_code, symbol=symbol)
