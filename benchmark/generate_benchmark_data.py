from __future__ import annotations

import sys
from pathlib import Path

import yaml


BENCHMARK_DIR = Path(__file__).resolve().parent
ROOT_DIR = BENCHMARK_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

CONFIG_PATH = BENCHMARK_DIR / "config.yaml"
OUTPUT_PATH = BENCHMARK_DIR / "benchmark_data.yaml"


def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config file not found: {CONFIG_PATH}")

    data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("benchmark/config.yaml must contain a YAML object")
    return data


def _get_accounts_config(config: dict) -> dict:
    accounts = config.get("accounts") or {}
    if not isinstance(accounts, dict):
        raise ValueError("accounts must be a YAML object")
    return accounts


def _get_books_config(config: dict) -> dict:
    books = config.get("books") or {}
    if not isinstance(books, dict):
        raise ValueError("books must be a YAML object")
    return books


def _build_books(username: str, books_config: dict) -> list[dict[str, object]]:
    books_per_user = int(books_config.get("books_per_user", 0))
    if books_per_user < 0:
        raise ValueError("books.books_per_user must be >= 0")

    include_cover = bool(books_config.get("include_cover", True))
    default_category = str(books_config.get("default_category", "benchmark")).strip()
    default_language = str(books_config.get("default_language", "zh-CN")).strip()
    default_year = int(books_config.get("default_year", 2024))

    books: list[dict[str, object]] = []
    for index in range(1, books_per_user + 1):
        book: dict[str, object] = {
            "title": f"压测书籍 {username} #{index:03d}",
            "author": username,
            "isbn": f"BENCH-{username}-{index:03d}",
            "category": default_category,
            "year": default_year,
            "language": default_language,
            "book_file": {
                "object_key": f"benchmark/books/{username}/{index:03d}.epub",
                "original_filename": f"{username}_{index:03d}.epub",
                "content_type": "application/epub+zip",
                "size": 2 * 1024 * 1024,
                "kind": "book",
                "etag": f"benchmark-book-{username}-{index:03d}",
            },
        }
        if include_cover:
            book["cover_file"] = {
                "object_key": f"benchmark/covers/{username}/{index:03d}.jpg",
                "original_filename": f"{username}_{index:03d}.jpg",
                "content_type": "image/jpeg",
                "size": 128 * 1024,
                "kind": "cover",
                "etag": f"benchmark-cover-{username}-{index:03d}",
            }
        books.append(book)
    return books


def _build_accounts(accounts_config: dict, books_config: dict) -> list[dict[str, object]]:
    user_count = int(accounts_config.get("user_count", 0))
    if user_count < 0:
        raise ValueError("accounts.user_count must be >= 0")

    username_prefix = str(accounts_config.get("username_prefix", "bench_user")).strip()
    email_domain = str(accounts_config.get("email_domain", "benchmark.local")).strip()
    default_password = str(accounts_config.get("default_password", "")).strip()
    if not username_prefix:
        raise ValueError("accounts.username_prefix must not be empty")
    if not email_domain:
        raise ValueError("accounts.email_domain must not be empty")
    if not default_password:
        raise ValueError("accounts.default_password must not be empty")

    users: list[dict[str, object]] = []
    for index in range(1, user_count + 1):
        username = f"{username_prefix}_{index:03d}"
        users.append(
            {
                "username": username,
                "email": f"{username}@{email_domain}",
                "password": default_password,
                "books": _build_books(username, books_config),
            }
        )
    return users


def _build_output(config: dict) -> dict[str, object]:
    accounts_config = _get_accounts_config(config)
    books_config = _get_books_config(config)
    users = _build_accounts(accounts_config, books_config)

    output: dict[str, object] = {
        "generated_from": str(CONFIG_PATH.relative_to(BENCHMARK_DIR.parent)),
        "accounts": users,
    }
    return output


def main() -> None:
    config = _load_config()
    output = _build_output(config)
    OUTPUT_PATH.write_text(
        yaml.safe_dump(output, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"Generated {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
