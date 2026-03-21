from sqlalchemy.orm import Session

from ..models import StoredFile


def create_file_record(
    db: Session,
    *,
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
