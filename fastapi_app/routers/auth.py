from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.deps import get_current_user, get_current_user_strict
from ..core.jwt import create_access_token
from ..core.security import hash_password, verify_password
from ..models import User
from ..repositories.user_repository import get_user_by_username
from ..services.cache_service import (
    delete_cached_auth_token_version,
    delete_cached_user_profile,
    set_cached_auth_token_version,
    set_cached_user_profile,
)
from ..services.captcha_service import (
    generate_captcha_payload,
    is_captcha_enabled,
    render_captcha_image,
    validate_captcha,
)

router = APIRouter(tags=["auth"])


@router.get("/api/auth/captcha")
def generate_captcha() -> dict:
    return generate_captcha_payload()


@router.get("/api/auth/captcha/{captcha_key}/image")
def get_captcha_image(captcha_key: str) -> Response:
    png = render_captcha_image(captcha_key)
    if not png:
        raise HTTPException(status_code=404, detail="Captcha expired")
    return Response(content=png, media_type="image/png")


@router.post("/api/auth/register")
def register(
    username: str = Form(...),
    email: str = Form(""),
    password: str = Form(...),
    captcha_key: str = Form(""),
    captcha_value: str = Form(""),
    db: Session = Depends(get_db),
):
    if not validate_captcha(captcha_key, captcha_value, consume=True):
        return JSONResponse({"success": False, "message": "??????"})

    exists = get_user_by_username(db, username)
    if exists:
        return JSONResponse({"success": False, "message": "??????"})

    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        is_superuser=False,
    )
    db.add(user)
    db.commit()
    return {"success": True, "message": "????"}


@router.post("/api/auth/login")
def login(
    username: str = Form(...),
    password: str = Form(...),
    captcha_key: str = Form(""),
    captcha_value: str = Form(""),
    db: Session = Depends(get_db),
):
    if not validate_captcha(captcha_key, captcha_value, consume=True):
        return JSONResponse({"success": False, "error": "?????"})

    user = get_user_by_username(db, username)
    if not user or not verify_password(password, user.password_hash):
        return JSONResponse({"success": False, "error": "Invalid credentials"})
    set_cached_auth_token_version(user.id, user.auth_token_version)
    set_cached_user_profile(user)

    return {
        "success": True,
        "access_token": create_access_token(user),
        "token_type": "bearer",
    }

@router.get("/api/auth/me")
def get_current_auth(current_user: User = Depends(get_current_user)):
    return {
        "isLoggedIn": True,
        "captchaEnabled": is_captcha_enabled(),
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "is_superuser": current_user.is_superuser,
        },
    }


@router.put("/api/users/me/password")
def change_password(
    current_password: str = Form(...),
    new_password: str = Form(...),
    current_user: User = Depends(get_current_user_strict),
    db: Session = Depends(get_db),
):
    if not verify_password(current_password, current_user.password_hash):
        return JSONResponse({"success": False, "message": "???????"}, status_code=400)

    current_user.password_hash = hash_password(new_password)
    current_user.auth_token_version += 1
    db.add(current_user)
    db.commit()
    delete_cached_auth_token_version(current_user.id)
    delete_cached_user_profile(current_user.id)
    return {"success": True, "message": "?????"}
