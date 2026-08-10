"""Typed exceptions for settfex.

Input-validation errors subclass :class:`ValueError` so existing ``except ValueError`` handlers
keep working; fetch/HTTP errors subclass :class:`Exception` and are still caught by
``except Exception``. All are therefore backward-compatible with pre-0.9 callers.

Example:
    >>> from settfex import get_highlight_data
    >>> from settfex.exceptions import SymbolNotFoundError
    >>> try:
    ...     await get_highlight_data("CPALLL")
    ... except SymbolNotFoundError as exc:
    ...     print(exc.status_code, exc.symbol, exc.suggestion)
    404 CPALLL CPALL
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import NoReturn

__all__ = [
    "FetchError",
    "SymbolNotFoundError",
    "StaleDataError",
    "InvalidSymbolError",
    "InvalidLanguageError",
    "InvalidDateError",
    "raise_for_status",
]

# A pluggable, network-free provider mapping a not-found symbol to a close match from an
# already-available (cached) symbol list, or None. Registered by the SET stock-list service so
# this module stays a dependency-free leaf. The provider MUST NOT perform network I/O.
_symbol_suggester: Callable[[str], str | None] | None = None


def register_symbol_suggester(suggester: Callable[[str], str | None] | None) -> None:
    """Register (or clear, with ``None``) the callable used to compute a "did you mean?" suggestion.

    The provider is consulted by :func:`raise_for_status` when raising a
    :class:`SymbolNotFoundError`. It **must not** perform network I/O — it should only consult
    already-available data (e.g. a previously-fetched, in-memory symbol list) and return ``None``
    otherwise, so that a 404 never triggers an extra fetch.
    """
    global _symbol_suggester
    _symbol_suggester = suggester


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
    """A symbol or index was not found (HTTP 404).

    ``suggestion`` is a close match from the SET stock-symbol list when one is available — but only
    if that list was already fetched earlier this session (it is never fetched on demand); ``None``
    otherwise. When present, the suggestion is also appended to the error message.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        symbol: str | None = None,
        suggestion: str | None = None,
    ) -> None:
        self.suggestion = suggestion
        if suggestion:
            message = f"{message} — did you mean '{suggestion}'?"
        super().__init__(message, status_code=status_code, symbol=symbol)


class StaleDataError(FetchError):
    """An API answered HTTP 200 with data for a **different date** than was requested.

    ThaiBMA's yield-curve endpoint rolls back silently: a weekend, a Thai public holiday, or any
    **future** date all return the most recent curve on or before the request, with HTTP 200 and
    no signal of the substitution. Raised only when the caller opts in with ``on_rollback="raise"``
    — the default is to warn and set :attr:`~settfex.services.thaibma.YieldCurve.is_rolled_back`.

    Subclasses :class:`FetchError` because the input was valid and the *response* was not, so
    existing ``except FetchError`` handlers keep working.
    """

    def __init__(
        self,
        message: str,
        *,
        requested_date: date | None = None,
        as_of: date | None = None,
        rollback_days: int | None = None,
    ) -> None:
        super().__init__(message)
        self.requested_date = requested_date
        self.as_of = as_of
        self.rollback_days = rollback_days


class InvalidSymbolError(ValueError):
    """A symbol was empty or invalid."""


class InvalidLanguageError(ValueError):
    """A language string was not recognized (not ``en``/``th`` or an accepted alias)."""


class InvalidDateError(ValueError):
    """A date string was not in the format the target API accepts (dd/MM/yyyy for SET news)."""


def raise_for_status(
    status_code: int,
    message: str,
    *,
    symbol: str | None = None,
    suggest: bool = True,
) -> NoReturn:
    """Raise :class:`SymbolNotFoundError` for HTTP 404, otherwise :class:`FetchError`.

    Args:
        status_code: The non-2xx HTTP status code from the response.
        message: The error message to attach.
        symbol: The stock/index symbol involved, when known.
        suggest: Whether to attempt a network-free "did you mean?" suggestion for a 404 (default
            True). Pass ``False`` for non-stock lookups (e.g. index symbols) that should not be
            matched against the stock-symbol list.

    Raises:
        SymbolNotFoundError: If ``status_code`` is 404.
        FetchError: For any other non-2xx status.
    """
    if status_code == 404:
        suggestion = (
            _symbol_suggester(symbol)
            if (suggest and symbol and _symbol_suggester is not None)
            else None
        )
        raise SymbolNotFoundError(
            message, status_code=status_code, symbol=symbol, suggestion=suggestion
        )
    raise FetchError(message, status_code=status_code, symbol=symbol)
