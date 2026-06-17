"""Tests for the shared JSON-decode + Pydantic-validation helpers."""

import json

import pytest
from pydantic import BaseModel, ValidationError

from settfex.utils.parsing import (
    ResponseParseError,
    decode_json,
    validate_list_or_raise,
    validate_or_raise,
)


class _Rec(BaseModel):
    """Representative model: a required string + a required int."""

    symbol: str
    level: int


class TestDecodeJson:
    """Tests for decode_json."""

    def test_valid_object(self) -> None:
        assert decode_json('{"a": 1, "b": "x"}', context="ctx") == {"a": 1, "b": "x"}

    def test_valid_array(self) -> None:
        assert decode_json("[1, 2, 3]", context="ctx") == [1, 2, 3]

    def test_finite_floats_preserved(self) -> None:
        # Guard must not disturb ordinary finite numbers.
        assert decode_json('{"pe": 12.5, "neg": -3.0}', context="ctx") == {"pe": 12.5, "neg": -3.0}

    def test_malformed_json_raises_with_context(self) -> None:
        with pytest.raises(ResponseParseError, match="CPALL"):
            decode_json("{not valid json", context="CPALL (highlight)")

    def test_malformed_json_is_valueerror(self) -> None:
        # Stays compatible with the documented `Raises: ValueError` contract.
        with pytest.raises(ValueError):
            decode_json("<<<", context="ctx")

    @pytest.mark.parametrize("payload", ['{"pe": NaN}', '{"x": Infinity}', '{"x": -Infinity}'])
    def test_nonfinite_rejected(self, payload: str) -> None:
        # The silent-corruption vector: default json.loads would accept these.
        with pytest.raises(ResponseParseError):
            decode_json(payload, context="PTT (trading-stat)")

    def test_nan_accepted_by_default_json_but_rejected_here(self) -> None:
        # Document the exact behavior we are hardening against.
        assert json.loads('{"pe": NaN}')["pe"] != json.loads('{"pe": NaN}')["pe"]  # nan != nan
        with pytest.raises(ResponseParseError):
            decode_json('{"pe": NaN}', context="ctx")

    def test_original_exception_chained(self) -> None:
        try:
            decode_json("{bad", context="ctx")
        except ResponseParseError as exc:
            assert exc.__cause__ is not None
        else:  # pragma: no cover - guard
            pytest.fail("expected ResponseParseError")


class TestValidateOrRaise:
    """Tests for validate_or_raise."""

    def test_valid(self) -> None:
        rec = validate_or_raise(_Rec, {"symbol": "CPALL", "level": -1}, context="ctx")
        assert isinstance(rec, _Rec)
        assert rec.symbol == "CPALL"
        assert rec.level == -1

    def test_missing_field_raises_validationerror(self) -> None:
        # Original ValidationError type is preserved (not wrapped).
        with pytest.raises(ValidationError):
            validate_or_raise(_Rec, {"symbol": "CPALL"}, context="CPALL (profile)")

    def test_wrong_type_raises_validationerror(self) -> None:
        with pytest.raises(ValidationError):
            validate_or_raise(_Rec, {"symbol": "CPALL", "level": "not-an-int"}, context="ctx")


class TestValidateListOrRaise:
    """Tests for validate_list_or_raise."""

    def test_valid_list(self) -> None:
        out = validate_list_or_raise(
            _Rec,
            [{"symbol": "A", "level": 1}, {"symbol": "B", "level": 2}],
            context="ctx",
        )
        assert [r.symbol for r in out] == ["A", "B"]

    def test_empty_list(self) -> None:
        assert validate_list_or_raise(_Rec, [], context="ctx") == []

    def test_non_list_raises_response_parse_error(self) -> None:
        with pytest.raises(ResponseParseError, match="got dict"):
            validate_list_or_raise(_Rec, {"symbol": "A", "level": 1}, context="CPALL (financial)")

    def test_none_raises_response_parse_error(self) -> None:
        with pytest.raises(ResponseParseError, match="got NoneType"):
            validate_list_or_raise(_Rec, None, context="ctx")

    def test_bad_item_raises_validationerror(self) -> None:
        with pytest.raises(ValidationError):
            validate_list_or_raise(
                _Rec,
                [{"symbol": "A", "level": 1}, {"symbol": "B"}],  # second item missing level
                context="ctx",
            )
