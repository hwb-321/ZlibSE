from __future__ import annotations

import mimetypes
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from ..core.config import get_settings
from ..core.schema import LEGACY_LOCAL_BUCKET, LEGACY_LOCAL_REGION
from ..models import StoredFile


def _get_client():
    import boto3
    from botocore.config import Config

    settings = get_settings().storage
    return boto3.client(
        "s3",
        region_name=settings.region,
        endpoint_url=settings.endpoint,
        aws_access_key_id=settings.secret_id,
        aws_secret_access_key=settings.secret_key,
        config=Config(
            signature_version="s3",
            s3={"addressing_style": "virtual"},
        ),
    )


def _guess_content_type(filename: str, fallback: str = "application/octet-stream") -> str:
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or fallback


def _normalize_kind(kind: str) -> str:
    kind = kind.lower().strip()
    if kind not in {"book", "cover"}:
        raise ValueError("Unsupported file kind")
    return kind


def _build_object_key(kind: str, filename: str) -> str:
    settings = get_settings().storage
    normalized_kind = _normalize_kind(kind)
    prefix = settings.book_prefix if normalized_kind == "book" else settings.cover_prefix
    ext = Path(filename or "").suffix.lower()
    now = datetime.utcnow()
    return f"{prefix}/{now:%Y/%m}/{uuid.uuid4().hex}{ext}"


def create_presigned_upload(filename: str, content_type: str, kind: str) -> dict:
    settings = get_settings().storage
    object_key = _build_object_key(kind, filename)
    normalized_content_type = content_type or _guess_content_type(filename)
    client = _get_client()
    upload_url = client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.bucket,
            "Key": object_key,
            "ContentType": normalized_content_type,
        },
        ExpiresIn=settings.upload_expires,
    )
    return {
        "bucket": settings.bucket,
        "region": settings.region,
        "object_key": object_key,
        "content_type": normalized_content_type,
        "upload_url": upload_url,
        "expires_in": settings.upload_expires,
    }


def head_object(object_key: str) -> dict:
    settings = get_settings().storage
    client = _get_client()
    return client.head_object(Bucket=settings.bucket, Key=object_key)


def upload_upload_file(upload: UploadFile, kind: str) -> dict:
    settings = get_settings().storage
    object_key = _build_object_key(kind, upload.filename or "")
    content_type = upload.content_type or _guess_content_type(upload.filename or "")
    client = _get_client()

    upload.file.seek(0)
    client.upload_fileobj(
        upload.file,
        settings.bucket,
        object_key,
        ExtraArgs={"ContentType": content_type},
    )
    metadata = client.head_object(Bucket=settings.bucket, Key=object_key)
    return {
        "bucket": settings.bucket,
        "region": settings.region,
        "object_key": object_key,
        "original_filename": upload.filename or Path(object_key).name,
        "content_type": metadata.get("ContentType", content_type),
        "size": int(metadata.get("ContentLength", 0)),
        "etag": str(metadata.get("ETag", "")).strip('"'),
        "kind": _normalize_kind(kind),
    }


def create_presigned_download_url(stored_file: StoredFile) -> str:
    if stored_file.bucket == LEGACY_LOCAL_BUCKET and stored_file.region == LEGACY_LOCAL_REGION:
        raise ValueError("Legacy local files do not have a direct COS download URL")

    settings = get_settings().storage
    client = _get_client()
    return client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": stored_file.bucket,
            "Key": stored_file.object_key,
            "ResponseContentDisposition": f"attachment; filename*=UTF-8''{quote(stored_file.original_filename)}",
        },
        ExpiresIn=settings.download_expires,
    )


def delete_object(stored_file: StoredFile) -> None:
    if stored_file.bucket == LEGACY_LOCAL_BUCKET and stored_file.region == LEGACY_LOCAL_REGION:
        local_path = Path(stored_file.object_key)
        if local_path.exists():
            local_path.unlink()
        return

    if get_settings().benchmark.mock_upload_enabled:
        return

    client = _get_client()
    client.delete_object(Bucket=stored_file.bucket, Key=stored_file.object_key)


def build_file_response(stored_file: StoredFile, *, force_download: bool = False):
    if stored_file.bucket == LEGACY_LOCAL_BUCKET and stored_file.region == LEGACY_LOCAL_REGION:
        filename = stored_file.original_filename if force_download else None
        return FileResponse(
            stored_file.object_key,
            media_type=stored_file.content_type,
            filename=filename,
        )

    client = _get_client()
    response = client.get_object(Bucket=stored_file.bucket, Key=stored_file.object_key)
    stream = response["Body"].iter_chunks()
    headers = {}
    if force_download:
        headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(stored_file.original_filename)}"
    return StreamingResponse(
        stream,
        media_type=response.get("ContentType") or stored_file.content_type,
        headers=headers,
    )
