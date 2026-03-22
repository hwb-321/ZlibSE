from __future__ import annotations

import itertools
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from locust import HttpUser, between, events, task

from benchmark.config_loader import get_all_accounts, load_benchmark_config


BENCHMARK_DIR = Path(__file__).resolve().parent
LOGS_DIR = BENCHMARK_DIR / "logs"
_config = load_benchmark_config()
_accounts = get_all_accounts()
_account_cycle = itertools.cycle(_accounts)
_account_lock = threading.Lock()
_book_ids: list[int] = []
_book_ids_lock = threading.Lock()
_report_lock = threading.Lock()
_written_report_paths: set[str] = set()
_current_environment = None


def _get_config_section(name: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
    value = _config.get(name, default or {})
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a YAML object")
    return value


def _next_account() -> dict[str, Any]:
    with _account_lock:
        return dict(next(_account_cycle))


def _remember_book_ids(ids: list[int]) -> None:
    if not ids:
        return
    with _book_ids_lock:
        known = set(_book_ids)
        for book_id in ids:
            if book_id not in known:
                _book_ids.append(book_id)
                known.add(book_id)


def _pick_book_id() -> int | None:
    with _book_ids_lock:
        if not _book_ids:
            return None
        return _book_ids[0]


@events.init_command_line_parser.add_listener
def _(parser):
    scenarios = _get_config_section("scenarios")
    parser.set_defaults(
        host=str(_config.get("base_url", "http://127.0.0.1:8000")),
        users=int(scenarios.get("vus", 1)),
        spawn_rate=float(scenarios.get("spawn_rate", 1)),
        run_time=str(scenarios.get("duration", "30s")),
    )


@events.init.add_listener
def _(environment, **_kwargs):
    global _current_environment
    thresholds = _get_config_section("thresholds")
    max_error_rate = float(thresholds.get("max_error_rate", 0.01))
    p95_ms = int(thresholds.get("p95_ms", 300))
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    _current_environment = environment
    environment._benchmark_report_path = LOGS_DIR / f"压测结果_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    environment._benchmark_max_error_rate = max_error_rate
    environment._benchmark_p95_ms = p95_ms

    environment.parsed_options.stop_timeout = 5


@events.test_stop.add_listener
def _on_test_stop(environment, **_kwargs):
    _write_chinese_report(environment)


@events.quitting.add_listener
def _on_quitting(**_kwargs):
    environment = _current_environment
    if environment is None:
        return
    _finalize_run(
        environment,
        max_error_rate=float(getattr(environment, "_benchmark_max_error_rate", 0.01)),
        p95_ms=int(getattr(environment, "_benchmark_p95_ms", 300)),
    )


def _finalize_run(environment, *, max_error_rate: float, p95_ms: int) -> None:
    stats = environment.stats.total
    total_requests = max(stats.num_requests, 1)
    error_rate = stats.num_failures / total_requests
    p95_value = stats.get_response_time_percentile(0.95) or 0

    _write_chinese_report(environment)

    if error_rate > max_error_rate or p95_value > p95_ms:
        environment.process_exit_code = 1
    else:
        environment.process_exit_code = 0


def _write_chinese_report(environment) -> None:
    report_path = getattr(
        environment,
        "_benchmark_report_path",
        LOGS_DIR / f"压测结果_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
    )
    total = environment.stats.total
    lines = [
        "# 压测结果",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 总请求数：{total.num_requests}",
        f"- 总失败数：{total.num_failures}",
        f"- 总体 QPS：{total.total_rps:.2f}",
        f"- 平均响应时间：{total.avg_response_time:.2f} ms",
        f"- P95 响应时间：{(total.get_response_time_percentile(0.95) or 0):.2f} ms",
        "",
        "## 各接口统计",
        "",
        "| 接口 | 请求数 | 失败数 | QPS | 平均耗时(ms) | P95(ms) |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]

    entries = sorted(
        environment.stats.entries.items(),
        key=lambda item: (item[0][1], item[0][0]),
    )
    for (name, _method), entry in entries:
        lines.append(
            f"| {name} | {entry.num_requests} | {entry.num_failures} | {entry.total_rps:.2f} | "
            f"{entry.avg_response_time:.2f} | {(entry.get_response_time_percentile(0.95) or 0):.2f} |"
        )

    with _report_lock:
        report_key = str(report_path)
        if report_key in _written_report_paths:
            return
        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        _written_report_paths.add(report_key)


class ZlibSEUser(HttpUser):
    account: dict[str, Any]
    abstract = False

    scenarios = _get_config_section("scenarios")
    books_config = _get_config_section("books")
    wait_time = between(
        float(scenarios.get("wait_time_min_ms", 500)) / 1000.0,
        float(scenarios.get("wait_time_max_ms", 1500)) / 1000.0,
    )

    def on_start(self) -> None:
        self.account = _next_account()
        self._login()

    def _login(self) -> None:
        payload = {
            "username": self.account["username"],
            "password": self.account["password"],
            "captcha_key": "",
            "captcha_value": "",
        }
        with self.client.post("/user/login_user", data=payload, name="POST /user/login_user", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"login failed: http {response.status_code}")
                return

            data = response.json()
            if not data.get("success"):
                response.failure(f"login failed: {data}")

    @task(4)
    def list_books(self) -> None:
        page = int(self.books_config.get("page", 1))
        page_size = int(self.books_config.get("page_size", 10))
        with self.client.get(
            "/book/list",
            params={"page": page, "pageSize": page_size},
            name="GET /book/list",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"list_books failed: http {response.status_code}")
                return

            data = response.json()
            books = data.get("books", [])
            if not isinstance(books, list):
                response.failure("list_books returned invalid books payload")
                return

            ids = [book["id"] for book in books if isinstance(book, dict) and "id" in book]
            _remember_book_ids(ids)

    @task(3)
    def search_books(self) -> None:
        query = str(self.books_config.get("search_query", "python"))
        with self.client.get(
            "/book/search",
            params={"query": query},
            name="GET /book/search",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"search_books failed: http {response.status_code}")
                return

            data = response.json()
            books = data.get("books", [])
            if not isinstance(books, list):
                response.failure("search_books returned invalid books payload")
                return

            ids = [book["id"] for book in books if isinstance(book, dict) and "id" in book]
            _remember_book_ids(ids)

    @task(2)
    def get_book_detail(self) -> None:
        book_id = _pick_book_id()
        if book_id is None:
            self.list_books()
            return

        with self.client.get(
            f"/book/get_descriptions/{book_id}",
            name="GET /book/get_descriptions/:id",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"get_book_detail failed: http {response.status_code}")

    @task(1)
    def toggle_favorite(self) -> None:
        book_id = _pick_book_id()
        if book_id is None:
            self.list_books()
            return

        with self.client.post(
            f"/user/add_to_favorites/{book_id}",
            name="POST /user/add_to_favorites/:id",
            catch_response=True,
        ) as add_response:
            if add_response.status_code >= 400:
                add_response.failure(f"add_to_favorites failed: http {add_response.status_code}")

        with self.client.post(
            f"/user/remove_from_favorites/{book_id}",
            name="POST /user/remove_from_favorites/:id",
            catch_response=True,
        ) as remove_response:
            if remove_response.status_code >= 400:
                remove_response.failure(f"remove_from_favorites failed: http {remove_response.status_code}")

    @task(1)
    def get_download_url(self) -> None:
        book_id = _pick_book_id()
        if book_id is None:
            self.list_books()
            return

        with self.client.get(
            f"/book/get_descriptions/{book_id}",
            name="GET /book/get_descriptions/:id (download setup)",
            catch_response=True,
        ) as detail_response:
            if detail_response.status_code != 200:
                detail_response.failure(f"detail before download failed: http {detail_response.status_code}")
                return

            book = detail_response.json()
            file_id = book.get("book_file_id")
            if not file_id:
                detail_response.failure("book detail does not include book_file_id")
                return

        with self.client.get(
            f"/api/files/{file_id}/download-url",
            name="GET /api/files/:id/download-url",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"download_url failed: http {response.status_code}")
