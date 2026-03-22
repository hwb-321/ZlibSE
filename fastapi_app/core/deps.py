from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .database import get_db
from .jwt import decode_access_token
from ..services.cache_service import get_cached_token_version, set_cached_token_version
from ..models import User


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
        token_version = int(payload["ver"])
    except (TypeError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=401, detail="Not authenticated") from exc
    return user_id, token_version


def _load_current_user(token: str, db: Session, *, use_cache: bool) -> User:
    user_id, token_version = _decode_identity(token)
    if use_cache:
        cached_token_version = get_cached_token_version(user_id)
        if cached_token_version is not None and cached_token_version != token_version:
            raise HTTPException(status_code=401, detail="Not authenticated")
    user = db.get(User, user_id)
    if not user or user.token_version != token_version:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if use_cache:
        set_cached_token_version(user.id, user.token_version)
    return user


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    token = _extract_bearer_token(authorization)
    return _load_current_user(token, db, use_cache=True)


def get_current_user_strict(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    token = _extract_bearer_token(authorization)
    return _load_current_user(token, db, use_cache=False)
