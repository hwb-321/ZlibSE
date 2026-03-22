from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


ROOT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = ROOT_DIR / "config.yaml"
DATA_PATH = ROOT_DIR / "benchmark_data.yaml"


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
