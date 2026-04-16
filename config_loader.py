from __future__ import annotations

from pathlib import Path
from typing import Any
import os

import yaml


ROOT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = Path(os.getenv("BENCHMARK_CONFIG_FILE", ROOT_DIR / "config.yaml"))
DATA_PATH = Path(os.getenv("BENCHMARK_DATA_FILE", ROOT_DIR / "benchmark_data.yaml"))
RUNTIME_STATE_PATH = Path(os.getenv("BENCHMARK_RUNTIME_STATE_FILE", ROOT_DIR / ".runtime_state.yaml"))
JWT_CACHE_PATH = Path(os.getenv("BENCHMARK_JWT_CACHE_FILE", ROOT_DIR / ".jwt_cache.yaml"))


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"YAML file not found: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML object")
    return data


def load_benchmark_config() -> dict[str, Any]:
    return _load_yaml(CONFIG_PATH)


def load_benchmark_data() -> dict[str, Any]:
    return _load_yaml(DATA_PATH)


def get_all_accounts() -> list[dict[str, Any]]:
    data = load_benchmark_data()
    accounts = data.get("accounts") or []

    if not isinstance(accounts, list):
        raise ValueError("benchmark_data.yaml accounts section must be a YAML list")

    if not accounts:
        raise ValueError("benchmark_data.yaml does not contain any benchmark accounts")
    return accounts


def read_benchmark_config_text() -> str:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"YAML file not found: {CONFIG_PATH}")
    return CONFIG_PATH.read_text(encoding="utf-8")


def save_benchmark_config_text(content: str) -> None:
    data = yaml.safe_load(content) or {}
    if not isinstance(data, dict):
        raise ValueError("config.yaml must contain a YAML object")
    CONFIG_PATH.write_text(content, encoding="utf-8")


def load_runtime_state() -> dict[str, Any]:
    if not RUNTIME_STATE_PATH.exists():
        return {}
    data = yaml.safe_load(RUNTIME_STATE_PATH.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("runtime state must contain a YAML object")
    return data


def save_runtime_state(data: dict[str, Any]) -> None:
    if not isinstance(data, dict):
        raise ValueError("runtime state must contain a YAML object")
    RUNTIME_STATE_PATH.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def load_jwt_cache() -> dict[str, Any]:
    if not JWT_CACHE_PATH.exists():
        return {}
    data = yaml.safe_load(JWT_CACHE_PATH.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("jwt cache must contain a YAML object")
    return data


def save_jwt_cache(data: dict[str, Any]) -> None:
    if not isinstance(data, dict):
        raise ValueError("jwt cache must contain a YAML object")
    JWT_CACHE_PATH.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
