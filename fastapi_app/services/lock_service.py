from __future__ import annotations

import secrets

from ..core.config import get_settings
from ..core.redis import get_async_redis_client, get_redis_client
from .metrics_service import async_increment_counter, increment_counter


_RELEASE_LOCK_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""


def build_lock_value() -> str:
    return secrets.token_hex(16)


def _lock_family(key: str) -> str:
    prefix = f"{get_settings().redis.prefix}:"
    normalized = key[len(prefix) :] if key.startswith(prefix) else key
    parts = [part for part in normalized.split(":") if part and not part.isdigit()]
    return ".".join(parts) if parts else "unknown"


def acquire_lock(key: str, value: str, ttl_seconds: int | None = None) -> bool:
    client = get_redis_client()
    if client is None:
        increment_counter("lock.acquire.no_redis")
        return True
    ttl = ttl_seconds or get_settings().redis.lock_ttl_seconds
    family = _lock_family(key)
    try:
        acquired = bool(client.set(key, value, nx=True, ex=ttl))
        increment_counter(f"lock.acquire.{family}.{'success' if acquired else 'fail'}")
        return acquired
    except Exception:
        increment_counter(f"lock.acquire.{family}.error")
        return False


async def async_acquire_lock(key: str, value: str, ttl_seconds: int | None = None) -> bool:
    client = get_async_redis_client()
    if client is None:
        await async_increment_counter("lock.acquire.no_redis")
        return True
    ttl = ttl_seconds or get_settings().redis.lock_ttl_seconds
    family = _lock_family(key)
    try:
        acquired = bool(await client.set(key, value, nx=True, ex=ttl))
        await async_increment_counter(f"lock.acquire.{family}.{'success' if acquired else 'fail'}")
        return acquired
    except Exception:
        await async_increment_counter(f"lock.acquire.{family}.error")
        return False


def release_lock(key: str, value: str) -> None:
    client = get_redis_client()
    if client is None:
        increment_counter("lock.release.no_redis")
        return
    family = _lock_family(key)
    try:
        released = int(client.eval(_RELEASE_LOCK_SCRIPT, 1, key, value) or 0)
        increment_counter(f"lock.release.{family}.{'success' if released else 'miss'}")
    except Exception:
        increment_counter(f"lock.release.{family}.error")
        return


async def async_release_lock(key: str, value: str) -> None:
    client = get_async_redis_client()
    if client is None:
        await async_increment_counter("lock.release.no_redis")
        return
    family = _lock_family(key)
    try:
        released = int(await client.eval(_RELEASE_LOCK_SCRIPT, 1, key, value) or 0)
        await async_increment_counter(f"lock.release.{family}.{'success' if released else 'miss'}")
    except Exception:
        await async_increment_counter(f"lock.release.{family}.error")
        return
