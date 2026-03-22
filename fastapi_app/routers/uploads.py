from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.deps import get_current_user
from ..models import UploadedBook, User, UserCollectedBook
from ..repositories.book_repository import get_book
from ..repositories.upload_repository import get_upload_relation, list_uploaded_books
from ..services.cache_service import bump_books_cache_version, delete_cached_public_file_meta
from ..services.book_service import book_to_dict, delete_book_files

router = APIRouter(tags=["uploads"])


@router.get("/user/get_upload_book_list")
def get_upload_book_list(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    books = list_uploaded_books(db, current_user.id, current_user.is_superuser)
    return {"uploadedBooks": [book_to_dict(book) for book in books]}


@router.post("/user/delete_uploaded_book/{book_id}")
def delete_uploaded_book(
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
    db.query(UserCollectedBook).filter(UserCollectedBook.book_id == book_id).delete()
    db.query(UploadedBook).filter(UploadedBook.book_id == book_id).delete()
    delete_book_files(db, book)
    db.delete(book)
    db.commit()
    bump_books_cache_version()
    delete_cached_public_file_meta(book_file_id)
    delete_cached_public_file_meta(cover_file_id)
    return {"success": True, "message": "书籍及相关文件已删除"}
