import os
from pathlib import Path

from fastapi import UploadFile

from ..core.paths import BOOKS_DIR, COVERS_DIR
from ..models import Book
from .storage_service import save_upload_file


def book_to_dict(book: Book) -> dict:
    return {
        "id": book.id,
        "title": book.title,
        "author": book.author,
        "isbn": book.isbn,
        "category": book.category,
        "year": book.year,
        "language": book.language,
        "file_type": book.file_type,
        "file_path": f"/media/books/{Path(book.file_path).name}" if book.file_path else "",
        "file_size": book.file_size,
        "cover_image_path": f"/media/covers/{Path(book.cover_image_path).name}" if book.cover_image_path else "",
    }


def build_book_detail(book: Book) -> dict:
    return {
        "title": book.title,
        "author": book.author,
        "isbn": book.isbn,
        "category": book.category,
        "year": book.year,
        "language": book.language,
        "file_type": book.file_type,
        "file_path": f"/media/books/{Path(book.file_path).name}" if book.file_path else "",
        "file_size": book.file_size,
        "cover_image_path": f"/media/covers/{Path(book.cover_image_path).name}" if book.cover_image_path else "",
    }


def create_book_record(
    title: str,
    author: str,
    isbn: str,
    category: str,
    year: int,
    language: str,
    file_path: UploadFile,
    cover_image_path: UploadFile | None,
) -> Book:
    file_bytes = file_path.file.read()
    file_path.file.seek(0)
    file_size = len(file_bytes)
    if file_size > 1024 * 1024 * 1024:
        raise ValueError("????????1GB")

    file_name, saved_file = save_upload_file(file_path, BOOKS_DIR)
    cover_saved = None
    if cover_image_path:
        _, cover_saved = save_upload_file(cover_image_path, COVERS_DIR)

    ext = Path(file_name).suffix.lstrip(".").lower()
    return Book(
        title=title,
        author=author,
        isbn=isbn,
        category=category,
        year=year,
        language=language,
        file_type=ext,
        file_path=saved_file,
        file_size=round(file_size / (1024 * 1024), 2),
        cover_image_path=cover_saved,
    )


def update_book_record(
    book: Book,
    title: str,
    author: str,
    isbn: str,
    category: str,
    year: int,
    language: str,
    file_path: UploadFile | None,
    cover_image_path: UploadFile | None,
) -> Book:
    book.title = title
    book.author = author
    book.isbn = isbn
    book.category = category
    book.year = year
    book.language = language

    if file_path:
        if book.file_path and os.path.exists(book.file_path):
            os.remove(book.file_path)
        file_name, saved_file = save_upload_file(file_path, BOOKS_DIR)
        ext = Path(file_name).suffix.lstrip(".").lower()
        size_bytes = os.path.getsize(saved_file)
        book.file_type = ext
        book.file_path = saved_file
        book.file_size = round(size_bytes / (1024 * 1024), 2)

    if cover_image_path:
        if book.cover_image_path and os.path.exists(book.cover_image_path):
            os.remove(book.cover_image_path)
        _, cover_saved = save_upload_file(cover_image_path, COVERS_DIR)
        book.cover_image_path = cover_saved

    return book
