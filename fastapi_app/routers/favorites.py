import time

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.database import get_db
from ..core.deps import get_current_user
from ..models import User, UserCollectedBook
from ..repositories.book_repository import get_book
from ..repositories.favorite_repository import list_favorite_book_ids, list_favorite_books
from ..services.book_service import book_to_summary
from ..services.cache_service import (
    delete_cached_favorite_ids,
    get_cached_favorite_status,
    set_cached_favorite_ids,
)
from ..services.lock_service import acquire_lock, build_lock_value, release_lock

router = APIRouter(tags=["favorites"])
FAVORITE_REBUILD_WAIT_SECONDS = 0.05
FAVORITE_REBUILD_MAX_RETRIES = 3


def _favorite_rebuild_lock_key(user_id: int) -> str:
    settings = get_settings()
    return f"{settings.redis.prefix}:cache:rebuild:user:{user_id}:favorite_ids"


@router.post("/api/users/me/favorites/{book_id}")
def add_favorite(
    book_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = get_book(db, book_id)
    if not book:
        return JSONResponse({"success": False, "message": "?????"}, status_code=404)

    db.add(UserCollectedBook(user_id=current_user.id, book_id=book_id))
    try:
        db.commit()
        delete_cached_favorite_ids(current_user.id)
        return {"success": True, "message": "??????"}
    except IntegrityError:
        db.rollback()
        delete_cached_favorite_ids(current_user.id)
        return {"success": True, "message": "????????"}


@router.delete("/api/users/me/favorites/{book_id}")
def remove_favorite(
    book_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(UserCollectedBook).filter(
        UserCollectedBook.user_id == current_user.id,
        UserCollectedBook.book_id == book_id,
    ).delete()
    db.commit()
    delete_cached_favorite_ids(current_user.id)
    return {"success": True, "message": "?????"}


@router.get("/api/users/me/favorites/{book_id}")
def get_favorite_status(
    book_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cached = get_cached_favorite_status(current_user.id, book_id)
    if cached is not None:
        return {"isFavorited": cached}

    lock_key = _favorite_rebuild_lock_key(current_user.id)
    lock_value = build_lock_value()
    if acquire_lock(lock_key, lock_value):
        try:
            cached = get_cached_favorite_status(current_user.id, book_id)
            if cached is not None:
                return {"isFavorited": cached}

            favorite_ids = list_favorite_book_ids(db, current_user.id)
            set_cached_favorite_ids(current_user.id, favorite_ids)
        finally:
            release_lock(lock_key, lock_value)
    else:
        favorite_ids = None
        for _ in range(FAVORITE_REBUILD_MAX_RETRIES):
            time.sleep(FAVORITE_REBUILD_WAIT_SECONDS)
            cached = get_cached_favorite_status(current_user.id, book_id)
            if cached is not None:
                return {"isFavorited": cached}
        if favorite_ids is None:
            favorite_ids = list_favorite_book_ids(db, current_user.id)
            set_cached_favorite_ids(current_user.id, favorite_ids)
    exists = book_id in set(favorite_ids)
    return {"isFavorited": exists}


@router.get("/api/users/me/favorites")
def list_favorites(
    page: int = 1,
    pageSize: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    effective_page_size = pageSize or settings.pagination.default_page_size
    if page < 1 or effective_page_size < 1 or effective_page_size > settings.pagination.max_page_size:
        return JSONResponse({"success": False, "message": "分页参数不合法"}, status_code=400)

    rows = list_favorite_books(db, current_user.id, page, effective_page_size)
    set_cached_favorite_ids(current_user.id, list_favorite_book_ids(db, current_user.id))
    return {
        "page": page,
        "pageSize": effective_page_size,
        "favorites": [book_to_summary(book) for book in rows],
    }
