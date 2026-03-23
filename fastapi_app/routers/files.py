from __future__ import annotations

from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.database import get_db
from ..core.deps import get_current_user
from ..models import User
from ..repositories.file_repository import (
    create_file_record,
    find_matching_file,
    find_matching_file_by_hash,
    get_file,
    get_file_by_object_key,
    is_file_referenced_by_book,
)
from ..repositories.upload_task_repository import (
    create_upload_task,
    find_active_upload_task_by_hash,
    get_file_parse_result,
    get_upload_task_by_object_key,
    get_or_create_file_parse_result,
    list_recent_active_upload_tasks,
    mark_upload_task_status,
)
from ..services.cache_service import (
    build_file_meta_cache_key,
    serialize_file_meta,
)
from ..services.hybrid_cache_service import EMPTY_MARKER, delete_cached, get_cached, set_cached
from ..services.lock_service import acquire_lock, build_lock_value, release_lock
from ..services.queue_service import publish_parse_task
from ..services.storage_service import (
    create_presigned_download_url,
    create_presigned_upload,
    head_object,
)

router = APIRouter(prefix="/api/files", tags=["files"])


class UploadUrlRequest(BaseModel):
    filename: str
    contentType: str = "application/octet-stream"
    size: int = 0
    kind: str
    fileHash: str | None = None


class UploadCompleteRequest(BaseModel):
    objectKey: str
    originalFilename: str
    contentType: str = "application/octet-stream"
    size: int = 0
    kind: str
    etag: str | None = None


def _load_public_file_meta(db: Session, file_id: int) -> dict:
    settings = get_settings()
    cache_key = build_file_meta_cache_key(file_id)
    cached = get_cached(cache_key, local_ttl_seconds=settings.local_cache.file_meta_ttl_seconds)
    if cached is not None:
        if cached == EMPTY_MARKER:
            raise HTTPException(status_code=404, detail="File not found")
        return cached

    stored_file = get_file(db, file_id)
    if not stored_file or not is_file_referenced_by_book(db, file_id):
        set_cached(
            cache_key,
            EMPTY_MARKER,
            redis_ttl_seconds=settings.redis.empty_ttl_seconds,
            local_ttl_seconds=settings.local_cache.empty_ttl_seconds,
        )
        raise HTTPException(status_code=404, detail="File not found")

    payload = serialize_file_meta(stored_file)
    set_cached(
        cache_key,
        payload,
        redis_ttl_seconds=settings.redis.file_meta_ttl_seconds,
        local_ttl_seconds=settings.local_cache.file_meta_ttl_seconds,
    )
    return payload


@router.post("/upload-url")
def get_upload_url(
    payload: UploadUrlRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    normalized_hash = (payload.fileHash or "").strip() or None
    if normalized_hash:
        matching = find_matching_file_by_hash(
            db,
            user_id=current_user.id,
            file_hash=normalized_hash,
            kind=payload.kind,
        )
    else:
        matching = find_matching_file(
            db,
            user_id=current_user.id,
            original_filename=payload.filename,
            size=payload.size,
            kind=payload.kind,
        )
    if matching:
        return {
            "fileId": matching.id,
            "objectKey": matching.object_key,
            "uploadUrl": None,
            "expiresIn": 0,
            "headers": {},
            "alreadyUploaded": True,
            "matchedByHash": bool(normalized_hash),
        }

    lock_key = f"{settings.redis.prefix}:upload:init:{current_user.id}:{payload.kind}:{payload.filename}"
    lock_value = build_lock_value()
    if not acquire_lock(lock_key, lock_value, ttl_seconds=settings.redis.lock_ttl_seconds):
        raise HTTPException(status_code=429, detail="Upload request is already being processed")

    try:
        if normalized_hash:
            active_tasks = []
            active_hash_task = find_active_upload_task_by_hash(
                db,
                user_id=current_user.id,
                kind=payload.kind,
                file_hash=normalized_hash,
                window_seconds=settings.storage.upload_expires,
            )
            if active_hash_task:
                active_tasks.append(active_hash_task)
        else:
            active_tasks = list_recent_active_upload_tasks(
                db,
                user_id=current_user.id,
                kind=payload.kind,
                window_seconds=settings.storage.upload_expires,
            )
        for active_task in active_tasks:
            mark_upload_task_status(db, active_task, status="expired", error_message="Superseded by a newer upload request")

        result = create_presigned_upload(payload.filename, payload.contentType, payload.kind)
        task = create_upload_task(
            db,
            user_id=current_user.id,
            original_filename=payload.filename,
            content_type=result["content_type"],
            size=payload.size,
            kind=payload.kind,
            file_hash=normalized_hash,
            object_key=result["object_key"],
        )
        db.commit()
    finally:
        release_lock(lock_key, lock_value)

    return {
        "uploadTaskId": task.id,
        "objectKey": result["object_key"],
        "uploadUrl": result["upload_url"],
        "expiresIn": result["expires_in"],
        "headers": {"Content-Type": result["content_type"]},
        "alreadyUploaded": False,
        "reusedTask": False,
        "matchedByHash": bool(normalized_hash),
    }


@router.post("/upload-complete")
def upload_complete(
    payload: UploadCompleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    lock_key = f"{settings.redis.prefix}:upload:complete:{payload.objectKey}"
    lock_value = build_lock_value()
    if not acquire_lock(lock_key, lock_value, ttl_seconds=settings.redis.lock_ttl_seconds):
        existing = get_file_by_object_key(db, payload.objectKey)
        if existing:
            parse_result = get_file_parse_result(db, existing.id)
            return {
                "fileId": existing.id,
                "alreadyCompleted": True,
                "parseStatus": parse_result.status if parse_result else None,
            }
        raise HTTPException(status_code=409, detail="Upload completion is already in progress")

    try:
        existing = get_file_by_object_key(db, payload.objectKey)
        if existing:
            parse_result = get_file_parse_result(db, existing.id)
            return {
                "fileId": existing.id,
                "alreadyCompleted": True,
                "parseStatus": parse_result.status if parse_result else None,
            }

        task = get_upload_task_by_object_key(db, payload.objectKey)
        if task and task.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Upload task does not belong to current user")
        if task and task.status == "expired":
            raise HTTPException(status_code=410, detail="Upload task has expired, please request a new upload link")

        if settings.benchmark.mock_upload_enabled:
            metadata = {
                "ContentType": payload.contentType,
                "ContentLength": payload.size,
                "ETag": payload.etag or "",
            }
        else:
            metadata = head_object(payload.objectKey)

        stored_file = create_file_record(
            db,
            user_id=current_user.id,
            bucket=settings.storage.bucket,
            region=settings.storage.region,
            object_key=payload.objectKey,
            original_filename=payload.originalFilename,
            content_type=metadata.get("ContentType", payload.contentType),
            size=int(metadata.get("ContentLength", payload.size)),
            etag=str(metadata.get("ETag", payload.etag or "")).strip('"'),
            kind=payload.kind,
            file_hash=task.file_hash if task else None,
        )
        db.flush()

        parse_status = "skipped"
        published_task_id = None
        if task:
            mark_upload_task_status(db, task, status="uploaded", file_id=stored_file.id)

        if settings.async_parse.enabled and settings.async_parse.mode != "off":
            parse_result = get_or_create_file_parse_result(db, stored_file.id, parser_mode=settings.async_parse.mode)
            parse_result.status = "pending"
            db.add(parse_result)
            if task:
                mark_upload_task_status(db, task, status="parsing", file_id=stored_file.id)

        db.commit()

        if settings.async_parse.enabled and settings.async_parse.mode != "off" and task:
            try:
                published_task_id = publish_parse_task(
                    file_id=stored_file.id,
                    upload_task_id=task.id,
                    parser_mode=settings.async_parse.mode,
                )
                parse_status = "pending"
            except Exception as exc:
                db.rollback()
                parse_result = get_or_create_file_parse_result(db, stored_file.id, parser_mode=settings.async_parse.mode)
                parse_result.status = "dispatch_failed"
                parse_result.error_message = str(exc)
                db.add(parse_result)
                mark_upload_task_status(db, task, status="uploaded", file_id=stored_file.id, error_message=str(exc))
                db.commit()
                parse_status = "dispatch_failed"
        delete_cached(build_file_meta_cache_key(stored_file.id))
        return {
            "fileId": stored_file.id,
            "alreadyCompleted": False,
            "parseStatus": parse_status,
            "parseTaskId": published_task_id,
        }
    except IntegrityError:
        db.rollback()
        existing = get_file_by_object_key(db, payload.objectKey)
        if existing:
            parse_result = get_file_parse_result(db, existing.id)
            return {
                "fileId": existing.id,
                "alreadyCompleted": True,
                "parseStatus": parse_result.status if parse_result else None,
            }
        raise
    finally:
        release_lock(lock_key, lock_value)


@router.get("/{file_id}/download-url")
def get_download_url(
    file_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    stored_file = _load_public_file_meta(db, file_id)

    if stored_file["bucket"] == "legacy-local" and stored_file["region"] == "local":
        base_url = str(request.base_url).rstrip("/")
        return {
            "downloadUrl": f"{base_url}/api/files/{file_id}/content",
            "expiresIn": get_settings().storage.download_expires,
            "filename": stored_file["original_filename"],
        }

    return {
        "downloadUrl": create_presigned_download_url(SimpleNamespace(**stored_file)),
        "expiresIn": get_settings().storage.download_expires,
        "filename": stored_file["original_filename"],
    }


@router.get("/{file_id}/content")
def get_file_content(
    file_id: int,
    download: bool = Query(True),
    db: Session = Depends(get_db),
):
    _load_public_file_meta(db, file_id)
    stored_file = get_file(db, file_id)
    if not stored_file:
        raise HTTPException(status_code=404, detail="File not found")

    from ..services.storage_service import build_file_response

    return build_file_response(stored_file, force_download=download)


@router.get("/{file_id}/parse-result")
def get_parse_result(
    file_id: int,
    db: Session = Depends(get_db),
):
    stored_file = get_file(db, file_id)
    if not stored_file:
        raise HTTPException(status_code=404, detail="File not found")

    result = get_file_parse_result(db, file_id)
    if not result:
        return {"status": "missing"}
    return {
        "status": result.status,
        "parserMode": result.parser_mode,
        "title": result.title,
        "author": result.author,
        "language": result.language,
        "pageCount": result.page_count,
        "coverFileId": result.cover_file_id,
        "rawMetadata": result.raw_metadata,
        "errorMessage": result.error_message,
    }
