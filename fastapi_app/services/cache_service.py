from __future__ import annotations

import json
from urllib.parse import quote_plus

from ..core.config import get_settings
from ..core.redis import get_redis_client
from ..models import StoredFile, User
from .local_cache_service import local_cache
from .metrics_service import record_timing_metric
import time

def _get_client():
    return get_redis_client()


def _key(*parts: object) -> str:
    prefix = get_settings().redis.prefix
    suffix = ":".join(str(part) for part in parts)
    return f"{prefix}:{suffix}"


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


def set_json(*parts: object, value, ttl_seconds: int | None = None) -> None:
    client = _get_client()
    if client is None:
        return
    ttl = ttl_seconds or get_settings().redis.default_ttl_seconds
    try:
        client.setex(_key(*parts), ttl, json.dumps(value, ensure_ascii=False, separators=(",", ":")))
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


def get_book_cache_version() -> int:
    start = time.perf_counter()
    client = _get_client()
    if client is None:
        record_timing_metric("books.version_read_ms", (time.perf_counter() - start) * 1000.0)
        return 1
    key = _key("books", "cache_version")
    try:
        value = client.get(key)
        if value is None:
            client.set(key, "1")
            record_timing_metric("books.version_read_ms", (time.perf_counter() - start) * 1000.0)
            return 1
        result = max(1, int(value))
        record_timing_metric("books.version_read_ms", (time.perf_counter() - start) * 1000.0)
        return result
    except Exception:
        record_timing_metric("books.version_read_ms", (time.perf_counter() - start) * 1000.0)
        return 1


def bump_book_cache_version() -> int:
    client = _get_client()
    if client is None:
        return 1
    key = _key("books", "cache_version")
    try:
        return int(client.incr(key))
    except Exception:
        return 1


def build_book_list_cache_key(page: int, page_size: int) -> tuple[object, ...]:
    version = get_book_cache_version()
    return ("books", "list", f"v{version}", f"page={page}", f"size={page_size}")


def build_book_search_cache_key(query: str, page: int, page_size: int) -> tuple[object, ...]:
    version = get_book_cache_version()
    return ("books", "search", f"v{version}", f"q={quote_plus(query)}", f"page={page}", f"size={page_size}")


def get_book_detail_cache_version(book_id: int) -> int:
    client = _get_client()
    if client is None:
        return 1
    key = _key("book", book_id, "detail_cache_version")
    try:
        value = client.get(key)
        if value is None:
            client.set(key, "1")
            return 1
        return max(1, int(value))
    except Exception:
        return 1


def bump_book_detail_cache_version(book_id: int) -> int:
    client = _get_client()
    if client is None:
        return 1
    key = _key("book", book_id, "detail_cache_version")
    try:
        return int(client.incr(key))
    except Exception:
        return 1


def build_book_detail_cache_key(book_id: int) -> tuple[object, ...]:
    version = get_book_detail_cache_version(book_id)
    return ("book", book_id, "detail", f"v{version}")


def build_book_count_cache_key() -> tuple[object, ...]:
    version = get_book_cache_version()
    return ("books", "count", f"v{version}")


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


def set_cached_auth_token_version(user_id: int, auth_token_version: int) -> None:
    ttl = get_settings().redis.auth_token_version_ttl_seconds
    client = _get_client()
    if client is None:
        return
    try:
        client.setex(_key(*_user_auth_token_version_key(user_id)), ttl, str(auth_token_version))
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
        "auth_token_version": user.auth_token_version,
    }
    set_local_cached_user_profile_payload(payload)
    client = _get_client()
    if client is None:
        return
    ttl = get_settings().redis.user_profile_ttl_seconds
    try:
        client.setex(_key(*_user_profile_key(user.id)), ttl, json.dumps(payload, ensure_ascii=False))
    except Exception:
        return


def delete_cached_user_profile(user_id: int) -> None:
    local_cache.delete(_local_user_profile_key(user_id))
    delete_key(*_user_profile_key(user_id))


def build_file_meta_cache_key(file_id: int) -> tuple[object, ...]:
    return ("files", "meta", file_id)


def build_download_url_cache_key(file_id: int) -> tuple[object, ...]:
    return ("files", "download_url", file_id)


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
    delete_key(*build_file_meta_cache_key(file_id))
    delete_key(*build_download_url_cache_key(file_id))


def get_cached_download_url_payload(file_id: int) -> dict | None:
    payload = get_json(*build_download_url_cache_key(file_id))
    return payload if isinstance(payload, dict) else None


def set_cached_download_url_payload(file_id: int, payload: dict) -> None:
    ttl = get_settings().download_cache.hot_signed_url_ttl_seconds
    set_json(*build_download_url_cache_key(file_id), value=payload, ttl_seconds=ttl)


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


def _favorite_version_key(user_id: int) -> tuple[object, ...]:
    return ("user", user_id, "favorite_version")


def _favorite_ids_key(user_id: int) -> tuple[object, ...]:
    return ("user", user_id, "favorite_ids")


def _local_favorite_ids_key(user_id: int) -> str:
    return ":".join(str(part) for part in _favorite_ids_key(user_id))


def get_favorite_cache_version(user_id: int) -> int | None:
    client = _get_client()
    if client is None:
        return None
    try:
        value = client.get(_key(*_favorite_version_key(user_id)))
        if value is None:
            client.set(_key(*_favorite_version_key(user_id)), "1")
            return 1
        return max(1, int(value))
    except Exception:
        return None


def bump_favorite_cache_version(user_id: int) -> int | None:
    client = _get_client()
    if client is None:
        return None
    try:
        return int(client.incr(_key(*_favorite_version_key(user_id))))
    except Exception:
        return None


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
    set_local_cached_favorite_ids_payload(payload)
    client = _get_client()
    if client is None:
        return
    ttl = get_settings().redis.favorite_set_ttl_seconds
    try:
        client.setex(_key(*_favorite_ids_key(int(payload["user_id"]))), ttl, json.dumps(payload, ensure_ascii=False))
    except Exception:
        return


def get_cached_favorite_status(user_id: int, book_id: int) -> bool | None:
    version = get_favorite_cache_version(user_id)
    if version is None:
        return None

    local_payload = get_local_cached_favorite_ids_payload(user_id)
    if local_payload and int(local_payload.get("version", -1)) == version:
        return book_id in set(int(item) for item in local_payload.get("book_ids", []))

    cached_payload = get_cached_favorite_ids_payload(user_id)
    if cached_payload and int(cached_payload.get("version", -1)) == version:
        set_local_cached_favorite_ids_payload(cached_payload)
        return book_id in set(int(item) for item in cached_payload.get("book_ids", []))
    return None


def refresh_cached_favorite_ids(user_id: int, book_ids: list[int], *, bump_version: bool) -> None:
    if bump_version:
        version = bump_favorite_cache_version(user_id)
    else:
        version = get_favorite_cache_version(user_id)
    if version is None:
        return

    payload = {
        "user_id": user_id,
        "version": version,
        "book_ids": book_ids,
    }
    set_cached_favorite_ids_payload(payload)
