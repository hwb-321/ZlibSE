from __future__ import annotations

import json
import threading
from uuid import uuid4

import pika

from ..core.config import get_settings

_connection_lock = threading.Lock()
_publish_lock = threading.Lock()
_connection: pika.BlockingConnection | None = None
_channel = None
_declared_signature: tuple[str, str, str] | None = None


def _declare(channel) -> None:
    settings = get_settings().async_parse
    channel.exchange_declare(exchange=settings.exchange_name, exchange_type="direct", durable=True)
    channel.queue_declare(queue=settings.queue_name, durable=True)
    channel.queue_bind(
        queue=settings.queue_name,
        exchange=settings.exchange_name,
        routing_key=settings.routing_key,
    )


def _get_channel():
    global _connection, _channel, _declared_signature
    settings = get_settings().async_parse
    signature = (settings.exchange_name, settings.queue_name, settings.routing_key)

    with _connection_lock:
        if _connection is None or _connection.is_closed:
            parameters = pika.URLParameters(settings.broker_url)
            _connection = pika.BlockingConnection(parameters)
            _channel = _connection.channel()
            _declared_signature = None

        assert _channel is not None
        if _declared_signature != signature or _channel.is_closed:
            if _channel.is_closed:
                _channel = _connection.channel()
            _declare(_channel)
            _declared_signature = signature
        return _channel


def publish_parse_task(*, file_id: int, parser_mode: str) -> str:
    settings = get_settings().async_parse
    task_id = uuid4().hex
    body = json.dumps(
        {
            "task_id": task_id,
            "file_id": file_id,
            "parser_mode": parser_mode,
        },
    )
    with _publish_lock:
        channel = _get_channel()
        channel.basic_publish(
            exchange=settings.exchange_name,
            routing_key=settings.routing_key,
            body=body,
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type="application/json",
            ),
        )
    return task_id
