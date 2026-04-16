from __future__ import annotations

import itertools
import math
import random
import string
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from gevent import sleep
from locust import HttpUser, between, events, task
from locust.util.timespan import parse_timespan

from config_loader import get_all_accounts, load_benchmark_config, load_runtime_state


ROOT_DIR = Path(__file__).resolve().parent
LOGS_DIR = ROOT_DIR / "logs"
_config = load_benchmark_config()
_accounts = get_all_accounts()
_account_cycle = itertools.cycle(_accounts)
_account_lock = threading.Lock()
_book_ids: list[int] = []
_book_ids_lock = threading.Lock()
_direct_download_file_ids: list[int] = []
_direct_download_file_ids_lock = threading.Lock()
_hot_download_file_id: int | None = None
_hot_download_file_lock = threading.Lock()
_direct_download_stats_lock = threading.Lock()
_direct_download_total_requests = 0
_direct_download_seen_ids: set[int] = set()
_bandwidth_stats_lock = threading.Lock()
_bandwidth_totals = {
    "request_app_bytes": 0,
    "response_app_bytes": 0,
    "request_wire_bytes": 0,
    "response_wire_bytes": 0,
}
_bandwidth_by_name: dict[str, dict[str, int]] = {}
_report_lock = threading.Lock()
_written_report_paths: set[str] = set()
_current_environment = None
_runtime_state = load_runtime_state()
_DEFAULT_SERIAL_FLOW = [
    "ping",
    "auth_login",
    "auth_me",
    "books_count",
    "list_books",
    "search_books",
    "book_detail",
    "favorite_status",
    "favorite_toggle",
    "favorites_list",
    "uploads_list",
    "download_url",
    "download_url_hot",
    "download_url_direct",
]
_serial_phase_lock = threading.Lock()
_serial_phase_index = 0
_serial_phase_generation = 0
_serial_phase_completed_users: set[str] = set()


def _reset_serial_phase_state() -> None:
    global _serial_phase_index, _serial_phase_generation
    with _serial_phase_lock:
        _serial_phase_index = 0
        _serial_phase_generation = 0
        _serial_phase_completed_users.clear()


def _reset_download_stats() -> None:
    global _direct_download_total_requests
    with _direct_download_stats_lock:
        _direct_download_total_requests = 0
        _direct_download_seen_ids.clear()


def _reset_bandwidth_stats() -> None:
    with _bandwidth_stats_lock:
        for key in _bandwidth_totals:
            _bandwidth_totals[key] = 0
        _bandwidth_by_name.clear()


def _record_direct_download_file_id(file_id: int) -> None:
    global _direct_download_total_requests
    with _direct_download_stats_lock:
        _direct_download_total_requests += 1
        _direct_download_seen_ids.add(int(file_id))


def _get_direct_download_stats() -> dict[str, int]:
    with _direct_download_stats_lock:
        distinct = len(_direct_download_seen_ids)
        total = _direct_download_total_requests
        return {
            "total_requests": total,
            "distinct_file_ids": distinct,
            "repeated_requests": max(0, total - distinct),
        }


def _header_bytes(headers: Any) -> int:
    total = 0
    if not headers:
        return total
    if hasattr(headers, "items"):
        items = headers.items()
    else:
        items = headers
    for key, value in items:
        total += len(str(key).encode("utf-8")) + 2 + len(str(value).encode("utf-8")) + 2
    return total


def _body_length(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bytes):
        return len(value)
    if isinstance(value, str):
        return len(value.encode("utf-8"))
    return len(str(value).encode("utf-8"))


def _segment_count(app_bytes: int) -> int:
    if app_bytes <= 0:
        return 1
    return max(1, math.ceil(app_bytes / 1460))


def _estimate_wire_bytes(request_app_bytes: int, response_app_bytes: int) -> tuple[int, int]:
    request_segments = _segment_count(request_app_bytes)
    response_segments = _segment_count(response_app_bytes)
    tcp_ip_header_bytes = 40
    request_wire_bytes = request_app_bytes + request_segments * tcp_ip_header_bytes + response_segments * tcp_ip_header_bytes
    response_wire_bytes = response_app_bytes + response_segments * tcp_ip_header_bytes + request_segments * tcp_ip_header_bytes
    return request_wire_bytes, response_wire_bytes


def _record_bandwidth_sample(name: str, request_app_bytes: int, response_app_bytes: int) -> None:
    request_wire_bytes, response_wire_bytes = _estimate_wire_bytes(request_app_bytes, response_app_bytes)
    with _bandwidth_stats_lock:
        _bandwidth_totals["request_app_bytes"] += request_app_bytes
        _bandwidth_totals["response_app_bytes"] += response_app_bytes
        _bandwidth_totals["request_wire_bytes"] += request_wire_bytes
        _bandwidth_totals["response_wire_bytes"] += response_wire_bytes
        per_name = _bandwidth_by_name.setdefault(
            name,
            {
                "request_count": 0,
                "request_app_bytes": 0,
                "response_app_bytes": 0,
                "request_wire_bytes": 0,
                "response_wire_bytes": 0,
            },
        )
        per_name["request_count"] += 1
        per_name["request_app_bytes"] += request_app_bytes
        per_name["response_app_bytes"] += response_app_bytes
        per_name["request_wire_bytes"] += request_wire_bytes
        per_name["response_wire_bytes"] += response_wire_bytes


def _extract_request_app_bytes(request_type: str, url: str | None, response: Any) -> int:
    request_line = f"{str(request_type).upper()} "
    if url:
        request_line += url
    request_line += " HTTP/1.1\r\n"
    request_obj = getattr(response, "request", None) if response is not None else None
    headers = getattr(request_obj, "headers", {}) if request_obj is not None else {}
    body = getattr(request_obj, "body", None) if request_obj is not None else None
    if body is None and request_obj is not None:
        body = getattr(request_obj, "data", None)
    return len(request_line.encode("utf-8")) + _header_bytes(headers) + 2 + _body_length(body)


def _extract_response_app_bytes(response_length: int | None, response: Any) -> int:
    status_code = getattr(response, "status_code", 0) if response is not None else 0
    reason = getattr(response, "reason", "") if response is not None else ""
    status_line = f"HTTP/1.1 {status_code} {reason}\r\n"
    headers = getattr(response, "headers", {}) if response is not None else {}
    body_bytes = max(0, int(response_length or 0))
    return len(status_line.encode("utf-8")) + _header_bytes(headers) + 2 + body_bytes


def _get_bandwidth_stats() -> dict[str, Any]:
    with _bandwidth_stats_lock:
        totals = dict(_bandwidth_totals)
        by_name = {name: dict(values) for name, values in _bandwidth_by_name.items()}
    return {"totals": totals, "by_name": by_name}


def _get_serial_phase_state() -> tuple[str, int]:
    with _serial_phase_lock:
        return _DEFAULT_SERIAL_FLOW[_serial_phase_index], _serial_phase_generation


def _advance_serial_phase() -> None:
    global _serial_phase_index, _serial_phase_generation
    _serial_phase_index = (_serial_phase_index + 1) % len(_DEFAULT_SERIAL_FLOW)
    _serial_phase_generation += 1
    _serial_phase_completed_users.clear()


def _skip_disabled_serial_phases(enabled_tests: dict[str, bool]) -> None:
    global _serial_phase_index, _serial_phase_generation
    with _serial_phase_lock:
        checked = 0
        while checked < len(_DEFAULT_SERIAL_FLOW):
            phase_name = _DEFAULT_SERIAL_FLOW[_serial_phase_index]
            if enabled_tests.get(phase_name, False):
                break
            _advance_serial_phase()
            checked += 1


def _mark_serial_phase_completed(user_key: str, *, participant_count: int) -> None:
    global _serial_phase_index, _serial_phase_generation
    with _serial_phase_lock:
        _serial_phase_completed_users.add(user_key)
        if participant_count > 0 and len(_serial_phase_completed_users) >= participant_count:
            _advance_serial_phase()


def _get_config_section(name: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
    value = _config.get(name, default or {})
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a YAML object")
    return value


def _expected_total_books() -> int:
    accounts_cfg = _get_config_section("accounts")
    books_cfg = _get_config_section("books")
    return max(0, int(accounts_cfg.get("user_count", 0))) * max(0, int(books_cfg.get("books_per_user", 0)))


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
        return random.choice(_book_ids)


def _load_runtime_ids() -> None:
    book_ids = _runtime_state.get("book_ids") or []
    if isinstance(book_ids, list):
        _remember_book_ids([int(item) for item in book_ids if isinstance(item, int) or str(item).isdigit()])

    direct_ids = _runtime_state.get("direct_download_file_ids") or []
    if isinstance(direct_ids, list):
        with _direct_download_file_ids_lock:
            _direct_download_file_ids.clear()
            _direct_download_file_ids.extend(
                [int(item) for item in direct_ids if isinstance(item, int) or str(item).isdigit()]
            )

    hot_id = _runtime_state.get("hot_download_file_id")
    if isinstance(hot_id, int) or (isinstance(hot_id, str) and hot_id.isdigit()):
        global _hot_download_file_id
        _hot_download_file_id = int(hot_id)

    token_map = _runtime_state.get("access_tokens") or {}
    if isinstance(token_map, dict):
        for account in _accounts:
            username = str(account.get("username", ""))
            token = token_map.get(username)
            if isinstance(token, str) and token:
                account["access_token"] = token
            else:
                account.pop("access_token", None)


def _get_enabled_tests() -> dict[str, bool]:
    default = {
        "ping": False,
        "auth_login": False,
        "auth_me": False,
        "books_count": False,
        "list_books": True,
        "search_books": True,
        "book_detail": True,
        "favorite_status": False,
        "favorite_toggle": False,
        "favorites_list": False,
        "uploads_list": False,
        "download_url": True,
        "download_url_hot": False,
        "download_url_direct": False,
    }
    tests = _get_config_section("enabled_tests", default)
    return {
        key: bool(tests.get(key, default_value))
        for key, default_value in default.items()
    }


@events.init_command_line_parser.add_listener
def _(parser):
    scenarios = _get_config_section("scenarios")
    default_users = int(scenarios.get("vus", 1))
    default_spawn_rate = float(scenarios.get("spawn_rate", 1))
    default_run_time = str(scenarios.get("duration", "30s"))
    default_host = str(_config.get("base_url", "http://127.0.0.1:8000"))
    parser.set_defaults(
        host=default_host,
        users=default_users,
        num_users=default_users,
        spawn_rate=default_spawn_rate,
        run_time=default_run_time,
    )


@events.init.add_listener
def _(environment, **_kwargs):
    global _current_environment
    thresholds = _get_config_section("thresholds")
    max_error_rate = float(thresholds.get("max_error_rate", 0.01))
    p95_ms = int(thresholds.get("p95_ms", 300))
    p99_ms = int(thresholds.get("p99_ms", 500))
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    _current_environment = environment
    _load_runtime_ids()
    environment._benchmark_report_path = LOGS_DIR / f"压测结果_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    environment._benchmark_max_error_rate = max_error_rate
    environment._benchmark_p95_ms = p95_ms
    environment._benchmark_p99_ms = p99_ms
    _reset_serial_phase_state()
    _reset_download_stats()
    _reset_bandwidth_stats()
    _skip_disabled_serial_phases(_get_enabled_tests())

    scenarios = _get_config_section("scenarios")
    parsed_options = environment.parsed_options
    configured_users = int(scenarios.get("vus", 1))
    configured_spawn_rate = float(scenarios.get("spawn_rate", 1))
    configured_run_time = parse_timespan(str(scenarios.get("duration", "30s")))
    configured_host = str(_config.get("base_url", "http://127.0.0.1:8000"))

    if getattr(parsed_options, "users", None) in (None, 1):
        parsed_options.users = configured_users
    if getattr(parsed_options, "num_users", None) in (None, 1):
        parsed_options.num_users = configured_users
    if getattr(parsed_options, "spawn_rate", None) in (None, 1):
        parsed_options.spawn_rate = configured_spawn_rate
    if not getattr(parsed_options, "run_time", None) or getattr(parsed_options, "run_time", None) == 20:
        parsed_options.run_time = configured_run_time
    if not getattr(parsed_options, "host", None):
        parsed_options.host = configured_host

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
        p99_ms=int(getattr(environment, "_benchmark_p99_ms", 500)),
    )


def _finalize_run(environment, *, max_error_rate: float, p95_ms: int, p99_ms: int) -> None:
    stats = environment.stats.total
    total_requests = max(stats.num_requests, 1)
    error_rate = stats.num_failures / total_requests
    p95_value = stats.get_response_time_percentile(0.95) or 0
    p99_value = stats.get_response_time_percentile(0.99) or 0

    _write_chinese_report(environment)

    if error_rate > max_error_rate or p95_value > p95_ms or p99_value > p99_ms:
        environment.process_exit_code = 1
    else:
        environment.process_exit_code = 0


@events.request.add_listener
def _record_request_bandwidth(
    request_type,
    name,
    response_time,
    response_length,
    response=None,
    context=None,
    exception=None,
    start_time=None,
    url=None,
    **_kwargs,
):
    if exception is not None:
        return
    request_app_bytes = _extract_request_app_bytes(request_type, url, response)
    response_app_bytes = _extract_response_app_bytes(response_length, response)
    _record_bandwidth_sample(str(name), request_app_bytes, response_app_bytes)


def _write_chinese_report(environment) -> None:
    report_path = getattr(
        environment,
        "_benchmark_report_path",
        LOGS_DIR / f"压测结果_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
    )
    total = environment.stats.total
    scenarios = _get_config_section("scenarios")
    execution = _get_config_section("execution")
    mock = _get_config_section("mock")
    accounts = _get_config_section("accounts")
    books = _get_config_section("books")
    enabled_tests = _get_enabled_tests()
    enabled_test_names = [name for name, enabled in enabled_tests.items() if enabled]
    configured_duration_seconds = max(1.0, float(parse_timespan(str(scenarios.get("duration", "30s")))))
    total_duration_qps = float(total.num_requests) / configured_duration_seconds
    bandwidth_stats = _get_bandwidth_stats()
    total_request_wire_bytes = bandwidth_stats["totals"]["request_wire_bytes"]
    total_response_wire_bytes = bandwidth_stats["totals"]["response_wire_bytes"]
    total_wire_bytes = total_request_wire_bytes + total_response_wire_bytes
    request_wire_mbps = (total_request_wire_bytes * 8) / configured_duration_seconds / 1_000_000
    response_wire_mbps = (total_response_wire_bytes * 8) / configured_duration_seconds / 1_000_000
    total_wire_mbps = (total_wire_bytes * 8) / configured_duration_seconds / 1_000_000
    lines = [
        "# 压测结果",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 后端地址：{_config.get('base_url', 'http://127.0.0.1:8000')}",
        f"- 执行模式：{execution.get('mode', 'parallel')}",
        f"- benchmark 串行编排：{bool(execution.get('orchestrated_serial', False))}",
        f"- 当前串行编排接口：{execution.get('orchestrated_test_name', '') or '无'}",
        f"- 串行模式语义：同一阶段所有用户先并发完成，待该阶段全部用户结束后再进入下一阶段" if str(execution.get('mode', 'parallel')).lower() == "serial" else "- 串行模式语义：未启用",
        f"- 串行默认顺序：{', '.join(_DEFAULT_SERIAL_FLOW)}" if str(execution.get('mode', 'parallel')).lower() == "serial" else "- 串行默认顺序：未启用",
        f"- 并发用户数：{scenarios.get('vus', 1)}",
        f"- 压测时长：{scenarios.get('duration', '30s')}",
        f"- 启动速率：{scenarios.get('spawn_rate', 1)}",
        f"- 等待时间：{scenarios.get('wait_time_min_ms', 0)}ms ~ {scenarios.get('wait_time_max_ms', 0)}ms",
        f"- 账号数量：{accounts.get('user_count', 0)}",
        f"- 每用户书籍数：{books.get('books_per_user', 0)}",
        f"- server-mock：{mock.get('server_mock', False)}",
        f"- 脚本上传模式：{mock.get('upload_mode', 'skip_upload')}",
        f"- 启用接口：{', '.join(enabled_test_names) if enabled_test_names else '无'}",
        f"- 总请求数：{total.num_requests}",
        f"- 总失败数：{total.num_failures}",
        f"- Locust QPS：{total.total_rps:.2f}",
        f"- Locust RPS：{total.total_rps:.2f}",
        f"- Duration QPS：{total_duration_qps:.2f}",
        f"- Duration RPS：{total_duration_qps:.2f}",
        f"- 平均响应时间：{total.avg_response_time:.2f} ms",
        f"- P95 响应时间：{(total.get_response_time_percentile(0.95) or 0):.2f} ms",
        f"- P99 响应时间：{(total.get_response_time_percentile(0.99) or 0):.2f} ms",
        f"- 估算请求上行带宽（含 TCP/IP 头与 ACK）：{request_wire_mbps:.2f} Mbps",
        f"- 估算响应下行带宽（含 TCP/IP 头与 ACK）：{response_wire_mbps:.2f} Mbps",
        f"- 估算总带宽（含 TCP/IP 头与 ACK）：{total_wire_mbps:.2f} Mbps",
    ]

    if enabled_tests.get("download_url_direct", False):
        direct_stats = _get_direct_download_stats()
        lines.extend(
            [
                f"- direct 下载总请求：{direct_stats['total_requests']}",
                f"- direct 不重复 file_id 数：{direct_stats['distinct_file_ids']}",
                f"- direct 重复命中次数：{direct_stats['repeated_requests']}",
            ]
        )

    lines.extend(
        [
            "",
            "## 各接口统计",
            "",
            "| 接口 | 请求数 | 失败数 | Locust QPS | Locust RPS | Duration QPS | Duration RPS | 平均耗时(ms) | P95(ms) | P99(ms) |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )

    entries = sorted(
        environment.stats.entries.items(),
        key=lambda item: (item[0][1], item[0][0]),
    )
    for (name, _method), entry in entries:
        entry_duration_qps = float(entry.num_requests) / configured_duration_seconds
        lines.append(
            f"| {name} | {entry.num_requests} | {entry.num_failures} | {entry.total_rps:.2f} | {entry.total_rps:.2f} | "
            f"{entry_duration_qps:.2f} | {entry_duration_qps:.2f} | {entry.avg_response_time:.2f} | {(entry.get_response_time_percentile(0.95) or 0):.2f} | "
            f"{(entry.get_response_time_percentile(0.99) or 0):.2f} |"
        )

    if bandwidth_stats["by_name"]:
        lines.extend(
            [
                "",
                "## 带宽估算",
                "",
                "说明：按 HTTP 请求/响应字节数估算，并折算 TCP/IP 头与 ACK；用于压测对比，不等同于抓包精确值。",
                "",
                f"- 总请求应用层字节：{bandwidth_stats['totals']['request_app_bytes']}",
                f"- 总响应应用层字节：{bandwidth_stats['totals']['response_app_bytes']}",
                f"- 总请求线缆字节估算：{total_request_wire_bytes}",
                f"- 总响应线缆字节估算：{total_response_wire_bytes}",
                "",
                "| 接口 | 次数 | 请求应用层字节 | 响应应用层字节 | 请求线缆字节估算 | 响应线缆字节估算 | 总带宽估算(Mbps) |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for name, values in sorted(bandwidth_stats["by_name"].items(), key=lambda item: item[0]):
            per_name_total_wire_bytes = values["request_wire_bytes"] + values["response_wire_bytes"]
            per_name_wire_mbps = (per_name_total_wire_bytes * 8) / configured_duration_seconds / 1_000_000
            lines.append(
                f"| {name} | {values['request_count']} | {values['request_app_bytes']} | {values['response_app_bytes']} | "
                f"{values['request_wire_bytes']} | {values['response_wire_bytes']} | {per_name_wire_mbps:.2f} |"
            )

    with _report_lock:
        report_key = str(report_path)
        if report_key in _written_report_paths:
            return
        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        _written_report_paths.add(report_key)


class ZlibSEUser(HttpUser):
    account: dict[str, Any]
    access_token: str = ""
    abstract = False

    scenarios = _get_config_section("scenarios")
    execution_config = _get_config_section("execution")
    list_books_config = _get_config_section("list_books")
    search_books_config = _get_config_section("search_books")
    favorites_config = _get_config_section("favorites")
    uploads_config = _get_config_section("uploads")
    enabled_tests = _get_enabled_tests()
    wait_time = between(
        float(scenarios.get("wait_time_min_ms", 500)) / 1000.0,
        float(scenarios.get("wait_time_max_ms", 1500)) / 1000.0,
    )
    execution_mode = str(execution_config.get("mode", "parallel")).lower()

    def on_start(self) -> None:
        self.account = _next_account()
        self._serial_user_key = uuid4().hex
        self._last_serial_generation = -1
        preloaded_token = self.account.get("access_token")
        if isinstance(preloaded_token, str) and preloaded_token:
            self.access_token = preloaded_token
            self.client.headers.update({"Authorization": f"Bearer {self.access_token}"})
        elif self._requires_login():
            self._login()

    def _requires_login(self) -> bool:
        required = ("auth_me", "favorite_status", "favorite_toggle", "favorites_list", "uploads_list")
        return any(self.enabled_tests.get(name, False) for name in required)

    def _is_parallel(self) -> bool:
        return self.execution_mode != "serial"

    def _is_serial(self) -> bool:
        return not self._is_parallel()

    def _ensure_login(self) -> bool:
        if self.access_token:
            return True
        self._login()
        return bool(self.access_token)

    def _choose_search_query(self) -> str:
        mode = str(self.search_books_config.get("mode", "fixed")).lower()
        fixed_query = str(self.search_books_config.get("query", "python")).strip() or "python"
        if mode == "random_from_list":
            queries = self.search_books_config.get("queries", [])
            valid_queries = [str(item).strip() for item in queries if str(item).strip()]
            if valid_queries:
                return random.choice(valid_queries)
            return fixed_query
        if mode == "random_generated":
            min_length = max(1, int(self.search_books_config.get("generated_min_length", 2)))
            max_length = max(min_length, int(self.search_books_config.get("generated_max_length", 6)))
            alphabet = string.ascii_lowercase
            return "".join(random.choice(alphabet) for _ in range(random.randint(min_length, max_length)))
        return fixed_query

    def _login(self) -> None:
        payload = {
            "username": self.account["username"],
            "password": self.account["password"],
            "captcha_key": "",
            "captcha_value": "",
        }
        with self.client.post("/api/auth/login", data=payload, name="POST /api/auth/login", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"login failed: http {response.status_code}")
                return

            data = response.json()
            if not data.get("success"):
                response.failure(f"login failed: {data}")
                return

            access_token = data.get("access_token")
            if not isinstance(access_token, str) or not access_token:
                response.failure(f"login did not return access_token: {data}")
                return

            self.access_token = access_token
            self.client.headers.update({"Authorization": f"Bearer {self.access_token}"})

    def _ensure_book_id(self) -> int | None:
        book_id = _pick_book_id()
        if book_id is not None:
            return book_id
        if self.enabled_tests.get("list_books", True):
            self.list_books()
        elif self.enabled_tests.get("search_books", True):
            self.search_books()
        elif self.enabled_tests.get("download_url", False) or self.enabled_tests.get("book_detail", False):
            page = int(self.list_books_config.get("page", 1))
            page_size = int(self.list_books_config.get("page_size", 10))
            preload_name = (
                "GET /api/books (detail preload)"
                if self.enabled_tests.get("book_detail", False) and not self.enabled_tests.get("download_url", False)
                else "GET /api/books (download preload)"
            )
            with self.client.get(
                "/api/books",
                params={"page": page, "pageSize": page_size},
                name=preload_name,
                catch_response=True,
            ) as response:
                if response.status_code != 200:
                    response.failure(f"book preload failed: http {response.status_code}")
                    return None
                data = response.json()
                books = data.get("books", [])
                if not isinstance(books, list):
                    response.failure("book preload returned invalid books payload")
                    return None
                ids = [book["id"] for book in books if isinstance(book, dict) and "id" in book]
                _remember_book_ids(ids)
        return _pick_book_id()

    def _ensure_direct_download_file_id(self) -> int | None:
        with _direct_download_file_ids_lock:
            if _direct_download_file_ids:
                return random.choice(_direct_download_file_ids)

            page_size = int(self.list_books_config.get("page_size", 20))
            expected_total = _expected_total_books()
            preload_book_ids: list[int] = []
            seen_book_ids: set[int] = set()
            page = 1
            while expected_total <= 0 or len(preload_book_ids) < expected_total:
                with self.client.get(
                    "/api/books",
                    params={"page": page, "pageSize": page_size},
                    name="GET /api/books (direct download preload)",
                    catch_response=True,
                ) as list_response:
                    if list_response.status_code != 200:
                        list_response.failure(f"direct download preload failed: http {list_response.status_code}")
                        return None
                    data = list_response.json()
                    books = data.get("books", [])
                    if not isinstance(books, list):
                        list_response.failure("direct download preload returned invalid books payload")
                        return None
                    if not books:
                        break
                    page_new_ids = []
                    for book in books:
                        if not isinstance(book, dict) or "id" not in book:
                            continue
                        book_id = int(book["id"])
                        if book_id in seen_book_ids:
                            continue
                        seen_book_ids.add(book_id)
                        preload_book_ids.append(book_id)
                        page_new_ids.append(book_id)
                        if expected_total > 0 and len(preload_book_ids) >= expected_total:
                            break
                    _remember_book_ids(page_new_ids)
                    if not page_new_ids:
                        break
                page += 1

            if not preload_book_ids:
                return None

            direct_file_ids: list[int] = []
            for book_id in preload_book_ids:
                with self.client.get(
                    f"/api/books/{book_id}",
                    name="GET /api/books/:id (direct download preload)",
                    catch_response=True,
                ) as detail_response:
                    if detail_response.status_code != 200:
                        detail_response.failure(f"direct download detail preload failed: http {detail_response.status_code}")
                        continue
                    book = detail_response.json()
                    file_id = book.get("book_file_id")
                    if not file_id:
                        detail_response.failure("direct download preload detail does not include book_file_id")
                        continue
                    direct_file_ids.append(int(file_id))

            if not direct_file_ids:
                return None

            with self.client.get(
                f"/api/files/{direct_file_ids[0]}/download",
                name="GET /api/files/:id/download (direct preload)",
                catch_response=True,
            ) as download_response:
                if download_response.status_code != 200:
                    download_response.failure(f"direct download preload sign failed: http {download_response.status_code}")
                    return None

            _direct_download_file_ids.extend(direct_file_ids)
            return random.choice(_direct_download_file_ids)

    def _ensure_hot_download_file_id(self) -> int | None:
        global _hot_download_file_id
        with _hot_download_file_lock:
            if _hot_download_file_id is not None:
                return _hot_download_file_id
            file_id = self._ensure_direct_download_file_id()
            if file_id is None:
                return None
            _hot_download_file_id = int(file_id)
            return _hot_download_file_id

    def _serial_actions(self) -> dict[str, Callable[[], None]]:
        return {
            "auth_login": lambda: self.auth_login(from_serial=True),
            "ping": lambda: self.get_ping(from_serial=True),
            "auth_me": lambda: self.get_auth_me(from_serial=True),
            "books_count": lambda: self.get_books_count(from_serial=True),
            "list_books": lambda: self.list_books(from_serial=True),
            "search_books": lambda: self.search_books(from_serial=True),
            "book_detail": lambda: self.get_book_detail(from_serial=True),
            "favorite_status": lambda: self.get_favorite_status(from_serial=True),
            "favorite_toggle": lambda: self.toggle_favorite(from_serial=True),
            "favorites_list": lambda: self.list_favorites(from_serial=True),
            "uploads_list": lambda: self.list_uploads(from_serial=True),
            "download_url": lambda: self.get_download_url(from_serial=True),
            "download_url_hot": lambda: self.get_hot_download_url(from_serial=True),
            "download_url_direct": lambda: self.get_direct_download_url(from_serial=True),
        }

    @task(1)
    def run_serial_flow(self) -> None:
        if self._is_parallel():
            return
        _skip_disabled_serial_phases(self.enabled_tests)
        phase_name, generation = _get_serial_phase_state()
        if self._last_serial_generation == generation:
            sleep(0.01)
            return

        actions = self._serial_actions()
        action = actions.get(str(phase_name))
        if action is not None:
            action()

        self._last_serial_generation = generation
        runner = getattr(self.environment, "runner", None)
        participant_count = int(getattr(runner, "user_count", 0) or int(self.scenarios.get("vus", 1)))
        _mark_serial_phase_completed(self._serial_user_key, participant_count=participant_count)

    @task(1)
    def get_ping(self, from_serial: bool = False) -> None:
        if self._is_serial() and not from_serial:
            return
        if not self.enabled_tests.get("ping", False):
            return
        with self.client.get("/ping", name="GET /ping", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"ping failed: http {response.status_code}")

    @task(1)
    def auth_login(self, from_serial: bool = False) -> None:
        if self._is_serial() and not from_serial:
            return
        if not self.enabled_tests.get("auth_login", False):
            return
        self._login()

    @task(1)
    def get_auth_me(self, from_serial: bool = False) -> None:
        if self._is_serial() and not from_serial:
            return
        if not self.enabled_tests.get("auth_me", False):
            return
        if not self._ensure_login():
            return
        with self.client.get("/api/auth/me", name="GET /api/auth/me", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"auth_me failed: http {response.status_code}")

    @task(1)
    def get_books_count(self, from_serial: bool = False) -> None:
        if self._is_serial() and not from_serial:
            return
        if not self.enabled_tests.get("books_count", False):
            return
        with self.client.get("/api/books/count", name="GET /api/books/count", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"books_count failed: http {response.status_code}")

    @task(4)
    def list_books(self, from_serial: bool = False) -> None:
        if self._is_serial() and not from_serial:
            return
        if not self.enabled_tests.get("list_books", True):
            return
        page = int(self.list_books_config.get("page", 1))
        page_size = int(self.list_books_config.get("page_size", 10))
        with self.client.get(
            "/api/books",
            params={"page": page, "pageSize": page_size},
            name="GET /api/books",
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
    def search_books(self, from_serial: bool = False) -> None:
        if self._is_serial() and not from_serial:
            return
        if not self.enabled_tests.get("search_books", True):
            return
        query = self._choose_search_query()
        page = int(self.search_books_config.get("page", 1))
        page_size = int(self.search_books_config.get("page_size", 10))
        with self.client.get(
            "/api/books/search",
            params={"query": query, "page": page, "pageSize": page_size},
            name="GET /api/books/search",
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
    def get_book_detail(self, from_serial: bool = False) -> None:
        if self._is_serial() and not from_serial:
            return
        if not self.enabled_tests.get("book_detail", True):
            return
        book_id = self._ensure_book_id()
        if book_id is None:
            return

        with self.client.get(
            f"/api/books/{book_id}",
            name="GET /api/books/:id",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"get_book_detail failed: http {response.status_code}")

    @task(1)
    def get_favorite_status(self, from_serial: bool = False) -> None:
        if self._is_serial() and not from_serial:
            return
        if not self.enabled_tests.get("favorite_status", False):
            return
        if not self._ensure_login():
            return
        book_id = self._ensure_book_id()
        if book_id is None:
            return
        with self.client.get(
            f"/api/users/me/favorites/{book_id}",
            name="GET /api/users/me/favorites/:id",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"favorite_status failed: http {response.status_code}")

    @task(1)
    def toggle_favorite(self, from_serial: bool = False) -> None:
        if self._is_serial() and not from_serial:
            return
        if not self.enabled_tests.get("favorite_toggle", False):
            return
        if not self._ensure_login():
            return
        book_id = self._ensure_book_id()
        if book_id is None:
            return

        with self.client.post(
            f"/api/users/me/favorites/{book_id}",
            name="POST /api/users/me/favorites/:id",
            catch_response=True,
        ) as add_response:
            if add_response.status_code >= 400:
                add_response.failure(f"add_favorite failed: http {add_response.status_code}")

        with self.client.delete(
            f"/api/users/me/favorites/{book_id}",
            name="DELETE /api/users/me/favorites/:id",
            catch_response=True,
        ) as remove_response:
            if remove_response.status_code >= 400:
                remove_response.failure(f"remove_favorite failed: http {remove_response.status_code}")

    @task(1)
    def list_favorites(self, from_serial: bool = False) -> None:
        if self._is_serial() and not from_serial:
            return
        if not self.enabled_tests.get("favorites_list", False):
            return
        if not self._ensure_login():
            return
        page = int(self.favorites_config.get("page", 1))
        page_size = int(self.favorites_config.get("page_size", 10))
        with self.client.get(
            "/api/users/me/favorites",
            params={"page": page, "pageSize": page_size},
            name="GET /api/users/me/favorites",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"favorites_list failed: http {response.status_code}")

    @task(1)
    def list_uploads(self, from_serial: bool = False) -> None:
        if self._is_serial() and not from_serial:
            return
        if not self.enabled_tests.get("uploads_list", False):
            return
        if not self._ensure_login():
            return
        page = int(self.uploads_config.get("page", 1))
        page_size = int(self.uploads_config.get("page_size", 10))
        with self.client.get(
            "/api/users/me/uploads",
            params={"page": page, "pageSize": page_size},
            name="GET /api/users/me/uploads",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"uploads_list failed: http {response.status_code}")

    @task(1)
    def get_download_url(self, from_serial: bool = False) -> None:
        if self._is_serial() and not from_serial:
            return
        if not self.enabled_tests.get("download_url", True):
            return
        book_id = self._ensure_book_id()
        if book_id is None:
            return

        with self.client.get(
            f"/api/books/{book_id}",
            name="GET /api/books/:id (download setup)",
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
            f"/api/files/{file_id}/download",
            name="GET /api/files/:id/download",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"download_url failed: http {response.status_code}")

    @task(1)
    def get_direct_download_url(self, from_serial: bool = False) -> None:
        if self._is_serial() and not from_serial:
            return
        if not self.enabled_tests.get("download_url_direct", False):
            return
        file_id = self._ensure_direct_download_file_id()
        if file_id is None:
            return
        _record_direct_download_file_id(file_id)

        with self.client.get(
            f"/api/files/{file_id}/download",
            name="GET /api/files/:id/download (direct)",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"download_url_direct failed: http {response.status_code}")

    @task(1)
    def get_hot_download_url(self, from_serial: bool = False) -> None:
        if self._is_serial() and not from_serial:
            return
        if not self.enabled_tests.get("download_url_hot", False):
            return
        file_id = self._ensure_hot_download_file_id()
        if file_id is None:
            return

        with self.client.get(
            f"/api/files/{file_id}/download",
            name="GET /api/files/:id/download (hot)",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"download_url_hot failed: http {response.status_code}")
