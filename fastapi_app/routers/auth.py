import time

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.deps import get_current_user
from ..core.security import hash_password, verify_password
from ..models import User
from ..repositories.user_repository import get_user_by_username
from ..services.captcha_service import (
    generate_captcha_payload,
    is_captcha_enabled,
    render_captcha_image,
    validate_captcha,
)

router = APIRouter(tags=["auth"])


@router.get("/user/init_csrf")
def init_csrf() -> dict:
    return {
        "detail": "CSRF cookie set",
        "captchaEnabled": is_captcha_enabled(),
    }


@router.get("/user/generate_captcha")
def generate_captcha() -> dict:
    return generate_captcha_payload()


@router.get("/user/captcha/image/{captcha_key}")
def get_captcha_image(captcha_key: str) -> Response:
    png = render_captcha_image(captcha_key)
    if not png:
        raise HTTPException(status_code=404, detail="Captcha expired")
    return Response(content=png, media_type="image/png")


@router.post("/user/register_user")
def register_user(
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


@router.post("/user/login_user")
def login_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    captcha_key: str = Form(""),
    captcha_value: str = Form(""),
    db: Session = Depends(get_db),
):
    if not validate_captcha(captcha_key, captcha_value, consume=True):
        return JSONResponse({"success": False, "error": "?????"})

    login_attempts = int(request.session.get("login_attempts", 0))
    last_attempt_ts = float(request.session.get("last_attempt_ts", 0.0))
    if login_attempts >= 5 and time.time() < last_attempt_ts + 60:
        return JSONResponse({"success": False, "error": "??????????????????"})

    user = get_user_by_username(db, username)
    if not user or not verify_password(password, user.password_hash):
        request.session["login_attempts"] = login_attempts + 1
        request.session["last_attempt_ts"] = time.time()
        return JSONResponse({"success": False, "error": "Invalid credentials"})

    request.session["user_id"] = user.id
    request.session["login_attempts"] = 0
    request.session["last_attempt_ts"] = 0.0
    return {"success": True}


@router.post("/user/logout_user")
def logout_user(request: Request):
    request.session.clear()
    return {"success": True}


@router.get("/user/check_session")
def check_session(request: Request):
    return {
        "isLoggedIn": bool(request.session.get("user_id")),
        "captchaEnabled": is_captcha_enabled(),
    }


@router.post("/user/change_password_user")
def change_password_user(
    current_password: str = Form(...),
    new_password: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(current_password, current_user.password_hash):
        return JSONResponse({"success": False, "message": "???????"}, status_code=400)

    current_user.password_hash = hash_password(new_password)
    db.add(current_user)
    db.commit()
    return {"success": True, "message": "?????"}
