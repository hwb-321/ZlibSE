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
    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = False


@dataclass(frozen=True)
class SecurityConfig:
    session_secret: str = "dev-session-secret-change-me"


@dataclass(frozen=True)
class DatabaseConfig:
    sqlite_path: Path


@dataclass(frozen=True)
class AppConfig:
    server: ServerConfig
    security: SecurityConfig
    database: DatabaseConfig
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
    cors_raw = raw.get("cors") or {}

    server = ServerConfig(
        host=str(server_raw.get("host", "127.0.0.1")),
        port=int(server_raw.get("port", 8000)),
        reload=bool(server_raw.get("reload", False)),
    )
    security = SecurityConfig(
        session_secret=str(
            os.getenv(
                "SESSION_SECRET",
                security_raw.get("session_secret", "dev-session-secret-change-me"),
            )
        )
    )
    sqlite_path = Path(database_raw.get("sqlite_path", "zlibse.db"))
    if not sqlite_path.is_absolute():
        sqlite_path = ROOT_DIR / sqlite_path
    database = DatabaseConfig(sqlite_path=sqlite_path)

    cors_allow_origins = _as_str_list(
        cors_raw.get("allow_origins"),
        [
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "http://192.168.157.177:8080",
        ],
    )

    return AppConfig(
        server=server,
        security=security,
        database=database,
        cors_allow_origins=cors_allow_origins,
    )
