from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.deps import get_current_user
from ..models import UploadedBook, User
from ..repositories.book_repository import count_books, get_book, list_books, search_books
from ..repositories.upload_repository import get_upload_relation
from ..services.book_service import (
    book_to_dict,
    build_book_detail,
    create_book_from_file_ids,
    update_book_from_file_ids,
)

router = APIRouter(tags=["books"])


class BookUpsertRequest(BaseModel):
    title: str
    author: str | None = None
    isbn: str | None = None
    category: str | None = None
    year: int | None = None
    language: str | None = None
    bookFileId: int
    coverFileId: int | None = None


@router.post("/api/books")
def create_book(
    payload: BookUpsertRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        book = create_book_from_file_ids(
            db=db,
            title=payload.title,
            author=payload.author,
            isbn=payload.isbn,
            category=payload.category,
            year=payload.year,
            language=payload.language,
            book_file_id=payload.bookFileId,
            cover_file_id=payload.coverFileId,
        )
    except ValueError as exc:
        db.rollback()
        return JSONResponse({"success": False, "message": str(exc)}, status_code=400)

    db.add(book)
    db.flush()
    db.add(UploadedBook(user_id=current_user.id, book_id=book.id))
    db.commit()
    db.refresh(book)
    return {"success": True, "book": book_to_dict(book)}


@router.put("/api/books/{book_id}")
def update_book(
    book_id: int,
    payload: BookUpsertRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = get_book(db, book_id)
    if not book:
        return JSONResponse({"success": False, "message": "书籍不存在"}, status_code=404)

    if not current_user.is_superuser:
        own_upload = get_upload_relation(db, current_user.id, book_id)
        if not own_upload:
            return JSONResponse({"success": False, "message": "无权修改此书籍"}, status_code=403)

    try:
        update_book_from_file_ids(
            db=db,
            book=book,
            title=payload.title,
            author=payload.author,
            isbn=payload.isbn,
            category=payload.category,
            year=payload.year,
            language=payload.language,
            book_file_id=payload.bookFileId,
            cover_file_id=payload.coverFileId,
        )
    except ValueError as exc:
        db.rollback()
        return JSONResponse({"success": False, "message": str(exc)}, status_code=400)

    db.add(book)
    db.commit()
    db.refresh(book)
    return {"success": True, "book": book_to_dict(book)}


@router.get("/book/count")
def count_book(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ = current_user
    return {"count": count_books(db)}


@router.get("/book/list")
def list_book(
    page: int = 1,
    pageSize: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = current_user
    if page < 1 or pageSize < 1:
        raise HTTPException(status_code=400, detail="Invalid page params")

    books = list_books(db, page, pageSize)
    if not books and page != 1:
        return JSONResponse({"error": "页面不存在"}, status_code=404)
    return {"books": [book_to_dict(book) for book in books]}


@router.get("/book/get_descriptions/{book_id}")
def get_descriptions(book_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ = current_user
    book = get_book(db, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")
    return build_book_detail(book)


@router.get("/book/search")
def book_search(
    query: str = "",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = current_user
    books = search_books(db, query)
    return {"query": query, "books": [book_to_dict(book) for book in books]}
