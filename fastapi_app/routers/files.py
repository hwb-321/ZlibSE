from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.database import get_async_db, get_db
from ..core.deps import get_current_user, get_current_user_optional_async
from ..models import User
from ..repositories.file_repository import (
    create_file_record,
    find_matching_file_by_hash,
    get_file,
    get_file_async,
    get_unbound_book_file_for_user,
)
from ..repositories.parse_result_repository import (
    get_file_parse_result,
    get_or_create_file_parse_result,
)
from ..services.cache_service import (
    add_unbound_cover_id,
    async_get_cached_download_url_payload,
    async_set_cached_download_url_payload,
    async_track_download_hot_access,
    build_file_meta_cache_key,
    delete_cached_public_file_meta,
    get_local_cached_download_url_payload,
    get_unbound_cover_ids_count,
    set_local_cached_download_url_payload,
    serialize_file_meta,
)
from ..services.hybrid_cache_service import EMPTY_MARKER, async_get_cached, async_set_cached, async_set_empty
from ..services.lock_service import acquire_lock, async_acquire_lock, async_release_lock, build_lock_value, release_lock
from ..services.metrics_service import (
    async_increment_counter,
    async_record_timing_metric,
)
from ..services.queue_service import publish_parse_task
from ..services.parse_service import build_server_mock_parse_result
from ..services.storage_service import (
    create_mock_upload_session,
    create_presigned_download_url,
    create_presigned_object_url_for_object_key,
    create_presigned_upload,
    create_presigned_upload_for_object_key,
    head_object,
)

router = APIRouter(prefix="/api/files", tags=["files"])
UPLOAD_REFRESH_THRESHOLD_SECONDS = 300
UNBOUND_COVER_LIMIT = 5
FILE_META_REBUILD_WAIT_SECONDS = 0.05
FILE_META_REBUILD_MAX_RETRIES = 3
DOWNLOAD_URL_REBUILD_WAIT_SECONDS = 0.02
DOWNLOAD_URL_REBUILD_MAX_RETRIES = 3


class CreateFileRequest(BaseModel):
    filename: str
    contentType: str = "application/octet-stream"
    size: int = 0
    kind: Literal["book", "cover"]
    fileHash: str | None = None


class UploadCompleteRequest(BaseModel):
    etag: str | None = None


async def _load_public_file_meta_async(db: AsyncSession, file_id: int) -> dict:
    settings = get_settings()
    cache_key = build_file_meta_cache_key(file_id)
    cache_lookup_start = time.perf_counter()
    cached = await async_get_cached(cache_key, local_ttl_seconds=settings.local_cache.file_meta_ttl_seconds)
    await async_record_timing_metric(
        "download.public_meta.cache_lookup_ms", (time.perf_counter() - cache_lookup_start) * 1000.0
    )
    if cached is not None:
        if cached == EMPTY_MARKER:
            raise HTTPException(status_code=404, detail="File not found")
        return cached

    lock_key = f"{settings.redis.prefix}:files:meta:rebuild:{file_id}"
    lock_value = build_lock_value()
    lock_acquire_start = time.perf_counter()
    if await async_acquire_lock(lock_key, lock_value, ttl_seconds=settings.redis.lock_ttl_seconds):
        await async_record_timing_metric(
            "download.public_meta.lock_wait_ms", (time.perf_counter() - lock_acquire_start) * 1000.0
        )
        try:
            second_cache_lookup_start = time.perf_counter()
            cached = await async_get_cached(cache_key, local_ttl_seconds=settings.local_cache.file_meta_ttl_seconds)
            await async_record_timing_metric(
                "download.public_meta.cache_lookup_ms", (time.perf_counter() - second_cache_lookup_start) * 1000.0
            )
            if cached is not None:
                if cached == EMPTY_MARKER:
                    raise HTTPException(status_code=404, detail="File not found")
                return cached

            db_lookup_start = time.perf_counter()
            stored_file = await get_file_async(db, file_id)
            await async_record_timing_metric(
                "download.public_meta.db_fetch_ms", (time.perf_counter() - db_lookup_start) * 1000.0
            )
            if not stored_file or stored_file.ref_count <= 0:
                await async_set_empty(cache_key, local_ttl_seconds=settings.local_cache.empty_ttl_seconds)
                raise HTTPException(status_code=404, detail="File not found")

            serialize_start = time.perf_counter()
            payload = serialize_file_meta(stored_file)
            await async_record_timing_metric(
                "download.public_meta.serialize_ms", (time.perf_counter() - serialize_start) * 1000.0
            )
            cache_store_start = time.perf_counter()
            await async_set_cached(
                cache_key,
                payload,
                redis_ttl_seconds=settings.redis.file_meta_ttl_seconds,
                local_ttl_seconds=settings.local_cache.file_meta_ttl_seconds,
            )
            await async_record_timing_metric(
                "download.public_meta.cache_fill_ms", (time.perf_counter() - cache_store_start) * 1000.0
            )
            return payload
        finally:
            await async_release_lock(lock_key, lock_value)
    await async_record_timing_metric("download.public_meta.lock_wait_ms", (time.perf_counter() - lock_acquire_start) * 1000.0)

    retry_wait_start = time.perf_counter()
    for _ in range(FILE_META_REBUILD_MAX_RETRIES):
        await asyncio.sleep(FILE_META_REBUILD_WAIT_SECONDS)
        retry_cache_lookup_start = time.perf_counter()
        cached = await async_get_cached(cache_key, local_ttl_seconds=settings.local_cache.file_meta_ttl_seconds)
        await async_record_timing_metric(
            "download.public_meta.cache_lookup_ms", (time.perf_counter() - retry_cache_lookup_start) * 1000.0
        )
        if cached is None:
            continue
        await async_record_timing_metric("download.public_meta.retry_wait_ms", (time.perf_counter() - retry_wait_start) * 1000.0)
        if cached == EMPTY_MARKER:
            raise HTTPException(status_code=404, detail="File not found")
        return cached
    await async_record_timing_metric("download.public_meta.retry_wait_ms", (time.perf_counter() - retry_wait_start) * 1000.0)

    final_db_lookup_start = time.perf_counter()
    stored_file = await get_file_async(db, file_id)
    await async_record_timing_metric("download.public_meta.db_fetch_ms", (time.perf_counter() - final_db_lookup_start) * 1000.0)
    if not stored_file or stored_file.ref_count <= 0:
        await async_set_empty(cache_key, local_ttl_seconds=settings.local_cache.empty_ttl_seconds)
        raise HTTPException(status_code=404, detail="File not found")

    final_serialize_start = time.perf_counter()
    payload = serialize_file_meta(stored_file)
    await async_record_timing_metric(
        "download.public_meta.serialize_ms", (time.perf_counter() - final_serialize_start) * 1000.0
    )
    final_cache_store_start = time.perf_counter()
    await async_set_cached(
        cache_key,
        payload,
        redis_ttl_seconds=settings.redis.file_meta_ttl_seconds,
        local_ttl_seconds=settings.local_cache.file_meta_ttl_seconds,
    )
    await async_record_timing_metric(
        "download.public_meta.cache_fill_ms", (time.perf_counter() - final_cache_store_start) * 1000.0
    )
    return payload


def _ensure_file_owner(stored_file, current_user: User) -> None:
    if stored_file.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="File does not belong to current user")


def _file_payload(stored_file) -> dict:
    return {
        "fileId": stored_file.id,
        "kind": stored_file.kind,
        "originalFilename": stored_file.original_filename,
        "contentType": stored_file.content_type,
        "size": stored_file.size,
        "fileHash": stored_file.file_hash,
        "uploadStatus": stored_file.upload_status,
        "parseStatus": stored_file.parse_status,
        "bindStatus": stored_file.bind_status,
        "objectKey": stored_file.object_key,
        "uploadExpiresAt": stored_file.upload_expires_at.isoformat() if stored_file.upload_expires_at else None,
    }


def _remaining_upload_seconds(stored_file) -> float:
    if not stored_file.upload_expires_at:
        return 0
    return (stored_file.upload_expires_at - datetime.utcnow()).total_seconds()


def _can_refresh_same_upload(stored_file, *, mock_upload: bool = False) -> bool:
    return (
        stored_file.upload_status == "uploading"
        and (bool(stored_file.upload_url) or mock_upload)
        and bool(stored_file.object_key)
        and _remaining_upload_seconds(stored_file) > UPLOAD_REFRESH_THRESHOLD_SECONDS
    )


def _build_server_mock_object_url() -> str:
    settings = get_settings()
    return create_presigned_object_url_for_object_key(
        settings.storage.bucket,
        settings.benchmark.mock_file_object_key,
        expires_in=settings.storage.download_expires,
    )


def _build_download_response(payload: dict, settings) -> dict:
    return {
        "downloadUrl": payload["downloadUrl"],
        "expiresIn": int(payload.get("expiresIn", settings.storage.download_expires)),
        "filename": payload["filename"],
    }


async def _resolve_download_file(
    db: AsyncSession,
    file_id: int,
    current_user: User | None,
) -> tuple[object, dict]:
    public_payload: dict | None = None
    stored_file = None
    public_meta_start = time.perf_counter()
    try:
        public_payload = await _load_public_file_meta_async(db, file_id)
        namespace_build_start = time.perf_counter()
        stored_file = SimpleNamespace(**public_payload)
        await async_record_timing_metric(
            "download.namespace_build_ms",
            (time.perf_counter() - namespace_build_start) * 1000.0,
        )
        await async_increment_counter("download.access_mode.public")
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
    finally:
        public_meta_elapsed_ms = (time.perf_counter() - public_meta_start) * 1000.0
        await async_record_timing_metric("download.public_meta_ms", public_meta_elapsed_ms)
        await async_record_timing_metric("download.route.resolve_public_ms", public_meta_elapsed_ms)

    if stored_file is not None:
        assert public_payload is not None
        return stored_file, public_payload

    owned_lookup_start = time.perf_counter()
    owned_file = await get_file_async(db, file_id)
    await async_record_timing_metric(
        "download.owned_lookup_ms",
        (time.perf_counter() - owned_lookup_start) * 1000.0,
    )
    if not owned_file:
        raise HTTPException(status_code=404, detail="File not found")
    if current_user is None:
        raise HTTPException(status_code=404, detail="File not found")

    access_check_start = time.perf_counter()
    _ensure_file_owner(owned_file, current_user)
    if owned_file.bind_status != "unbound":
        await async_record_timing_metric(
            "download.access_check_ms",
            (time.perf_counter() - access_check_start) * 1000.0,
        )
        raise HTTPException(status_code=403, detail="File is not available for direct access")
    await async_record_timing_metric(
        "download.access_check_ms",
        (time.perf_counter() - access_check_start) * 1000.0,
    )

    serialize_start = time.perf_counter()
    public_payload = serialize_file_meta(owned_file)
    await async_record_timing_metric(
        "download.serialize_owned_meta_ms",
        (time.perf_counter() - serialize_start) * 1000.0,
    )
    await async_increment_counter("download.access_mode.owned_unbound")
    await async_record_timing_metric(
        "download.route.resolve_owned_ms",
        (time.perf_counter() - owned_lookup_start) * 1000.0,
    )
    return owned_file, public_payload


async def _try_get_hot_download_response(
    file_id: int,
    filename: str,
    settings,
) -> tuple[dict | None, bool]:
    if not settings.download_cache.hot_enabled:
        return None, False

    hot_window_count = await async_track_download_hot_access(file_id)
    download_is_hot = hot_window_count >= settings.download_cache.hot_threshold
    download_hot_armed = hot_window_count > settings.download_cache.hot_threshold
    await async_increment_counter("download.hot_window.hot" if download_is_hot else "download.hot_window.cold")
    if not download_hot_armed:
        return None, download_is_hot

    hot_local_lookup_start = time.perf_counter()
    local_cached_download = get_local_cached_download_url_payload(file_id)
    hot_local_lookup_elapsed_ms = (time.perf_counter() - hot_local_lookup_start) * 1000.0
    await async_record_timing_metric("download.hot_url_local_lookup_ms", hot_local_lookup_elapsed_ms)
    if local_cached_download and local_cached_download.get("filename") == filename:
        await async_increment_counter("download.hot_url_cache.local_hit")
        build_start = time.perf_counter()
        response = _build_download_response(local_cached_download, settings)
        await async_record_timing_metric("download.response_build_ms", (time.perf_counter() - build_start) * 1000.0)
        return response, download_is_hot

    hot_lookup_start = time.perf_counter()
    cached_download = await async_get_cached_download_url_payload(file_id)
    hot_lookup_elapsed_ms = (time.perf_counter() - hot_lookup_start) * 1000.0
    await async_record_timing_metric("download.hot_url_lookup_ms", hot_lookup_elapsed_ms)
    await async_record_timing_metric("download.route.hot_cache_lookup_ms", hot_lookup_elapsed_ms)
    if cached_download:
        if cached_download.get("filename") == filename:
            await async_increment_counter("download.hot_url_cache.hit")
            set_local_cached_download_url_payload(file_id, cached_download)
            build_start = time.perf_counter()
            response = _build_download_response(cached_download, settings)
            await async_record_timing_metric("download.response_build_ms", (time.perf_counter() - build_start) * 1000.0)
            return response, download_is_hot
        await async_increment_counter("download.hot_url_cache.miss.filename_mismatch")
    else:
        await async_increment_counter("download.hot_url_cache.miss.empty")
    await async_increment_counter("download.hot_url_cache.miss")

    download_lock_key = f"{settings.redis.prefix}:files:download_url:rebuild:{file_id}"
    download_lock_value = build_lock_value()
    if await async_acquire_lock(download_lock_key, download_lock_value, ttl_seconds=2):
        try:
            second_hot_lookup_start = time.perf_counter()
            cached_download = await async_get_cached_download_url_payload(file_id)
            second_hot_lookup_elapsed_ms = (time.perf_counter() - second_hot_lookup_start) * 1000.0
            await async_record_timing_metric("download.hot_url_lookup_ms", second_hot_lookup_elapsed_ms)
            await async_record_timing_metric("download.route.hot_cache_lookup_ms", second_hot_lookup_elapsed_ms)
            if cached_download and cached_download.get("filename") == filename:
                await async_increment_counter("download.hot_url_cache.hit")
                set_local_cached_download_url_payload(file_id, cached_download)
                build_start = time.perf_counter()
                response = _build_download_response(cached_download, settings)
                await async_record_timing_metric(
                    "download.response_build_ms",
                    (time.perf_counter() - build_start) * 1000.0,
                )
                return response, download_is_hot
        finally:
            await async_release_lock(download_lock_key, download_lock_value)
    else:
        retry_wait_start = time.perf_counter()
        for _ in range(DOWNLOAD_URL_REBUILD_MAX_RETRIES):
            await asyncio.sleep(DOWNLOAD_URL_REBUILD_WAIT_SECONDS)
            retry_hot_lookup_start = time.perf_counter()
            cached_download = await async_get_cached_download_url_payload(file_id)
            retry_hot_lookup_elapsed_ms = (time.perf_counter() - retry_hot_lookup_start) * 1000.0
            await async_record_timing_metric("download.hot_url_lookup_ms", retry_hot_lookup_elapsed_ms)
            await async_record_timing_metric("download.route.hot_cache_lookup_ms", retry_hot_lookup_elapsed_ms)
            if not cached_download:
                continue
            await async_record_timing_metric(
                "download.hot_url_retry_wait_ms",
                (time.perf_counter() - retry_wait_start) * 1000.0,
            )
            if cached_download.get("filename") == filename:
                await async_increment_counter("download.hot_url_cache.hit")
                set_local_cached_download_url_payload(file_id, cached_download)
                build_start = time.perf_counter()
                response = _build_download_response(cached_download, settings)
                await async_record_timing_metric(
                    "download.response_build_ms",
                    (time.perf_counter() - build_start) * 1000.0,
                )
                return response, download_is_hot
        await async_record_timing_metric(
            "download.hot_url_retry_wait_ms",
            (time.perf_counter() - retry_wait_start) * 1000.0,
        )

    return None, download_is_hot


@router.post("/draft")
def create_file(
    payload: CreateFileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    normalized_hash = (payload.fileHash or "").strip() or None
    if payload.kind == "book":
        existing = get_unbound_book_file_for_user(db, current_user.id)
        if existing:
            return _file_payload(existing)
    elif payload.kind == "cover":
        if get_unbound_cover_ids_count(current_user.id) >= UNBOUND_COVER_LIMIT:
            raise HTTPException(status_code=429, detail=f"Too many unbound cover files; limit is {UNBOUND_COVER_LIMIT}")
        if normalized_hash:
            existing = find_matching_file_by_hash(
                db,
                user_id=current_user.id,
                file_hash=normalized_hash,
                kind=payload.kind,
            )
            if existing and existing.bind_status == "unbound":
                return _file_payload(existing)
    elif normalized_hash:
        existing = find_matching_file_by_hash(
            db,
            user_id=current_user.id,
            file_hash=normalized_hash,
            kind=payload.kind,
        )
        if existing and existing.bind_status == "unbound":
            return _file_payload(existing)

    stored_file = create_file_record(
        db,
        user_id=current_user.id,
        bucket="",
        region="",
        object_key=None,
        original_filename=payload.filename,
        content_type=payload.contentType,
        size=payload.size,
        etag="",
        kind=payload.kind,
        file_hash=normalized_hash,
        upload_url=None,
        upload_status="init",
        parse_status="not_started",
        bind_status="unbound",
    )
    db.commit()
    db.refresh(stored_file)
    if payload.kind == "cover":
        add_unbound_cover_id(current_user.id, stored_file.id)
    return _file_payload(stored_file)


@router.post("/{file_id}/upload-session")
def get_upload_url(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    stored_file = get_file(db, file_id)
    if not stored_file:
        raise HTTPException(status_code=404, detail="File not found")
    _ensure_file_owner(stored_file, current_user)
    if stored_file.bind_status != "unbound":
        raise HTTPException(status_code=409, detail="File has already been bound to a book")

    lock_key = f"{settings.redis.prefix}:files:upload-session:{file_id}"
    lock_value = build_lock_value()
    if not acquire_lock(lock_key, lock_value, ttl_seconds=settings.redis.lock_ttl_seconds):
        raise HTTPException(status_code=429, detail="Upload link request is already being processed")

    try:
        db.refresh(stored_file)
        if stored_file.upload_status == "uploaded" or stored_file.parse_status in {"pending", "processing", "done"}:
            raise HTTPException(status_code=409, detail="File upload has already finished")

        if _can_refresh_same_upload(stored_file, mock_upload=settings.benchmark.mock_upload_enabled):
            return {
                **_file_payload(stored_file),
                "uploadUrl": stored_file.upload_url,
                "expiresIn": max(0, int(_remaining_upload_seconds(stored_file))),
                "headers": {"Content-Type": stored_file.content_type},
                "reused": True,
                "refreshed": False,
                "mockUpload": settings.benchmark.mock_upload_enabled,
            }

        if stored_file.upload_status not in {"init", "uploading"}:
            raise HTTPException(status_code=409, detail="File cannot request an upload link in its current state")

        if settings.benchmark.mock_upload_enabled:
            result = create_mock_upload_session(stored_file.original_filename, stored_file.content_type, stored_file.kind)
            if stored_file.object_key:
                result["object_key"] = stored_file.object_key
            else:
                stored_file.object_key = result["object_key"]
                stored_file.bucket = result["bucket"]
                stored_file.region = result["region"]
        elif stored_file.object_key:
            result = create_presigned_upload_for_object_key(stored_file.object_key, stored_file.content_type)
        else:
            result = create_presigned_upload(stored_file.original_filename, stored_file.content_type, stored_file.kind)
            stored_file.object_key = result["object_key"]
            stored_file.bucket = result["bucket"]
            stored_file.region = result["region"]

        stored_file.upload_url = result["upload_url"]
        stored_file.upload_status = "uploading"
        stored_file.upload_expires_at = datetime.utcnow() + timedelta(seconds=result["expires_in"])
        db.add(stored_file)
        db.commit()
        db.refresh(stored_file)
        return {
            **_file_payload(stored_file),
            "uploadUrl": stored_file.upload_url,
            "expiresIn": result["expires_in"],
            "headers": {"Content-Type": stored_file.content_type},
            "reused": False,
            "refreshed": True,
            "mockUpload": settings.benchmark.mock_upload_enabled,
        }
    finally:
        release_lock(lock_key, lock_value)


@router.post("/{file_id}/complete")
def upload_complete(
    file_id: int,
    payload: UploadCompleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    stored_file = get_file(db, file_id)
    if not stored_file:
        raise HTTPException(status_code=404, detail="File not found")
    _ensure_file_owner(stored_file, current_user)

    lock_key = f"{settings.redis.prefix}:files:complete:{file_id}"
    lock_value = build_lock_value()
    if not acquire_lock(lock_key, lock_value, ttl_seconds=settings.redis.lock_ttl_seconds):
        raise HTTPException(status_code=429, detail="Upload completion is already being processed")

    try:
        db.refresh(stored_file)
        if stored_file.upload_status == "uploaded":
            return {
                **_file_payload(stored_file),
                "alreadyCompleted": True,
            }
        if stored_file.upload_status != "uploading" or not stored_file.object_key:
            raise HTTPException(status_code=409, detail="File is not ready for upload completion")

        if settings.benchmark.mock_upload_enabled:
            stored_file.upload_status = "uploaded"
            stored_file.upload_url = None
            stored_file.etag = payload.etag or "server-mock"
            stored_file.parse_status = "done"

            parse_result = get_or_create_file_parse_result(db, stored_file.id, parser_mode="server-mock")
            server_mock_result = build_server_mock_parse_result(stored_file)
            parse_result.status = "done"
            parse_result.parser_mode = "server-mock"
            parse_result.title = server_mock_result["title"]
            parse_result.author = server_mock_result["author"]
            parse_result.language = server_mock_result["language"]
            parse_result.page_count = server_mock_result["page_count"]
            parse_result.cover_file_id = None
            parse_result.raw_metadata = server_mock_result["raw_metadata"]
            parse_result.error_message = None

            db.add(stored_file)
            db.add(parse_result)
            db.commit()
            delete_cached_public_file_meta(stored_file.id)
            db.refresh(stored_file)
            return {
                **_file_payload(stored_file),
                "alreadyCompleted": False,
                "parseTaskId": None,
            }

        metadata = head_object(stored_file.object_key)
        stored_file.bucket = settings.storage.bucket
        stored_file.region = settings.storage.region
        stored_file.content_type = metadata.get("ContentType", stored_file.content_type)
        stored_file.size = int(metadata.get("ContentLength", stored_file.size))
        stored_file.etag = str(metadata.get("ETag", payload.etag or "")).strip('"')
        stored_file.upload_status = "uploaded"
        stored_file.upload_url = None

        parse_task_id = None
        if stored_file.kind == "book" and settings.async_parse.enabled and settings.async_parse.mode != "off":
            stored_file.parse_status = "pending"
            parse_result = get_or_create_file_parse_result(db, stored_file.id, parser_mode=settings.async_parse.mode)
            parse_result.status = "pending"
            parse_result.error_message = None
            db.add(parse_result)
        else:
            stored_file.parse_status = "done"

        db.add(stored_file)
        db.commit()

        if stored_file.kind == "book" and settings.async_parse.enabled and settings.async_parse.mode != "off":
            try:
                parse_task_id = publish_parse_task(
                    file_id=stored_file.id,
                    parser_mode=settings.async_parse.mode,
                )
            except Exception as exc:
                db.rollback()
                stored_file = get_file(db, file_id)
                parse_result = get_or_create_file_parse_result(db, file_id, parser_mode=settings.async_parse.mode)
                parse_result.error_message = str(exc)
                parse_result.status = "done"
                stored_file.parse_status = "done"
                db.add(parse_result)
                db.add(stored_file)
                db.commit()

        delete_cached_public_file_meta(stored_file.id)
        db.refresh(stored_file)
        return {
            **_file_payload(stored_file),
            "alreadyCompleted": False,
            "parseTaskId": parse_task_id,
        }
    finally:
        release_lock(lock_key, lock_value)


@router.get("/{file_id}/download")
async def get_download_url(
    file_id: int,
    current_user: User | None = Depends(get_current_user_optional_async),
    db: AsyncSession = Depends(get_async_db),
):
    route_start = time.perf_counter()
    stored_file, public_payload = await _resolve_download_file(db, file_id, current_user)

    settings_start = time.perf_counter()
    settings = get_settings()
    await async_record_timing_metric("download.route.settings_ms", (time.perf_counter() - settings_start) * 1000.0)

    mode_branch_start = time.perf_counter()
    if settings.benchmark.mock_upload_enabled:
        await async_increment_counter("download.mode.mock")
        build_start = time.perf_counter()
        response = _build_download_response(
            {
                "downloadUrl": _build_server_mock_object_url(),
                "expiresIn": settings.storage.download_expires,
                "filename": public_payload["original_filename"],
            },
            settings,
        )
        await async_record_timing_metric("download.route.mode_branch_ms", (time.perf_counter() - mode_branch_start) * 1000.0)
        await async_record_timing_metric("download.response_build_ms", (time.perf_counter() - build_start) * 1000.0)
        await async_record_timing_metric("download.route_ms", (time.perf_counter() - route_start) * 1000.0)
        return response
    await async_record_timing_metric("download.route.mode_branch_ms", (time.perf_counter() - mode_branch_start) * 1000.0)

    cached_response, download_is_hot = await _try_get_hot_download_response(
        file_id,
        public_payload["original_filename"],
        settings,
    )
    if cached_response is not None:
        await async_record_timing_metric("download.route_ms", (time.perf_counter() - route_start) * 1000.0)
        return cached_response

    presign_start = time.perf_counter()
    download_url = await run_in_threadpool(create_presigned_download_url, stored_file)
    presign_elapsed_ms = (time.perf_counter() - presign_start) * 1000.0
    await async_record_timing_metric("download.presign_ms", presign_elapsed_ms)
    await async_record_timing_metric("download.route.presign_phase_ms", presign_elapsed_ms)
    await async_increment_counter("download.mode.real")
    response_payload = {
        "downloadUrl": download_url,
        "expiresIn": settings.storage.download_expires,
        "filename": public_payload["original_filename"],
    }
    if download_is_hot:
        hot_store_start = time.perf_counter()
        await async_set_cached_download_url_payload(file_id, response_payload)
        hot_store_elapsed_ms = (time.perf_counter() - hot_store_start) * 1000.0
        await async_record_timing_metric("download.hot_url_store_ms", hot_store_elapsed_ms)
        await async_record_timing_metric("download.route.hot_cache_store_ms", hot_store_elapsed_ms)
        await async_increment_counter("download.hot_url_cache.store")
    build_start = time.perf_counter()
    response = _build_download_response(response_payload, settings)
    response_build_elapsed_ms = (time.perf_counter() - build_start) * 1000.0
    await async_record_timing_metric("download.response_build_ms", response_build_elapsed_ms)
    await async_record_timing_metric("download.route.response_phase_ms", response_build_elapsed_ms)
    await async_record_timing_metric("download.route_ms", (time.perf_counter() - route_start) * 1000.0)
    return response


@router.get("/{file_id}/parse")
def get_parse_result(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stored_file = get_file(db, file_id)
    if not stored_file:
        raise HTTPException(status_code=404, detail="File not found")
    _ensure_file_owner(stored_file, current_user)

    result = get_file_parse_result(db, file_id)
    return {
        **_file_payload(stored_file),
        "title": result.title if result else None,
        "author": result.author if result else None,
        "language": result.language if result else None,
        "pageCount": result.page_count if result else None,
        "coverFileId": result.cover_file_id if result else None,
        "rawMetadata": result.raw_metadata if result else None,
        "errorMessage": result.error_message if result else None,
    }
