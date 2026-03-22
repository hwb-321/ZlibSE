from __future__ import annotations

from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from ..models import Book, StoredFile, User
from ..repositories.file_repository import create_file_record, get_file
from .storage_service import delete_object, upload_upload_file


def _file_ext(filename: str) -> str:
    return Path(filename or "").suffix.lstrip(".").lower()


def _size_to_mb(size: int) -> float:
    return round(size / (1024 * 1024), 2) if size else 0.0


def _ensure_required_upload(upload: UploadFile | None, field_name: str) -> UploadFile:
    if upload is None:
        raise ValueError(f"{field_name} is required")
    return upload


def _persist_uploaded_file(db: Session, upload: UploadFile, kind: str) -> StoredFile:
    payload = upload_upload_file(upload, kind)
    return create_file_record(db, user_id=None, **payload)


def _ensure_file_access(
    stored_file: StoredFile,
    *,
    current_user: User,
    current_book: Book | None = None,
) -> None:
    if current_user.is_superuser:
        return

    if current_book and stored_file.id in {current_book.book_file_id, current_book.cover_file_id}:
        return

    if stored_file.user_id != current_user.id:
        raise ValueError("fileId does not belong to current user")


def _validate_file_refs(
    db: Session,
    book_file_id: int,
    cover_file_id: int | None,
    *,
    current_user: User,
    current_book: Book | None = None,
) -> tuple[StoredFile, StoredFile | None]:
    book_file = get_file(db, book_file_id)
    if not book_file:
        raise ValueError("bookFileId does not exist")
    if book_file.kind != "book":
        raise ValueError("bookFileId must point to a book file")
    _ensure_file_access(book_file, current_user=current_user, current_book=current_book)

    cover_file = None
    if cover_file_id is not None:
        cover_file = get_file(db, cover_file_id)
        if not cover_file:
            raise ValueError("coverFileId does not exist")
        if cover_file.kind != "cover":
            raise ValueError("coverFileId must point to a cover file")
        _ensure_file_access(cover_file, current_user=current_user, current_book=current_book)

    return book_file, cover_file


def book_to_dict(book: Book) -> dict:
    book_file = book.book_file
    cover_file = book.cover_file
    return {
        "id": book.id,
        "title": book.title,
        "author": book.author or "",
        "isbn": book.isbn or "",
        "category": book.category or "",
        "year": book.year,
        "language": book.language or "",
        "file_type": _file_ext(book_file.original_filename),
        "file_size": _size_to_mb(book_file.size),
        "book_file_id": book.book_file_id,
        "cover_file_id": book.cover_file_id,
        "file_path": f"/api/files/{book.book_file_id}/download-url",
        "cover_image_path": f"/api/files/{book.cover_file_id}/content?download=false" if cover_file else "",
    }


def build_book_detail(book: Book) -> dict:
    return book_to_dict(book)


def create_book_record(
    db: Session,
    *,
    title: str,
    author: str | None,
    isbn: str | None,
    category: str | None,
    year: int | None,
    language: str | None,
    file_path: UploadFile,
    cover_image_path: UploadFile | None,
) -> Book:
    main_upload = _ensure_required_upload(file_path, "file")
    book_file = _persist_uploaded_file(db, main_upload, "book")
    cover_file = _persist_uploaded_file(db, cover_image_path, "cover") if cover_image_path else None

    return Book(
        title=title,
        author=author or None,
        isbn=isbn or None,
        category=category or None,
        year=year,
        language=language or None,
        book_file_id=book_file.id,
        cover_file_id=cover_file.id if cover_file else None,
    )


def create_book_from_file_ids(
    db: Session,
    *,
    current_user: User,
    title: str,
    author: str | None,
    isbn: str | None,
    category: str | None,
    year: int | None,
    language: str | None,
    book_file_id: int,
    cover_file_id: int | None,
) -> Book:
    _validate_file_refs(db, book_file_id, cover_file_id, current_user=current_user)
    return Book(
        title=title,
        author=author or None,
        isbn=isbn or None,
        category=category or None,
        year=year,
        language=language or None,
        book_file_id=book_file_id,
        cover_file_id=cover_file_id,
    )


def update_book_record(
    db: Session,
    *,
    book: Book,
    title: str,
    author: str | None,
    isbn: str | None,
    category: str | None,
    year: int | None,
    language: str | None,
    file_path: UploadFile | None,
    cover_image_path: UploadFile | None,
) -> Book:
    book.title = title
    book.author = author or None
    book.isbn = isbn or None
    book.category = category or None
    book.year = year
    book.language = language or None

    if file_path:
        old_file = book.book_file
        new_file = _persist_uploaded_file(db, file_path, "book")
        book.book_file_id = new_file.id
        if old_file:
            delete_object(old_file)
            db.delete(old_file)

    if cover_image_path:
        old_cover = book.cover_file
        new_cover = _persist_uploaded_file(db, cover_image_path, "cover")
        book.cover_file_id = new_cover.id
        if old_cover:
            delete_object(old_cover)
            db.delete(old_cover)

    return book


def update_book_from_file_ids(
    db: Session,
    *,
    book: Book,
    current_user: User,
    title: str,
    author: str | None,
    isbn: str | None,
    category: str | None,
    year: int | None,
    language: str | None,
    book_file_id: int,
    cover_file_id: int | None,
) -> Book:
    _validate_file_refs(
        db,
        book_file_id,
        cover_file_id,
        current_user=current_user,
        current_book=book,
    )
    book.title = title
    book.author = author or None
    book.isbn = isbn or None
    book.category = category or None
    book.year = year
    book.language = language or None
    book.book_file_id = book_file_id
    book.cover_file_id = cover_file_id
    return book


def delete_book_files(db: Session, book: Book) -> None:
    for stored_file in [book.book_file, book.cover_file]:
        if stored_file is None:
            continue
        delete_object(stored_file)
        db.delete(stored_file)
