"""The docs must name every exception the library raises — enforced, not remembered.

`AGENTS.md`'s exception list went **two releases stale**: it was written before `ParseError`,
`HTTPStatusError`, `IncompleteListingError` and `CompanyNotFoundError` existed and nothing noticed,
because nothing was checking. It is the file an agent reads to decide *what to catch*, so a missing
entry there is not cosmetic — it is a handler that never gets written.

This is the third direction of the documentation-currency discipline: not board → doc, not
doc → ticket, but **code → doc**, checked mechanically. A new exception now fails CI until the docs
name it.

Two directions, deliberately asymmetric:

* **Completeness** is required of `AGENTS.md` only, because that file carries an explicit list that
  claims to be exhaustive. `CLAUDE.md` mentions exceptions *incidentally*, inside gotchas, and
  forcing it to enumerate all of them would make the doc serve the test rather than the reader.
* **No phantoms** is required of both: every settfex-looking exception named in either file must
  actually exist, or be a declared exception to the rule with its reason recorded below.

The allowlist is itself verified, which is the part that keeps it from rotting: each entry states
*why* the name is not exported, and the test asserts that reason is still true. A "planned" entry
goes red the moment the name ships — which is how `BlockedError` left the list in 0.25.0.

"Exported" means `settfex.exceptions.__all__` **plus** `settfex.utils.parsing.__all__`: the two
parse-level exceptions (`ResponseParseError`, `BlockedError`) live beside the JSON decoder, because
`parsing` imports from `exceptions` and the reverse would be a cycle. Both are public, both are
documented, and both are held to the same completeness rule as the rest.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import settfex.exceptions as exceptions
import settfex.utils.parsing as parsing

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_MD = REPO_ROOT / "AGENTS.md"
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"

#: Anything spelled like an exception. Deliberately broad -- a name the docs invent is exactly
#: what the "no phantoms" direction exists to catch.
_EXCEPTION_NAME = re.compile(r"\b([A-Z][A-Za-z0-9]*(?:Error|Exception))\b")


#: The modules whose exported exception classes the docs must name. `__all__` also exports helper
#: functions; only the exception classes are documentable names.
_EXCEPTION_MODULES = (exceptions, parsing)


def _exported_exceptions() -> set[str]:
    return {
        name
        for module in _EXCEPTION_MODULES
        for name in module.__all__
        if isinstance(getattr(module, name, None), type)
        and issubclass(getattr(module, name), BaseException)
    }


#: Names the docs may mention that are NOT in `settfex.exceptions.__all__`, each with the reason
#: it is legitimate. Every entry is re-verified below, so a stale one fails rather than lingers.
_ALLOWED_ELSEWHERE: dict[str, str] = {
    # Python builtins, named when explaining which family something belongs to.
    "ValueError": "builtin",
    "TypeError": "builtin",
    "ImportError": "builtin",
    "OSError": "builtin",
    "AttributeError": "builtin",
    "Exception": "builtin",
    "BaseException": "builtin",
    "ValidationError": "pydantic",
    "JSONDecodeError": "stdlib json",
}


def _names_in(path: Path) -> set[str]:
    return set(_EXCEPTION_NAME.findall(path.read_text(encoding="utf-8")))


class TestAgentsMdListsEveryException:
    """`AGENTS.md` claims an exhaustive list, so it is held to one."""

    def test_every_exported_exception_is_named(self) -> None:
        documented = _names_in(AGENTS_MD)
        missing = sorted(_exported_exceptions() - documented)
        assert not missing, (
            f"AGENTS.md does not name {missing}. It is the file an agent reads to decide what to "
            f"catch, so an unnamed exception is a handler nobody writes. Add it to the import "
            f"block under '## Errors you should expect', on the correct side of the "
            f"fetch-family / input-error split."
        )

    def test_the_family_split_is_stated(self) -> None:
        """The split is the thing an agent must act on: a FetchError may be worth a retry.

        Pinned because losing this sentence would leave a correct list that still misleads.
        """
        text = AGENTS_MD.read_text(encoding="utf-8")
        assert "except FetchError" in text
        assert "ValueError" in text, "the input-error family must be named as such"


class TestNeitherDocInventsAnException:
    """A name in the docs that does not exist is a handler that can never fire."""

    @pytest.mark.parametrize("path", [AGENTS_MD, CLAUDE_MD], ids=["AGENTS.md", "CLAUDE.md"])
    def test_every_named_exception_exists_or_is_declared(self, path: Path) -> None:
        exported = _exported_exceptions()
        phantom = sorted(_names_in(path) - exported - set(_ALLOWED_ELSEWHERE))
        assert not phantom, (
            f"{path.name} names {phantom}, which are not in settfex.exceptions.__all__. Either the "
            f"name is wrong/renamed, or it belongs in _ALLOWED_ELSEWHERE in this module with the "
            f"reason recorded."
        )


class TestTheAllowlistIsItselfChecked:
    """An allowlist nobody verifies becomes a second place for drift to hide."""

    def test_no_entry_shadows_a_real_export(self) -> None:
        """If one of these ships for real, its entry must go -- this is what forces that."""
        shadowed = sorted(set(_ALLOWED_ELSEWHERE) & _exported_exceptions())
        assert not shadowed, (
            f"{shadowed} are now exported from settfex.exceptions, so their _ALLOWED_ELSEWHERE "
            f"entries are stale and must be removed."
        )

    def test_the_parse_level_exceptions_are_held_to_the_rule(self) -> None:
        """They used to be allowlisted; since 0.25.0 they are exported and must be documented."""
        assert {"ResponseParseError", "BlockedError"} <= _exported_exceptions()

    def test_planned_names_are_not_yet_real(self) -> None:
        """A planned name that ships turns this red -- which is the point of listing it.

        A "planned" entry is a promise with an expiry date. Without this the allowlist would
        quietly keep excusing a name that had since become real and undocumented. (It worked:
        `BlockedError` was planned here until it shipped in 0.25.0. No planned names remain.)
        """
        planned = [n for n, reason in _ALLOWED_ELSEWHERE.items() if reason == "planned"]
        for name in planned:
            assert not any(hasattr(module, name) for module in _EXCEPTION_MODULES), (
                f"{name} now exists. Remove its 'planned' entry from _ALLOWED_ELSEWHERE and add it "
                f"to AGENTS.md's exception list."
            )

    def test_the_builtin_entries_really_are_builtins(self) -> None:
        import builtins

        for name, reason in _ALLOWED_ELSEWHERE.items():
            if reason == "builtin":
                assert hasattr(builtins, name), f"{name} is not a builtin; fix its reason"
