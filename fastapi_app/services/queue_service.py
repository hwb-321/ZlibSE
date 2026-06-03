from __future__ import annotations

import json
import threading
from uuid import uuid4

from kafka import KafkaProducer

from ..core.config import get_settings


_producer_lock = threading.Lock()
_publish_lock = threading.Lock()
_producer: KafkaProducer | None = None
_producer_signature: tuple[str, str] | None = None


def _get_producer() -> KafkaProducer:
    global _producer, _producer_signature
    settings = get_settings().async_parse
    signature = (settings.bootstrap_servers, settings.topic_name)

    with _producer_lock:
        if _producer is None or _producer_signature != signature:
            if _producer is not None:
                _producer.close(timeout=5)
            _producer = KafkaProducer(
                bootstrap_servers=settings.bootstrap_servers,
                key_serializer=lambda value: str(value).encode("utf-8"),
                value_serializer=lambda value: json.dumps(value, ensure_ascii=False).encode("utf-8"),
                acks="all",
                retries=3,
            )
            _producer_signature = signature
        return _producer


def publish_parse_task(*, file_id: int, parser_mode: str) -> str:
    settings = get_settings().async_parse
    task_id = uuid4().hex
    payload = {
        "task_id": task_id,
        "file_id": int(file_id),
        "parser_mode": parser_mode,
    }
    with _publish_lock:
        producer = _get_producer()
        future = producer.send(settings.topic_name, key=file_id, value=payload)
        future.get(timeout=10)
        producer.flush(timeout=5)
    return task_id
