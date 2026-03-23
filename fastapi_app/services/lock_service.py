from __future__ import annotations

import secrets

from ..core.config import get_settings
from ..core.redis import get_redis_client


_RELEASE_LOCK_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""


def build_lock_value() -> str:
    return secrets.token_hex(16)


def acquire_lock(key: str, value: str, ttl_seconds: int | None = None) -> bool:
    client = get_redis_client()
    if client is None:
        return True
    ttl = ttl_seconds or get_settings().redis.lock_ttl_seconds
    try:
        return bool(client.set(key, value, nx=True, ex=ttl))
    except Exception:
        return False


def release_lock(key: str, value: str) -> None:
    client = get_redis_client()
    if client is None:
        return
    try:
        client.eval(_RELEASE_LOCK_SCRIPT, 1, key, value)
    except Exception:
        return
