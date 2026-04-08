from __future__ import annotations

import time
from threading import Lock

from ..core.config import get_settings
from ..core.redis import get_redis_client


_local_windows: dict[str, tuple[int, float]] = {}
_local_lock = Lock()


def _rate_limit_key(scope: str, identifier: str) -> str:
    prefix = get_settings().redis.prefix
    return f"{prefix}:rate_limit:{scope}:{identifier}"


def is_allowed(*, scope: str, identifier: str, max_requests: int, window_seconds: int) -> bool:
    client = get_redis_client()
    if client is not None:
        key = _rate_limit_key(scope, identifier)
        try:
            current = int(client.incr(key))
            if current == 1:
                client.expire(key, window_seconds)
            return current <= max_requests
        except Exception:
            return True

    now = time.time()
    local_key = f"{scope}:{identifier}"
    with _local_lock:
        count, expires_at = _local_windows.get(local_key, (0, now + window_seconds))
        if expires_at <= now:
            count = 0
            expires_at = now + window_seconds
        count += 1
        _local_windows[local_key] = (count, expires_at)
        return count <= max_requests
