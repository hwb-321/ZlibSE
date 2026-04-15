from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.database import get_db
from ..core.deps import get_current_user
from ..models import UploadedBook, User, UserCollectedBook
from ..repositories.book_repository import get_book
from ..repositories.upload_repository import get_upload_relation, list_uploaded_books
from ..services.cache_service import (
    delete_cached_book_collection,
    delete_cached_book_detail,
    delete_cached_favorite_ids,
    delete_cached_public_file_meta,
)
from ..services.book_service import book_to_summary, delete_book_files

router = APIRouter(tags=["uploads"])


@router.get("/api/users/me/uploads")
def list_uploaded_books_view(
    page: int = 1,
    pageSize: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    effective_page_size = pageSize or settings.pagination.default_page_size
    if page < 1 or effective_page_size < 1 or effective_page_size > settings.pagination.max_page_size:
        return JSONResponse({"success": False, "message": "分页参数不合法"}, status_code=400)

    books = list_uploaded_books(db, current_user.id, current_user.is_superuser, page, effective_page_size)
    return {
        "page": page,
        "pageSize": effective_page_size,
        "uploadedBooks": [book_to_summary(book) for book in books],
    }


@router.delete("/api/users/me/uploads/{book_id}")
def delete_uploaded_book_entry(
    book_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = get_book(db, book_id)
    if not book:
        return JSONResponse({"success": False, "message": "书籍不存在"}, status_code=404)

    if not current_user.is_superuser:
        own_upload = get_upload_relation(db, current_user.id, book_id)
        if not own_upload:
            return JSONResponse({"success": False, "message": "无权删除此书籍"}, status_code=403)

    book_file_id = book.book_file_id
    cover_file_id = book.cover_file_id
    favorite_user_ids = [user_id for (user_id,) in db.query(UserCollectedBook.user_id).filter(UserCollectedBook.book_id == book_id).all()]
    db.query(UserCollectedBook).filter(UserCollectedBook.book_id == book_id).delete()
    db.query(UploadedBook).filter(UploadedBook.book_id == book_id).delete()
    delete_book_files(db, book)
    db.delete(book)
    db.commit()
    delete_cached_book_collection()
    delete_cached_book_detail(book_id)
    delete_cached_public_file_meta(book_file_id)
    delete_cached_public_file_meta(cover_file_id)
    for favorite_user_id in favorite_user_ids:
        delete_cached_favorite_ids(favorite_user_id)
    return {"success": True, "message": "书籍及相关文件已删除"}
