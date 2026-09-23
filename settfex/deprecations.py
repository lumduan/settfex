"""Every ``DeprecationWarning`` settfex emits, declared in one place.

The deprecation policy (CLAUDE.md, "Deprecation policy") says a change to the public contract warns
for at least one full minor release first, naming the replacement and the release it changes in.
This registry is what makes that policy checkable instead of remembered:

* **The golden pins it.** ``tests/golden/api_surface.json`` carries a top-level ``deprecations``
  list built from :data:`DEPRECATIONS`, so *removing* a warning — the step that silently skips the
  deprecation period — is a golden diff someone has to review.
* **Each entry is proven to fire.** ``tests/test_deprecations.py`` triggers every entry and
  asserts the warning, and fails if settfex calls :func:`warnings.warn` anywhere but
  :func:`warn_deprecated`.
* **Each entry expires.** The same test fails once the installed version reaches an entry's
  ``changes_in`` — the release that was promised has come, so either the change ships or the
  entry is re-dated on purpose.

The warning is attributed to **your** line, not settfex's: the stack is walked to the first frame
outside the ``settfex`` package, so ``-W error::DeprecationWarning`` and pytest's warning summary
both point at the call you need to change.
"""

from __future__ import annotations

import sys
import warnings
from types import FrameType

from pydantic import BaseModel, ConfigDict

__all__ = ["DEPRECATIONS", "Deprecation", "warn_deprecated"]


class Deprecation(BaseModel):
    """One announced change to the public contract."""

    model_config = ConfigDict(frozen=True)

    id: str
    """Stable identifier, used by :func:`warn_deprecated` and the tests."""
    what: str
    """The current behaviour that is going to change, in one sentence."""
    replacement: str
    """What a caller should do instead, today."""
    since: str
    """The first release that emits the warning."""
    changes_in: str
    """The release that makes the change."""

    def message(self) -> str:
        return (
            f"{self.what} This changes in settfex {self.changes_in}. {self.replacement} "
            f"[settfex deprecation {self.id!r}, since {self.since}]"
        )


#: The registry. An entry is added in the release that starts warning, and removed in the
#: release that makes the change — never before, and never silently.
DEPRECATIONS: tuple[Deprecation, ...] = ()

_BY_ID: dict[str, Deprecation] = {d.id: d for d in DEPRECATIONS}


def _first_frame_outside_settfex() -> int:
    """The ``stacklevel`` of the nearest caller that is not settfex's own code.

    Counted from :func:`warn_deprecated`'s call to :func:`warnings.warn`: level 1 is
    ``warn_deprecated`` itself, level 2 its caller, and so on. Python 3.11 has no
    ``skip_file_prefixes``, and the same deprecation is reached at different depths (a service
    method, a module-level ``get_*()`` wrapper, the ``Stock`` facade), so a fixed number would
    blame settfex for some of them.
    """
    frame: FrameType | None = sys._getframe(2)  # the caller of warn_deprecated
    level = 2
    while frame is not None:
        module = frame.f_globals.get("__name__", "")
        if module != "settfex" and not module.startswith("settfex."):
            return level
        frame = frame.f_back
        level += 1
    return 2


def warn_deprecated(deprecation_id: str) -> None:
    """Emit the registered warning for ``deprecation_id``.

    The only :func:`warnings.warn` call in settfex. An unknown id is a settfex bug and raises
    ``KeyError`` rather than emitting nothing.
    """
    entry = _BY_ID[deprecation_id]
    warnings.warn(entry.message(), DeprecationWarning, stacklevel=_first_frame_outside_settfex())
