"""Context-rich JSON decoding and Pydantic validation for SET/TFEX API responses.

These helpers centralize the *decode -> validate* step shared by every service so that
malformed financial data fails **loudly** with the originating symbol/endpoint context
instead of surfacing as a bare, context-free ``ValidationError`` or ``AssertionError``.

Hardening guarantees:

- ``NaN`` / ``Infinity`` / ``-Infinity`` JSON literals are **rejected**. Python's default
  ``json.loads`` accepts them, which would let a non-finite price, P/E, or margin flow
  silently into a model -- the primary silent-corruption vector for a financial library.
- Decode and structural-validation failures are re-raised with the ``symbol``/``endpoint``
  context that produced them, so logs and tracebacks are actionable.
- Untrusted payloads always go through **full** Pydantic validation
  (``model_validate``); no ``model_construct`` / validation bypass is used.
"""

import json
import re
from typing import Any, TypeVar

from loguru import logger
from pydantic import BaseModel, ValidationError

from settfex.exceptions import ParseError

__all__ = [
    "BlockedError",
    "ResponseParseError",
    "decode_json",
    "looks_like_block_page",
    "validate_list_or_raise",
    "validate_or_raise",
]

ModelT = TypeVar("ModelT", bound=BaseModel)


class ResponseParseError(ParseError, ValueError):
    """Raised when an API response cannot be decoded or fails structural validation.

    **Both** a :class:`~settfex.exceptions.ParseError` and a :class:`ValueError`, deliberately.

    It began as a plain ``ValueError`` to match the service layer's documented
    ``Raises: ValueError`` contract. That was right about compatibility and wrong about reach: it
    is the exception a malformed or non-JSON response body actually produces — the single most
    common real failure — and as a bare ``ValueError`` it escaped ``except FetchError``, the
    handler every service documents. The library therefore had two unrelated "parse error" types,
    and the one that fires most often was outside the family. A fault-injection sweep put a number
    on it: 49 of 165 injected-fault cells raised something no documented handler catches.

    Adding :class:`~settfex.exceptions.ParseError` as a base is purely additive — nothing is
    removed from the MRO, so ``except ValueError`` keeps working exactly as before, and
    ``except FetchError`` / ``except ParseError`` now work too.
    """


class BlockedError(ResponseParseError):
    """The server's bot protection refused the request and answered with a block page.

    **Stop and back off. Do not retry** — every further request, and fast retries most of all,
    deepens the block. On 2026-09-20 a sweep drew one from ``market.sec.or.th`` that answered every
    request for about an hour.

    Until 0.25.0 a block page surfaced as ``ResponseParseError``: the right family and the wrong
    diagnosis, which invited exactly the retry that makes it worse. Worse still, the SEC download
    path accepted it as a *file* — the page carries no ``Content-Type`` — so ``download_all`` saved
    the block page under the filing's filename.

    **Why a ResponseParseError subclass:** every handler that caught a block page before 0.25.0
    (``except ResponseParseError``, ``except ParseError``, ``except FetchError``,
    ``except ValueError``) still catches it, and ``except BlockedError`` can now tell it apart.
    Because it is also a ``ValueError``, **catch ``BlockedError`` before ``ValueError``** if you
    treat ``ValueError`` as "bad input".

    Attributes:
        url: The URL that was refused.
        status_code: The HTTP status the block page arrived with (200 in every observation).
        content_type: The ``Content-Type`` header, or ``None`` — the observed page had none.
        headers: The response headers, minus ``Set-Cookie``.
        body: The block page itself, with its per-incident support ID screened. Kept so the next
            block observed in the wild yields a byte-exact fixture; it is never part of
            ``str(exc)``.

    Only the BIG-IP ASM page observed on SEC is recognised (see :func:`looks_like_block_page`).
    No SET/Incapsula block page has been captured, so none is classified.
    """

    def __init__(
        self,
        message: str,
        *,
        url: str | None = None,
        status_code: int | None = None,
        content_type: str | None = None,
        headers: dict[str, str] | None = None,
        body: bytes = b"",
    ) -> None:
        super().__init__(message, url=url)
        self.status_code = status_code
        self.content_type = content_type
        self.headers = dict(headers or {})
        self.body = body


#: A block page is small: the one observed was 242 bytes. The cap keeps the check off real
#: documents entirely — a multi-megabyte PDF is never scanned.
_MAX_BLOCK_PAGE_BYTES = 8192

# The two stable markers of F5 BIG-IP ASM's default block page, as observed on market.sec.or.th on
# 2026-09-20. Both are vendor boilerplate, not per-request content. Case-insensitive and
# whitespace-tolerant on purpose: the only capture normalised newlines to spaces, so the page's
# exact whitespace was never byte-verified. BOTH must match — either alone is ordinary prose.
_BLOCK_TITLE = re.compile(rb"<title>\s*request\s+rejected\s*</title>", re.IGNORECASE)
_BLOCK_SUPPORT_ID = re.compile(rb"your\s+support\s+id\s+is\s*:", re.IGNORECASE)
_SUPPORT_ID_VALUE = re.compile(rb"(your\s+support\s+id\s+is\s*:\s*)[0-9A-Za-z-]+", re.IGNORECASE)


def looks_like_block_page(content: bytes) -> bool:
    """Is this body the BIG-IP ASM block page? Needs both markers, and a small body."""
    if len(content) > _MAX_BLOCK_PAGE_BYTES:
        return False
    return bool(_BLOCK_TITLE.search(content)) and bool(_BLOCK_SUPPORT_ID.search(content))


def _screen_support_id(content: bytes) -> bytes:
    """Replace the per-incident support ID, which identifies one request from one client."""
    return _SUPPORT_ID_VALUE.sub(rb"\1<SCREENED>", content)


def _reject_nonfinite(token: str) -> float:
    """``json.loads`` ``parse_constant`` hook: reject NaN/Infinity rather than accept them."""
    raise ValueError(f"non-finite JSON constant {token!r} is not valid in financial data")


def decode_json(text: str, *, context: str) -> Any:
    """Decode a JSON response body, rejecting non-finite numbers, with error context.

    Args:
        text: Raw response body.
        context: Human-readable origin used in any raised error/log line, e.g.
            ``"CPALL (balance_sheet)"`` or the request URL.

    Returns:
        The decoded JSON value (``dict``, ``list``, or primitive).

    Raises:
        ResponseParseError: If the body is not valid JSON, or contains a
            ``NaN``/``Infinity``/``-Infinity`` literal.
    """
    try:
        # parse_constant fires only for NaN/Infinity/-Infinity tokens, so it adds no
        # measurable overhead on well-formed numeric payloads.
        return json.loads(text, parse_constant=_reject_nonfinite)
    except ValueError as exc:  # JSONDecodeError and the parse_constant guard are ValueErrors
        logger.error(f"Failed to decode JSON response for {context}: {exc}")
        logger.debug(f"Undecodable response body for {context} (first 500 chars): {text[:500]}")
        raise ResponseParseError(f"Failed to decode JSON response for {context}: {exc}") from exc


def validate_or_raise(model_cls: type[ModelT], data: Any, *, context: str) -> ModelT:
    """Validate ``data`` into ``model_cls``, logging symbol/endpoint context on failure.

    The ``pydantic.ValidationError`` is wrapped in a :class:`ResponseParseError` (which is a
    ``ParseError``, a ``FetchError`` and a ``ValueError``) and chained as ``__cause__``, so a
    malformed response is catchable with the same ``except FetchError`` every service documents.
    Until 0.24.0 it was re-raised unchanged, which kept ``except ValidationError`` working but put
    the library's most common real failure outside the documented handler.

    Args:
        model_cls: Target Pydantic model.
        data: Decoded payload to validate.
        context: Human-readable origin (symbol/endpoint) for the log line.

    Returns:
        A validated ``model_cls`` instance.

    Raises:
        ResponseParseError: If ``data`` does not satisfy the model. It is both a
            :class:`~settfex.exceptions.ParseError` and a :class:`ValueError`, and it chains the
            original ``pydantic.ValidationError`` as ``__cause__``.
    """
    try:
        return model_cls.model_validate(data)
    except ValidationError as exc:
        # Wrapped rather than re-raised. A response that arrives intact and does not match the
        # model is a PARSE failure, and callers are told to handle those with `except FetchError`
        # -- a bare pydantic ValidationError escapes that, and says "validation failed" for what is
        # usually a 200 carrying an error page. The original is chained, so the field-level detail
        # is one `__cause__` away and `except ValidationError` on the cause still works.
        #
        # This is RESPONSE validation only. User input keeps its own contract: InvalidSymbolError /
        # InvalidDateError / InvalidLanguageError, and a user-built FetcherConfig still raises
        # pydantic's ValidationError, because none of those pass through here.
        message = f"Validation failed for {context} ({model_cls.__name__})"
        logger.error(message)
        raise ResponseParseError(f"{message}: {exc}") from exc


def validate_list_or_raise(model_cls: type[ModelT], data: Any, *, context: str) -> list[ModelT]:
    """Validate a JSON array into a list of ``model_cls`` instances, with per-item context.

    Args:
        model_cls: Target Pydantic model for each element.
        data: Decoded payload expected to be a ``list``.
        context: Human-readable origin (symbol/endpoint) for any log line.

    Returns:
        A list of validated ``model_cls`` instances (empty if ``data`` is an empty list).

    Raises:
        ResponseParseError: If ``data`` is not a list.
        ResponseParseError: If ``data`` is not an array, or any element fails validation
            (logged with its index; the pydantic error is chained as ``__cause__``).
    """
    if not isinstance(data, list):
        raise ResponseParseError(f"Expected a JSON array for {context}, got {type(data).__name__}")
    validated: list[ModelT] = []
    for index, item in enumerate(data):
        try:
            validated.append(model_cls.model_validate(item))
        except ValidationError as exc:
            # Same reasoning as validate_or_raise: a response that does not match the model is a
            # parse failure, and belongs in the family callers are told to catch.
            message = (
                f"Validation failed for {context} ({model_cls.__name__}) at item index {index}"
            )
            logger.error(message)
            raise ResponseParseError(f"{message}: {exc}") from exc
    return validated
