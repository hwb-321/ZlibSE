from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import SessionLocal
from ..routers.auth import router as auth_router
from ..routers.books import router as books_router
from ..routers.favorites import router as favorites_router
from ..routers.files import router as files_router
from ..routers.uploads import router as uploads_router
from ..services.bloom_service import warm_book_bloom


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title="ZlibSE FastAPI")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def startup_event() -> None:
        db = SessionLocal()
        try:
            warm_book_bloom(db)
        finally:
            db.close()

    @app.get("/ping", tags=["health"])
    async def ping() -> dict[str, str]:
        return {"msg": "hello world"}

    app.include_router(auth_router)
    app.include_router(books_router)
    app.include_router(favorites_router)
    app.include_router(files_router)
    app.include_router(uploads_router)
    return app
