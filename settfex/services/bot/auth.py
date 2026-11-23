"""Token resolution for the Bank of Thailand API (1.0.0).

A user registers at https://portal.api.bot.or.th and gets one token per product. settfex only
connects: it never stores a token, never logs one, and never puts one in an error message.
"""

from __future__ import annotations

import os
from pathlib import Path

from settfex.exceptions import BotTokenMissingError
from settfex.services.bot.constants import BOT_MANUAL_URL, BOT_TOKEN_ENV, BotProduct

#: Default ``.env`` location: the current working directory, as most tools expect.
DEFAULT_ENV_FILE = ".env"


def read_env_file(path: str | Path) -> dict[str, str]:
    """Read ``KEY=VALUE`` lines from a ``.env`` file. A missing file is an empty mapping.

    Deliberately small, so settfex needs no extra dependency: blank lines and ``#`` comments are
    skipped, an ``export`` prefix is allowed, and one pair of matching quotes around a value is
    removed. Nothing is expanded or interpolated.
    """
    file = Path(path)
    if not file.is_file():
        return {}
    values: dict[str, str] = {}
    for raw in file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def resolve_bot_token(
    product: BotProduct | str,
    token: str | None = None,
    *,
    env_file: str | Path | None = DEFAULT_ENV_FILE,
) -> str:
    """The token to send for ``product``.

    Order:
    1. ``token`` (the argument);
    2. the product's own environment variable;
    3. ``BANK_OF_THAILAND_TOKEN``;
    4. the same two names in ``env_file`` (``None`` skips the file).

    Raises:
        BotTokenMissingError: None of them holds a non-empty token.
    """
    product = BotProduct(product)
    if token and token.strip():
        return token.strip()
    keys = (product.env_key, BOT_TOKEN_ENV)
    for key in keys:
        value = os.environ.get(key, "").strip()
        if value:
            return value
    file_values = read_env_file(env_file) if env_file is not None else {}
    for key in keys:
        value = file_values.get(key, "").strip()
        if value:
            return value
    where = f" or in {env_file}" if env_file is not None else ""
    raise BotTokenMissingError(
        f"No Bank of Thailand API token for '{product.value}'. Pass token=..., or set "
        f"{keys[0]} (or {keys[1]}) in the environment{where}. Tokens are free from "
        f"{BOT_MANUAL_URL}: one per product, copy the 'Token' field (not 'Token Hash').",
        product=product.value,
        env_keys=keys,
    )
