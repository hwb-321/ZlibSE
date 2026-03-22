from __future__ import annotations

import json
from urllib.parse import quote_plus

from ..core.config import get_settings
from ..core.redis import get_redis_client
from ..models import StoredFile


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


def get_books_cache_version() -> int:
    client = _get_client()
    if client is None:
        return 1
    key = _key("books", "version")
    try:
        value = client.get(key)
        if value is None:
            client.set(key, "1")
            return 1
        return max(1, int(value))
    except Exception:
        return 1


def bump_books_cache_version() -> int:
    client = _get_client()
    if client is None:
        return 1
    key = _key("books", "version")
    try:
        return int(client.incr(key))
    except Exception:
        return 1


def build_book_list_cache_key(page: int, page_size: int) -> tuple[object, ...]:
    version = get_books_cache_version()
    return ("books", "list", f"v{version}", f"page={page}", f"size={page_size}")


def build_book_search_cache_key(query: str) -> tuple[object, ...]:
    version = get_books_cache_version()
    return ("books", "search", f"v{version}", f"q={quote_plus(query)}")


def build_book_detail_cache_key(book_id: int) -> tuple[object, ...]:
    version = get_books_cache_version()
    return ("books", "detail", f"v{version}", book_id)


def get_cached_token_version(user_id: int) -> int | None:
    client = _get_client()
    if client is None:
        return None
    try:
        value = client.get(_key("users", "token_version", user_id))
        return None if value is None else int(value)
    except Exception:
        return None


def set_cached_token_version(user_id: int, token_version: int) -> None:
    ttl = get_settings().redis.token_version_ttl_seconds
    client = _get_client()
    if client is None:
        return
    try:
        client.setex(_key("users", "token_version", user_id), ttl, str(token_version))
    except Exception:
        return


def delete_cached_token_version(user_id: int) -> None:
    delete_key("users", "token_version", user_id)


def build_file_meta_cache_key(file_id: int) -> tuple[object, ...]:
    return ("files", "meta", file_id)


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
    delete_key(*build_file_meta_cache_key(file_id))
