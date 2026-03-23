from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_CONFIG_PATH = ROOT_DIR / "config.yaml"


@dataclass(frozen=True)
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False
    workers: int = 1
    access_log: bool = True


@dataclass(frozen=True)
class SecurityConfig:
    jwt_secret_key: str = "dev-jwt-secret-change-me-please-use-32bytes-min"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_days: int = 7
    captcha_enabled: bool = True


@dataclass(frozen=True)
class DatabaseConfig:
    url: str


@dataclass(frozen=True)
class StorageConfig:
    provider: str
    bucket: str
    region: str
    endpoint: str
    secret_id: str
    secret_key: str
    upload_expires: int
    download_expires: int
    book_prefix: str
    cover_prefix: str


@dataclass(frozen=True)
class BenchmarkConfig:
    mock_upload_enabled: bool = False


@dataclass(frozen=True)
class AsyncParseConfig:
    enabled: bool = False
    mode: str = "off"
    broker: str = "rabbitmq"
    broker_url: str = "amqp://guest:guest@127.0.0.1:5672/%2F"
    queue_name: str = "zlibse.file.parse"
    exchange_name: str = "zlibse.file"
    routing_key: str = "parse"
    task_ttl_seconds: int = 3600


@dataclass(frozen=True)
class RedisConfig:
    enabled: bool = False
    url: str = "redis://127.0.0.1:6379/0"
    prefix: str = "zlibse"
    default_ttl_seconds: int = 300
    book_list_ttl_seconds: int = 120
    book_search_ttl_seconds: int = 120
    book_detail_ttl_seconds: int = 300
    token_version_ttl_seconds: int = 300
    file_meta_ttl_seconds: int = 300
    empty_ttl_seconds: int = 30
    lock_ttl_seconds: int = 10
    bloom_expected_items: int = 10000
    bloom_error_rate: float = 0.01


@dataclass(frozen=True)
class LocalCacheConfig:
    enabled: bool = True
    max_entries: int = 1024
    default_ttl_seconds: int = 30
    book_detail_ttl_seconds: int = 20
    file_meta_ttl_seconds: int = 20
    empty_ttl_seconds: int = 10


@dataclass(frozen=True)
class AppConfig:
    server: ServerConfig
    security: SecurityConfig
    database: DatabaseConfig
    storage: StorageConfig
    benchmark: BenchmarkConfig
    async_parse: AsyncParseConfig
    redis: RedisConfig
    local_cache: LocalCacheConfig
    cors_allow_origins: list[str]


def _read_yaml_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config file must contain a YAML object: {path}")
    return data


def _as_str_list(value: Any, default: list[str]) -> list[str]:
    if value is None:
        return default
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError("cors.allow_origins must be a list of strings")
    return value


@lru_cache(maxsize=1)
def get_settings() -> AppConfig:
    config_path = Path(os.getenv("APP_CONFIG_FILE", DEFAULT_CONFIG_PATH))
    raw = _read_yaml_config(config_path)

    server_raw = raw.get("server") or {}
    security_raw = raw.get("security") or {}
    database_raw = raw.get("database") or {}
    storage_raw = raw.get("storage") or {}
    benchmark_raw = raw.get("benchmark") or {}
    async_parse_raw = raw.get("async_parse") or {}
    redis_raw = raw.get("redis") or {}
    local_cache_raw = raw.get("local_cache") or {}
    cors_raw = raw.get("cors") or {}

    server = ServerConfig(
        host=str(server_raw.get("host", "0.0.0.0")),
        port=int(server_raw.get("port", 8000)),
        reload=bool(server_raw.get("reload", False)),
        workers=max(1, int(server_raw.get("workers", 1))),
        access_log=bool(server_raw.get("access_log", True)),
    )
    security = SecurityConfig(
        jwt_secret_key=str(
            security_raw.get("jwt_secret_key", "dev-jwt-secret-change-me-please-use-32bytes-min")
        ),
        jwt_algorithm=str(security_raw.get("jwt_algorithm", "HS256")),
        jwt_access_token_expire_days=int(security_raw.get("jwt_access_token_expire_days", 7)),
        captcha_enabled=bool(security_raw.get("captcha_enabled", True)),
    )

    database_url = database_raw.get("url")
    if database_url:
        database = DatabaseConfig(url=str(database_url))
    else:
        sqlite_path = Path(database_raw.get("sqlite_path", "zlibse.db"))
        if not sqlite_path.is_absolute():
            sqlite_path = ROOT_DIR / sqlite_path
        database = DatabaseConfig(url=f"sqlite:///{sqlite_path.as_posix()}")

    storage = StorageConfig(
        provider=str(storage_raw.get("provider", "cos")),
        bucket=str(storage_raw.get("bucket", "")),
        region=str(storage_raw.get("region", "ap-beijing")),
        endpoint=str(storage_raw.get("endpoint", "https://cos.ap-beijing.myqcloud.com")),
        secret_id=str(storage_raw.get("secret_id", "")),
        secret_key=str(storage_raw.get("secret_key", "")),
        upload_expires=int(storage_raw.get("upload_expires", 900)),
        download_expires=int(storage_raw.get("download_expires", 300)),
        book_prefix=str(storage_raw.get("book_prefix", "books")),
        cover_prefix=str(storage_raw.get("cover_prefix", "covers")),
    )
    benchmark = BenchmarkConfig(
        mock_upload_enabled=bool(benchmark_raw.get("mock_upload_enabled", False)),
    )
    async_parse = AsyncParseConfig(
        enabled=bool(async_parse_raw.get("enabled", False)),
        mode=str(async_parse_raw.get("mode", "off")).lower(),
        broker=str(async_parse_raw.get("broker", "rabbitmq")),
        broker_url=str(async_parse_raw.get("broker_url", "amqp://guest:guest@127.0.0.1:5672/%2F")),
        queue_name=str(async_parse_raw.get("queue_name", "zlibse.file.parse")),
        exchange_name=str(async_parse_raw.get("exchange_name", "zlibse.file")),
        routing_key=str(async_parse_raw.get("routing_key", "parse")),
        task_ttl_seconds=max(1, int(async_parse_raw.get("task_ttl_seconds", 3600))),
    )
    redis = RedisConfig(
        enabled=bool(redis_raw.get("enabled", False)),
        url=str(redis_raw.get("url", "redis://127.0.0.1:6379/0")),
        prefix=str(redis_raw.get("prefix", "zlibse")),
        default_ttl_seconds=max(1, int(redis_raw.get("default_ttl_seconds", 300))),
        book_list_ttl_seconds=max(1, int(redis_raw.get("book_list_ttl_seconds", 120))),
        book_search_ttl_seconds=max(1, int(redis_raw.get("book_search_ttl_seconds", 120))),
        book_detail_ttl_seconds=max(1, int(redis_raw.get("book_detail_ttl_seconds", 300))),
        token_version_ttl_seconds=max(1, int(redis_raw.get("token_version_ttl_seconds", 300))),
        file_meta_ttl_seconds=max(1, int(redis_raw.get("file_meta_ttl_seconds", 300))),
        empty_ttl_seconds=max(1, int(redis_raw.get("empty_ttl_seconds", 30))),
        lock_ttl_seconds=max(1, int(redis_raw.get("lock_ttl_seconds", 10))),
        bloom_expected_items=max(100, int(redis_raw.get("bloom_expected_items", 10000))),
        bloom_error_rate=max(0.0001, float(redis_raw.get("bloom_error_rate", 0.01))),
    )
    local_cache = LocalCacheConfig(
        enabled=bool(local_cache_raw.get("enabled", True)),
        max_entries=max(16, int(local_cache_raw.get("max_entries", 1024))),
        default_ttl_seconds=max(1, int(local_cache_raw.get("default_ttl_seconds", 30))),
        book_detail_ttl_seconds=max(1, int(local_cache_raw.get("book_detail_ttl_seconds", 20))),
        file_meta_ttl_seconds=max(1, int(local_cache_raw.get("file_meta_ttl_seconds", 20))),
        empty_ttl_seconds=max(1, int(local_cache_raw.get("empty_ttl_seconds", 10))),
    )

    cors_allow_origins = _as_str_list(
        cors_raw.get("allow_origins"),
        [
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "http://4070s-linux.xinghen.ip-ddns.com:8080",
        ],
    )

    return AppConfig(
        server=server,
        security=security,
        database=database,
        storage=storage,
        benchmark=benchmark,
        async_parse=async_parse,
        redis=redis,
        local_cache=local_cache,
        cors_allow_origins=cors_allow_origins,
    )
