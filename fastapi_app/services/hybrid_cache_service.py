from __future__ import annotations

import time

from ..core.config import get_settings
from .cache_service import (
    async_delete_key,
    async_get_json,
    async_set_json,
    delete_key,
    get_json,
    set_json,
)
from .local_cache_service import local_cache
from .metrics_service import async_increment_counter, async_record_timing_metric, increment_counter, record_timing_metric


EMPTY_MARKER = {"__empty__": True}


def _normalize_key(parts: tuple[object, ...]) -> str:
    return ":".join(str(part) for part in parts)


def _cache_metric_family(parts: tuple[object, ...]) -> str:
    if not parts:
        return "unknown"
    if parts[0] == "books" and len(parts) > 1 and parts[1] == "list":
        return "books_list"
    if parts[0] == "books" and len(parts) > 1 and parts[1] == "count":
        return "books_count"
    if parts[0] == "book" and len(parts) > 2 and parts[2] == "detail":
        return "book_detail"
    if parts[0] == "files" and len(parts) > 1 and parts[1] == "meta":
        return "file_meta"
    return str(parts[0])


def get_cached(parts: tuple[object, ...], *, local_ttl_seconds: int):
    local_key = _normalize_key(parts)
    family = _cache_metric_family(parts)
    local_start = time.perf_counter()
    cached = local_cache.get(local_key)
    local_duration_ms = (time.perf_counter() - local_start) * 1000.0
    record_timing_metric(f"cache.{family}.local_read_ms", local_duration_ms)
    if cached is not None:
        increment_counter(f"cache.{family}.local_empty_hit" if cached == EMPTY_MARKER else f"cache.{family}.local_hit")
        return cached

    redis_start = time.perf_counter()
    cached = get_json(*parts)
    redis_duration_ms = (time.perf_counter() - redis_start) * 1000.0
    record_timing_metric(f"cache.{family}.redis_read_ms", redis_duration_ms)
    if cached is not None:
        increment_counter(f"cache.{family}.redis_empty_hit" if cached == EMPTY_MARKER else f"cache.{family}.redis_hit")
        local_cache.set(local_key, cached, local_ttl_seconds)
        return cached
    increment_counter(f"cache.{family}.miss")
    return None


async def async_get_cached(parts: tuple[object, ...], *, local_ttl_seconds: int):
    local_key = _normalize_key(parts)
    family = _cache_metric_family(parts)
    local_start = time.perf_counter()
    cached = local_cache.get(local_key)
    local_duration_ms = (time.perf_counter() - local_start) * 1000.0
    await async_record_timing_metric(f"cache.{family}.local_read_ms", local_duration_ms)
    if cached is not None:
        await async_increment_counter(
            f"cache.{family}.local_empty_hit" if cached == EMPTY_MARKER else f"cache.{family}.local_hit"
        )
        return cached

    redis_start = time.perf_counter()
    cached = await async_get_json(*parts)
    redis_duration_ms = (time.perf_counter() - redis_start) * 1000.0
    await async_record_timing_metric(f"cache.{family}.redis_read_ms", redis_duration_ms)
    if cached is not None:
        await async_increment_counter(
            f"cache.{family}.redis_empty_hit" if cached == EMPTY_MARKER else f"cache.{family}.redis_hit"
        )
        local_cache.set(local_key, cached, local_ttl_seconds)
        return cached
    await async_increment_counter(f"cache.{family}.miss")
    return None


def set_cached(parts: tuple[object, ...], value, *, redis_ttl_seconds: int, local_ttl_seconds: int) -> None:
    local_key = _normalize_key(parts)
    set_json(*parts, value=value, ttl_seconds=redis_ttl_seconds)
    local_cache.set(local_key, value, local_ttl_seconds)


async def async_set_cached(parts: tuple[object, ...], value, *, redis_ttl_seconds: int, local_ttl_seconds: int) -> None:
    local_key = _normalize_key(parts)
    await async_set_json(*parts, value=value, ttl_seconds=redis_ttl_seconds)
    local_cache.set(local_key, value, local_ttl_seconds)


def set_empty(parts: tuple[object, ...], *, local_ttl_seconds: int) -> None:
    settings = get_settings()
    set_cached(
        parts,
        EMPTY_MARKER,
        redis_ttl_seconds=settings.redis.empty_ttl_seconds,
        local_ttl_seconds=local_ttl_seconds or settings.local_cache.empty_ttl_seconds,
    )


async def async_set_empty(parts: tuple[object, ...], *, local_ttl_seconds: int) -> None:
    settings = get_settings()
    await async_set_cached(
        parts,
        EMPTY_MARKER,
        redis_ttl_seconds=settings.redis.empty_ttl_seconds,
        local_ttl_seconds=local_ttl_seconds or settings.local_cache.empty_ttl_seconds,
    )


def delete_cached(parts: tuple[object, ...]) -> None:
    local_cache.delete(_normalize_key(parts))
    delete_key(*parts)


async def async_delete_cached(parts: tuple[object, ...]) -> None:
    local_cache.delete(_normalize_key(parts))
    await async_delete_key(*parts)
