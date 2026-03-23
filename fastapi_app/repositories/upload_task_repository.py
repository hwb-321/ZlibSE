from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from ..models import FileParseResult, UploadTask


ACTIVE_UPLOAD_STATUSES = {"init", "uploaded", "parsing"}


def create_upload_task(
    db: Session,
    *,
    user_id: int,
    original_filename: str,
    content_type: str,
    size: int,
    kind: str,
    file_hash: str | None,
    object_key: str,
) -> UploadTask:
    task = UploadTask(
        user_id=user_id,
        original_filename=original_filename,
        content_type=content_type,
        size=size,
        kind=kind,
        file_hash=file_hash or None,
        object_key=object_key,
        status="init",
    )
    db.add(task)
    db.flush()
    return task


def find_recent_active_upload_task(
    db: Session,
    *,
    user_id: int,
    original_filename: str,
    size: int,
    kind: str,
    window_seconds: int,
) -> UploadTask | None:
    threshold = datetime.utcnow() - timedelta(seconds=window_seconds)
    return (
        db.query(UploadTask)
        .filter(
            UploadTask.user_id == user_id,
            UploadTask.original_filename == original_filename,
            UploadTask.size == size,
            UploadTask.kind == kind,
            UploadTask.status.in_(ACTIVE_UPLOAD_STATUSES),
            UploadTask.updated_at >= threshold,
        )
        .order_by(UploadTask.id.desc())
        .first()
    )


def list_recent_active_upload_tasks(
    db: Session,
    *,
    user_id: int,
    kind: str,
    window_seconds: int,
) -> list[UploadTask]:
    threshold = datetime.utcnow() - timedelta(seconds=window_seconds)
    return (
        db.query(UploadTask)
        .filter(
            UploadTask.user_id == user_id,
            UploadTask.kind == kind,
            UploadTask.status.in_(ACTIVE_UPLOAD_STATUSES),
            UploadTask.updated_at >= threshold,
        )
        .order_by(UploadTask.id.desc())
        .all()
    )


def find_active_upload_task_by_hash(
    db: Session,
    *,
    user_id: int,
    kind: str,
    file_hash: str,
    window_seconds: int,
) -> UploadTask | None:
    threshold = datetime.utcnow() - timedelta(seconds=window_seconds)
    return (
        db.query(UploadTask)
        .filter(
            UploadTask.user_id == user_id,
            UploadTask.kind == kind,
            UploadTask.file_hash == file_hash,
            UploadTask.status.in_(ACTIVE_UPLOAD_STATUSES),
            UploadTask.updated_at >= threshold,
        )
        .order_by(UploadTask.id.desc())
        .first()
    )


def get_upload_task_by_object_key(db: Session, object_key: str) -> UploadTask | None:
    return db.query(UploadTask).filter(UploadTask.object_key == object_key).first()


def mark_upload_task_status(
    db: Session,
    task: UploadTask,
    *,
    status: str,
    file_id: int | None = None,
    error_message: str | None = None,
) -> UploadTask:
    task.status = status
    if file_id is not None:
        task.file_id = file_id
    task.error_message = error_message
    task.updated_at = datetime.utcnow()
    db.add(task)
    db.flush()
    return task


def list_expired_unfinished_tasks(
    db: Session,
    *,
    older_than_seconds: int,
) -> list[UploadTask]:
    threshold = datetime.utcnow() - timedelta(seconds=older_than_seconds)
    return (
        db.query(UploadTask)
        .filter(
            UploadTask.status == "expired",
            UploadTask.file_id.is_(None),
            UploadTask.updated_at < threshold,
        )
        .order_by(UploadTask.updated_at.asc())
        .all()
    )


def get_file_parse_result(db: Session, file_id: int) -> FileParseResult | None:
    return db.query(FileParseResult).filter(FileParseResult.file_id == file_id).first()


def get_or_create_file_parse_result(db: Session, file_id: int, *, parser_mode: str) -> FileParseResult:
    existing = get_file_parse_result(db, file_id)
    if existing:
        return existing
    result = FileParseResult(file_id=file_id, status="pending", parser_mode=parser_mode)
    db.add(result)
    db.flush()
    return result
