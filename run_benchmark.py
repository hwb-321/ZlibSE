from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from config_loader import CONFIG_PATH, RUNTIME_STATE_PATH, get_all_accounts, load_benchmark_config, save_runtime_state
from jwt_cache import get_valid_token, prune_cache, set_token


ROOT_DIR = Path(__file__).resolve().parent
LOGS_DIR = ROOT_DIR / "logs"
SEQUENTIAL_ORDER = [
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
AUTH_REQUIRED_TESTS = {
    "auth_me",
    "favorite_status",
    "favorite_toggle",
    "favorites_list",
    "uploads_list",
}


def _json_request(method: str, url: str, *, retries: int = 0, retry_delay_seconds: float = 0.2) -> dict[str, Any]:
    request = urllib.request.Request(url=url, method=method)
    attempt = 0
    while True:
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            if exc.code >= 500 and attempt < retries:
                attempt += 1
                time.sleep(retry_delay_seconds * attempt)
                continue
            raise RuntimeError(f"{method} {url} failed: {exc.code} {detail}") from exc
        except urllib.error.URLError as exc:
            if attempt < retries:
                attempt += 1
                time.sleep(retry_delay_seconds * attempt)
                continue
            raise RuntimeError(f"{method} {url} failed: {exc}") from exc


def _get_json(url: str) -> dict[str, Any]:
    return _json_request("GET", url)


def _delete_json(url: str) -> dict[str, Any]:
    return _json_request("DELETE", url)


def _is_debug_metrics_disabled_error(exc: RuntimeError) -> bool:
    message = str(exc)
    return "/debug/metrics" in message and "404" in message and "Debug metrics disabled" in message


def _prepare_runtime_state(config: dict[str, Any]) -> dict[str, Any]:
    base_url = str(config.get("base_url", "http://127.0.0.1:8000")).rstrip("/")
    list_cfg = config.get("list_books") or {}
    page_size = int(list_cfg.get("page_size", 20))
    accounts_cfg = config.get("accounts") or {}
    books_cfg = config.get("books") or {}
    expected_book_count = max(0, int(accounts_cfg.get("user_count", 0))) * max(0, int(books_cfg.get("books_per_user", 0)))

    book_ids: list[int] = []
    seen_book_ids: set[int] = set()
    page = 1
    while expected_book_count <= 0 or len(book_ids) < expected_book_count:
        params = urllib.parse.urlencode({"page": page, "pageSize": page_size})
        books_payload = _get_json(f"{base_url}/api/books?{params}")
        books = books_payload.get("books") or []
        if not isinstance(books, list) or not books:
            break
        page_new_ids = 0
        for item in books:
            if not isinstance(item, dict) or item.get("id") is None:
                continue
            book_id = int(item["id"])
            if book_id in seen_book_ids:
                continue
            seen_book_ids.add(book_id)
            book_ids.append(book_id)
            page_new_ids += 1
            if expected_book_count > 0 and len(book_ids) >= expected_book_count:
                break
        if page_new_ids == 0:
            break
        page += 1

    direct_file_ids: list[int] = []
    hot_download_file_id: int | None = None
    for book_id in book_ids:
        try:
            detail = _json_request("GET", f"{base_url}/api/books/{book_id}", retries=2, retry_delay_seconds=0.3)
        except RuntimeError as exc:
            print(f"[prepare][skip] {exc}")
            continue
        file_id = detail.get("book_file_id")
        if isinstance(file_id, int) or (isinstance(file_id, str) and str(file_id).isdigit()):
            direct_file_ids.append(int(file_id))
    if direct_file_ids:
        hot_download_file_id = direct_file_ids[0]

    runtime_state = {
        "generated_at": datetime.now().isoformat(),
        "book_ids": book_ids,
        "direct_download_file_ids": direct_file_ids,
        "hot_download_file_id": hot_download_file_id,
        "access_tokens": {},
    }
    save_runtime_state(runtime_state)
    return runtime_state


def _should_prelogin_tokens(selected_tests: list[str]) -> bool:
    unique = [name for name in selected_tests if name]
    if not unique:
        return False
    if unique == ["auth_login"]:
        return False
    return any(name in AUTH_REQUIRED_TESTS for name in unique)


def _prelogin_tokens(config: dict[str, Any], runtime_state: dict[str, Any], *, selected_tests: list[str]) -> dict[str, Any]:
    if not _should_prelogin_tokens(selected_tests):
        runtime_state["access_tokens"] = {}
        save_runtime_state(runtime_state)
        return runtime_state

    base_url = str(config.get("base_url", "http://127.0.0.1:8000")).rstrip("/")
    accounts = get_all_accounts()
    prune_cache()
    token_map: dict[str, str] = {}
    for account in accounts:
        username = str(account["username"])
        cached_token = get_valid_token(base_url, username)
        if cached_token:
            token_map[username] = cached_token
            continue
        payload = urllib.parse.urlencode(
            {
                "username": username,
                "password": str(account["password"]),
                "captcha_key": "",
                "captcha_value": "",
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            url=f"{base_url}/api/auth/login",
            method="POST",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            data = json.loads(raw) if raw else {}
        access_token = data.get("access_token")
        if isinstance(access_token, str) and access_token:
            token_map[username] = access_token
            set_token(base_url, username, access_token)
    runtime_state["access_tokens"] = token_map
    save_runtime_state(runtime_state)
    return runtime_state


def _clear_debug_metrics(base_url: str) -> None:
    try:
        _delete_json(f"{base_url.rstrip('/')}/debug/metrics")
    except RuntimeError as exc:
        if _is_debug_metrics_disabled_error(exc):
            print("[debug_metrics] disabled, skip reset")
            return
        raise


def _read_debug_metrics(base_url: str) -> dict[str, Any]:
    try:
        return _get_json(f"{base_url.rstrip('/')}/debug/metrics")
    except RuntimeError as exc:
        if _is_debug_metrics_disabled_error(exc):
            print("[debug_metrics] disabled, skip read")
            return {
                "enabled": False,
                "generatedAt": datetime.now().isoformat(),
                "requests": [],
                "timings": [],
                "counters": {},
            }
        raise


def _latest_report(existing: set[Path]) -> Path:
    candidates = {path for path in LOGS_DIR.glob("压测结果_*.md")} - existing
    if not candidates:
        raise RuntimeError("未找到新的压测报告文件")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _append_debug_metrics(report_path: Path, debug_metrics: dict[str, Any]) -> None:
    lines = ["", "## 后端调试指标", ""]
    if not debug_metrics.get("enabled"):
        lines.append("- 调试指标未开启或无法读取")
        report_path.write_text(report_path.read_text(encoding="utf-8") + "\n".join(lines) + "\n", encoding="utf-8")
        return

    counters = debug_metrics.get("counters") or {}
    timings = debug_metrics.get("timings") or []
    requests = debug_metrics.get("requests") or []
    lines.append(f"- 采样时间：{debug_metrics.get('generatedAt')}")
    lines.append("")
    lines.append("### Counters")
    lines.append("")
    if counters:
        for name, value in counters.items():
            lines.append(f"- `{name}`: {value}")
    else:
        lines.append("- 无")
    lines.append("")
    lines.append("### Timings")
    lines.append("")
    if timings:
        lines.append("| 名称 | 次数 | 总耗时(ms) | 平均耗时(ms) |")
        lines.append("| --- | ---: | ---: | ---: |")
        for item in timings:
            lines.append(
                f"| `{item.get('name','')}` | {item.get('count',0)} | {item.get('totalMs',0)} | {item.get('avgMs',0)} |"
            )
    else:
        lines.append("- 无")
    lines.append("")
    lines.append("### Requests")
    lines.append("")
    if requests:
        lines.append("| 方法 | 路由 | 次数 | 失败 | 总耗时(ms) | 平均耗时(ms) |")
        lines.append("| --- | --- | ---: | ---: | ---: | ---: |")
        for item in requests:
            lines.append(
                f"| {item.get('method','')} | `{item.get('route','')}` | {item.get('count',0)} | {item.get('failures',0)} | {item.get('totalMs',0)} | {item.get('avgMs',0)} |"
            )
    else:
        lines.append("- 无")
    report_path.write_text(report_path.read_text(encoding="utf-8") + "\n".join(lines) + "\n", encoding="utf-8")


def _run_locust_with_config(config_path: Path, *, mode: str) -> tuple[int, str, Path]:
    existing_reports = set(LOGS_DIR.glob("压测结果_*.md"))
    env = os.environ.copy()
    env["BENCHMARK_CONFIG_FILE"] = str(config_path)
    env["BENCHMARK_RUNTIME_STATE_FILE"] = str(RUNTIME_STATE_PATH)
    command = [sys.executable, "-m", "locust", "-f", "locustfile.py"]
    if mode == "headless":
        command.append("--headless")
    completed = subprocess.run(
        command,
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        env=env,
    )
    report_path = _latest_report(existing_reports)
    return completed.returncode, (completed.stdout + ("\n" + completed.stderr if completed.stderr else "")).strip(), report_path


def _build_single_test_config(config: dict[str, Any], test_name: str) -> dict[str, Any]:
    cloned = yaml.safe_load(yaml.safe_dump(config, allow_unicode=True, sort_keys=False))
    enabled = cloned.get("enabled_tests") or {}
    for key in list(enabled.keys()):
        enabled[key] = key == test_name
    cloned["enabled_tests"] = enabled
    execution = cloned.get("execution") or {}
    execution["mode"] = "parallel"
    execution["orchestrated_serial"] = True
    execution["orchestrated_test_name"] = test_name
    cloned["execution"] = execution
    return cloned


def _write_temp_config(config: dict[str, Any]) -> Path:
    handle = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, dir=ROOT_DIR, encoding="utf-8")
    with handle:
        yaml.safe_dump(config, handle, allow_unicode=True, sort_keys=False)
    return Path(handle.name)


def _selected_tests(config: dict[str, Any]) -> list[str]:
    enabled = config.get("enabled_tests") or {}
    return [name for name in SEQUENTIAL_ORDER if enabled.get(name, False)]


def run_benchmark(locust_mode: str = "headless") -> int:
    config = load_benchmark_config()
    base_url = str(config.get("base_url", "http://127.0.0.1:8000")).rstrip("/")
    execution_mode = str((config.get("execution") or {}).get("mode", "parallel")).lower()
    selected_tests = _selected_tests(config)

    if locust_mode != "headless" and execution_mode == "serial":
        print("serial 模式当前仅支持 headless 运行")
        return 1

    if execution_mode == "serial":
        if not selected_tests:
            print("未启用任何接口，无法进行串行压测")
            return 1
        summary_lines = ["串行压测开始"]
        overall_exit = 0
        for test_name in selected_tests:
            print(f"[prepare] {test_name}")
            runtime_state = _prepare_runtime_state(config)
            runtime_state = _prelogin_tokens(config, runtime_state, selected_tests=[test_name])
            print(f"[runtime_state] book_ids={len(runtime_state.get('book_ids', []))} direct_file_ids={len(runtime_state.get('direct_download_file_ids', []))}")
            _clear_debug_metrics(base_url)
            test_config = _build_single_test_config(config, test_name)
            temp_config = _write_temp_config(test_config)
            try:
                code, output, report_path = _run_locust_with_config(temp_config, mode=locust_mode)
            finally:
                temp_config.unlink(missing_ok=True)
            debug_metrics = _read_debug_metrics(base_url)
            _append_debug_metrics(report_path, debug_metrics)
            print(f"[done] {test_name} report={report_path}")
            if output:
                print(output)
            summary_lines.append(f"- {test_name}: exit={code}, report={report_path.name}")
            overall_exit = overall_exit or code
        print("\n".join(summary_lines))
        return overall_exit

    runtime_state = _prepare_runtime_state(config)
    runtime_state = _prelogin_tokens(config, runtime_state, selected_tests=selected_tests)
    print(f"[runtime_state] book_ids={len(runtime_state.get('book_ids', []))} direct_file_ids={len(runtime_state.get('direct_download_file_ids', []))}")
    _clear_debug_metrics(base_url)
    code, output, report_path = _run_locust_with_config(CONFIG_PATH, mode=locust_mode)
    debug_metrics = _read_debug_metrics(base_url)
    _append_debug_metrics(report_path, debug_metrics)
    if output:
        print(output)
    print(f"[done] report={report_path}")
    return code


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "headless"
    raise SystemExit(run_benchmark(mode))
