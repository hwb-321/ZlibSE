from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..models import Book, StoredFile, User
from ..repositories.file_repository import get_file
from ..repositories.parse_result_repository import get_file_parse_result
from ..services.cache_service import remove_unbound_cover_id
from .storage_service import delete_object


def _file_ext(filename: str) -> str:
    return Path(filename or "").suffix.lstrip(".").lower()


def _size_to_mb(size: int) -> float:
    return round(size / (1024 * 1024), 2) if size else 0.0


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


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


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
        raise ValueError("storedFileId does not exist")
    if book_file.kind != "book":
        raise ValueError("storedFileId must point to a book file")
    _ensure_file_access(book_file, current_user=current_user, current_book=current_book)
    if current_book is None:
        if book_file.bind_status != "unbound":
            raise ValueError("storedFileId has already been bound to a book")
        if book_file.parse_status != "done":
            raise ValueError("storedFileId is not ready for book creation")

    cover_file = None
    if cover_file_id is not None:
        cover_file = get_file(db, cover_file_id)
        if not cover_file:
            raise ValueError("coverFileId does not exist")
        if cover_file.kind != "cover":
            raise ValueError("coverFileId must point to a cover file")
        _ensure_file_access(cover_file, current_user=current_user, current_book=current_book)

    return book_file, cover_file


def _increase_file_ref(stored_file: StoredFile | None) -> None:
    if stored_file is None:
        return
    stored_file.ref_count += 1


def _decrease_file_ref(stored_file: StoredFile | None) -> None:
    if stored_file is None:
        return
    stored_file.ref_count = max(0, stored_file.ref_count - 1)


def book_to_summary(book: Book) -> dict:
    book_file = book.book_file
    cover_file = book.cover_file
    return {
        "id": book.id,
        "title": book.title,
        "author": book.author or "",
        "language": book.language or "",
        "file_type": _file_ext(book_file.original_filename),
        "file_size": _size_to_mb(book_file.size),
        "cover_image_path": f"/api/files/{book.cover_file_id}/download" if cover_file else "",
    }


def build_book_detail(book: Book) -> dict:
    book_file = book.book_file
    cover_file = book.cover_file
    return {
        **book_to_summary(book),
        "isbn": book.isbn or "",
        "category": book.category or "",
        "year": book.year,
        "book_file_id": book.book_file_id,
        "cover_file_id": book.cover_file_id,
        "file_path": f"/api/files/{book.book_file_id}/download",
        "cover_image_path": f"/api/files/{book.cover_file_id}/download" if cover_file else "",
        "file_type": _file_ext(book_file.original_filename),
        "file_size": _size_to_mb(book_file.size),
    }


def create_book_from_file_ids(
    db: Session,
    *,
    current_user: User,
    title: str | None,
    author: str | None,
    isbn: str | None,
    category: str | None,
    year: int | None,
    language: str | None,
    book_file_id: int,
    cover_file_id: int | None,
) -> Book:
    book_file, cover_file = _validate_file_refs(
        db,
        book_file_id,
        cover_file_id,
        current_user=current_user,
    )
    parse_result = get_file_parse_result(db, book_file_id)
    if get_settings().benchmark.mock_upload_enabled and parse_result:
        title = title if title is not None else parse_result.title
        author = author if author is not None else parse_result.author
        language = language if language is not None else parse_result.language

    _increase_file_ref(book_file)
    _increase_file_ref(cover_file)
    book_file.bind_status = "bound"
    db.add(book_file)
    if cover_file is not None:
        cover_file.bind_status = "bound"
        db.add(cover_file)
        remove_unbound_cover_id(cover_file.user_id, cover_file.id)

    return Book(
        title=_normalize_optional_text(title) or "",
        author=_normalize_optional_text(author),
        isbn=_normalize_optional_text(isbn),
        category=_normalize_optional_text(category),
        year=year,
        language=_normalize_optional_text(language),
        book_file_id=book_file_id,
        cover_file_id=cover_file_id,
    )

def delete_book_files(db: Session, book: Book) -> None:
    for stored_file in [book.book_file, book.cover_file]:
        if stored_file is None:
            continue
        if stored_file.kind == "book":
            stored_file.bind_status = "unbound"
            db.add(stored_file)
        if stored_file.kind == "cover":
            stored_file.bind_status = "unbound"
            db.add(stored_file)
            remove_unbound_cover_id(stored_file.user_id, stored_file.id)
        _decrease_file_ref(stored_file)
        if stored_file.ref_count > 0:
            continue
        delete_object(stored_file)
        db.delete(stored_file)
