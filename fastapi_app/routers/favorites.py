from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.deps import get_current_user
from ..models import User, UserCollectedBook
from ..repositories.book_repository import get_book
from ..repositories.favorite_repository import get_favorite_relation, list_favorite_books
from ..services.book_service import book_to_dict

router = APIRouter(tags=["favorites"])


@router.post("/user/add_to_favorites/{book_id}")
def add_to_favorites(
    book_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = get_book(db, book_id)
    if not book:
        return JSONResponse({"success": False, "message": "?????"}, status_code=404)

    exists = get_favorite_relation(db, current_user.id, book_id)
    if exists:
        return {"success": False, "message": "????????"}

    db.add(UserCollectedBook(user_id=current_user.id, book_id=book_id))
    db.commit()
    return {"success": True, "message": "??????"}


@router.post("/user/remove_from_favorites/{book_id}")
def remove_from_favorites(
    book_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    relation = get_favorite_relation(db, current_user.id, book_id)
    if not relation:
        return {"success": False, "message": "?????"}

    db.delete(relation)
    db.commit()
    return {"success": True, "message": "?????"}


@router.get("/user/check_favorite/{book_id}")
def check_favorite(
    book_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    exists = get_favorite_relation(db, current_user.id, book_id) is not None
    return {"isFavorited": exists}


@router.get("/user/favorites")
def get_favorites(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = list_favorite_books(db, current_user.id)
    return {"favorites": [book_to_dict(book) for book in rows]}
