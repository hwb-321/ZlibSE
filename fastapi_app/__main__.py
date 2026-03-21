import uvicorn

from .core.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "fastapi_app.main:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=settings.server.reload,
    )


if __name__ == "__main__":
    main()
