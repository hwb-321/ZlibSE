from __future__ import annotations

from functools import lru_cache

from .config import get_settings


@lru_cache(maxsize=1)
def get_redis_client():
    settings = get_settings()
    if not settings.redis.enabled:
        return None

    import redis

    return redis.Redis.from_url(settings.redis.url, decode_responses=True)
