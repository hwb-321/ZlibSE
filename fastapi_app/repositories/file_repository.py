from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models import Book, StoredFile


def create_file_record(
    db: Session,
    *,
    user_id: int | None,
    bucket: str,
    region: str,
    object_key: str,
    original_filename: str,
    content_type: str,
    size: int,
    etag: str,
    kind: str,
) -> StoredFile:
    stored_file = StoredFile(
        user_id=user_id,
        bucket=bucket,
        region=region,
        object_key=object_key,
        original_filename=original_filename,
        content_type=content_type,
        size=size,
        etag=etag,
        kind=kind,
    )
    db.add(stored_file)
    db.flush()
    return stored_file


def get_file(db: Session, file_id: int) -> StoredFile | None:
    return db.get(StoredFile, file_id)


def is_file_referenced_by_book(db: Session, file_id: int) -> bool:
    return (
        db.query(Book.id)
        .filter(
            or_(
                Book.book_file_id == file_id,
                Book.cover_file_id == file_id,
            )
        )
        .first()
        is not None
    )
