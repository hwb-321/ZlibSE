import uvicorn

from .core.config import get_settings


def main() -> None:
    settings = get_settings()
    workers = 1 if settings.server.reload else settings.server.workers
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
