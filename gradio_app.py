from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import gradio as gr
import yaml

from config_loader import CONFIG_PATH, load_benchmark_config


ROOT_DIR = Path(__file__).resolve().parent
_process_lock = threading.Lock()
_locust_process: subprocess.Popen[str] | None = None


def _run_command(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
    )
    output = completed.stdout + ("\n" + completed.stderr if completed.stderr else "")
    if completed.returncode != 0:
        return f"[exit={completed.returncode}]\n{output}".strip()
    return output.strip() or "[ok]"


def _stream_command(command: list[str]):
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    process = subprocess.Popen(
        command,
        cwd=ROOT_DIR,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        env=env,
    )
    if process.stdout is None:
        yield "[error] 无法读取脚本输出"
        return

    chunks: list[str] = []
    pending: list[str] = []
    last_emit = time.monotonic()
    while True:
        chunk = process.stdout.read(1)
        if chunk == "" and process.poll() is not None:
            break
        if not chunk:
            continue
        if chunk == "\r":
            chunk = "\n"
        pending.append(chunk)

        now = time.monotonic()
        should_emit = chunk == "\n" or (now - last_emit) >= 0.2
        if should_emit:
            chunks.extend(pending)
            pending.clear()
            last_emit = now
            yield "".join(chunks)

    if pending:
        chunks.extend(pending)
        yield "".join(chunks)

    process.wait()
    output = "".join(chunks).strip()
    if process.returncode != 0:
        yield f"[exit={process.returncode}]\n{output}".strip()
        return
    yield output or "[ok]"


def _bool_value(value: Any) -> bool:
    return bool(value)


def _int_value(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float_value(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _str_value(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _list_to_text(values: list[Any] | None) -> str:
    if not values:
        return ""
    return "\n".join(str(item) for item in values)


def _text_to_list(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _load_form_values() -> list[Any]:
    config = load_benchmark_config()
    accounts = config.get("accounts") or {}
    scenarios = config.get("scenarios") or {}
    execution = config.get("execution") or {}
    init_data = config.get("init_data") or {}
    mock = config.get("mock") or {}
    enabled_tests = config.get("enabled_tests") or {}
    books = config.get("books") or {}
    books_count = config.get("books_count") or {}
    list_books = config.get("list_books") or {}
    search_books = config.get("search_books") or {}
    favorites = config.get("favorites") or {}
    uploads = config.get("uploads") or {}
    thresholds = config.get("thresholds") or {}

    return [
        _str_value(config.get("base_url"), "http://127.0.0.1:8000"),
        _int_value(accounts.get("user_count"), 300),
        _str_value(accounts.get("username_prefix"), "bench_user"),
        _str_value(accounts.get("email_domain"), "benchmark@local"),
        _str_value(accounts.get("default_password"), "BenchmarkPass123!"),
        _int_value(scenarios.get("vus"), 200),
        _str_value(scenarios.get("duration"), "10s"),
        _float_value(scenarios.get("spawn_rate"), 200),
        _int_value(scenarios.get("wait_time_min_ms"), 0),
        _int_value(scenarios.get("wait_time_max_ms"), 0),
        _str_value(execution.get("mode"), "parallel"),
        _int_value(init_data.get("workers"), 4),
        _bool_value(mock.get("server_mock")),
        _str_value(mock.get("upload_mode"), "skip_upload"),
        _bool_value(enabled_tests.get("ping")),
        _bool_value(enabled_tests.get("auth_login")),
        _bool_value(enabled_tests.get("auth_me")),
        _bool_value(enabled_tests.get("books_count")),
        _bool_value(enabled_tests.get("list_books", True)),
        _bool_value(enabled_tests.get("search_books", True)),
        _bool_value(enabled_tests.get("book_detail", True)),
        _bool_value(enabled_tests.get("favorite_status")),
        _bool_value(enabled_tests.get("favorite_toggle")),
        _bool_value(enabled_tests.get("favorites_list")),
        _bool_value(enabled_tests.get("uploads_list")),
        _bool_value(enabled_tests.get("download_url")),
        _bool_value(enabled_tests.get("download_url_hot")),
        _bool_value(enabled_tests.get("download_url_direct")),
        _int_value(books.get("books_per_user"), 5),
        _str_value(books.get("default_category"), "benchmark"),
        _str_value(books.get("default_language"), "zh-CN"),
        _int_value(books.get("default_year"), 2024),
        _bool_value(books.get("include_cover", True)),
        _bool_value(books_count.get("jitter")),
        _int_value(list_books.get("page"), 1),
        _int_value(list_books.get("page_size"), 20),
        _str_value(search_books.get("mode"), "random_from_list"),
        _str_value(search_books.get("query"), "python"),
        _list_to_text(search_books.get("queries")),
        _int_value(search_books.get("generated_min_length"), 2),
        _int_value(search_books.get("generated_max_length"), 6),
        _int_value(search_books.get("page"), 1),
        _int_value(search_books.get("page_size"), 20),
        _int_value(favorites.get("page"), 1),
        _int_value(favorites.get("page_size"), 20),
        _int_value(uploads.get("page"), 1),
        _int_value(uploads.get("page_size"), 20),
        _float_value(thresholds.get("max_error_rate"), 0.01),
        _int_value(thresholds.get("p95_ms"), 200),
        _int_value(thresholds.get("p99_ms"), 400),
    ]


def _build_config_from_form(*values: Any) -> dict[str, Any]:
    (
        base_url,
        user_count,
        username_prefix,
        email_domain,
        default_password,
        vus,
        duration,
        spawn_rate,
        wait_time_min_ms,
        wait_time_max_ms,
        execution_mode,
        init_workers,
        server_mock,
        upload_mode,
        ping,
        auth_login,
        auth_me,
        books_count_enabled,
        list_books_enabled,
        search_books_enabled,
        book_detail,
        favorite_status,
        favorite_toggle,
        favorites_list,
        uploads_list,
        download_url,
        download_url_hot,
        download_url_direct,
        books_per_user,
        default_category,
        default_language,
        default_year,
        include_cover,
        books_count_jitter,
        list_page,
        list_page_size,
        search_mode,
        search_query,
        search_queries_text,
        generated_min_length,
        generated_max_length,
        search_page,
        search_page_size,
        favorites_page,
        favorites_page_size,
        uploads_page,
        uploads_page_size,
        max_error_rate,
        p95_ms,
        p99_ms,
    ) = values

    return {
        "base_url": _str_value(base_url, "http://127.0.0.1:8000"),
        "accounts": {
            "user_count": _int_value(user_count, 300),
            "username_prefix": _str_value(username_prefix, "bench_user"),
            "email_domain": _str_value(email_domain, "benchmark@local"),
            "default_password": _str_value(default_password, "BenchmarkPass123!"),
        },
        "scenarios": {
            "vus": _int_value(vus, 200),
            "duration": _str_value(duration, "10s"),
            "spawn_rate": _float_value(spawn_rate, 200),
            "wait_time_min_ms": _int_value(wait_time_min_ms, 0),
            "wait_time_max_ms": _int_value(wait_time_max_ms, 0),
        },
        "execution": {
            "mode": _str_value(execution_mode, "parallel"),
        },
        "init_data": {
            "workers": _int_value(init_workers, 4),
        },
        "mock": {
            "server_mock": _bool_value(server_mock),
            "upload_mode": _str_value(upload_mode, "skip_upload"),
        },
        "enabled_tests": {
            "ping": _bool_value(ping),
            "auth_login": _bool_value(auth_login),
            "auth_me": _bool_value(auth_me),
            "books_count": _bool_value(books_count_enabled),
            "list_books": _bool_value(list_books_enabled),
            "search_books": _bool_value(search_books_enabled),
            "book_detail": _bool_value(book_detail),
            "favorite_status": _bool_value(favorite_status),
            "favorite_toggle": _bool_value(favorite_toggle),
            "favorites_list": _bool_value(favorites_list),
            "uploads_list": _bool_value(uploads_list),
            "download_url": _bool_value(download_url),
            "download_url_hot": _bool_value(download_url_hot),
            "download_url_direct": _bool_value(download_url_direct),
        },
        "books": {
            "books_per_user": _int_value(books_per_user, 5),
            "default_category": _str_value(default_category, "benchmark"),
            "default_language": _str_value(default_language, "zh-CN"),
            "default_year": _int_value(default_year, 2024),
            "include_cover": _bool_value(include_cover),
        },
        "books_count": {
            "jitter": _bool_value(books_count_jitter),
        },
        "list_books": {
            "page": _int_value(list_page, 1),
            "page_size": _int_value(list_page_size, 20),
        },
        "search_books": {
            "mode": _str_value(search_mode, "random_from_list"),
            "query": _str_value(search_query, "python"),
            "queries": _text_to_list(_str_value(search_queries_text)),
            "generated_min_length": _int_value(generated_min_length, 2),
            "generated_max_length": _int_value(generated_max_length, 6),
            "page": _int_value(search_page, 1),
            "page_size": _int_value(search_page_size, 20),
        },
        "favorites": {
            "page": _int_value(favorites_page, 1),
            "page_size": _int_value(favorites_page_size, 20),
        },
        "uploads": {
            "page": _int_value(uploads_page, 1),
            "page_size": _int_value(uploads_page_size, 20),
        },
        "thresholds": {
            "max_error_rate": _float_value(max_error_rate, 0.01),
            "p95_ms": _int_value(p95_ms, 200),
            "p99_ms": _int_value(p99_ms, 400),
        },
    }


def _save_form_config(*values: Any) -> str:
    config = _build_config_from_form(*values)
    content = yaml.safe_dump(config, allow_unicode=True, sort_keys=False)
    CONFIG_PATH.write_text(content, encoding="utf-8")
    return f"已保存到 {CONFIG_PATH}"


def _preview_form_config(*values: Any) -> str:
    config = _build_config_from_form(*values)
    return yaml.safe_dump(config, allow_unicode=True, sort_keys=False)


def generate_data():
    yield from _stream_command([sys.executable, "-u", "generate_benchmark_data.py"])


def init_data():
    yield from _stream_command([sys.executable, "-u", "init_benchmark_data.py"])


def start_locust(mode: str) -> str:
    global _locust_process
    with _process_lock:
        if _locust_process is not None and _locust_process.poll() is None:
            return f"Locust 已在运行，PID={_locust_process.pid}"

        execution_mode = str((load_benchmark_config().get("execution") or {}).get("mode", "parallel")).lower()
        if mode == "headless":
            command = [sys.executable, "run_benchmark.py", "headless"]
        else:
            if execution_mode == "serial":
                return "serial 模式当前仅支持 headless 运行"
            command = [sys.executable, "-m", "locust", "-f", "locustfile.py"]

        _locust_process = subprocess.Popen(
            command,
            cwd=ROOT_DIR,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        return f"Locust 已启动，PID={_locust_process.pid}，模式={mode}"


def stop_locust() -> str:
    global _locust_process
    with _process_lock:
        if _locust_process is None or _locust_process.poll() is not None:
            _locust_process = None
            return "Locust 当前未运行"
        _locust_process.terminate()
        try:
            _locust_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _locust_process.kill()
            _locust_process.wait(timeout=5)
        pid = _locust_process.pid
        _locust_process = None
        return f"Locust 已停止，PID={pid}"


def poll_locust_output() -> str:
    with _process_lock:
        process = _locust_process
    if process is None:
        return "Locust 当前未运行"
    if process.stdout is None:
        return "Locust 输出不可用"

    lines: list[str] = []
    while True:
        line = process.stdout.readline()
        if not line:
            break
        lines.append(line.rstrip("\n"))
    if not lines:
        if process.poll() is None:
            return f"Locust 运行中，PID={process.pid}"
        return f"Locust 已结束，exit={process.returncode}"
    return "\n".join(lines)


def build_app() -> gr.Blocks:
    defaults = _load_form_values()
    with gr.Blocks(title="ZlibSE Benchmark 控制台") as demo:
        gr.Markdown("# ZlibSE Benchmark 控制台")
        gr.Markdown("通过表单配置压测参数，保存时会自动生成新的 `config.yaml`。")

        with gr.Accordion("基础配置", open=True):
            with gr.Row():
                base_url = gr.Textbox(label="后端地址", value=defaults[0])
            with gr.Row():
                user_count = gr.Number(label="用户数", value=defaults[1], precision=0)
                username_prefix = gr.Textbox(label="用户名前缀", value=defaults[2])
                email_domain = gr.Textbox(label="邮箱域名", value=defaults[3])
                default_password = gr.Textbox(label="默认密码", value=defaults[4], type="password")
            with gr.Row():
                vus = gr.Number(label="并发用户数", value=defaults[5], precision=0)
                duration = gr.Textbox(label="持续时间", value=defaults[6])
                spawn_rate = gr.Number(label="每秒启动数", value=defaults[7])
            with gr.Row():
                wait_time_min_ms = gr.Number(label="最小等待(ms)", value=defaults[8], precision=0)
                wait_time_max_ms = gr.Number(label="最大等待(ms)", value=defaults[9], precision=0)

        with gr.Accordion("执行与 Mock", open=False):
            with gr.Row():
                execution_mode = gr.Dropdown(
                    label="执行模式",
                    choices=["parallel", "serial"],
                    value=defaults[10],
                )
                init_workers = gr.Number(label="初始化 worker 数", value=defaults[11], precision=0)
                upload_mode = gr.Dropdown(
                    label="脚本上传模式",
                    choices=["skip_upload", "empty_file", "small_sample"],
                    value=defaults[13],
                )
                server_mock = gr.Checkbox(label="后端 server-mock", value=defaults[12])
            gr.Markdown("`serial` 模式下会自动按默认顺序依次执行已勾选接口，无需手动配置执行链路。")

        with gr.Accordion("接口开关", open=False):
            with gr.Row():
                ping = gr.Checkbox(label="ping", value=defaults[14])
                auth_login = gr.Checkbox(label="auth_login", value=defaults[15])
                auth_me = gr.Checkbox(label="auth_me", value=defaults[16])
                books_count_enabled = gr.Checkbox(label="books_count", value=defaults[17])
            with gr.Row():
                list_books_enabled = gr.Checkbox(label="list_books", value=defaults[18])
                search_books_enabled = gr.Checkbox(label="search_books", value=defaults[19])
                book_detail = gr.Checkbox(label="book_detail", value=defaults[20])
                favorite_status = gr.Checkbox(label="favorite_status", value=defaults[21])
            with gr.Row():
                favorite_toggle = gr.Checkbox(label="favorite_toggle", value=defaults[22])
                favorites_list = gr.Checkbox(label="favorites_list", value=defaults[23])
                uploads_list = gr.Checkbox(label="uploads_list", value=defaults[24])
                download_url = gr.Checkbox(label="download_url", value=defaults[25])
                download_url_hot = gr.Checkbox(label="download_url_hot", value=defaults[26])
                download_url_direct = gr.Checkbox(label="download_url_direct", value=defaults[27])

        with gr.Accordion("书籍与分页", open=False):
            with gr.Row():
                books_per_user = gr.Number(label="每用户书籍数", value=defaults[28], precision=0)
                default_category = gr.Textbox(label="默认分类", value=defaults[29])
                default_language = gr.Textbox(label="默认语言", value=defaults[30])
                default_year = gr.Number(label="默认年份", value=defaults[31], precision=0)
                include_cover = gr.Checkbox(label="包含封面", value=defaults[32])
            books_count_jitter = gr.Checkbox(label="books_count jitter", value=defaults[33])
            with gr.Row():
                list_page = gr.Number(label="列表页码", value=defaults[34], precision=0)
                list_page_size = gr.Number(label="列表每页", value=defaults[35], precision=0)
            with gr.Row():
                favorites_page = gr.Number(label="收藏页码", value=defaults[43], precision=0)
                favorites_page_size = gr.Number(label="收藏每页", value=defaults[44], precision=0)
            with gr.Row():
                uploads_page = gr.Number(label="上传页码", value=defaults[45], precision=0)
                uploads_page_size = gr.Number(label="上传每页", value=defaults[46], precision=0)

        with gr.Accordion("搜索配置", open=False):
            with gr.Row():
                search_mode = gr.Dropdown(
                    label="搜索模式",
                    choices=["fixed", "random_from_list", "random_generated"],
                    value=defaults[36],
                )
                search_query = gr.Textbox(label="固定搜索词", value=defaults[37])
            search_queries_text = gr.Textbox(
                label="随机词池（每行一个）",
                lines=8,
                value=defaults[38],
            )
            with gr.Row():
                generated_min_length = gr.Number(label="随机词最短长度", value=defaults[39], precision=0)
                generated_max_length = gr.Number(label="随机词最长长度", value=defaults[40], precision=0)
            with gr.Row():
                search_page = gr.Number(label="搜索页码", value=defaults[41], precision=0)
                search_page_size = gr.Number(label="搜索每页", value=defaults[42], precision=0)

        with gr.Accordion("阈值与预览", open=False):
            with gr.Row():
                max_error_rate = gr.Number(label="最大错误率", value=defaults[47])
                p95_ms = gr.Number(label="P95 上限(ms)", value=defaults[48], precision=0)
                p99_ms = gr.Number(label="P99 上限(ms)", value=defaults[49], precision=0)
            config_preview = gr.Code(label="生成后的 config.yaml 预览", language="yaml", interactive=False)

        form_inputs = [
            base_url,
            user_count,
            username_prefix,
            email_domain,
            default_password,
            vus,
            duration,
            spawn_rate,
            wait_time_min_ms,
            wait_time_max_ms,
            execution_mode,
            init_workers,
            server_mock,
            upload_mode,
            ping,
            auth_login,
            auth_me,
            books_count_enabled,
            list_books_enabled,
            search_books_enabled,
            book_detail,
            favorite_status,
            favorite_toggle,
            favorites_list,
            uploads_list,
            download_url,
            download_url_hot,
            download_url_direct,
            books_per_user,
            default_category,
            default_language,
            default_year,
            include_cover,
            books_count_jitter,
            list_page,
            list_page_size,
            search_mode,
            search_query,
            search_queries_text,
            generated_min_length,
            generated_max_length,
            search_page,
            search_page_size,
            favorites_page,
            favorites_page_size,
            uploads_page,
            uploads_page_size,
            max_error_rate,
            p95_ms,
            p99_ms,
        ]

        for component in form_inputs:
            component.change(_preview_form_config, inputs=form_inputs, outputs=config_preview)

        with gr.Row():
            load_button = gr.Button("从文件重新加载")
            save_button = gr.Button("保存配置")
        save_status = gr.Textbox(label="配置状态", interactive=False)

        with gr.Row():
            generate_button = gr.Button("生成 benchmark_data.yaml")
            init_button = gr.Button("初始化压测数据")
        command_output = gr.Textbox(label="脚本输出", lines=14, interactive=False)

        with gr.Row():
            locust_mode = gr.Radio(
                choices=["headless", "webui"],
                value="headless",
                label="Locust 启动模式",
            )
            start_button = gr.Button("启动 Locust")
            stop_button = gr.Button("停止 Locust")
        locust_status = gr.Textbox(label="Locust 状态 / 输出", lines=14, interactive=False)
        refresh_button = gr.Button("刷新 Locust 输出")

        demo.load(_preview_form_config, inputs=form_inputs, outputs=config_preview)
        load_button.click(_load_form_values, outputs=form_inputs)
        save_button.click(_save_form_config, inputs=form_inputs, outputs=save_status)
        generate_button.click(generate_data, outputs=command_output)
        init_button.click(init_data, outputs=command_output)
        start_button.click(start_locust, inputs=[locust_mode], outputs=locust_status)
        stop_button.click(stop_locust, outputs=locust_status)
        refresh_button.click(poll_locust_output, outputs=locust_status)

    return demo


if __name__ == "__main__":
    build_app().launch(server_name="0.0.0.0", server_port=7860)
