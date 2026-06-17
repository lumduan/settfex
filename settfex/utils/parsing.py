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
from typing import Any, TypeVar

from loguru import logger
from pydantic import BaseModel, ValidationError

__all__ = [
    "ResponseParseError",
    "decode_json",
    "validate_list_or_raise",
    "validate_or_raise",
]

ModelT = TypeVar("ModelT", bound=BaseModel)


class ResponseParseError(ValueError):
    """Raised when an API response cannot be decoded or fails structural validation.

    Subclasses :class:`ValueError` to remain compatible with the service layer's
    documented ``Raises: ValueError`` contract while carrying actionable context
    (the symbol/endpoint that produced the bad payload).
    """


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

    The original :class:`pydantic.ValidationError` is re-raised unchanged so callers that
    catch it keep working; the actionable context is emitted to the error log.

    Args:
        model_cls: Target Pydantic model.
        data: Decoded payload to validate.
        context: Human-readable origin (symbol/endpoint) for the log line.

    Returns:
        A validated ``model_cls`` instance.

    Raises:
        pydantic.ValidationError: If ``data`` does not satisfy the model.
    """
    try:
        return model_cls.model_validate(data)
    except ValidationError:
        logger.error(f"Validation failed for {context} ({model_cls.__name__})")
        raise


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
        pydantic.ValidationError: If any element fails validation (logged with its index).
    """
    if not isinstance(data, list):
        raise ResponseParseError(f"Expected a JSON array for {context}, got {type(data).__name__}")
    validated: list[ModelT] = []
    for index, item in enumerate(data):
        try:
            validated.append(model_cls.model_validate(item))
        except ValidationError:
            logger.error(
                f"Validation failed for {context} ({model_cls.__name__}) at item index {index}"
            )
            raise
    return validated
