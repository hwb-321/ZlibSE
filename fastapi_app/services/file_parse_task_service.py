from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import StoredFile
from ..repositories.file_repository import create_file_record, get_file
from ..repositories.parse_result_repository import (
    get_file_parse_result,
    get_or_create_file_parse_result,
)
from .cache_service import add_unbound_cover_id
from .parse_service import parse_file_metadata
from .storage_service import upload_bytes


def process_file_parse(db: Session, *, file_id: int, parser_mode: str) -> None:
    stored_file = get_file(db, file_id)
    if not stored_file:
        return

    parse_result = get_or_create_file_parse_result(db, file_id, parser_mode=parser_mode)
    if parse_result.status == "done":
        return

    stored_file.parse_status = "processing"
    parse_result.status = "processing"
    db.add(stored_file)
    db.add(parse_result)
    db.commit()

    error_message = None
    try:
        result = parse_file_metadata(stored_file, mode=parser_mode)
    except Exception as exc:
        error_message = str(exc)
        result = {}

    cover_file_id = _maybe_store_cover(db, stored_file, result)
    parse_result.title = result.get("title")
    parse_result.author = result.get("author")
    parse_result.language = result.get("language")
    parse_result.page_count = result.get("page_count")
    parse_result.cover_file_id = cover_file_id
    parse_result.raw_metadata = result.get("raw_metadata")
    parse_result.error_message = error_message
    parse_result.status = "done"
    stored_file.parse_status = "done"
    db.add(stored_file)
    db.add(parse_result)
    db.commit()


def mark_parse_failure(db: Session, *, file_id: int, error: Exception) -> None:
    stored_file = get_file(db, file_id)
    parse_result = get_file_parse_result(db, file_id)
    if stored_file:
        stored_file.parse_status = "done"
        db.add(stored_file)
    if parse_result:
        parse_result.status = "done"
        parse_result.error_message = str(error)
        db.add(parse_result)
    db.commit()


def _maybe_store_cover(db: Session, stored_file: StoredFile, parse_result: dict) -> int | None:
    cover_bytes = parse_result.get("cover_bytes")
    if not cover_bytes:
        return None
    payload = upload_bytes(
        data=cover_bytes,
        filename=parse_result.get("cover_filename") or "cover.png",
        content_type=parse_result.get("cover_content_type") or "image/png",
        kind="cover",
    )
    cover = create_file_record(
        db,
        user_id=stored_file.user_id,
        upload_status="uploaded",
        parse_status="done",
        bind_status="unbound",
        **payload,
    )
    db.flush()
    add_unbound_cover_id(stored_file.user_id, cover.id)
    return cover.id
