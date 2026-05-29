from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import get_settings
from ..services.metrics_service import increment_counter, record_timing_metric


settings = get_settings()
DATABASE_URL = settings.database.url
DB_PATH = None
if DATABASE_URL.startswith("sqlite:///"):
    DB_PATH = Path(DATABASE_URL.removeprefix("sqlite:///"))


def _build_async_database_url(url: str) -> str:
    if url.startswith("mysql+pymysql://"):
        return url.replace("mysql+pymysql://", "mysql+asyncmy://", 1)
    if url.startswith("mysql://"):
        return url.replace("mysql://", "mysql+asyncmy://", 1)
    if url.startswith("mysql+asyncmy://"):
        return url
    raise ValueError("Async download path only supports MySQL database URLs")

engine_kwargs = {
    "pool_pre_ping": True,
    "pool_size": settings.database.pool_size,
    "max_overflow": settings.database.max_overflow,
    "pool_recycle": settings.database.pool_recycle_seconds,
    "pool_timeout": settings.database.pool_timeout_seconds,
}
if DATABASE_URL.startswith("sqlite:///"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
    engine_kwargs.pop("pool_size", None)
    engine_kwargs.pop("max_overflow", None)
    engine_kwargs.pop("pool_recycle", None)
    engine_kwargs.pop("pool_timeout", None)

engine = create_engine(
    DATABASE_URL,
    **engine_kwargs,
)

ASYNC_DATABASE_URL = _build_async_database_url(DATABASE_URL)
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=settings.database.pool_size,
    max_overflow=settings.database.max_overflow,
    pool_recycle=settings.database.pool_recycle_seconds,
    pool_timeout=settings.database.pool_timeout_seconds,
)


@event.listens_for(engine, "before_cursor_execute")
def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
    conn.info.setdefault("_query_start_time", []).append(__import__("time").perf_counter())


@event.listens_for(engine, "after_cursor_execute")
def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
    start_stack = conn.info.get("_query_start_time") or []
    if not start_stack:
        return
    start_time = start_stack.pop()
    duration_ms = (__import__("time").perf_counter() - start_time) * 1000.0
    increment_counter("sql.query.count")
    record_timing_metric("sql.query_ms", duration_ms)
    if duration_ms >= settings.debug_metrics.slow_sql_threshold_ms:
        increment_counter("sql.slow.count")
        record_timing_metric("sql.slow_ms", duration_ms)


@event.listens_for(async_engine.sync_engine, "before_cursor_execute")
def _async_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
    conn.info.setdefault("_query_start_time", []).append(__import__("time").perf_counter())


@event.listens_for(async_engine.sync_engine, "after_cursor_execute")
def _async_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
    start_stack = conn.info.get("_query_start_time") or []
    if not start_stack:
        return
    start_time = start_stack.pop()
    duration_ms = (__import__("time").perf_counter() - start_time) * 1000.0
    increment_counter("sql.query.count")
    record_timing_metric("sql.query_ms", duration_ms)
    if duration_ms >= settings.debug_metrics.slow_sql_threshold_ms:
        increment_counter("sql.slow.count")
        record_timing_metric("sql.slow_ms", duration_ms)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False, autoflush=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db():
    async with AsyncSessionLocal() as db:
        yield db
