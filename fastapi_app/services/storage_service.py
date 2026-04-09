from __future__ import annotations

import time
import mimetypes
import uuid
from functools import lru_cache
from datetime import datetime
from io import BytesIO
from pathlib import Path

from ..core.config import get_settings
from ..models import StoredFile
from .metrics_service import record_timing_metric


@lru_cache(maxsize=1)
def _build_client():
    import boto3
    from botocore.config import Config

    settings = get_settings().storage
    build_start = time.perf_counter()
    client = boto3.client(
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
    record_timing_metric("download.client_build_ms", (time.perf_counter() - build_start) * 1000.0)
    return client


def _get_client():
    return _build_client()


def prewarm_storage_client() -> None:
    _get_client()


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
    object_key = _build_object_key(kind, filename)
    return create_presigned_upload_for_object_key(object_key, content_type or _guess_content_type(filename))


def create_mock_upload_session(filename: str, content_type: str, kind: str) -> dict:
    object_key = _build_object_key(kind, filename)
    settings = get_settings().storage
    normalized_content_type = content_type or _guess_content_type(filename)
    return {
        "bucket": settings.bucket,
        "region": settings.region,
        "object_key": object_key,
        "content_type": normalized_content_type,
        "upload_url": None,
        "expires_in": settings.upload_expires,
    }


def create_presigned_upload_for_object_key(object_key: str, content_type: str) -> dict:
    settings = get_settings().storage
    normalized_content_type = content_type or "application/octet-stream"
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


def upload_bytes(*, data: bytes, filename: str, content_type: str, kind: str) -> dict:
    settings = get_settings().storage
    object_key = _build_object_key(kind, filename)
    client = _get_client()
    client.upload_fileobj(
        BytesIO(data),
        settings.bucket,
        object_key,
        ExtraArgs={"ContentType": content_type},
    )
    metadata = client.head_object(Bucket=settings.bucket, Key=object_key)
    return {
        "bucket": settings.bucket,
        "region": settings.region,
        "object_key": object_key,
        "original_filename": filename or Path(object_key).name,
        "content_type": metadata.get("ContentType", content_type),
        "size": int(metadata.get("ContentLength", len(data))),
        "etag": str(metadata.get("ETag", "")).strip('"'),
        "kind": _normalize_kind(kind),
    }


def download_object_bytes(stored_file: StoredFile) -> bytes:
    client = _get_client()
    response = client.get_object(Bucket=stored_file.bucket, Key=stored_file.object_key)
    return response["Body"].read()


def create_presigned_download_url(stored_file: StoredFile) -> str:
    return create_presigned_object_url_for_object_key(
        stored_file.bucket,
        stored_file.object_key,
        expires_in=get_settings().storage.download_expires,
    )


def create_presigned_object_url_for_object_key(bucket: str, object_key: str, *, expires_in: int | None = None) -> str:
    settings = get_settings().storage
    client = _get_client()
    generate_start = time.perf_counter()
    url = client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": bucket,
            "Key": object_key,
        },
        ExpiresIn=expires_in or settings.download_expires,
    )
    record_timing_metric("download.generate_url_ms", (time.perf_counter() - generate_start) * 1000.0)
    return url


def delete_object(stored_file: StoredFile) -> None:
    if get_settings().benchmark.mock_upload_enabled:
        return

    client = _get_client()
    client.delete_object(Bucket=stored_file.bucket, Key=stored_file.object_key)
