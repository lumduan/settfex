"""``NotFoundError`` — one catch for "that name does not exist", added without moving anything.

Before 0.25.0 the two "not found" errors lived in different families: ``SymbolNotFoundError`` is a
``FetchError`` (SET answering 404) and ``CompanyNotFoundError`` is a ``ValueError`` (the SEC search
answering honestly). A retry handler written as ``except FetchError`` therefore retried a SET typo
forever while never seeing the SEC one.

The fix is additive on purpose, and these tests pin both halves of that: the new base catches
both, AND neither class left its old family — because moving ``SymbolNotFoundError`` out of
``FetchError`` would break every existing handler that relies on catching it, which the
deprecation policy forbids without a warning period (tracked on #135 as a 1.0 decision).
"""

from __future__ import annotations

import pytest

import settfex
import settfex.exceptions as exceptions_module
from settfex.exceptions import (
    CompanyNotFoundError,
    FetchError,
    NotFoundError,
    SymbolNotFoundError,
)


class TestTheCommonCatch:
    @pytest.mark.parametrize(
        "exc",
        [
            SymbolNotFoundError("no such symbol", status_code=404, symbol="CPALLL"),
            CompanyNotFoundError("no such issuer"),
        ],
        ids=["set-symbol", "sec-company"],
    )
    def test_except_not_found_catches_both(self, exc: Exception) -> None:
        with pytest.raises(NotFoundError):
            raise exc

    def test_it_is_exported_where_the_other_exceptions_are(self) -> None:
        assert settfex.NotFoundError is NotFoundError
        assert "NotFoundError" in settfex.__all__
        assert "NotFoundError" in exceptions_module.__all__


class TestNeitherClassMovedFamily:
    """The additive half. Each assertion here is one existing handler that must keep working."""

    def test_a_set_404_is_still_a_fetch_error(self) -> None:
        assert issubclass(SymbolNotFoundError, FetchError)
        assert not issubclass(SymbolNotFoundError, ValueError)

    def test_an_sec_miss_is_still_an_input_error_not_a_fetch_error(self) -> None:
        assert issubclass(CompanyNotFoundError, ValueError)
        assert not issubclass(CompanyNotFoundError, FetchError), (
            "CompanyNotFoundError must stay out of the FetchError family, or retry handlers "
            "would start retrying a company name that does not exist"
        )

    def test_the_old_bases_come_first_in_the_mro(self) -> None:
        """The marker is appended, not inserted: existing bases keep their MRO precedence."""
        assert SymbolNotFoundError.__mro__[1:3] == (FetchError, NotFoundError)
        assert CompanyNotFoundError.__mro__[1:3] == (ValueError, NotFoundError)

    def test_the_marker_carries_no_behaviour(self) -> None:
        """A pure marker: no __init__ of its own, so it cannot change how either class builds."""
        assert "__init__" not in NotFoundError.__dict__
        exc = SymbolNotFoundError("x", status_code=404, symbol="AAA", suggestion="AAB")
        assert (exc.status_code, exc.symbol, exc.suggestion) == (404, "AAA", "AAB")
        assert str(exc) == "x — did you mean 'AAB'?"


class TestTheDocumentedHandlerOrder:
    """AGENTS.md tells callers to catch NotFoundError BEFORE FetchError; show why it matters."""

    @staticmethod
    def classify(exc: Exception) -> str:
        try:
            raise exc
        except NotFoundError:
            return "fix the input"
        except FetchError:
            return "maybe retry"

    def test_a_set_typo_is_not_retried(self) -> None:
        assert self.classify(SymbolNotFoundError("gone", status_code=404)) == "fix the input"

    def test_an_upstream_failure_still_is(self) -> None:
        assert self.classify(FetchError("boom", status_code=503)) == "maybe retry"
