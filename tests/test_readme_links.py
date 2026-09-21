"""Every anchor link out of README.md must resolve — and point somewhere unambiguous.

The README ships as package metadata (`readme = "README.md"`), so it is the **only** one of these
documents an installed agent can see. Its links to the CHANGELOG are how a reader reaches the data
completeness advisory, and a link that silently stops resolving costs exactly the reader who most
needs it: someone checking whether their stored data is affected.

Two assertions, and the second is the load-bearing one.

**Resolution** catches a renamed heading. **Uniqueness** catches something subtler that would
otherwise happen on the very next release: the CHANGELOG is newest-first, and `#migration` resolves
today only because 0.24.0 is the only release carrying a `### Migration` heading. The moment another
release adds one, GitHub gives the anchor to whichever comes first in the document — the *new* one —
and the README starts pointing at the wrong release's migration notes, with every link still
"working". Requiring the target heading to be unique turns that into a CI failure at the moment of
collision, which is the only point at which it is cheap to fix.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Markdown links whose target is a file in this repo plus an anchor, e.g. `CHANGELOG.md#migration`.
_LINK = re.compile(r"\[[^\]]+\]\((?P<file>[A-Za-z0-9_./-]*)#(?P<anchor>[A-Za-z0-9_-]+)\)")
_HEADING = re.compile(r"^(#{1,6})\s+(?P<text>.+?)\s*$", re.MULTILINE)


def github_anchor(heading_text: str) -> str:
    """GitHub's slug: lowercase, drop punctuation, spaces to hyphens.

    Emoji and other symbols fall out with the punctuation, which matches GitHub's behaviour for
    the headings this repo uses (``## ⚡ Quick Install`` → ``quick-install``).
    """
    slug = heading_text.strip().lower()
    slug = re.sub(r"[^\w\s-]", "", slug, flags=re.UNICODE)
    return re.sub(r"\s+", "-", slug.strip())


def anchors_in(path: Path) -> list[str]:
    return [github_anchor(m.group("text")) for m in _HEADING.finditer(path.read_text("utf-8"))]


def readme_links() -> list[tuple[str, str]]:
    text = (REPO_ROOT / "README.md").read_text("utf-8")
    return [(m.group("file") or "README.md", m.group("anchor")) for m in _LINK.finditer(text)]


class TestReadmeAnchorsResolve:
    def test_there_are_links_to_check(self) -> None:
        """Guard the guard: a regex that silently matches nothing would pass every test below."""
        links = readme_links()
        assert links, "no anchor links found in README.md — the link regex has stopped matching"
        assert any(f == "CHANGELOG.md" for f, _ in links), (
            "README.md no longer links to any CHANGELOG anchor. The advisory pointer is how an "
            "installed agent reaches it; do not remove it while the advisory is current."
        )

    @pytest.mark.parametrize(("target", "anchor"), readme_links(), ids=lambda v: str(v))
    def test_each_link_resolves_to_exactly_one_heading(self, target: str, anchor: str) -> None:
        path = REPO_ROOT / target
        assert path.is_file(), f"README.md links to {target}, which does not exist"

        found = anchors_in(path)
        count = found.count(anchor)

        assert count != 0, (
            f"README.md links to {target}#{anchor}, but {target} has no heading with that anchor. "
            f"A heading was probably renamed. Closest headings: "
            f"{sorted(h for h in set(found) if anchor.split('-')[0] in h) or sorted(set(found))[:5]}"
        )
        assert count == 1, (
            f"{target} has {count} headings producing the anchor #{anchor}, so the link is "
            f"ambiguous — GitHub resolves it to whichever appears FIRST, which in a newest-first "
            f"CHANGELOG means the most recent release silently steals it. Rename the new heading "
            f"(e.g. 'Migration to 0.25') so the README keeps pointing where it meant to."
        )
