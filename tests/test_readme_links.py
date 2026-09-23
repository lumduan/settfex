"""Every anchor link out of README.md must resolve — and point somewhere unambiguous.

The README ships as package metadata (`readme = "README.md"`), so it is the **only** one of these
documents an installed user or agent can see, and **PyPI does not resolve relative links**. Its
links to the CHANGELOG are how a reader reaches the data completeness advisory, so they are written
as absolute, tag-pinned GitHub URLs — and this module is what keeps them honest, because an
absolute URL cannot be checked by simply existing on disk.

Four assertions, in increasing order of subtlety:

1. **The target file exists.** Catches a moved file.
2. **The fragment resolves to a heading.** Catches a renamed heading.
3. **That heading is unique.** `#migration` resolves today only because 0.24.0 is the sole release
   carrying a ``### Migration`` heading. The CHANGELOG is newest-first, so the moment 0.25.0 adds
   its own, GitHub hands the anchor to whichever comes first in the document — the *new* one — and
   the README starts pointing at the wrong release's notes with every link still "working".
4. **Release notes are pinned to a version tag, not a branch.** A ``blob/main/`` link into the
   CHANGELOG silently re-points at whatever ``main`` says later, which is the same drift as (3)
   wearing a different hat. The advisory links must keep pointing at *0.24.0's* notes after a
   later release rewrites that section. **Only the CHANGELOG is held to this.** Links into
   ``docs/`` and ``examples/`` deliberately follow ``main``: they describe the current library,
   and a reader arriving from PyPI should land on today's docs, not on the docs of the release
   that happened to add the link.

Two more, because the README is also the PyPI project page (added in 0.25.0, when 87 relative links
were found broken there):

5. **No relative links at all.** PyPI resolves nothing relative, so ``docs/x.md`` is a dead link
   for every reader who never opens GitHub.
6. **Every link into this repo points at something that exists.** An absolute URL cannot be
   checked by simply existing on disk, so the path inside it is.

All six are checked offline, against the files in this repo. Nothing here fetches a URL — the tag
a link pins to does not exist until release.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
REPO_SLUG = "lumduan/settfex"

#: Any markdown link carrying a fragment — relative (`CHANGELOG.md#x`) or absolute GitHub blob URL.
_LINK = re.compile(r"\[[^\]]+\]\((?P<target>[^)\s]*#[A-Za-z0-9_-]+)\)")
_GITHUB_BLOB = re.compile(
    r"^https://github\.com/(?P<slug>[^/]+/[^/]+)/blob/(?P<ref>[^/]+)/(?P<path>[^#]+)#(?P<anchor>.+)$"
)
_RELATIVE = re.compile(r"^(?P<path>[A-Za-z0-9_./-]*)#(?P<anchor>.+)$")
_HEADING = re.compile(r"^#{1,6}\s+(?P<text>.+?)\s*$", re.MULTILINE)
_VERSION_TAG = re.compile(r"^v\d+\.\d+\.\d+")

#: Every link target, with or without a fragment: markdown links and HTML href/src attributes.
_ANY_LINK = re.compile(r"\]\((?P<target>[^)\s]+)\)")
_ANY_ATTR = re.compile(r"""(?:href|src)=["'](?P<target>[^"']+)["']""")
_NOT_RELATIVE = re.compile(r"^(https?:|#|mailto:)")
_REPO_URL = re.compile(
    rf"^https://github\.com/{re.escape(REPO_SLUG)}/"
    r"(?P<kind>blob|tree)/(?P<ref>[^/]+)/(?P<path>[^#?]*)"
)


def github_anchor(heading_text: str) -> str:
    """GitHub's slug: lowercase, drop punctuation, spaces to hyphens.

    Emoji fall out with the punctuation, matching GitHub's own behaviour for the headings this
    repo uses (``## ⚡ Quick Install`` → ``quick-install``).
    """
    slug = re.sub(r"[^\w\s-]", "", heading_text.strip().lower(), flags=re.UNICODE)
    return re.sub(r"\s+", "-", slug.strip())


def anchors_in(path: Path) -> list[str]:
    return [github_anchor(m.group("text")) for m in _HEADING.finditer(path.read_text("utf-8"))]


def readme_links() -> list[tuple[str, str, str | None]]:
    """(local path, anchor, pinned ref or None) for every fragment link in README.md."""
    out: list[tuple[str, str, str | None]] = []
    for match in _LINK.finditer((REPO_ROOT / "README.md").read_text("utf-8")):
        target = match.group("target")
        if blob := _GITHUB_BLOB.match(target):
            out.append((blob.group("path"), blob.group("anchor"), blob.group("ref")))
            continue
        if target.startswith("http"):
            continue  # an external URL with a fragment; not ours to verify
        if rel := _RELATIVE.match(target):
            out.append((rel.group("path") or "README.md", rel.group("anchor"), None))
    return out


def github_slugs() -> list[str]:
    return [
        m.group("slug")
        for m in (
            _GITHUB_BLOB.match(x.group("target"))
            for x in _LINK.finditer((REPO_ROOT / "README.md").read_text("utf-8"))
        )
        if m
    ]


class TestReadmeAnchorLinks:
    def test_there_are_links_to_check(self) -> None:
        """Guard the guard: a regex that silently matches nothing would pass everything below."""
        links = readme_links()
        assert links, "no anchor links found in README.md — the link regex has stopped matching"
        assert any(path == "CHANGELOG.md" for path, _, _ in links), (
            "README.md no longer links to any CHANGELOG anchor. That pointer is how an installed "
            "user reaches the data completeness advisory; do not remove it while it is current."
        )

    @pytest.mark.parametrize(("path", "anchor", "ref"), readme_links(), ids=lambda v: str(v))
    def test_each_link_resolves_to_exactly_one_heading(
        self, path: str, anchor: str, ref: str | None
    ) -> None:
        target = REPO_ROOT / path
        assert target.is_file(), f"README.md links to {path}, which does not exist in this repo"

        found = anchors_in(target)
        count = found.count(anchor)

        assert count != 0, (
            f"README.md links to {path}#{anchor}, but {path} has no heading with that anchor — a "
            f"heading was probably renamed. Nearest: "
            f"{sorted(h for h in set(found) if anchor.split('-')[0] in h) or sorted(set(found))[:5]}"
        )
        assert count == 1, (
            f"{path} has {count} headings producing #{anchor}, so the link is ambiguous — GitHub "
            f"resolves it to whichever appears FIRST, which in a newest-first CHANGELOG means the "
            f"most recent release silently steals it. Rename the new heading (e.g. 'Migration to "
            f"0.25') so this link keeps pointing where it meant to."
        )

    @pytest.mark.parametrize(("path", "anchor", "ref"), readme_links(), ids=lambda v: str(v))
    def test_release_note_links_are_pinned_to_a_version_tag(
        self, path: str, anchor: str, ref: str | None
    ) -> None:
        """A branch ref re-points itself later; a tag does not — for release notes.

        Scoped to the CHANGELOG on purpose: docs and examples links follow ``main`` (see (4) in the
        module docstring), so pinning them would freeze PyPI readers on stale documentation.
        """
        if ref is None or path != "CHANGELOG.md":
            return  # a relative link has no ref; a docs link is meant to follow main
        assert _VERSION_TAG.match(ref), (
            f"README.md links to {path}#{anchor} at ref {ref!r}. Pin release notes to a version "
            f"tag (e.g. 'v0.24.0'): a branch ref silently re-points at whatever that branch says "
            f"later, so this link would stop describing the release it was written for."
        )

    def test_github_links_point_at_this_repo(self) -> None:
        """A typo'd owner or repo would otherwise 404 in the wild and pass every check here."""
        wrong = sorted({s for s in github_slugs() if s != REPO_SLUG})
        assert not wrong, f"README.md has GitHub links to {wrong}; expected {REPO_SLUG!r}"


def all_link_targets() -> list[str]:
    """Every link target in README.md: markdown links and HTML attributes, fragment or not."""
    text = (REPO_ROOT / "README.md").read_text("utf-8")
    return [m.group("target") for rx in (_ANY_LINK, _ANY_ATTR) for m in rx.finditer(text)]


class TestReadmeLinksWorkOnPyPI:
    """The README is the PyPI project page, and PyPI resolves nothing relative."""

    def test_there_are_repo_links_to_check(self) -> None:
        """Guard the guard: the repo-link regex must keep matching, or (6) proves nothing."""
        repo_links = [t for t in all_link_targets() if _REPO_URL.match(t)]
        assert len(repo_links) >= 80, (
            f"only {len(repo_links)} links into {REPO_SLUG} found — the README used to carry 87 "
            f"docs/examples links; either they were removed or _REPO_URL has stopped matching"
        )

    def test_no_relative_links(self) -> None:
        relative = sorted({t for t in all_link_targets() if not _NOT_RELATIVE.match(t)})
        assert not relative, (
            f"README.md has {len(relative)} relative link(s), dead on PyPI: {relative[:10]}. "
            f"Write them as https://github.com/{REPO_SLUG}/blob/main/<path> "
            f"(tree/main/ for a directory)."
        )

    def test_every_repo_link_points_at_something_that_exists(self) -> None:
        """A moved or renamed file would 404 for every PyPI reader and pass every other check."""
        missing = []
        for target in all_link_targets():
            if not (m := _REPO_URL.match(target)):
                continue
            path = REPO_ROOT / m.group("path")
            exists = path.is_dir() if m.group("kind") == "tree" else path.is_file()
            if not exists:
                missing.append(target)
        assert not missing, f"README.md links to paths that do not exist in this repo: {missing}"
