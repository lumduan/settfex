"""Tests for SessionCache, focused on the on-disk permissions of the cache directory.

The mode of that directory is a security property, not a cosmetic one: diskcache reads cached
values back with pickle (CVE-2025-69872, no fixed release upstream), so write access to the
directory is code execution inside the calling process. These tests pin the cases that behave
differently — a directory we create, a loose default directory we own, a loose directory the
caller chose deliberately, and a chmod we are not allowed to make.
"""

import os
import stat
from pathlib import Path
from typing import Any

import pytest
from loguru import logger

from settfex.utils.session_cache import SessionCache

# POSIX mode bits do not express this on Windows, where the implementation skips the check.
pytestmark = pytest.mark.skipif(
    os.name == "nt", reason="POSIX permission bits are not meaningful on Windows"
)


def _mode(path: Path) -> int:
    """Permission bits of ``path``."""
    return stat.S_IMODE(path.stat().st_mode)


def _capture_warnings() -> tuple[list[str], int]:
    """Collect loguru WARNING records; returns the list and the sink id to remove."""
    messages: list[str] = []
    # settfex is disabled by default since 0.24.2 (#146), so a sink alone captures
    # nothing from it. Capturing settfex's own records is an explicit opt-in.
    logger.enable("settfex")
    sink_id = logger.add(lambda m: messages.append(str(m)), level="WARNING")
    return messages, sink_id


class TestCacheDirectoryPermissions:
    """The cache directory must not be writable by other accounts on the machine."""

    def test_new_directory_is_created_private(self, tmp_path: Path) -> None:
        """A directory settfex creates has no group or other access at all."""
        cache_dir = tmp_path / "fresh"

        with SessionCache(cache_dir=cache_dir):
            pass

        # & 0o077 rather than == 0o700: mkdir's mode is masked by the process umask, and the
        # property that matters is "no group/other access", not the exact literal.
        assert cache_dir.is_dir()
        assert not _mode(cache_dir) & 0o077

    def test_default_directory_is_tightened_in_place(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An existing ~/.settfex/cache left loose by an older version is fixed on next use."""
        home = tmp_path / "home"
        default_dir = home / ".settfex" / "cache"
        default_dir.mkdir(parents=True)
        default_dir.chmod(0o755)
        monkeypatch.setenv("HOME", str(home))

        with SessionCache():
            pass

        # chmod is not umask-masked, so the exact mode is assertable here.
        assert _mode(default_dir) == 0o700

    def test_caller_supplied_writable_directory_is_reported_not_changed(
        self, tmp_path: Path
    ) -> None:
        """A shared directory the caller chose is left alone — but the risk is named."""
        shared = tmp_path / "shared"
        shared.mkdir()
        shared.chmod(0o777)
        messages, sink_id = _capture_warnings()

        try:
            with SessionCache(cache_dir=shared):
                pass
        finally:
            logger.remove(sink_id)

        # Breaking a deliberate multi-account layout silently would be worse than warning.
        assert _mode(shared) == 0o777
        assert any("CVE-2025-69872" in message for message in messages)

    def test_caller_supplied_readable_directory_is_left_alone_silently(
        self, tmp_path: Path
    ) -> None:
        """0755 is readable but not writable, so it is not the vulnerable case — no warning."""
        readable = tmp_path / "readable"
        readable.mkdir()
        readable.chmod(0o755)
        messages, sink_id = _capture_warnings()

        try:
            with SessionCache(cache_dir=readable):
                pass
        finally:
            logger.remove(sink_id)

        assert _mode(readable) == 0o755
        assert not [m for m in messages if "cache directory" in m.lower()]

    def test_chmod_failure_does_not_break_the_cache(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A directory owned by another account cannot be chmod'd — the cache still works."""
        home = tmp_path / "home"
        default_dir = home / ".settfex" / "cache"
        default_dir.mkdir(parents=True)
        default_dir.chmod(0o755)
        monkeypatch.setenv("HOME", str(home))

        def _denied(self: Path, *args: Any, **kwargs: Any) -> None:
            raise OSError("Operation not permitted")

        monkeypatch.setattr(Path, "chmod", _denied)
        messages, sink_id = _capture_warnings()

        try:
            with SessionCache() as cache:
                assert cache.set("k", {"cookies": "a=b"}) is True
                assert cache.get("k") is not None
        finally:
            logger.remove(sink_id)

        assert any("Could not verify permissions" in message for message in messages)
