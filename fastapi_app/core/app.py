import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import SessionLocal
from ..routers.auth import router as auth_router
from ..routers.books import router as books_router
from ..routers.favorites import router as favorites_router
from ..routers.files import router as files_router
from ..routers.uploads import router as uploads_router
from ..services.metrics_service import read_all_metrics, record_request_metric, reset_all_metrics
from ..services.bloom_service import warm_book_bloom
from ..services.storage_service import prewarm_storage_client


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

    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            route = request.scope.get("route")
            route_path = getattr(route, "path", request.url.path)
            duration_ms = (time.perf_counter() - start) * 1000.0
            record_request_metric(
                method=request.method,
                route=route_path,
                status_code=status_code,
                duration_ms=duration_ms,
            )

    @app.on_event("startup")
    def startup_event() -> None:
        db = SessionLocal()
        try:
            warm_book_bloom(db)
        finally:
            db.close()
        try:
            prewarm_storage_client()
        except Exception:
            pass

    @app.get("/ping", tags=["health"])
    async def ping() -> dict[str, str]:
        return {"msg": "hello world"}

    @app.get("/debug/metrics", tags=["debug"])
    async def debug_metrics():
        if not settings.debug_metrics.enabled:
            raise HTTPException(status_code=404, detail="Debug metrics disabled")
        return JSONResponse(read_all_metrics())

    @app.delete("/debug/metrics", tags=["debug"])
    async def reset_debug_metrics():
        if not settings.debug_metrics.enabled:
            raise HTTPException(status_code=404, detail="Debug metrics disabled")
        reset_all_metrics()
        return {"success": True}

    app.include_router(auth_router)
    app.include_router(books_router)
    app.include_router(favorites_router)
    app.include_router(files_router)
    app.include_router(uploads_router)
    return app
