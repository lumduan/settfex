"""Tests for the AssetType classification enum and its StockProfile integration."""

from typing import Any

import pytest

from settfex.services.set.asset_type import SECURITY_TYPE_TO_ASSET_TYPE, AssetType
from settfex.services.set.stock.profile_stock import StockProfile


def _profile_payload(security_type: str = "S") -> dict[str, Any]:
    """Minimal but complete StockProfile payload (all keys present, nullable ones null)."""
    return {
        "symbol": "TEST",
        "name": "Test Security",
        "market": "SET",
        "industry": "",
        "industryName": "",
        "sector": "",
        "sectorName": "",
        "securityType": security_type,
        "securityTypeName": "Anything",
        "status": "Listed",
        "listedDate": None,
        "firstTradeDate": None,
        "lastTradeDate": None,
        "maturityDate": None,
        "fiscalYearEnd": None,
        "fiscalYearEndDisplay": None,
        "accountForm": None,
        "par": None,
        "currency": None,
        "listedShare": None,
        "ipo": None,
        "isinLocal": None,
        "isinForeign": None,
        "isinNVDR": None,
        "percentFreeFloat": None,
        "foreignLimitAsOf": None,
        "percentForeignRoom": None,
        "percentForeignLimit": None,
        "foreignAvailable": None,
        "underlying": None,
        "exercisePrice": None,
        "exerciseRatio": None,
        "reservedShare": None,
        "convertedShare": None,
        "lastExerciseDate": None,
        "issuedShare": None,
    }


class TestAssetTypeEnum:
    """StrEnum semantics and the securityType code mapping (live-probed 2026-08-03)."""

    def test_is_strenum_str_renders_bare_value(self) -> None:
        assert str(AssetType.DEPOSITARY_RECEIPT) == "dr"
        assert f"{AssetType.ETF}" == "etf"

    def test_equality_with_plain_string(self) -> None:
        # Widen to AssetType first — mypy's strict-equality otherwise flags the
        # Literal-member vs literal-str comparison even though StrEnum subclasses str.
        dr: AssetType = AssetType.DEPOSITARY_RECEIPT
        stock: AssetType = AssetType.STOCK
        dw: AssetType = AssetType.DERIVATIVE_WARRANT
        assert dr == "dr"
        assert stock == "stock"
        assert dw == "dw"

    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            ("S", AssetType.STOCK),
            ("F", AssetType.STOCK_FOREIGN),
            ("P", AssetType.PREFERRED_STOCK),
            ("Q", AssetType.PREFERRED_STOCK_FOREIGN),
            ("W", AssetType.WARRANT),
            ("V", AssetType.DERIVATIVE_WARRANT),
            ("L", AssetType.ETF),
            ("U", AssetType.UNIT_TRUST),
            ("X", AssetType.DEPOSITARY_RECEIPT),
        ],
    )
    def test_all_probed_codes_map(self, code: str, expected: AssetType) -> None:
        assert AssetType.from_security_type(code) is expected

    def test_code_is_case_and_whitespace_insensitive(self) -> None:
        assert AssetType.from_security_type(" x ") is AssetType.DEPOSITARY_RECEIPT
        assert AssetType.from_security_type("s") is AssetType.STOCK

    def test_unknown_code_maps_to_unknown(self) -> None:
        assert AssetType.from_security_type("Z") is AssetType.UNKNOWN
        assert AssetType.from_security_type("XYZ") is AssetType.UNKNOWN

    def test_none_and_empty_map_to_unknown(self) -> None:
        assert AssetType.from_security_type(None) is AssetType.UNKNOWN
        assert AssetType.from_security_type("") is AssetType.UNKNOWN

    def test_no_bond_member_documented_limitation(self) -> None:
        # Bonds do not appear in SET's stock APIs at all — deliberately no BOND member.
        assert "BOND" not in AssetType.__members__

    def test_mapping_covers_every_member_except_unknown(self) -> None:
        assert set(SECURITY_TYPE_TO_ASSET_TYPE.values()) == set(AssetType) - {AssetType.UNKNOWN}


class TestStockProfileAssetType:
    """The derived asset_type property on StockProfile."""

    def test_asset_type_property_dr(self) -> None:
        profile = StockProfile.model_validate(_profile_payload("X"))
        assert profile.asset_type is AssetType.DEPOSITARY_RECEIPT

    def test_asset_type_property_common_stock(self) -> None:
        profile = StockProfile.model_validate(_profile_payload("S"))
        assert profile.asset_type is AssetType.STOCK

    def test_asset_type_not_in_model_dump(self) -> None:
        # Plain @property, not a computed field — serialization output stays unchanged.
        profile = StockProfile.model_validate(_profile_payload("X"))
        assert "asset_type" not in profile.model_dump()
