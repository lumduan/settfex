"""
Session cache for persistent cookie storage using diskcache.

This module provides disk-based caching for curl_cffi session cookies,
enabling fast session reuse without warming up every time.

Key features:
- Persistent storage across program restarts
- Automatic expiration and refresh
- Thread-safe disk cache
- Fallback to warm-up on cache miss or failure
"""

import asyncio
import time
from pathlib import Path
from typing import Any

import diskcache
from loguru import logger


class SessionCache:
    """
    Disk-based cache for session cookies and metadata.

    This class manages persistent storage of curl_cffi session cookies,
    allowing sessions to be reused across program restarts. When cached
    cookies are available and valid, they're used immediately (fast path).
    Otherwise, a new session is warmed up and cached.

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
            size_limit: Maximum cache size in bytes (default: 100MB)
        """
        if cache_dir is None:
            cache_dir = Path.home() / ".settfex" / "cache"
        else:
            cache_dir = Path(cache_dir)

        # Create cache directory if needed
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Initialize diskcache
        self.cache = diskcache.Cache(str(cache_dir), size_limit=size_limit)
        self.default_ttl = default_ttl

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
            Cached session data dict or None if not found

        Example:
            >>> cached = cache.get("set_session")
            >>> if cached:
            >>>     cookies = cached["cookies"]
            >>>     browser = cached["browser"]
        """
        try:
            value = self.cache.get(key)
            if value is not None:
                logger.debug(f"Cache HIT: {key}")
                return value
            else:
                logger.debug(f"Cache MISS: {key}")
                return None
        except Exception as e:
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
            value: Session data to cache (must be dict with "cookies", "browser", etc.)
            ttl: Time-to-live in seconds (uses default_ttl if None)

        Returns:
            True if successfully cached, False otherwise

        Example:
            >>> cache.set("set_session", {
            >>>     "cookies": "charlot=abc; incap_ses=xyz",
            >>>     "browser": "chrome120",
            >>>     "warmup_time": time.time(),
            >>>     "cookie_count": 12
            >>> })
        """
        try:
            ttl = ttl or self.default_ttl
            # Add metadata
            value["cached_at"] = time.time()
            value["ttl"] = ttl

            self.cache.set(key, value, expire=ttl)
            logger.success(f"✓ Cached session: {key} (ttl={ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Failed to write to cache: {e}")
            return False

    def delete(self, key: str) -> bool:
        """
        Delete cached session data.

        Args:
            key: Cache key to delete

        Returns:
            True if deleted, False otherwise
        """
        try:
            result = self.cache.delete(key)
            if result:
                logger.debug(f"Deleted from cache: {key}")
            return result
        except Exception as e:
            logger.error(f"Failed to delete from cache: {e}")
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

        return is_expired

    def clear(self) -> None:
        """Clear all cached data."""
        try:
            self.cache.clear()
            logger.info("Cache cleared")
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")

    def stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with cache statistics (size, volume, hits, etc.)
        """
        try:
            return {
                "size": self.cache.volume(),  # Bytes used
                "count": len(self.cache),  # Number of items
            }
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {"size": 0, "count": 0}

    def close(self) -> None:
        """Close the cache."""
        try:
            self.cache.close()
            logger.debug("Cache closed")
        except Exception as e:
            logger.error(f"Failed to close cache: {e}")

    def __enter__(self) -> "SessionCache":
        """Context manager entry."""
        return self

    def __exit__(self, *args) -> None:
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
            _global_cache = SessionCache(cache_dir=cache_dir, default_ttl=default_ttl)
        return _global_cache
