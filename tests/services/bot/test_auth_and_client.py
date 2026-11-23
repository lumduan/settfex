"""Bank of Thailand tokens and the gateway client (1.0.0).

Each user gets one token per product from https://portal.api.bot.or.th. settfex reads it from the
argument, the product's variable, ``BANK_OF_THAILAND_TOKEN``, or a ``.env`` file, in that order.
It sends it only in the ``Authorization`` header, and never shows it in a repr or an error.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from settfex.exceptions import (
    BotAccessDeniedError,
    BotApiError,
    BotTokenMissingError,
    FetchError,
    HTTPStatusError,
    InvalidDateError,
)
from settfex.services.bot import BankOfThailand, BotClient, BotProduct, read_env_file
from settfex.services.bot.auth import resolve_bot_token
from settfex.services.bot.client import day_param, default_day_window, period_param
from settfex.utils.data_fetcher import AsyncDataFetcher, FetchResponse
from settfex.utils.parsing import ResponseParseError

SECRET = "s3cr3t-token-value"


def _response(
    body: Any, status: int = 200, content_type: str = "application/json"
) -> FetchResponse:
    text = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
    return FetchResponse(
        status_code=status,
        content=text.encode(),
        text=text,
        headers={"content-type": content_type},
        url="https://gateway.api.bot.or.th/x",
        elapsed=0.1,
    )


class TestTokenResolution:
    @pytest.fixture(autouse=True)
    def _clean(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("BANK_OF_THAILAND_TOKEN", raising=False)

    def test_the_argument_wins(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("BANK_OF_THAILAND_TOKEN_STATISTICS", "from-env")
        assert resolve_bot_token("statistics", " given ", env_file=tmp_path / "none") == "given"

    def test_the_products_own_variable_beats_the_fallback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("BANK_OF_THAILAND_TOKEN", "fallback")
        monkeypatch.setenv("BANK_OF_THAILAND_TOKEN_STATISTICS", "own")
        assert resolve_bot_token(BotProduct.STATISTICS, env_file=None) == "own"
        assert resolve_bot_token(BotProduct.OTHERS, env_file=None) == "fallback"

    def test_the_environment_beats_the_env_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        env = tmp_path / ".env"
        env.write_text("BANK_OF_THAILAND_TOKEN_OTHERS=from-file\n")
        monkeypatch.setenv("BANK_OF_THAILAND_TOKEN", "from-env")
        assert resolve_bot_token("others", env_file=env) == "from-env"

    def test_the_env_file_is_read_product_first(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        env.write_text(
            "# a comment\n\nexport BANK_OF_THAILAND_TOKEN='generic'\n"
            'BANK_OF_THAILAND_TOKEN_LICENSE_CHECK="license"\nBANK_OF_THAILAND_TOKEN_OTHERS=\n'
        )
        assert resolve_bot_token("license_check", env_file=env) == "license"
        assert resolve_bot_token("others", env_file=env) == "generic", "an empty value is no token"

    def test_no_token_anywhere_raises_before_any_request(self, tmp_path: Path) -> None:
        with pytest.raises(BotTokenMissingError) as excinfo:
            resolve_bot_token("interest_rates", env_file=tmp_path / "missing.env")
        exc = excinfo.value
        assert exc.env_keys == ("BANK_OF_THAILAND_TOKEN_INTEREST_RATES", "BANK_OF_THAILAND_TOKEN")
        assert "portal.api.bot.or.th/manual" in str(exc) and "Token Hash" in str(exc)
        assert isinstance(exc, ValueError) and not isinstance(exc, FetchError)

    def test_env_file_none_skips_the_file(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        env.write_text("BANK_OF_THAILAND_TOKEN=from-file\n")
        with pytest.raises(BotTokenMissingError):
            resolve_bot_token("statistics", env_file=None)

    def test_read_env_file(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        env.write_text("A=1\n  B = two words \nexport C='q'\n#D=x\nnoequals\n")
        assert read_env_file(env) == {"A": "1", "B": "two words", "C": "q"}
        assert read_env_file(tmp_path / "absent") == {}

    def test_every_product_has_its_own_variable(self) -> None:
        assert [p.env_key for p in BotProduct] == [
            "BANK_OF_THAILAND_TOKEN_INTEREST_RATES",
            "BANK_OF_THAILAND_TOKEN_STATISTICS",
            "BANK_OF_THAILAND_TOKEN_EXCHANGE_RATES",
            "BANK_OF_THAILAND_TOKEN_DEBT_SECURITIES_AUCTION",
            "BANK_OF_THAILAND_TOKEN_OTHERS",
            "BANK_OF_THAILAND_TOKEN_LICENSE_CHECK",
        ]


class TestTheClient:
    @pytest.mark.asyncio
    async def test_the_token_goes_in_the_authorization_header_only(self) -> None:
        seen: dict[str, Any] = {}

        async def fetch(
            self: Any, url: str, headers: dict[str, str] | None = None, **kw: Any
        ) -> FetchResponse:
            seen.update(url=url, headers=headers)
            return _response({"result": {"api": "x", "data": []}})

        with patch.object(AsyncDataFetcher, "fetch", fetch):
            client = BotClient("statistics", token=SECRET)
            await client.get_json("observations/", {"series_code": "A", "empty": ""})
        assert seen["headers"]["Authorization"] == SECRET
        assert SECRET not in seen["url"]
        assert seen["url"] == "https://gateway.api.bot.or.th/observations/?series_code=A"
        assert SECRET not in repr(client) and SECRET not in repr(
            BankOfThailand(tokens={"statistics": SECRET})
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status", [401, 403])
    async def test_a_refused_token_is_access_denied_and_names_the_variable(
        self, status: int
    ) -> None:
        body = {"error": "Access to this API has been disallowed"}
        with (
            patch.object(AsyncDataFetcher, "fetch", return_value=_response(body, status)),
            pytest.raises(BotAccessDeniedError) as excinfo,
        ):
            await BotClient("statistics", token=SECRET).get_json("observations/")
        exc = excinfo.value
        assert exc.status_code == status and exc.product == "statistics"
        assert "BANK_OF_THAILAND_TOKEN_STATISTICS" in str(exc) and "disallowed" in str(exc)
        assert SECRET not in str(exc)
        assert isinstance(exc, HTTPStatusError) and isinstance(exc, FetchError)

    @pytest.mark.asyncio
    async def test_a_404_carries_bots_own_words(self) -> None:
        body = {"Message": "No HTTP resource was found that matches the request URI '...'."}
        with (
            patch.object(AsyncDataFetcher, "fetch", return_value=_response(body, 404)),
            pytest.raises(HTTPStatusError) as excinfo,
        ):
            await BotClient("interest_rates").get_json("BIBOR/v2/bibor_avg_rate/")
        assert excinfo.value.status_code == 404 and "No HTTP resource" in str(excinfo.value)
        assert not isinstance(excinfo.value, BotAccessDeniedError)

    @pytest.mark.asyncio
    async def test_an_error_under_http_200_is_raised(self) -> None:
        body = {"result": {"success": "false", "api": "Bond Auction", "error": [
            {"code": "es001", "message": "Parameter: start_period must not be null"}]}}  # fmt: skip
        with (
            patch.object(AsyncDataFetcher, "fetch", return_value=_response(body)),
            pytest.raises(BotApiError) as excinfo,
        ):
            await BotClient("debt_securities_auction").get_json("BondAuction/bond_auction_v2/")
        assert excinfo.value.errors[0]["code"] == "es001"
        assert "start_period must not be null" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_a_body_that_is_not_json_is_a_parse_error(self) -> None:
        page = _response("<html>gateway error</html>", 200, "text/html")
        with (
            patch.object(AsyncDataFetcher, "fetch", return_value=page),
            pytest.raises(ResponseParseError),
        ):
            await BotClient("others").get_json("financial-institutions-holidays/")


class TestPeriods:
    def test_day_param(self) -> None:
        from datetime import date, datetime

        assert day_param(date(2026, 11, 20), "d") == "2026-11-20"
        assert day_param(datetime(2026, 11, 20, 9), "d") == "2026-11-20"
        assert day_param(" 2026-11-20 ", "d") == "2026-11-20"
        for bad in ("20/11/2026", "2026-02-30", "2026-11"):
            with pytest.raises(InvalidDateError):
                day_param(bad, "d")

    @pytest.mark.parametrize(
        ("value", "frequency", "expected"),
        [
            ("2026-10", "monthly", "2026-10"),
            ("2026-Q3", "quarterly", "2026-Q3"),
            (2025, "annual", "2025"),
        ],
    )
    def test_period_param(self, value: Any, frequency: str, expected: str) -> None:
        assert period_param(value, "p", frequency) == expected

    def test_period_param_from_a_date(self) -> None:
        from datetime import date

        assert period_param(date(2026, 8, 31), "p", "quarterly") == "2026-Q3"
        assert period_param(date(2026, 8, 31), "p", "monthly") == "2026-08"
        with pytest.raises(InvalidDateError):
            period_param("2026-13", "p", "monthly")

    def test_default_window(self) -> None:
        assert default_day_window("2026-11-20", None) == ("2026-11-20", "2026-11-20")
        assert default_day_window(None, "2026-11-20", days=7) == ("2026-11-13", "2026-11-20")
        start, end = default_day_window(None, None)
        assert start < end
