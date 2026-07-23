from __future__ import annotations

import json

from kafka import KafkaConsumer

from ..core.config import get_settings
from ..core.database import SessionLocal
import time

from ..services.file_parse_task_service import mark_parse_failure, process_file_parse
from ..services.lock_service import acquire_lock, build_lock_value, release_lock
from ..services.metrics_service import increment_counter, record_timing_metric


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
    process_start = time.perf_counter()
    try:
        process_file_parse(db, file_id=file_id, parser_mode=parser_mode)
        increment_counter("parse.worker.completed")
    except Exception as exc:
        mark_parse_failure(db, file_id=file_id, error=exc)
        increment_counter("parse.worker.failed")
    finally:
        record_timing_metric("parse.worker.process_ms", (time.perf_counter() - process_start) * 1000.0)
        db.close()
        release_lock(lock_key, lock_value)


if __name__ == "__main__":
    run_worker()
