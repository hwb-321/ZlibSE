from __future__ import annotations

import json

import pika

from ..core.config import get_settings
from ..core.database import SessionLocal
from ..models import StoredFile
from ..repositories.file_repository import create_file_record, get_file
from ..repositories.upload_task_repository import (
    get_file_parse_result,
    get_or_create_file_parse_result,
    get_upload_task_by_object_key,
    mark_upload_task_status,
)
from ..services.lock_service import acquire_lock, build_lock_value, release_lock
from ..services.parse_service import parse_file_metadata
from ..services.storage_service import upload_bytes


def run_worker() -> None:
    settings = get_settings().async_parse
    parameters = pika.URLParameters(settings.broker_url)
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    channel.exchange_declare(exchange=settings.exchange_name, exchange_type="direct", durable=True)
    channel.queue_declare(queue=settings.queue_name, durable=True)
    channel.queue_bind(queue=settings.queue_name, exchange=settings.exchange_name, routing_key=settings.routing_key)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=settings.queue_name, on_message_callback=_handle_message)
    channel.start_consuming()


def _handle_message(channel, method, _properties, body: bytes) -> None:
    payload = json.loads(body.decode("utf-8"))
    file_id = int(payload["file_id"])
    parser_mode = str(payload.get("parser_mode") or get_settings().async_parse.mode)
    lock_key = f"parse:lock:{file_id}"
    lock_value = build_lock_value()
    if not acquire_lock(lock_key, lock_value, ttl_seconds=get_settings().async_parse.task_ttl_seconds):
        channel.basic_ack(delivery_tag=method.delivery_tag)
        return

    db = SessionLocal()
    try:
        stored_file = get_file(db, file_id)
        if not stored_file:
            channel.basic_ack(delivery_tag=method.delivery_tag)
            return

        parse_result = get_or_create_file_parse_result(db, file_id, parser_mode=parser_mode)
        if parse_result.status == "done":
            channel.basic_ack(delivery_tag=method.delivery_tag)
            return

        parse_result.status = "processing"
        db.add(parse_result)
        db.commit()

        result = parse_file_metadata(stored_file, mode=parser_mode)
        cover_file_id = _maybe_store_cover(db, stored_file, result)
        parse_result.title = result.get("title")
        parse_result.author = result.get("author")
        parse_result.language = result.get("language")
        parse_result.page_count = result.get("page_count")
        parse_result.cover_file_id = cover_file_id
        parse_result.raw_metadata = result.get("raw_metadata")
        parse_result.error_message = None
        parse_result.status = "done"
        db.add(parse_result)
        _mark_related_task_parsed(db, stored_file.object_key)
        db.commit()
        channel.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as exc:
        parse_result = get_file_parse_result(db, file_id)
        if parse_result:
            parse_result.status = "failed"
            parse_result.error_message = str(exc)
            db.add(parse_result)
        _mark_related_task_failed(db, file_id, str(exc))
        db.commit()
        channel.basic_ack(delivery_tag=method.delivery_tag)
    finally:
        db.close()
        release_lock(lock_key, lock_value)


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
    cover = create_file_record(db, user_id=stored_file.user_id, **payload)
    db.flush()
    return cover.id


def _mark_related_task_parsed(db, object_key: str) -> None:
    task = get_upload_task_by_object_key(db, object_key)
    if not task:
        return
    mark_upload_task_status(db, task, status="parsed", file_id=task.file_id)


def _mark_related_task_failed(db, file_id: int, error_message: str) -> None:
    stored_file = get_file(db, file_id)
    if not stored_file:
        return
    task = get_upload_task_by_object_key(db, stored_file.object_key)
    if not task:
        return
    mark_upload_task_status(db, task, status="failed", file_id=task.file_id, error_message=error_message)


if __name__ == "__main__":
    run_worker()
