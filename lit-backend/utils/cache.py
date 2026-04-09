import time
from typing import Any, Optional
from functools import wraps
from utils.logger import get_logger

logger = get_logger(__name__)


class TTLCache:
    """Simple in-memory cache with time-to-live expiration."""

    def __init__(self, ttl: int = 3600):
        """
        Initialize TTL cache.

        Args:
            ttl: Time-to-live in seconds (default: 1 hour)
        """
        self._cache: dict[str, tuple[Any, float]] = {}
        self._ttl = ttl

    def get(self, key: str) -> Optional[Any]:
        """Retrieve value from cache if not expired."""
        if key not in self._cache:
            return None

        value, timestamp = self._cache[key]
        if time.time() - timestamp > self._ttl:
            del self._cache[key]
            logger.debug(f"Cache expired for key: {key}")
            return None

        logger.debug(f"Cache hit for key: {key}")
        return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Store value in cache with optional custom TTL."""
        self._cache[key] = (value, time.time())
        logger.debug(f"Cache set for key: {key}")

    def delete(self, key: str) -> bool:
        """Remove a key from cache."""
        if key in self._cache:
            del self._cache[key]
            logger.debug(f"Cache deleted for key: {key}")
            return True
        return False

    def clear(self) -> None:
        """Clear all cached entries."""
        count = len(self._cache)
        self._cache.clear()
        logger.info(f"Cache cleared ({count} entries removed)")

    def cleanup(self) -> int:
        """Remove all expired entries. Returns count of removed items."""
        now = time.time()
        expired = [
            k for k, (_, ts) in self._cache.items()
            if now - ts > self._ttl
        ]
        for k in expired:
            del self._cache[k]
        if expired:
            logger.debug(f"Cleanup removed {len(expired)} expired entries")
        return len(expired)

    @property
    def size(self) -> int:
        """Return number of entries in cache."""
        return len(self._cache)


# Global cache instance (TTL configured via settings at startup)
cache = TTLCache()


def cached(key_prefix: str, ttl: Optional[int] = None):
    """Decorator to cache function results."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{key_prefix}:{args}:{sorted(kwargs.items())}"
            result = cache.get(cache_key)
            if result is not None:
                return result

            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl=ttl)
            return result
        return wrapper
    return decorator
