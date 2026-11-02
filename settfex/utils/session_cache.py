"""
Session cache for persistent cookie storage: stdlib ``sqlite3`` holding JSON values.

This module provides disk-based caching for curl_cffi session cookies,
enabling fast session reuse without warming up every time.

Key features:
- Persistent storage across program restarts
- Automatic expiration and refresh
- Thread-safe, and safe for several processes sharing one cache directory (SQLite WAL)
- Fallback to warm-up on cache miss or failure

**Nothing here unpickles.** Until 0.17.1 the store was ``diskcache``, which reads values back with
pickle (CVE-2025-69872 / PYSEC-2026-2447, no fixed release upstream): write access to the cache
directory meant code execution in the reading process. Values are now JSON text, decoded with
``json.loads``; a row that does not decode to a JSON object is a cache miss, never code. The old
diskcache database (``cache.db``) is never opened, so it is never unpickled either.
"""

import asyncio
import json
import os
import sqlite3
import stat
import threading
import time
from pathlib import Path
from typing import Any

from loguru import logger

# The cached cookies are credentials in their own right: another account that can read the
# directory can replay the session, and one that can write it can plant cookies. 0700 on the
# directory and 0600 on the database remove both reaches for every other account on the machine.
_CACHE_DIR_MODE = 0o700
_CACHE_FILE_MODE = 0o600
_DB_NAME = "sessions.sqlite3"
# The pre-0.17.1 diskcache database. Never opened: diskcache would unpickle it.
_LEGACY_DISKCACHE_DB = "cache.db"
_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS sessions ("
    " key TEXT PRIMARY KEY,"
    " value TEXT NOT NULL,"
    " stored_at REAL NOT NULL,"
    " expires_at REAL NOT NULL)"
)


def _secure_cache_dir(cache_dir: Path, *, owned: bool) -> None:
    """Create the cache directory private, and vet the permissions of one that already exists.

    New directories are always created ``0700``. An existing one is treated differently
    depending on who chose it:

    * The default ``~/.settfex/cache`` is ours, so loose bits are tightened (and logged).
    * A caller-supplied directory may be shared on purpose — a service account, a mounted
      volume — so a group/other-writable one is *reported and left alone*. Silently breaking a
      deliberate layout would be worse than the warning.

    Never raises: a cache that cannot be permission-checked is still a usable cache, and this
    module's contract is to degrade rather than fail (see the try/except in every method below).

    Args:
        cache_dir: Directory that will hold the session database.
        owned: True when settfex chose the location, False when the caller passed one.
    """
    cache_dir.mkdir(mode=_CACHE_DIR_MODE, parents=True, exist_ok=True)

    # POSIX mode bits do not express this on Windows; skip rather than pretend.
    if os.name == "nt":
        return

    try:
        mode = stat.S_IMODE(cache_dir.stat().st_mode)
        # A directory this call just created is already private -- mkdir's mode can only be
        # tightened by the umask, never loosened -- so reaching past here means it pre-existed.
        if not mode & 0o077:
            return

        if owned:
            cache_dir.chmod(_CACHE_DIR_MODE)
            logger.info(
                f"Tightened cache directory permissions: {cache_dir} {mode:04o} -> 0700 "
                f"(cached cookies are credentials)"
            )
        elif mode & 0o022:
            logger.warning(
                f"Cache directory {cache_dir} is group/other-writable ({mode:04o}). The cached "
                f"session cookies are credentials: anyone who can write here can plant cookies "
                f"this process will send. Leaving the mode alone because you chose this path -- "
                f"pass a private directory, or chmod 700 it, if the sharing is not deliberate."
            )
    except OSError as e:
        logger.warning(f"Could not verify permissions on cache directory {cache_dir}: {e}")


def _secure_db_file(path: Path) -> None:
    """Create the database file ``0600`` before SQLite opens it; tighten a loose existing one.

    SQLite creates its ``-wal`` / ``-shm`` files with the main database's permissions, so getting
    this file right covers all three. Never raises (same contract as :func:`_secure_cache_dir`).
    """
    try:
        fd = os.open(path, os.O_CREAT | os.O_WRONLY, _CACHE_FILE_MODE)
        os.close(fd)
        if os.name != "nt" and stat.S_IMODE(path.stat().st_mode) & 0o077:
            path.chmod(_CACHE_FILE_MODE)
    except OSError as e:
        logger.warning(f"Could not verify permissions on cache file {path}: {e}")


class SessionCache:
    """
    Disk-based cache for session cookies and metadata.

    This class manages persistent storage of curl_cffi session cookies,
    allowing sessions to be reused across program restarts. When cached
    cookies are available and valid, they're used immediately (fast path).
    Otherwise, a new session is warmed up and cached.

    Values must be JSON-serializable dicts (cookies as ``{name: value}`` strings, the browser
    name, timestamps, counts). They are stored as JSON text in SQLite; nothing is unpickled.

    Architecture:
        1. Check cache for valid cookies → Use if found (fast)
        2. If not found or expired → Warm up → Cache it
        3. If request fails → Re-warm and update cache

    Example:
        >>> cache = SessionCache()
        >>>
        >>> # Try to get cached cookies
        >>> cached = cache.get("set_session")
        >>> if cached and not cache.is_expired("set_session"):
        >>>     cookies = cached["cookies"]
        >>> else:
        >>>     # Warm up new session
        >>>     cookies = await warm_up_session()
        >>>     cache.set("set_session", {"cookies": cookies, "browser": "chrome120"})
    """

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        default_ttl: int = 3600,
        size_limit: int = 100 * 1024 * 1024,  # 100MB
    ) -> None:
        """
        Initialize session cache.

        Args:
            cache_dir: Directory for cache storage (default: ~/.settfex/cache)
            default_ttl: Default time-to-live for cached items in seconds (default: 1 hour)
            size_limit: Maximum total size of stored values in bytes (default: 100MB); the
                oldest entries are evicted beyond it
        """
        # The `is None` test is repeated rather than reusing `is_default`, because mypy narrows
        # the parameter on the literal check but not through the flag.
        is_default = cache_dir is None
        cache_dir = Path.home() / ".settfex" / "cache" if cache_dir is None else Path(cache_dir)

        # Create the cache directory 0700 -- see _secure_cache_dir for why the mode matters.
        _secure_cache_dir(cache_dir, owned=is_default)

        self.path = cache_dir / _DB_NAME
        _secure_db_file(self.path)
        self.default_ttl = default_ttl
        self.size_limit = size_limit
        self._lock = threading.Lock()
        # Autocommit (isolation_level=None) with a busy timeout: several processes on one host
        # may share this directory, and WAL lets their readers and the one writer coexist.
        self._db = sqlite3.connect(
            str(self.path), timeout=10.0, isolation_level=None, check_same_thread=False
        )
        with self._lock:
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute(_SCHEMA)

        if (cache_dir / _LEGACY_DISKCACHE_DB).exists():
            logger.info(
                f"A pre-0.17.1 diskcache database is present at {cache_dir / _LEGACY_DISKCACHE_DB}"
                f" and is NOT read (diskcache unpickles its values). It can be deleted; the "
                f"session will warm up once and be cached in {_DB_NAME}."
            )

        logger.info(
            f"SessionCache initialized at {cache_dir} "
            f"(ttl={default_ttl}s, size_limit={size_limit // 1024 // 1024}MB)"
        )

    def get(self, key: str) -> dict[str, Any] | None:
        """
        Get cached session data.

        Args:
            key: Cache key (e.g., "set_session", "tfex_session")

        Returns:
            Cached session data dict or None if not found, expired, or unreadable

        Example:
            >>> cached = cache.get("set_session")
            >>> if cached:
            >>>     cookies = cached["cookies"]
            >>>     browser = cached["browser"]
        """
        try:
            with self._lock:
                row = self._db.execute(
                    "SELECT value, expires_at FROM sessions WHERE key = ?", (key,)
                ).fetchone()
                if row is not None and row[1] <= time.time():
                    self._db.execute("DELETE FROM sessions WHERE key = ?", (key,))
                    row = None
            if row is None:
                logger.debug(f"Cache MISS: {key}")
                return None
            value = json.loads(row[0])
            if not isinstance(value, dict):
                logger.warning(f"Cache entry {key!r} is not a JSON object; treating it as a miss")
                return None
            logger.debug(f"Cache HIT: {key}")
            return value
        except (sqlite3.Error, ValueError) as e:
            logger.error(f"Failed to read from cache: {e}")
            return None

    def set(
        self,
        key: str,
        value: dict[str, Any],
        ttl: int | None = None,
    ) -> bool:
        """
        Store session data in cache.

        Args:
            key: Cache key (e.g., "set_session")
            value: Session data to cache: a JSON-serializable dict with "cookies", "browser",
                etc.
            ttl: Time-to-live in seconds (uses default_ttl if None)

        Returns:
            True if successfully cached, False otherwise (including a value JSON cannot encode)

        Example:
            >>> cache.set("set_session", {
            >>>     "cookies": {"incap_ses": "xyz"},
            >>>     "browser": "chrome120",
            >>>     "warmup_time": time.time(),
            >>>     "cookie_count": 12
            >>> })
        """
        try:
            ttl = ttl or self.default_ttl
            now = time.time()
            # Add metadata
            value["cached_at"] = now
            value["ttl"] = ttl
            encoded = json.dumps(value)

            with self._lock:
                self._db.execute(
                    "INSERT OR REPLACE INTO sessions (key, value, stored_at, expires_at)"
                    " VALUES (?, ?, ?, ?)",
                    (key, encoded, now, now + ttl),
                )
                self._db.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
                self._evict_over_limit()
            logger.success(f"✓ Cached session: {key} (ttl={ttl}s)")
            return True
        except (sqlite3.Error, TypeError, ValueError) as e:
            logger.error(f"Failed to write to cache: {e}")
            return False

    def _evict_over_limit(self) -> None:
        """Drop the oldest entries while the stored values exceed ``size_limit``. Lock held."""
        while True:
            total = self._db.execute(
                "SELECT COALESCE(SUM(LENGTH(value)), 0), COUNT(*) FROM sessions"
            ).fetchone()
            if total[0] <= self.size_limit or total[1] <= 1:
                return
            self._db.execute(
                "DELETE FROM sessions WHERE key ="
                " (SELECT key FROM sessions ORDER BY stored_at ASC LIMIT 1)"
            )

    def delete(self, key: str) -> bool:
        """
        Delete cached session data.

        Args:
            key: Cache key to delete

        Returns:
            True if deleted, False otherwise
        """
        try:
            with self._lock:
                deleted = self._db.execute("DELETE FROM sessions WHERE key = ?", (key,)).rowcount
            if deleted:
                logger.debug(f"Deleted from cache: {key}")
            return bool(deleted)
        except sqlite3.Error as e:
            # "delete from" below is log text, not SQL (bandit B608 false positive).
            logger.error(f"Failed to delete from cache: {e}")  # nosec B608
            return False

    def is_expired(self, key: str, max_age: int | None = None) -> bool:
        """
        Check if cached session is expired.

        Args:
            key: Cache key to check
            max_age: Maximum age in seconds (uses default_ttl if None)

        Returns:
            True if expired or not found, False if still valid
        """
        cached = self.get(key)
        if cached is None:
            return True

        max_age = max_age or self.default_ttl
        cached_at = cached.get("cached_at", 0)
        age = time.time() - cached_at

        is_expired = age > max_age
        if is_expired:
            logger.debug(f"Cache expired: {key} (age={age:.0f}s > max={max_age}s)")
        else:
            logger.debug(f"Cache valid: {key} (age={age:.0f}s < max={max_age}s)")

        return bool(is_expired)

    def clear(self) -> None:
        """Clear all cached data."""
        try:
            with self._lock:
                self._db.execute("DELETE FROM sessions")
            logger.info("Cache cleared")
        except sqlite3.Error as e:
            logger.error(f"Failed to clear cache: {e}")

    def stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with ``size`` (bytes of stored values) and ``count`` (number of entries)
        """
        try:
            with self._lock:
                size, count = self._db.execute(
                    "SELECT COALESCE(SUM(LENGTH(value)), 0), COUNT(*) FROM sessions"
                ).fetchone()
            return {"size": int(size), "count": int(count)}
        except sqlite3.Error as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {"size": 0, "count": 0}

    def close(self) -> None:
        """Close the cache."""
        try:
            with self._lock:
                self._db.close()
            logger.debug("Cache closed")
        except sqlite3.Error as e:
            logger.error(f"Failed to close cache: {e}")

    def __enter__(self) -> "SessionCache":
        """Context manager entry."""
        return self

    def __exit__(self, *args: object) -> None:
        """Context manager exit."""
        self.close()


# Global cache instance (singleton pattern)
_global_cache: SessionCache | None = None
_cache_lock = asyncio.Lock()


async def get_global_cache(
    cache_dir: str | Path | None = None,
    default_ttl: int = 3600,
) -> SessionCache:
    """
    Get or create global SessionCache instance.

    This function provides a singleton cache instance that can be shared
    across all services for optimal performance.

    Args:
        cache_dir: Directory for cache storage (default: ~/.settfex/cache)
        default_ttl: Default time-to-live in seconds (default: 1 hour)

    Returns:
        Global SessionCache instance

    Example:
        >>> cache = await get_global_cache()
        >>> cached = cache.get("set_session")
    """
    global _global_cache

    async with _cache_lock:
        if _global_cache is None:
            # SessionCache.__init__ does blocking disk I/O (mkdir + opening the SQLite
            # database); run it off the event loop so cold cache init never blocks the loop.
            _global_cache = await asyncio.to_thread(
                SessionCache, cache_dir=cache_dir, default_ttl=default_ttl
            )
        return _global_cache
