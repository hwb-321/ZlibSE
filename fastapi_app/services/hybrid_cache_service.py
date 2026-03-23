from __future__ import annotations

import random

from ..core.config import get_settings
from .cache_service import delete_key, get_json, set_json
from .local_cache_service import local_cache


EMPTY_MARKER = {"__empty__": True}


def _normalize_key(parts: tuple[object, ...]) -> str:
    return ":".join(str(part) for part in parts)


def get_cached(parts: tuple[object, ...], *, local_ttl_seconds: int):
    local_key = _normalize_key(parts)
    cached = local_cache.get(local_key)
    if cached is not None:
        return cached

    cached = get_json(*parts)
    if cached is not None:
        local_cache.set(local_key, cached, local_ttl_seconds)
        return cached
    return None


def set_cached(parts: tuple[object, ...], value, *, redis_ttl_seconds: int, local_ttl_seconds: int) -> None:
    local_key = _normalize_key(parts)
    ttl = redis_ttl_seconds + random.randint(5, 30)
    set_json(*parts, value=value, ttl_seconds=ttl)
    local_cache.set(local_key, value, local_ttl_seconds)


def set_empty(parts: tuple[object, ...], *, local_ttl_seconds: int) -> None:
    settings = get_settings()
    set_cached(
        parts,
        EMPTY_MARKER,
        redis_ttl_seconds=settings.redis.empty_ttl_seconds,
        local_ttl_seconds=local_ttl_seconds or settings.local_cache.empty_ttl_seconds,
    )


def delete_cached(parts: tuple[object, ...]) -> None:
    local_cache.delete(_normalize_key(parts))
    delete_key(*parts)
