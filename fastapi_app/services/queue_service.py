from __future__ import annotations

import json
from uuid import uuid4

import pika

from ..core.config import get_settings


def _declare(channel) -> None:
    settings = get_settings().async_parse
    channel.exchange_declare(exchange=settings.exchange_name, exchange_type="direct", durable=True)
    channel.queue_declare(queue=settings.queue_name, durable=True)
    channel.queue_bind(
        queue=settings.queue_name,
        exchange=settings.exchange_name,
        routing_key=settings.routing_key,
    )


def publish_parse_task(*, file_id: int, upload_task_id: int, parser_mode: str) -> str:
    settings = get_settings().async_parse
    task_id = uuid4().hex
    body = json.dumps(
        {
            "task_id": task_id,
            "file_id": file_id,
            "upload_task_id": upload_task_id,
            "parser_mode": parser_mode,
        },
    )
    parameters = pika.URLParameters(settings.broker_url)
    connection = pika.BlockingConnection(parameters)
    try:
        channel = connection.channel()
        _declare(channel)
        channel.basic_publish(
            exchange=settings.exchange_name,
            routing_key=settings.routing_key,
            body=body,
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type="application/json",
            ),
        )
    finally:
        connection.close()
    return task_id
