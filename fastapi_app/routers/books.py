import os
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.deps import get_current_user
from ..models import UploadedBook, User
from ..repositories.book_repository import count_books, get_book, list_books, search_books
from ..services.book_service import book_to_dict, build_book_detail, create_book_record

router = APIRouter(tags=["books"])


@router.post("/book/upload_book")
def upload_book(
    title: str = Form(...),
    author: str = Form(...),
    isbn: str = Form(...),
    category: str = Form(...),
    year: int = Form(...),
    language: str = Form(...),
    file_path: UploadFile = File(...),
    cover_image_path: UploadFile = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        book = create_book_record(
            title=title,
            author=author,
            isbn=isbn,
            category=category,
            year=year,
            language=language,
            file_path=file_path,
            cover_image_path=cover_image_path,
        )
    except ValueError as exc:
        return JSONResponse({"success": False, "message": str(exc)})

    db.add(book)
    db.flush()

    uploaded = UploadedBook(user_id=current_user.id, book_id=book.id)
    db.add(uploaded)
    db.commit()

    return {"success": True, "message": "????"}


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
        return JSONResponse({"error": "?????"}, status_code=404)
    return {"books": [book_to_dict(book) for book in books]}


@router.get("/book/cover/{book_id}")
def book_cover(book_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ = current_user
    book = get_book(db, book_id)
    if not book or not book.cover_image_path or not os.path.exists(book.cover_image_path):
        raise HTTPException(status_code=404, detail="???????")
    return FileResponse(book.cover_image_path)


@router.get("/book/get_descriptions/{book_id}")
def get_descriptions(book_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ = current_user
    book = get_book(db, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="?????")
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


@router.get("/book/download/{book_id}")
@router.get("/book/download/{book_id}.epub")
def download_book(book_id: int, db: Session = Depends(get_db)):
    book = get_book(db, book_id)
    if not book or not os.path.exists(book.file_path):
        raise HTTPException(status_code=404, detail="?????")

    ext = Path(book.file_path).suffix.lower()
    media_type = "application/epub+zip" if ext == ".epub" else "application/octet-stream"
    filename = f"{book.title}{ext}"
    return FileResponse(book.file_path, media_type=media_type, filename=filename)
