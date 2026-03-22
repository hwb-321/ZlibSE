from __future__ import annotations

from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.database import get_db
from ..core.deps import get_current_user
from ..models import User
from ..repositories.file_repository import create_file_record, get_file, is_file_referenced_by_book
from ..services.cache_service import (
    build_file_meta_cache_key,
    get_json,
    serialize_file_meta,
    set_cached_public_file_meta,
)
from ..services.storage_service import create_presigned_download_url, create_presigned_upload, head_object

router = APIRouter(prefix="/api/files", tags=["files"])


class UploadUrlRequest(BaseModel):
    filename: str
    contentType: str = "application/octet-stream"
    size: int = 0
    kind: str


class UploadCompleteRequest(BaseModel):
    objectKey: str
    originalFilename: str
    contentType: str = "application/octet-stream"
    size: int = 0
    kind: str
    etag: str | None = None


def _load_public_file_meta(db: Session, file_id: int) -> dict:
    cached = get_json(*build_file_meta_cache_key(file_id))
    if cached is not None:
        return cached

    stored_file = get_file(db, file_id)
    if not stored_file or not is_file_referenced_by_book(db, file_id):
        raise HTTPException(status_code=404, detail="File not found")

    payload = serialize_file_meta(stored_file)
    set_cached_public_file_meta(stored_file)
    return payload


@router.post("/upload-url")
def get_upload_url(
    payload: UploadUrlRequest,
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    result = create_presigned_upload(payload.filename, payload.contentType, payload.kind)
    return {
        "objectKey": result["object_key"],
        "uploadUrl": result["upload_url"],
        "expiresIn": result["expires_in"],
        "headers": {"Content-Type": result["content_type"]},
    }


@router.post("/upload-complete")
def upload_complete(
    payload: UploadCompleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = current_user
    settings = get_settings()
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
    )
    db.commit()
    return {"fileId": stored_file.id}


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
