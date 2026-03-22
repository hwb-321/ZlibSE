from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .database import get_db
from .jwt import decode_access_token
from ..models import User


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return token


def _load_current_user(token: str, db: Session) -> User:
    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Not authenticated") from exc

    try:
        user_id = int(payload["sub"])
        token_version = int(payload["ver"])
    except (TypeError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=401, detail="Not authenticated") from exc

    user = db.get(User, user_id)
    if not user or user.token_version != token_version:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    token = _extract_bearer_token(authorization)
    return _load_current_user(token, db)


def get_current_user_strict(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    token = _extract_bearer_token(authorization)
    return _load_current_user(token, db)
