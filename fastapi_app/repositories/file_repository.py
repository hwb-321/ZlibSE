from datetime import datetime

from sqlalchemy.orm import Session

from ..models import StoredFile


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
    upload_url: str | None = None,
    upload_status: str = "uploaded",
    parse_status: str = "not_started",
    bind_status: str = "unbound",
    upload_expires_at: datetime | None = None,
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
        upload_url=upload_url,
        upload_status=upload_status,
        parse_status=parse_status,
        bind_status=bind_status,
        upload_expires_at=upload_expires_at,
    )
    db.add(stored_file)
    db.flush()
    return stored_file


def get_file(db: Session, file_id: int) -> StoredFile | None:
    return db.get(StoredFile, file_id)


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


def get_unbound_book_file_for_user(db: Session, user_id: int) -> StoredFile | None:
    return (
        db.query(StoredFile)
        .filter(
            StoredFile.user_id == user_id,
            StoredFile.kind == "book",
            StoredFile.bind_status == "unbound",
        )
        .order_by(StoredFile.id.desc())
        .first()
    )
