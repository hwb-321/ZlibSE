import atexit
import subprocess
import sys

import uvicorn

from .core.config import get_settings


def _start_parse_worker() -> subprocess.Popen | None:
    settings = get_settings()
    if not settings.async_parse.enabled or settings.async_parse.mode == "off":
        return None
    if settings.async_parse.broker != "rabbitmq":
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
