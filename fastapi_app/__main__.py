import atexit
import socket
import subprocess
import sys
import time

import uvicorn

from .core.config import get_settings


def _parse_bootstrap_endpoint(bootstrap_servers: str) -> tuple[str, int]:
    first = bootstrap_servers.split(",", 1)[0].strip()
    if not first:
        return "127.0.0.1", 9092
    host, separator, port_text = first.rpartition(":")
    if not separator:
        return first, 9092
    return host or "127.0.0.1", int(port_text)


def _tcp_port_ready(host: str, port: int, *, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _run_start_command(command: str, *, use_sudo: bool, sudo_password: str) -> None:
    if not command.strip():
        raise RuntimeError("Kafka broker auto-start requires async_parse.broker_start_command")

    if use_sudo:
        process = subprocess.Popen(
            ["sudo", "-S", "-p", "", "sh", "-lc", command],
            text=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert process.stdin is not None
        process.stdin.write(sudo_password + "\n")
        process.stdin.flush()
    else:
        process = subprocess.Popen(
            ["sh", "-lc", command],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    try:
        stdout, stderr = process.communicate(timeout=3)
    except subprocess.TimeoutExpired:
        return
    if process.returncode != 0:
        detail = "\n".join(part for part in (stdout.strip(), stderr.strip()) if part)
        raise RuntimeError(
            "Kafka start command failed. "
            "Check async_parse.broker_start_command in config.secret.yaml. "
            f"Command: {command}. Detail: {detail or 'no output'}"
        )


def _ensure_kafka_broker() -> None:
    settings = get_settings().async_parse
    if not settings.enabled or settings.mode == "off" or not settings.broker_auto_start:
        return

    host, port = _parse_bootstrap_endpoint(settings.bootstrap_servers)
    if _tcp_port_ready(host, port):
        return

    if settings.broker_start_requires_sudo and not settings.broker_start_sudo_password:
        raise RuntimeError("Kafka broker auto-start requires async_parse.broker_start_sudo_password")
    _run_start_command(
        settings.broker_start_command,
        use_sudo=settings.broker_start_requires_sudo,
        sudo_password=settings.broker_start_sudo_password,
    )

    deadline = time.monotonic() + settings.broker_start_timeout_seconds
    while time.monotonic() < deadline:
        if _tcp_port_ready(host, port):
            return
        time.sleep(0.5)
    raise RuntimeError(
        "Kafka broker did not become ready. "
        f"Expected {host}:{port}; start command was: {settings.broker_start_command}"
    )


def _start_parse_worker() -> subprocess.Popen | None:
    settings = get_settings()
    if not settings.async_parse.enabled or settings.async_parse.mode == "off":
        return None
    if settings.server.reload:
        # Avoid duplicate worker processes during hot reload development mode.
        return None

    process = subprocess.Popen(
        [sys.executable, "-m", "fastapi_app.workers.parse_worker"],
        stdout=sys.stdout,
        stderr=sys.stderr,
        cwd=None,
    )

    def _cleanup() -> None:
        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

    atexit.register(_cleanup)
    return process


def main() -> None:
    settings = get_settings()
    workers = 1 if settings.server.reload else settings.server.workers
    _ensure_kafka_broker()
    _start_parse_worker()
    uvicorn.run(
        "fastapi_app.main:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=settings.server.reload,
        workers=workers,
        access_log=settings.server.access_log,
    )


if __name__ == "__main__":
    main()
