from __future__ import annotations

import json

from kafka import KafkaConsumer

from ..core.config import get_settings
from ..core.database import SessionLocal
from ..models import StoredFile
from ..repositories.file_repository import create_file_record, get_file
from ..repositories.parse_result_repository import (
    get_file_parse_result,
    get_or_create_file_parse_result,
)
from ..services.cache_service import add_unbound_cover_id
from ..services.lock_service import acquire_lock, build_lock_value, release_lock
from ..services.parse_service import parse_file_metadata
from ..services.storage_service import upload_bytes


def run_worker() -> None:
    settings = get_settings().async_parse
    consumer = KafkaConsumer(
        settings.topic_name,
        bootstrap_servers=settings.bootstrap_servers,
        group_id=settings.consumer_group,
        enable_auto_commit=False,
        auto_offset_reset=settings.auto_offset_reset,
        value_deserializer=lambda value: json.loads(value.decode("utf-8")),
    )
    try:
        for message in consumer:
            try:
                _handle_message(message.value)
            except Exception as exc:
                print(f"failed to handle parse task: {exc}", flush=True)
            consumer.commit()
    finally:
        consumer.close()


def _handle_message(payload: dict) -> None:
    file_id = int(payload["file_id"])
    parser_mode = str(payload.get("parser_mode") or get_settings().async_parse.mode)
    lock_key = f"parse:lock:{file_id}"
    lock_value = build_lock_value()
    if not acquire_lock(lock_key, lock_value, ttl_seconds=get_settings().async_parse.task_ttl_seconds):
        return

    db = SessionLocal()
    try:
        process_file_parse(db, file_id=file_id, parser_mode=parser_mode)
    except Exception as exc:
        stored_file = get_file(db, file_id)
        parse_result = get_file_parse_result(db, file_id)
        if stored_file:
            stored_file.parse_status = "done"
            db.add(stored_file)
        if parse_result:
            parse_result.status = "done"
            parse_result.error_message = str(exc)
            db.add(parse_result)
        db.commit()
    finally:
        db.close()
        release_lock(lock_key, lock_value)


def process_file_parse(db, *, file_id: int, parser_mode: str) -> None:
    stored_file = get_file(db, file_id)
    if not stored_file:
        return

    parse_result = get_or_create_file_parse_result(db, file_id, parser_mode=parser_mode)
    if parse_result.status == "done":
        return

    stored_file.parse_status = "processing"
    db.add(stored_file)
    parse_result.status = "processing"
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


def _maybe_store_cover(db, stored_file: StoredFile, parse_result: dict) -> int | None:
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


if __name__ == "__main__":
    run_worker()
