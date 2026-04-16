from __future__ import annotations

import base64
import json
import time
from typing import Any

from config_loader import load_jwt_cache, save_jwt_cache


def _decode_exp(token: str) -> int | None:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload = parts[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload.encode("utf-8")).decode("utf-8"))
        exp = data.get("exp")
        return int(exp) if exp is not None else None
    except Exception:
        return None


def _cache_key(base_url: str, username: str) -> str:
    return f"{base_url.rstrip('/')}::{username}"


def get_valid_token(base_url: str, username: str, *, min_remaining_seconds: int = 60) -> str | None:
    cache = load_jwt_cache()
    entry = cache.get(_cache_key(base_url, username))
    if not isinstance(entry, dict):
        return None
    token = entry.get("access_token")
    exp = entry.get("exp")
    if not isinstance(token, str) or not token:
        return None
    if not isinstance(exp, int):
        exp = _decode_exp(token)
        if exp is None:
            return None
    if exp <= int(time.time()) + int(min_remaining_seconds):
        return None
    return token


def set_token(base_url: str, username: str, token: str) -> None:
    cache = load_jwt_cache()
    cache[_cache_key(base_url, username)] = {
        "access_token": token,
        "exp": _decode_exp(token),
        "updated_at": int(time.time()),
    }
    save_jwt_cache(cache)


def prune_cache() -> None:
    cache = load_jwt_cache()
    now = int(time.time())
    pruned: dict[str, Any] = {}
    for key, entry in cache.items():
        if not isinstance(entry, dict):
            continue
        token = entry.get("access_token")
        exp = entry.get("exp")
        if not isinstance(token, str) or not token:
            continue
        if not isinstance(exp, int):
            exp = _decode_exp(token)
        if isinstance(exp, int) and exp > now + 60:
            pruned[key] = {
                "access_token": token,
                "exp": exp,
                "updated_at": int(entry.get("updated_at", now)),
            }
    save_jwt_cache(pruned)
