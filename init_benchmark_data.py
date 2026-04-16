from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import io
import json
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from tqdm import tqdm

from config_loader import get_all_accounts, load_benchmark_config


BOOK_TITLE_PREFIX = "压测书籍"
PARSE_TIMEOUT_SECONDS = 60
PARSE_INTERVAL_SECONDS = 1
REQUEST_TIMEOUT_SECONDS = 30
RETRYABLE_HTTP_CODES = {429, 502, 503, 504}
REQUEST_MAX_RETRIES = 3
REQUEST_BACKOFF_SECONDS = 0.5


def _should_retry_http(exc: urllib.error.HTTPError) -> bool:
    return int(exc.code) in RETRYABLE_HTTP_CODES


def _retry_delay(attempt: int) -> float:
    return REQUEST_BACKOFF_SECONDS * (2 ** attempt)


def _json_request(method: str, url: str, payload: dict | None = None, *, token: str | None = None) -> dict:
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    for attempt in range(REQUEST_MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            if attempt < REQUEST_MAX_RETRIES and _should_retry_http(exc):
                time.sleep(_retry_delay(attempt))
                continue
            raise RuntimeError(f"{method} {url} failed: {exc.code} {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt < REQUEST_MAX_RETRIES:
                time.sleep(_retry_delay(attempt))
                continue
            raise RuntimeError(f"{method} {url} failed: {exc}") from exc


def _form_request(method: str, url: str, payload: dict[str, str], *, token: str | None = None) -> dict:
    data = urllib.parse.urlencode(payload).encode("utf-8")
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    for attempt in range(REQUEST_MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            if attempt < REQUEST_MAX_RETRIES and _should_retry_http(exc):
                time.sleep(_retry_delay(attempt))
                continue
            raise RuntimeError(f"{method} {url} failed: {exc.code} {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt < REQUEST_MAX_RETRIES:
                time.sleep(_retry_delay(attempt))
                continue
            raise RuntimeError(f"{method} {url} failed: {exc}") from exc


def _put_bytes(url: str, data: bytes, headers: dict[str, str] | None = None) -> str:
    request = urllib.request.Request(url, data=data, method="PUT", headers=headers or {})
    for attempt in range(REQUEST_MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                return str(response.headers.get("etag", ""))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            if attempt < REQUEST_MAX_RETRIES and _should_retry_http(exc):
                time.sleep(_retry_delay(attempt))
                continue
            raise RuntimeError(f"PUT {url} failed: {exc.code} {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt < REQUEST_MAX_RETRIES:
                time.sleep(_retry_delay(attempt))
                continue
            raise RuntimeError(f"PUT {url} failed: {exc}") from exc


def _build_minimal_epub_bytes(title: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr(
            "META-INF/container.xml",
            """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>""",
        )
        zf.writestr(
            "OEBPS/content.opf",
            f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="BookId">benchmark-{title}</dc:identifier>
    <dc:title>{title}</dc:title>
    <dc:language>zh-CN</dc:language>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="chapter1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="chapter1"/>
  </spine>
</package>""",
        )
        zf.writestr(
            "OEBPS/nav.xhtml",
            """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>nav</title></head>
  <body><nav epub:type="toc" xmlns:epub="http://www.idpf.org/2007/ops"><ol><li><a href="chapter1.xhtml">Chapter 1</a></li></ol></nav></body>
</html>""",
        )
        zf.writestr(
            "OEBPS/chapter1.xhtml",
            f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>{title}</title></head>
  <body><p>Benchmark sample content.</p></body>
</html>""",
        )
    return buffer.getvalue()


def _build_upload_bytes(file_payload: dict[str, object], upload_mode: str) -> bytes:
    if upload_mode == "empty_file":
        return b""

    filename = str(file_payload.get("original_filename", "sample.bin"))
    kind = str(file_payload.get("kind", "book"))
    if upload_mode == "small_sample":
        if kind == "book" and filename.lower().endswith(".epub"):
            return _build_minimal_epub_bytes(filename.rsplit(".", 1)[0])
        return f"benchmark-{kind}-{filename}".encode("utf-8")

    raise RuntimeError(f"Unsupported upload_mode: {upload_mode}")


def _login(base_url: str, account: dict[str, object]) -> str:
    payload = {
        "username": str(account["username"]),
        "password": str(account["password"]),
        "captcha_key": "",
        "captcha_value": "",
    }
    data = _form_request("POST", f"{base_url}/api/auth/login", payload)
    if not data.get("success"):
        raise RuntimeError(f"login failed for {account['username']}: {data}")
    access_token = data.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise RuntimeError(f"login did not return access_token for {account['username']}: {data}")
    return access_token


def _list_uploaded_books(base_url: str, token: str) -> list[dict]:
    data = _json_request("GET", f"{base_url}/api/users/me/uploads", token=token)
    books = data.get("uploadedBooks", [])
    if not isinstance(books, list):
        raise RuntimeError("uploadedBooks response is invalid")
    return books


def _delete_existing_benchmark_books(base_url: str, token: str) -> int:
    deleted_count = 0
    for book in _list_uploaded_books(base_url, token):
        title = str(book.get("title", ""))
        if not title.startswith(BOOK_TITLE_PREFIX):
            continue
        _json_request("DELETE", f"{base_url}/api/users/me/uploads/{book['id']}", token=token)
        deleted_count += 1
    return deleted_count


def _create_file_record(base_url: str, token: str, file_payload: dict[str, object]) -> dict:
    data = _json_request(
        "POST",
        f"{base_url}/api/files/draft",
        {
            "filename": str(file_payload["original_filename"]),
            "contentType": str(file_payload["content_type"]),
            "size": int(file_payload["size"]),
            "kind": str(file_payload["kind"]),
        },
        token=token,
    )
    file_id = data.get("fileId")
    if not isinstance(file_id, int):
        raise RuntimeError(f"create file did not return a valid fileId: {data}")
    return data


def _request_upload_url(base_url: str, token: str, file_id: int) -> dict:
    data = _json_request(
        "POST",
        f"{base_url}/api/files/{file_id}/upload-session",
        token=token,
    )
    object_key = data.get("objectKey")
    if not isinstance(object_key, str) or not object_key:
        raise RuntimeError(f"upload-session did not return a valid objectKey: {data}")
    return data


def _complete_upload(base_url: str, token: str, file_id: int, *, etag: str = "") -> dict:
    data = _json_request(
        "POST",
        f"{base_url}/api/files/{file_id}/complete",
        {"etag": etag},
        token=token,
    )
    completed_file_id = data.get("fileId")
    if not isinstance(completed_file_id, int):
        raise RuntimeError(f"complete did not return a valid fileId: {data}")
    return data


def _wait_for_parse_done(base_url: str, token: str, file_id: int) -> dict:
    deadline = time.time() + PARSE_TIMEOUT_SECONDS
    while time.time() < deadline:
        data = _json_request(
            "GET",
            f"{base_url}/api/files/{file_id}/parse",
            token=token,
        )
        if data.get("parseStatus") == "done":
            return data
        time.sleep(PARSE_INTERVAL_SECONDS)
    raise RuntimeError(f"parse timeout for file {file_id}")


def _create_uploaded_file(base_url: str, token: str, file_payload: dict[str, object], *, upload_mode: str) -> tuple[int, dict]:
    file_record = _create_file_record(base_url, token, file_payload)
    file_id = int(file_record["fileId"])
    upload_status = str(file_record.get("uploadStatus", ""))
    parse_status = str(file_record.get("parseStatus", ""))
    if upload_status == "uploaded" or parse_status in {"pending", "processing", "done"}:
        parse_result = {}
        if str(file_payload["kind"]) == "book":
            parse_result = _wait_for_parse_done(base_url, token, file_id)
        return file_id, parse_result

    try:
        upload_session = _request_upload_url(base_url, token, file_id)
    except RuntimeError as exc:
        if "409" in str(exc) and "File upload has already finished" in str(exc):
            parse_result = {}
            if str(file_payload["kind"]) == "book":
                parse_result = _wait_for_parse_done(base_url, token, file_id)
            return file_id, parse_result
        raise
    etag = str(file_payload.get("etag", ""))
    if not bool(upload_session.get("mockUpload")):
        if upload_mode == "skip_upload":
            raise RuntimeError("upload_mode=skip_upload 需要后端开启 server-mock，否则 complete 会因为对象不存在而失败")
        upload_url = str(upload_session.get("uploadUrl", ""))
        if not upload_url:
            raise RuntimeError(f"upload-session did not return a valid uploadUrl: {upload_session}")
        headers = upload_session.get("headers") or {}
        payload_bytes = _build_upload_bytes(file_payload, upload_mode)
        request_headers = {str(key): str(value) for key, value in headers.items()}
        request_headers.setdefault("Content-Type", str(file_payload.get("content_type", "application/octet-stream")))
        etag = _put_bytes(upload_url, payload_bytes, headers=request_headers)

    completion = _complete_upload(base_url, token, file_id, etag=etag)
    parse_result = {}
    if str(file_payload["kind"]) == "book":
        parse_result = _wait_for_parse_done(base_url, token, file_id)
    return int(completion["fileId"]), parse_result


def _create_book(base_url: str, token: str, book_payload: dict[str, object], stored_file_id: int, cover_file_id: int | None) -> None:
    data = _json_request(
        "POST",
        f"{base_url}/api/books",
        {
            "title": str(book_payload["title"]),
            "author": str(book_payload.get("author", "")),
            "isbn": str(book_payload.get("isbn", "")),
            "category": str(book_payload.get("category", "")),
            "year": int(book_payload.get("year", 2024)),
            "language": str(book_payload.get("language", "")),
            "storedFileId": stored_file_id,
            "coverFileId": cover_file_id,
        },
        token=token,
    )
    if not data.get("success"):
        raise RuntimeError(f"create book failed: {data}")


def _sync_single_user(
    account: dict[str, object],
    *,
    base_url: str,
    upload_mode: str,
    progress: tqdm,
    progress_lock: threading.Lock,
) -> tuple[int, int, int, int]:
    created_count = 0
    existing_count = 0
    created_book_count = 0
    deleted_book_count = 0

    data = _form_request(
        "POST",
        f"{base_url}/api/auth/register",
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
            raise RuntimeError(f"register user failed: {account['username']} {data}")

    with progress_lock:
        progress.set_postfix_str(f"用户 {account['username']}")
        progress.update(1)

    token = _login(base_url, account)
    deleted_book_count += _delete_existing_benchmark_books(base_url, token)

    books = account.get("books", [])
    if not isinstance(books, list):
        raise RuntimeError(f"books config is invalid for user {account['username']}")

    for book in books:
        if not isinstance(book, dict):
            raise RuntimeError(f"book config is invalid for user {account['username']}")
        book_file_payload = book.get("book_file")
        if not isinstance(book_file_payload, dict):
            raise RuntimeError(f"book_file config is invalid for user {account['username']}")

        book_file_id, _parse_result = _create_uploaded_file(base_url, token, book_file_payload, upload_mode=upload_mode)
        cover_file_payload = book.get("cover_file")
        cover_file_id = None
        if isinstance(cover_file_payload, dict):
            cover_file_id, _ = _create_uploaded_file(base_url, token, cover_file_payload, upload_mode=upload_mode)

        _create_book(base_url, token, book, book_file_id, cover_file_id)
        created_book_count += 1
        with progress_lock:
            progress.set_postfix_str(f"书籍 {book.get('title', '')}")
            progress.update(1)

    return created_count, existing_count, created_book_count, deleted_book_count


def sync_users() -> tuple[int, int, int, int]:
    accounts = get_all_accounts()
    config = load_benchmark_config()
    base_url = str(config.get("base_url", "http://127.0.0.1:8000")).rstrip("/")
    mock_config = config.get("mock") or {}
    upload_mode = str(mock_config.get("upload_mode", "skip_upload")).strip().lower() or "skip_upload"
    init_config = config.get("init_data") or {}
    worker_count = max(1, int(init_config.get("workers", 1)))

    created_count = 0
    existing_count = 0
    created_book_count = 0
    deleted_book_count = 0

    total_books = sum(
        len(account.get("books", []))
        for account in accounts
        if isinstance(account, dict) and isinstance(account.get("books", []), list)
    )
    progress = tqdm(total=len(accounts) + total_books, desc="初始化压测数据", unit="项", file=sys.stdout)
    progress_lock = threading.Lock()
    failures: list[str] = []

    try:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_map = {
                executor.submit(
                    _sync_single_user,
                    account,
                    base_url=base_url,
                    upload_mode=upload_mode,
                    progress=progress,
                    progress_lock=progress_lock,
                ): str(account.get("username", "<unknown>"))
                for account in accounts
            }
            for future in as_completed(future_map):
                username = future_map[future]
                try:
                    c1, c2, c3, c4 = future.result()
                    created_count += c1
                    existing_count += c2
                    created_book_count += c3
                    deleted_book_count += c4
                except Exception as exc:
                    failures.append(f"{username}: {exc}")
    finally:
        progress.close()

    if failures:
        message = "\n".join(failures[:10])
        if len(failures) > 10:
            message += f"\n... 其余 {len(failures) - 10} 个失败未展开"
        raise RuntimeError(f"初始化失败用户数={len(failures)}\n{message}")

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
