"""Tests for SessionCache: the on-disk permissions, and the store that never unpickles.

The cached cookies are credentials, so the directory and file modes are a security property.
Until 0.15.1 the store was diskcache, which reads values back with pickle (CVE-2025-69872 /
PYSEC-2026-2447, no fixed release upstream): write access to the directory was code execution in
the reading process. The store is now stdlib sqlite3 holding JSON text, and these tests pin that
nothing in a row can become code, plus the behaviour SessionManager relies on.
"""

import os
import stat
import time
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
        assert any("are credentials" in message for message in messages)

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


class TestNothingIsUnpickled:
    """The store is JSON text in SQLite: a hostile row is a cache miss, never code."""

    def _raw(self, cache: SessionCache, key: str, value: str) -> None:
        cache._db.execute(
            "INSERT OR REPLACE INTO sessions (key, value, stored_at, expires_at) VALUES (?,?,?,?)",
            (key, value, time.time(), time.time() + 3600),
        )

    def test_a_pickle_payload_is_a_miss_not_code(self, tmp_path: Path) -> None:
        import pickle

        class Boom:
            def __reduce__(self) -> tuple[Any, ...]:
                return (os.system, ("touch " + str(tmp_path / "pwned"),))

        with SessionCache(cache_dir=tmp_path) as cache:
            self._raw(cache, "k", pickle.dumps(Boom()).decode("latin-1"))
            assert cache.get("k") is None
        assert not (tmp_path / "pwned").exists()

    def test_json_that_is_not_an_object_is_a_miss(self, tmp_path: Path) -> None:
        with SessionCache(cache_dir=tmp_path) as cache:
            self._raw(cache, "k", "[1, 2, 3]")
            assert cache.get("k") is None

    def test_the_legacy_diskcache_database_is_never_opened(self, tmp_path: Path) -> None:
        legacy = tmp_path / "cache.db"
        legacy.write_bytes(b"not a database, and certainly not read")
        before = legacy.stat().st_mtime_ns
        with SessionCache(cache_dir=tmp_path) as cache:
            assert cache.get("set_session_chrome120") is None
            assert cache.set("k", {"cookies": {"a": "b"}})
        assert legacy.read_bytes() == b"not a database, and certainly not read"
        assert legacy.stat().st_mtime_ns == before

    def test_the_module_does_not_depend_on_diskcache(self) -> None:
        import settfex.utils.session_cache as module

        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "import diskcache" not in source and "import pickle" not in source


class TestTheStoreBehavesAsBefore:
    """What SessionManager relies on: round-trip, TTL, delete, clear, stats, size limit."""

    def test_round_trip_adds_metadata(self, tmp_path: Path) -> None:
        with SessionCache(cache_dir=tmp_path) as cache:
            assert cache.set("k", {"cookies": {"incap_ses": "x"}, "browser": "chrome120"})
            got = cache.get("k")
        assert got is not None
        assert got["cookies"] == {"incap_ses": "x"} and got["browser"] == "chrome120"
        assert got["ttl"] == 3600 and isinstance(got["cached_at"], float)

    def test_an_expired_entry_is_gone(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        with SessionCache(cache_dir=tmp_path) as cache:
            cache.set("k", {"cookies": {}}, ttl=10)
            real = time.time
            monkeypatch.setattr(time, "time", lambda: real() + 11)
            assert cache.get("k") is None
            assert cache.is_expired("k")
            assert cache.stats()["count"] == 0

    def test_is_expired_honours_max_age(self, tmp_path: Path) -> None:
        with SessionCache(cache_dir=tmp_path) as cache:
            cache.set("k", {"cookies": {}})
            assert not cache.is_expired("k")
            assert cache.is_expired("k", max_age=-1)
            assert cache.is_expired("missing")

    def test_delete_clear_and_stats(self, tmp_path: Path) -> None:
        with SessionCache(cache_dir=tmp_path) as cache:
            cache.set("a", {"cookies": {}})
            cache.set("b", {"cookies": {}})
            assert cache.stats()["count"] == 2 and cache.stats()["size"] > 0
            assert cache.delete("a") is True and cache.delete("a") is False
            cache.clear()
            assert cache.stats() == {"size": 0, "count": 0}

    def test_a_value_json_cannot_encode_is_refused_not_raised(self, tmp_path: Path) -> None:
        with SessionCache(cache_dir=tmp_path) as cache:
            assert cache.set("k", {"cookies": object()}) is False
            assert cache.get("k") is None

    def test_size_limit_evicts_the_oldest(self, tmp_path: Path) -> None:
        with SessionCache(cache_dir=tmp_path, size_limit=400) as cache:
            for i in range(5):
                cache.set(f"k{i}", {"cookies": {"c": "x" * 100}})
            assert cache.get("k4") is not None
            assert cache.get("k0") is None
            assert cache.stats()["size"] <= 400

    def test_the_database_file_is_private(self, tmp_path: Path) -> None:
        with SessionCache(cache_dir=tmp_path / "c") as cache:
            cache.set("k", {"cookies": {}})
            assert not _mode(cache.path) & 0o077

    def test_two_instances_share_one_directory(self, tmp_path: Path) -> None:
        """Several processes on one host share ~/.settfex/cache; WAL lets them coexist."""
        with SessionCache(cache_dir=tmp_path) as writer, SessionCache(cache_dir=tmp_path) as reader:
            writer.set("set_session_chrome120", {"cookies": {"a": "b"}})
            got = reader.get("set_session_chrome120")
        assert got is not None and got["cookies"] == {"a": "b"}
