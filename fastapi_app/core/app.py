from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .config import get_settings
from .paths import MEDIA_DIR, ensure_runtime_dirs
from .schema import init_schema
from ..routers.auth import router as auth_router
from ..routers.books import router as books_router
from ..routers.favorites import router as favorites_router
from ..routers.files import router as files_router
from ..routers.uploads import router as uploads_router


def create_app() -> FastAPI:
    ensure_runtime_dirs()
    settings = get_settings()

    app = FastAPI(title="ZlibSE FastAPI")
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.security.session_secret,
        same_site="lax",
        https_only=False,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    if MEDIA_DIR.exists():
        app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")

    @app.on_event("startup")
    def startup_event() -> None:
        init_schema()

    app.include_router(auth_router)
    app.include_router(books_router)
    app.include_router(favorites_router)
    app.include_router(files_router)
    app.include_router(uploads_router)
    return app
