import time

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from .jwt import decode_access_token
from ..services.cache_service import (
    get_cached_auth_token_version,
    get_cached_user_profile,
    get_local_cached_user_profile,
    set_cached_auth_token_version,
    set_cached_user_profile,
    set_local_cached_user_profile_payload,
)
from ..services.lock_service import acquire_lock, build_lock_value, release_lock
from ..models import User

AUTH_REBUILD_WAIT_SECONDS = 0.05
AUTH_REBUILD_MAX_RETRIES = 3


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return token


def _decode_identity(token: str) -> tuple[int, int]:
    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Not authenticated") from exc

    try:
        user_id = int(payload["sub"])
        auth_version = int(payload["auth_version"])
    except (TypeError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=401, detail="Not authenticated") from exc
    return user_id, auth_version


def _build_user_from_cached_profile(cached_profile: dict, *, auth_version: int) -> User:
    return User(
        id=int(cached_profile["id"]),
        username=str(cached_profile.get("username") or ""),
        email=str(cached_profile.get("email") or ""),
        password_hash="",
        is_superuser=bool(cached_profile.get("is_superuser", False)),
        auth_token_version=auth_version,
    )


def _auth_rebuild_lock_key(user_id: int) -> str:
    settings = get_settings()
    return f"{settings.redis.prefix}:cache:rebuild:user:{user_id}:auth"


def _load_user_from_profile_cache(user_id: int, auth_version: int) -> User | None:
    local_profile = get_local_cached_user_profile(user_id)
    if local_profile:
        return _build_user_from_cached_profile(local_profile, auth_version=auth_version)

    cached_profile = get_cached_user_profile(user_id)
    if cached_profile:
        set_local_cached_user_profile_payload(cached_profile)
        return _build_user_from_cached_profile(cached_profile, auth_version=auth_version)
    return None


def _load_current_user(token: str, db: Session, *, use_cache: bool) -> User:
    user_id, auth_version = _decode_identity(token)
    if use_cache:
        cached_auth_version = get_cached_auth_token_version(user_id)
        if cached_auth_version is not None and cached_auth_version != auth_version:
            raise HTTPException(status_code=401, detail="Not authenticated")
        if cached_auth_version is not None:
            cached_user = _load_user_from_profile_cache(user_id, auth_version)
            if cached_user is not None:
                return cached_user
        lock_key = _auth_rebuild_lock_key(user_id)
        lock_value = build_lock_value()
        if acquire_lock(lock_key, lock_value):
            try:
                cached_auth_version = get_cached_auth_token_version(user_id)
                if cached_auth_version is not None and cached_auth_version != auth_version:
                    raise HTTPException(status_code=401, detail="Not authenticated")
                if cached_auth_version is not None:
                    cached_user = _load_user_from_profile_cache(user_id, auth_version)
                    if cached_user is not None:
                        return cached_user
                user = db.get(User, user_id)
                if not user or user.auth_token_version != auth_version:
                    raise HTTPException(status_code=401, detail="Not authenticated")
                set_cached_auth_token_version(user.id, user.auth_token_version)
                set_cached_user_profile(user)
                return user
            finally:
                release_lock(lock_key, lock_value)
        else:
            for _ in range(AUTH_REBUILD_MAX_RETRIES):
                time.sleep(AUTH_REBUILD_WAIT_SECONDS)
                cached_auth_version = get_cached_auth_token_version(user_id)
                if cached_auth_version is None:
                    continue
                if cached_auth_version != auth_version:
                    raise HTTPException(status_code=401, detail="Not authenticated")
                cached_user = _load_user_from_profile_cache(user_id, auth_version)
                if cached_user is not None:
                    return cached_user
    user = db.get(User, user_id)
    if not user or user.auth_token_version != auth_version:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if use_cache:
        set_cached_auth_token_version(user.id, user.auth_token_version)
        set_cached_user_profile(user)
    return user


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    token = _extract_bearer_token(authorization)
    return _load_current_user(token, db, use_cache=True)


def get_current_user_optional(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User | None:
    if not authorization:
        return None
    token = _extract_bearer_token(authorization)
    return _load_current_user(token, db, use_cache=True)


def get_current_user_strict(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    token = _extract_bearer_token(authorization)
    return _load_current_user(token, db, use_cache=False)
