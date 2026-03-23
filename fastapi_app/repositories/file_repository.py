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
    file_hash: str | None = None,
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
        file_hash=file_hash or None,
    )
    db.add(stored_file)
    db.flush()
    return stored_file


def get_file(db: Session, file_id: int) -> StoredFile | None:
    return db.get(StoredFile, file_id)


def get_file_by_object_key(db: Session, object_key: str) -> StoredFile | None:
    return db.query(StoredFile).filter(StoredFile.object_key == object_key).first()


def find_matching_file(
    db: Session,
    *,
    user_id: int,
    original_filename: str,
    size: int,
    kind: str,
) -> StoredFile | None:
    return (
        db.query(StoredFile)
        .filter(
            StoredFile.user_id == user_id,
            StoredFile.original_filename == original_filename,
            StoredFile.size == size,
            StoredFile.kind == kind,
        )
        .order_by(StoredFile.id.desc())
        .first()
    )


def find_matching_file_by_hash(
    db: Session,
    *,
    user_id: int,
    file_hash: str,
    kind: str,
) -> StoredFile | None:
    return (
        db.query(StoredFile)
        .filter(
            StoredFile.user_id == user_id,
            StoredFile.file_hash == file_hash,
            StoredFile.kind == kind,
        )
        .order_by(StoredFile.id.desc())
        .first()
    )


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
