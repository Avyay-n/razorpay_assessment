"""
In-memory thread-safe TTL Cache to reduce upstream request volume and avoid rate limits.
"""

import time
import threading
from typing import Any, Optional, Dict, Tuple
from app.config import CACHE_TTL_SECONDS, CACHE_MAX_ENTRIES


class InMemoryTTLCache:
    """A lightweight, thread-safe in-memory cache with Time-To-Live (TTL) expiration."""

    def __init__(self, default_ttl: int = CACHE_TTL_SECONDS, max_entries: int = CACHE_MAX_ENTRIES):
        self._default_ttl = default_ttl
        self._max_entries = max_entries
        self._store: Dict[str, Tuple[Any, float]] = {}  # key -> (value, expire_timestamp)
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Retrieve an item from cache if not expired."""
        with self._lock:
            if key not in self._store:
                self._misses += 1
                return None

            value, expire_at = self._store[key]
            if time.time() > expire_at:
                # Expired
                del self._store[key]
                self._misses += 1
                return None

            self._hits += 1
            return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Store an item in the cache with a specified or default TTL."""
        ttl_val = ttl if ttl is not None else self._default_ttl
        expire_at = time.time() + ttl_val

        with self._lock:
            # Enforce capacity eviction if max_entries reached
            if len(self._store) >= self._max_entries and key not in self._store:
                # Evict oldest expired or first item
                now = time.time()
                expired_keys = [k for k, (_, exp) in self._store.items() if exp < now]
                if expired_keys:
                    for k in expired_keys:
                        del self._store[k]
                else:
                    # Evict an arbitrary item
                    first_key = next(iter(self._store))
                    del self._store[first_key]

            self._store[key] = (value, expire_at)

    def clear(self) -> None:
        """Clear all entries from cache."""
        with self._lock:
            self._store.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> Dict[str, Any]:
        """Return cache performance statistics."""
        with self._lock:
            return {
                "size": len(self._store),
                "max_entries": self._max_entries,
                "hits": self._hits,
                "misses": self._misses,
                "default_ttl_seconds": self._default_ttl,
            }


# Singleton cache instance
cache = InMemoryTTLCache()
