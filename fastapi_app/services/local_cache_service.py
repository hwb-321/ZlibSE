from __future__ import annotations

import time
from threading import Lock

from cachetools import TTLCache

from ..core.config import get_settings


class LocalTTLCache:
    def __init__(self) -> None:
        app_settings = get_settings()
        settings = app_settings.local_cache
        # L1 cache is only meaningful when Redis is enabled as the shared cache/version source.
        self._enabled = bool(app_settings.redis.enabled and settings.enabled)
        self._cache: TTLCache[str, object] = TTLCache(maxsize=settings.max_entries, ttl=settings.default_ttl_seconds)
        self._expires_at: dict[str, float] = {}
        self._lock = Lock()

    def get(self, key: str):
        if not self._enabled:
            return None
        with self._lock:
            expires_at = self._expires_at.get(key)
            if expires_at is not None and expires_at < time.time():
                self._cache.pop(key, None)
                self._expires_at.pop(key, None)
                return None
            return self._cache.get(key)

    def set(self, key: str, value, ttl_seconds: int) -> None:
        if not self._enabled:
            return
        with self._lock:
            self._cache[key] = value
            self._expires_at[key] = time.time() + ttl_seconds

    def delete(self, key: str) -> None:
        with self._lock:
            self._cache.pop(key, None)
            self._expires_at.pop(key, None)

    def delete_prefix(self, prefix: str) -> None:
        with self._lock:
            keys = [key for key in self._cache.keys() if key.startswith(prefix)]
            for key in keys:
                self._cache.pop(key, None)
                self._expires_at.pop(key, None)


local_cache = LocalTTLCache()
