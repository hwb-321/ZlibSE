from __future__ import annotations

import json
import http.cookiejar
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BENCHMARK_DIR = Path(__file__).resolve().parent
ROOT_DIR = BENCHMARK_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tqdm import tqdm

from benchmark.config_loader import get_all_accounts, load_benchmark_config


BOOK_TITLE_PREFIX = "压测书籍"


def _build_opener():
    cookie_jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))


def _json_request(opener, method: str, url: str, payload: dict | None = None) -> dict:
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with opener.open(request) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"{method} {url} failed: {exc.code} {detail}") from exc


def _form_request(opener, method: str, url: str, payload: dict[str, str]) -> dict:
    data = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method)
    try:
        with opener.open(request) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"{method} {url} failed: {exc.code} {detail}") from exc


def _login(base_url: str, opener, account: dict[str, object]) -> None:
    payload = {
        "username": str(account["username"]),
        "password": str(account["password"]),
        "captcha_key": "",
        "captcha_value": "",
    }
    data = _form_request(opener, "POST", f"{base_url}/user/login_user", payload)
    if not data.get("success"):
        raise RuntimeError(f"login failed for {account['username']}: {data}")


def _list_uploaded_books(base_url: str, opener) -> list[dict]:
    data = _json_request(opener, "GET", f"{base_url}/user/get_upload_book_list")
    books = data.get("uploadedBooks", [])
    if not isinstance(books, list):
        raise RuntimeError("uploadedBooks response is invalid")
    return books


def _delete_existing_benchmark_books(base_url: str, opener) -> int:
    deleted_count = 0
    for book in _list_uploaded_books(base_url, opener):
        title = str(book.get("title", ""))
        if not title.startswith(BOOK_TITLE_PREFIX):
            continue
        _json_request(opener, "POST", f"{base_url}/user/delete_uploaded_book/{book['id']}")
        deleted_count += 1
    return deleted_count


def _create_mock_file(base_url: str, opener, file_payload: dict[str, object]) -> int:
    data = _json_request(
        opener,
        "POST",
        f"{base_url}/api/files/upload-complete",
        {
            "objectKey": str(file_payload["object_key"]),
            "originalFilename": str(file_payload["original_filename"]),
            "contentType": str(file_payload["content_type"]),
            "size": int(file_payload["size"]),
            "kind": str(file_payload["kind"]),
            "etag": str(file_payload.get("etag", "")),
        },
    )
    file_id = data.get("fileId")
    if not isinstance(file_id, int):
        raise RuntimeError(f"upload-complete did not return a valid fileId: {data}")
    return file_id


def _create_book(base_url: str, opener, book_payload: dict[str, object], book_file_id: int, cover_file_id: int | None) -> None:
    data = _json_request(
        opener,
        "POST",
        f"{base_url}/api/books",
        {
            "title": str(book_payload["title"]),
            "author": str(book_payload.get("author", "")),
            "isbn": str(book_payload.get("isbn", "")),
            "category": str(book_payload.get("category", "")),
            "year": int(book_payload.get("year", 2024)),
            "language": str(book_payload.get("language", "")),
            "bookFileId": book_file_id,
            "coverFileId": cover_file_id,
        },
    )
    if not data.get("success"):
        raise RuntimeError(f"create book failed: {data}")


def sync_users() -> tuple[int, int, int, int]:
    accounts = get_all_accounts()
    config = load_benchmark_config()
    base_url = str(config.get("base_url", "http://127.0.0.1:8000")).rstrip("/")

    created_count = 0
    existing_count = 0
    created_book_count = 0
    deleted_book_count = 0

    total_books = sum(
        len(account.get("books", []))
        for account in accounts
        if isinstance(account, dict) and isinstance(account.get("books", []), list)
    )
    progress = tqdm(total=len(accounts) + total_books, desc="初始化压测数据", unit="项")

    for account in accounts:
        opener = _build_opener()
        data = _form_request(
            opener,
            "POST",
            f"{base_url}/user/register_user",
            {
                "username": str(account["username"]),
                "email": str(account.get("email", "")),
                "password": str(account["password"]),
                "captcha_key": "",
                "captcha_value": "",
            },
        )
        if data.get("success"):
            created_count += 1
        else:
            message = str(data.get("message", ""))
            if "用户名已存在" in message or "??????" in message:
                existing_count += 1
            else:
                progress.close()
                raise RuntimeError(f"register user failed: {account['username']} {data}")

        progress.set_postfix_str(f"用户 {account['username']}")
        progress.update(1)
        _login(base_url, opener, account)
        deleted_book_count += _delete_existing_benchmark_books(base_url, opener)

        books = account.get("books", [])
        if not isinstance(books, list):
            progress.close()
            raise RuntimeError(f"books config is invalid for user {account['username']}")

        for book in books:
            if not isinstance(book, dict):
                progress.close()
                raise RuntimeError(f"book config is invalid for user {account['username']}")
            book_file_payload = book.get("book_file")
            if not isinstance(book_file_payload, dict):
                progress.close()
                raise RuntimeError(f"book_file config is invalid for user {account['username']}")

            book_file_id = _create_mock_file(base_url, opener, book_file_payload)
            cover_file_payload = book.get("cover_file")
            cover_file_id = None
            if isinstance(cover_file_payload, dict):
                cover_file_id = _create_mock_file(base_url, opener, cover_file_payload)

            _create_book(base_url, opener, book, book_file_id, cover_file_id)
            created_book_count += 1
            progress.set_postfix_str(f"书籍 {book.get('title', '')}")
            progress.update(1)

    progress.close()
    return created_count, existing_count, created_book_count, deleted_book_count


def main() -> None:
    created_count, existing_count, created_book_count, deleted_book_count = sync_users()
    print(
        "Benchmark data synced. "
        f"created={created_count}, existing={existing_count}, "
        f"books_created={created_book_count}, books_deleted={deleted_book_count}"
    )


if __name__ == "__main__":
    main()
