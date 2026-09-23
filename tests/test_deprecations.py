"""The deprecation registry is enforced, not remembered — see ``settfex/deprecations.py``.

Four properties, each of which a deprecation period depends on:

1. **Every registered deprecation actually warns.** A registry entry with no warning behind it is
   a promise nobody keeps; :data:`TRIGGERS` maps each entry to the call that must emit it.
2. **There is no other way to warn.** ``warn_deprecated`` is the only ``warnings.warn`` in the
   package, so a deprecation cannot exist outside the registry — and therefore outside the golden.
3. **Entries expire.** Once the installed version reaches ``changes_in``, the promised release has
   arrived and the entry must go (the change ships) or be re-dated on purpose.
4. **The warning names the caller's line.** Otherwise ``-W error`` and pytest's summary point into
   settfex, where the reader can do nothing.
"""

from __future__ import annotations

import ast
import warnings
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest
from packaging.version import Version

import settfex
import settfex.deprecations as deprecations
from settfex.deprecations import DEPRECATIONS, Deprecation, warn_deprecated

PACKAGE_ROOT = Path(settfex.__file__).resolve().parent


#: One trigger per registered deprecation: an async callable that performs the deprecated action
#: with the network faked, and must emit that entry's warning. Keyed by deprecation id.
TRIGGERS: dict[str, Callable[[], Awaitable[Any]]] = {}


class TestTheRegistryIsComplete:
    def test_every_entry_has_a_trigger(self) -> None:
        registered = {d.id for d in DEPRECATIONS}
        assert registered == set(TRIGGERS), (
            f"registry and triggers disagree — registered only: {registered - set(TRIGGERS)}, "
            f"triggered only: {set(TRIGGERS) - registered}"
        )

    def test_ids_are_unique(self) -> None:
        ids = [d.id for d in DEPRECATIONS]
        assert len(ids) == len(set(ids))

    @pytest.mark.parametrize("entry", DEPRECATIONS, ids=lambda d: d.id)
    @pytest.mark.asyncio
    async def test_each_entry_warns(self, entry: Deprecation) -> None:
        with pytest.warns(DeprecationWarning, match=f"settfex deprecation '{entry.id}'"):
            await TRIGGERS[entry.id]()

    @pytest.mark.parametrize("entry", DEPRECATIONS, ids=lambda d: d.id)
    def test_each_entry_is_inside_its_window(self, entry: Deprecation) -> None:
        installed = Version(settfex.__version__)
        assert Version(entry.since) <= installed, f"{entry.id} claims to warn since {entry.since}"
        assert installed < Version(entry.changes_in), (
            f"{entry.id} promised its change for {entry.changes_in}, and this is "
            f"{installed}: ship the change and remove the entry, or re-date it deliberately"
        )


def _warn_calls(path: Path) -> list[int]:
    """Line numbers of ``warnings.warn(...)`` / ``warn(...)`` calls in one source file."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    lines = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (isinstance(func, ast.Attribute) and func.attr == "warn") or (
            isinstance(func, ast.Name) and func.id == "warn"
        ):
            lines.append(node.lineno)
    return lines


class TestThereIsNoOtherWayToWarn:
    def test_warn_deprecated_is_the_only_warnings_warn(self) -> None:
        offenders = {
            str(path.relative_to(PACKAGE_ROOT.parent)): lines
            for path in sorted(PACKAGE_ROOT.rglob("*.py"))
            if path.name != "deprecations.py" and (lines := _warn_calls(path))
        }
        assert not offenders, (
            f"warnings.warn outside settfex/deprecations.py: {offenders}. Register the "
            f"deprecation in DEPRECATIONS and call warn_deprecated(), so the golden records it."
        )

    def test_the_scan_can_see_a_warn_call(self) -> None:
        """Guard the guard: the scanner must find the one legitimate call."""
        assert _warn_calls(PACKAGE_ROOT / "deprecations.py"), "the AST scan found no warn() call"


@pytest.fixture
def registered(monkeypatch: pytest.MonkeyPatch) -> Deprecation:
    """A throwaway registry entry, so the mechanics are tested even while the registry is empty."""
    entry = Deprecation(
        id="test-entry",
        what="Calling the thing is deprecated.",
        replacement="Call the other thing.",
        since="0.25.0",
        changes_in="0.26.0",
    )
    monkeypatch.setitem(deprecations._BY_ID, entry.id, entry)
    return entry


class TestTheWarningItself:
    def test_the_message_names_the_change_the_release_and_the_replacement(
        self, registered: Deprecation
    ) -> None:
        text = registered.message()
        for fragment in ("Calling the thing", "settfex 0.26.0", "Call the other thing", "0.25.0"):
            assert fragment in text

    def test_an_unknown_id_is_a_bug_not_a_silent_no_op(self) -> None:
        with pytest.raises(KeyError):
            warn_deprecated("no-such-deprecation")

    def test_it_is_attributed_to_the_direct_caller(self, registered: Deprecation) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            warn_deprecated(registered.id)
        assert caught and caught[0].filename == __file__

    @pytest.mark.parametrize("depth", [1, 3], ids=["one-settfex-frame", "three-settfex-frames"])
    def test_it_skips_settfex_frames_at_any_depth(
        self, registered: Deprecation, depth: int
    ) -> None:
        """The same deprecation is reached through a service, a get_*() wrapper or a facade."""
        namespace: dict[str, Any] = {"__name__": "settfex.fake", "warn_deprecated": warn_deprecated}
        source = "def level0():\n    warn_deprecated('test-entry')\n"
        for i in range(1, depth):
            source += f"def level{i}():\n    level{i - 1}()\n"
        exec(compile(source, "settfex/fake.py", "exec"), namespace)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            namespace[f"level{depth - 1}"]()
        assert caught and caught[0].filename == __file__, (
            f"warning attributed to {caught[0].filename if caught else None}, not the caller"
        )
