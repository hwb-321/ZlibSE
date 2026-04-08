#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_FILE="${APP_CONFIG_FILE:-$ROOT_DIR/config.yaml}"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"

if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "Config file not found: $CONFIG_FILE" >&2
  exit 1
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

echo "Initializing database with config: $CONFIG_FILE"
APP_CONFIG_FILE="$CONFIG_FILE" "$PYTHON_BIN" -m fastapi_app.init_db
