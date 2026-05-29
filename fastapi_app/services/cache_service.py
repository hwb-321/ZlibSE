from __future__ import annotations

import json
import random
import time
from urllib.parse import quote_plus

from ..core.config import get_settings
from ..core.redis import get_async_redis_client, get_redis_client
from ..models import StoredFile, User
from .local_cache_service import local_cache

def _get_client():
    return get_redis_client()


def _get_async_client():
    return get_async_redis_client()


def _key(*parts: object) -> str:
    prefix = get_settings().redis.prefix
    suffix = ":".join(str(part) for part in parts)
    return f"{prefix}:{suffix}"


def _with_ttl_jitter(ttl_seconds: int) -> int:
    return max(1, ttl_seconds) + random.randint(5, 30)


def get_json(*parts: object):
    client = _get_client()
    if client is None:
        return None
    try:
        value = client.get(_key(*parts))
    except Exception:
        return None
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


async def async_get_json(*parts: object):
    client = _get_async_client()
    if client is None:
        return None
    try:
        value = await client.get(_key(*parts))
    except Exception:
        return None
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def set_json(*parts: object, value, ttl_seconds: int | None = None) -> None:
    client = _get_client()
    if client is None:
        return
    ttl = _with_ttl_jitter(ttl_seconds or get_settings().redis.default_ttl_seconds)
    try:
        client.setex(_key(*parts), ttl, json.dumps(value, ensure_ascii=False, separators=(",", ":")))
    except Exception:
        return


async def async_set_json(*parts: object, value, ttl_seconds: int | None = None) -> None:
    client = _get_async_client()
    if client is None:
        return
    ttl = _with_ttl_jitter(ttl_seconds or get_settings().redis.default_ttl_seconds)
    try:
        await client.setex(_key(*parts), ttl, json.dumps(value, ensure_ascii=False, separators=(",", ":")))
    except Exception:
        return


def delete_key(*parts: object) -> None:
    client = _get_client()
    if client is None:
        return
    try:
        client.delete(_key(*parts))
    except Exception:
        return


async def async_delete_key(*parts: object) -> None:
    client = _get_async_client()
    if client is None:
        return
    try:
        await client.delete(_key(*parts))
    except Exception:
        return


def delete_key_pattern(*parts: object) -> None:
    client = _get_client()
    if client is None:
        return
    pattern = _key(*parts)
    try:
        cursor = 0
        while True:
            cursor, keys = client.scan(cursor=cursor, match=pattern, count=100)
            if keys:
                client.delete(*keys)
            if cursor == 0:
                break
    except Exception:
        return


def build_book_list_cache_key(page: int, page_size: int) -> tuple[object, ...]:
    return ("books", "list", f"page={page}", f"size={page_size}")


def build_book_list_cursor_cache_key(last_id: int, page_size: int) -> tuple[object, ...]:
    return ("books", "list", f"cursor={last_id}", f"size={page_size}")


def build_book_search_cache_key(query: str, page: int, page_size: int) -> tuple[object, ...]:
    return ("books", "search", f"q={quote_plus(query)}", f"page={page}", f"size={page_size}")


def build_book_detail_cache_key(book_id: int) -> tuple[object, ...]:
    return ("book", book_id, "detail")


def build_book_count_cache_key() -> tuple[object, ...]:
    return ("books", "count")


def delete_cached_book_collection() -> None:
    local_cache.delete(":".join(str(part) for part in build_book_count_cache_key()))
    local_cache.delete_prefix("books:list:")
    local_cache.delete_prefix("books:search:")
    delete_key(*build_book_count_cache_key())
    delete_key_pattern("books", "list", "*")
    delete_key_pattern("books", "search", "*")


def delete_cached_book_detail(book_id: int) -> None:
    parts = build_book_detail_cache_key(book_id)
    local_cache.delete(":".join(str(part) for part in parts))
    delete_key(*parts)


def _user_auth_token_version_key(user_id: int) -> tuple[object, ...]:
    return ("user", user_id, "auth_token_version")


def _user_profile_key(user_id: int) -> tuple[object, ...]:
    return ("user", user_id, "profile")


def _local_user_profile_key(user_id: int) -> str:
    return ":".join(str(part) for part in _user_profile_key(user_id))


def get_cached_auth_token_version(user_id: int) -> int | None:
    client = _get_client()
    if client is None:
        return None
    try:
        value = client.get(_key(*_user_auth_token_version_key(user_id)))
        return None if value is None else int(value)
    except Exception:
        return None


async def async_get_cached_auth_token_version(user_id: int) -> int | None:
    client = _get_async_client()
    if client is None:
        return None
    try:
        value = await client.get(_key(*_user_auth_token_version_key(user_id)))
        return None if value is None else int(value)
    except Exception:
        return None


def set_cached_auth_token_version(user_id: int, auth_token_version: int) -> None:
    ttl = _with_ttl_jitter(get_settings().redis.auth_token_version_ttl_seconds)
    client = _get_client()
    if client is None:
        return
    try:
        client.setex(_key(*_user_auth_token_version_key(user_id)), ttl, str(auth_token_version))
    except Exception:
        return


async def async_set_cached_auth_token_version(user_id: int, auth_token_version: int) -> None:
    ttl = _with_ttl_jitter(get_settings().redis.auth_token_version_ttl_seconds)
    client = _get_async_client()
    if client is None:
        return
    try:
        await client.setex(_key(*_user_auth_token_version_key(user_id)), ttl, str(auth_token_version))
    except Exception:
        return


def delete_cached_auth_token_version(user_id: int) -> None:
    delete_key(*_user_auth_token_version_key(user_id))


def get_local_cached_user_profile(user_id: int) -> dict | None:
    cached = local_cache.get(_local_user_profile_key(user_id))
    return cached if isinstance(cached, dict) else None


def get_cached_user_profile(user_id: int) -> dict | None:
    client = _get_client()
    if client is None:
        return None
    try:
        value = client.get(_key(*_user_profile_key(user_id)))
    except Exception:
        return None
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


async def async_get_cached_user_profile(user_id: int) -> dict | None:
    client = _get_async_client()
    if client is None:
        return None
    try:
        value = await client.get(_key(*_user_profile_key(user_id)))
    except Exception:
        return None
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def set_local_cached_user_profile_payload(payload: dict) -> None:
    local_cache.set(
        _local_user_profile_key(int(payload["id"])),
        payload,
        get_settings().local_cache.default_ttl_seconds,
    )


def set_cached_user_profile(user: User) -> None:
    payload = {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_superuser": user.is_superuser,
    }
    ttl = get_settings().redis.user_profile_ttl_seconds
    set_json(*_user_profile_key(user.id), value=payload, ttl_seconds=ttl)
    set_local_cached_user_profile_payload(payload)


async def async_set_cached_user_profile(user: User) -> None:
    payload = {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_superuser": user.is_superuser,
    }
    ttl = get_settings().redis.user_profile_ttl_seconds
    await async_set_json(*_user_profile_key(user.id), value=payload, ttl_seconds=ttl)
    set_local_cached_user_profile_payload(payload)


def delete_cached_user_profile(user_id: int) -> None:
    local_cache.delete(_local_user_profile_key(user_id))
    delete_key(*_user_profile_key(user_id))


def build_file_meta_cache_key(file_id: int) -> tuple[object, ...]:
    return ("files", "meta", file_id)


def build_download_url_cache_key(file_id: int) -> tuple[object, ...]:
    return ("files", "download_url", file_id)


def _download_hot_window_key(file_id: int) -> tuple[object, ...]:
    return ("files", "download_hot_window", file_id)


def _local_download_url_key(file_id: int) -> str:
    return ":".join(str(part) for part in build_download_url_cache_key(file_id))


def _download_url_local_ttl_seconds() -> int:
    settings = get_settings()
    return max(1, min(10, settings.download_cache.hot_signed_url_ttl_seconds))


def serialize_file_meta(stored_file: StoredFile) -> dict:
    return {
        "id": stored_file.id,
        "bucket": stored_file.bucket,
        "region": stored_file.region,
        "object_key": stored_file.object_key,
        "original_filename": stored_file.original_filename,
        "content_type": stored_file.content_type,
        "size": stored_file.size,
        "etag": stored_file.etag,
        "kind": stored_file.kind,
    }


def set_cached_public_file_meta(stored_file: StoredFile) -> None:
    ttl = get_settings().redis.file_meta_ttl_seconds
    set_json(*build_file_meta_cache_key(stored_file.id), value=serialize_file_meta(stored_file), ttl_seconds=ttl)


def delete_cached_public_file_meta(file_id: int | None) -> None:
    if file_id is None:
        return
    local_cache.delete(":".join(str(part) for part in build_file_meta_cache_key(file_id)))
    local_cache.delete(_local_download_url_key(file_id))
    delete_key(*build_file_meta_cache_key(file_id))
    delete_key(*build_download_url_cache_key(file_id))


def get_local_cached_download_url_payload(file_id: int) -> dict | None:
    cached = local_cache.get(_local_download_url_key(file_id))
    return cached if isinstance(cached, dict) else None


def set_local_cached_download_url_payload(file_id: int, payload: dict) -> None:
    local_cache.set(_local_download_url_key(file_id), payload, _download_url_local_ttl_seconds())


def get_cached_download_url_payload(file_id: int) -> dict | None:
    payload = get_json(*build_download_url_cache_key(file_id))
    return payload if isinstance(payload, dict) else None


async def async_get_cached_download_url_payload(file_id: int) -> dict | None:
    payload = await async_get_json(*build_download_url_cache_key(file_id))
    return payload if isinstance(payload, dict) else None


def set_cached_download_url_payload(file_id: int, payload: dict) -> None:
    ttl = get_settings().download_cache.hot_signed_url_ttl_seconds
    set_json(*build_download_url_cache_key(file_id), value=payload, ttl_seconds=ttl)
    set_local_cached_download_url_payload(file_id, payload)


async def async_set_cached_download_url_payload(file_id: int, payload: dict) -> None:
    ttl = get_settings().download_cache.hot_signed_url_ttl_seconds
    await async_set_json(*build_download_url_cache_key(file_id), value=payload, ttl_seconds=ttl)
    set_local_cached_download_url_payload(file_id, payload)


def track_download_hot_access(file_id: int) -> int:
    client = _get_client()
    if client is None:
        return 0
    key = _key(*_download_hot_window_key(file_id))
    window_seconds = get_settings().download_cache.hot_window_seconds
    now = time.time()
    member = str(time.time_ns())
    try:
        client.zadd(key, {member: now})
        client.zremrangebyscore(key, 0, now - window_seconds)
        client.expire(key, window_seconds + 5)
        return int(client.zcard(key))
    except Exception:
        return 0


async def async_track_download_hot_access(file_id: int) -> int:
    client = _get_async_client()
    if client is None:
        return 0
    key = _key(*_download_hot_window_key(file_id))
    window_seconds = get_settings().download_cache.hot_window_seconds
    now = time.time()
    member = str(time.time_ns())
    try:
        await client.zadd(key, {member: now})
        await client.zremrangebyscore(key, 0, now - window_seconds)
        await client.expire(key, window_seconds + 5)
        return int(await client.zcard(key))
    except Exception:
        return 0


def _cover_set_key(user_id: int) -> tuple[object, ...]:
    return ("users", "cover_unbound_ids", user_id)


def get_unbound_cover_ids_count(user_id: int) -> int:
    client = _get_client()
    if client is None:
        return 0
    try:
        return int(client.scard(_key(*_cover_set_key(user_id))))
    except Exception:
        return 0


def add_unbound_cover_id(user_id: int, file_id: int) -> None:
    client = _get_client()
    if client is None:
        return
    try:
        client.sadd(_key(*_cover_set_key(user_id)), str(file_id))
    except Exception:
        return


def remove_unbound_cover_id(user_id: int | None, file_id: int | None) -> None:
    if user_id is None or file_id is None:
        return
    client = _get_client()
    if client is None:
        return
    try:
        client.srem(_key(*_cover_set_key(user_id)), str(file_id))
    except Exception:
        return


def _favorite_ids_key(user_id: int) -> tuple[object, ...]:
    return ("user", user_id, "favorite_ids")


def _local_favorite_ids_key(user_id: int) -> str:
    return ":".join(str(part) for part in _favorite_ids_key(user_id))


def get_local_cached_favorite_ids_payload(user_id: int) -> dict | None:
    cached = local_cache.get(_local_favorite_ids_key(user_id))
    return cached if isinstance(cached, dict) else None


def get_cached_favorite_ids_payload(user_id: int) -> dict | None:
    client = _get_client()
    if client is None:
        return None
    try:
        value = client.get(_key(*_favorite_ids_key(user_id)))
    except Exception:
        return None
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def set_local_cached_favorite_ids_payload(payload: dict) -> None:
    local_cache.set(
        _local_favorite_ids_key(int(payload["user_id"])),
        payload,
        get_settings().local_cache.default_ttl_seconds,
    )


def set_cached_favorite_ids_payload(payload: dict) -> None:
    ttl = get_settings().redis.favorite_set_ttl_seconds
    set_json(*_favorite_ids_key(int(payload["user_id"])), value=payload, ttl_seconds=ttl)
    set_local_cached_favorite_ids_payload(payload)


def get_cached_favorite_status(user_id: int, book_id: int) -> bool | None:
    local_payload = get_local_cached_favorite_ids_payload(user_id)
    if local_payload:
        return book_id in set(int(item) for item in local_payload.get("book_ids", []))

    cached_payload = get_cached_favorite_ids_payload(user_id)
    if cached_payload:
        set_local_cached_favorite_ids_payload(cached_payload)
        return book_id in set(int(item) for item in cached_payload.get("book_ids", []))
    return None


def set_cached_favorite_ids(user_id: int, book_ids: list[int]) -> None:
    payload = {
        "user_id": user_id,
        "book_ids": book_ids,
    }
    set_cached_favorite_ids_payload(payload)


def delete_cached_favorite_ids(user_id: int) -> None:
    local_cache.delete(_local_favorite_ids_key(user_id))
    delete_key(*_favorite_ids_key(user_id))
