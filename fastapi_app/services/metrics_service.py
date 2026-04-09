from __future__ import annotations

from datetime import datetime

from ..core.config import get_settings
from ..core.redis import get_async_redis_client, get_redis_client


def _get_client():
    settings = get_settings()
    if not getattr(settings, "debug_metrics", None) or not settings.debug_metrics.enabled:
        return None
    return get_redis_client()


def _get_async_client():
    settings = get_settings()
    if not getattr(settings, "debug_metrics", None) or not settings.debug_metrics.enabled:
        return None
    return get_async_redis_client()


def _key(*parts: object) -> str:
    prefix = get_settings().redis.prefix
    suffix = ":".join(str(part) for part in parts)
    return f"{prefix}:{suffix}"


def _metric_key(kind: str, name: str) -> str:
    return _key("debug", "metrics", kind, name)


def _safe_name(value: str) -> str:
    return value.replace(" ", "_")


def record_request_metric(*, method: str, route: str, status_code: int, duration_ms: float) -> None:
    client = _get_client()
    if client is None:
        return
    metric_name = _safe_name(f"{method}:{route}")
    key = _metric_key("request", metric_name)
    try:
        pipeline = client.pipeline()
        pipeline.hset(key, mapping={"method": method, "route": route, "kind": "request"})
        pipeline.hincrby(key, "count", 1)
        pipeline.hincrbyfloat(key, "total_ms", float(duration_ms))
        pipeline.hset(key, "last_status", int(status_code))
        pipeline.hset(key, "updated_at", datetime.utcnow().isoformat())
        if status_code >= 400:
            pipeline.hincrby(key, "failures", 1)
        pipeline.execute()
    except Exception:
        return


def record_timing_metric(name: str, duration_ms: float) -> None:
    client = _get_client()
    if client is None:
        return
    key = _metric_key("timing", _safe_name(name))
    try:
        pipeline = client.pipeline()
        pipeline.hset(key, mapping={"name": name, "kind": "timing"})
        pipeline.hincrby(key, "count", 1)
        pipeline.hincrbyfloat(key, "total_ms", float(duration_ms))
        pipeline.hset(key, "updated_at", datetime.utcnow().isoformat())
        pipeline.execute()
    except Exception:
        return


async def async_record_timing_metric(name: str, duration_ms: float) -> None:
    client = _get_async_client()
    if client is None:
        return
    key = _metric_key("timing", _safe_name(name))
    try:
        pipeline = client.pipeline()
        pipeline.hset(key, mapping={"name": name, "kind": "timing"})
        pipeline.hincrby(key, "count", 1)
        pipeline.hincrbyfloat(key, "total_ms", float(duration_ms))
        pipeline.hset(key, "updated_at", datetime.utcnow().isoformat())
        await pipeline.execute()
    except Exception:
        return


def increment_counter(name: str, amount: int = 1) -> None:
    client = _get_client()
    if client is None:
        return
    key = _metric_key("counter", _safe_name(name))
    try:
        pipeline = client.pipeline()
        pipeline.hset(key, mapping={"name": name, "kind": "counter"})
        pipeline.hincrby(key, "count", int(amount))
        pipeline.hset(key, "updated_at", datetime.utcnow().isoformat())
        pipeline.execute()
    except Exception:
        return


async def async_increment_counter(name: str, amount: int = 1) -> None:
    client = _get_async_client()
    if client is None:
        return
    key = _metric_key("counter", _safe_name(name))
    try:
        pipeline = client.pipeline()
        pipeline.hset(key, mapping={"name": name, "kind": "counter"})
        pipeline.hincrby(key, "count", int(amount))
        pipeline.hset(key, "updated_at", datetime.utcnow().isoformat())
        await pipeline.execute()
    except Exception:
        return


def read_all_metrics() -> dict:
    settings = get_settings()
    if not settings.debug_metrics.enabled:
        return {
            "enabled": False,
            "generatedAt": datetime.utcnow().isoformat(),
            "requests": [],
            "timings": [],
            "counters": {},
        }

    client = _get_client()
    if client is None:
        return {
            "enabled": False,
            "generatedAt": datetime.utcnow().isoformat(),
            "requests": [],
            "timings": [],
            "counters": {},
        }

    pattern = _metric_key("*", "*")
    requests: list[dict] = []
    timings: list[dict] = []
    counters: dict[str, int] = {}
    try:
        for key in client.scan_iter(match=pattern):
            payload = client.hgetall(key)
            kind = payload.get("kind")
            if kind == "request":
                count = int(payload.get("count", 0))
                total_ms = float(payload.get("total_ms", 0.0))
                failures = int(payload.get("failures", 0))
                requests.append(
                    {
                        "method": payload.get("method", ""),
                        "route": payload.get("route", ""),
                        "count": count,
                        "failures": failures,
                        "totalMs": round(total_ms, 2),
                        "avgMs": round(total_ms / count, 2) if count else 0.0,
                        "lastStatus": int(payload.get("last_status", 0) or 0),
                        "updatedAt": payload.get("updated_at"),
                    }
                )
            elif kind == "timing":
                count = int(payload.get("count", 0))
                total_ms = float(payload.get("total_ms", 0.0))
                timings.append(
                    {
                        "name": payload.get("name", ""),
                        "count": count,
                        "totalMs": round(total_ms, 2),
                        "avgMs": round(total_ms / count, 2) if count else 0.0,
                        "updatedAt": payload.get("updated_at"),
                    }
                )
            elif kind == "counter":
                counters[payload.get("name", key)] = int(payload.get("count", 0))
    except Exception:
        return {
            "enabled": False,
            "generatedAt": datetime.utcnow().isoformat(),
            "requests": [],
            "timings": [],
            "counters": {},
        }

    requests.sort(key=lambda item: (item["route"], item["method"]))
    timings.sort(key=lambda item: item["name"])
    counters = dict(sorted(counters.items()))
    return {
        "enabled": True,
        "generatedAt": datetime.utcnow().isoformat(),
        "requests": requests,
        "timings": timings,
        "counters": counters,
    }


def reset_all_metrics() -> None:
    client = _get_client()
    if client is None:
        return
    try:
        keys = list(client.scan_iter(match=_metric_key("*", "*")))
        if keys:
            client.delete(*keys)
    except Exception:
        return
