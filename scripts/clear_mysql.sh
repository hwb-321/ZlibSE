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

readarray -t DB_INFO < <("$PYTHON_BIN" - <<'PY' "$CONFIG_FILE"
import sys
from urllib.parse import urlparse, parse_qs, unquote
import yaml

config_path = sys.argv[1]
with open(config_path, "r", encoding="utf-8") as fh:
    raw = yaml.safe_load(fh) or {}

db_url = str((raw.get("database") or {}).get("url") or "").strip()
if not db_url:
    raise SystemExit("Missing database.url in config")

parsed = urlparse(db_url)
if not parsed.scheme.startswith("mysql"):
    raise SystemExit(f"database.url is not a MySQL URL: {db_url}")

database = parsed.path.lstrip("/")
if not database:
    raise SystemExit("Missing database name in database.url")

print(parsed.hostname or "127.0.0.1")
print(parsed.port or 3306)
print(unquote(parsed.username or "root"))
print(unquote(parsed.password or ""))
print(database)
PY
)

DB_HOST="${DB_INFO[0]}"
DB_PORT="${DB_INFO[1]}"
DB_USER="${DB_INFO[2]}"
DB_PASS="${DB_INFO[3]}"
DB_NAME="${DB_INFO[4]}"

if [[ "${1:-}" != "--yes" ]]; then
  echo "About to clear MySQL data from:"
  echo "  host: $DB_HOST"
  echo "  port: $DB_PORT"
  echo "  user: $DB_USER"
  echo "  database: $DB_NAME"
  read -r -p "Type 'yes' to continue: " answer
  if [[ "$answer" != "yes" ]]; then
    echo "Aborted."
    exit 0
  fi
fi

MYSQL_ARGS=(
  "--host=$DB_HOST"
  "--port=$DB_PORT"
  "--user=$DB_USER"
  "--password=$DB_PASS"
  "$DB_NAME"
)

mysql "${MYSQL_ARGS[@]}" <<'SQL'
SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE file_parse_results;
TRUNCATE TABLE upload_tasks;
TRUNCATE TABLE uploaded_books;
TRUNCATE TABLE user_collected_books;
TRUNCATE TABLE books;
TRUNCATE TABLE stored_files;
TRUNCATE TABLE users;
SET FOREIGN_KEY_CHECKS = 1;
SQL

echo "Cleared MySQL business tables in database: $DB_NAME"
