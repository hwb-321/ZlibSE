#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

OLDER_THAN_SECONDS="${1:-}"

if [[ -n "$OLDER_THAN_SECONDS" ]]; then
  "$PYTHON_BIN" - <<'PY' "$OLDER_THAN_SECONDS"
import sys
from fastapi_app.workers.cleanup_expired_uploads import cleanup_expired_uploads

older_than_seconds = int(sys.argv[1])
count = cleanup_expired_uploads(older_than_seconds=older_than_seconds)
print(f"cleaned_upload_tasks={count}")
PY
else
  "$PYTHON_BIN" -m fastapi_app.workers.cleanup_expired_uploads
fi
