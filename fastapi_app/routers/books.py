import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.database import get_db
from ..core.deps import get_current_user
from ..models import UploadedBook, User
from ..repositories.book_repository import (
    count_books,
    get_book,
    list_books,
    list_books_by_cursor,
    search_books,
)
from ..services.book_service import (
    book_to_summary,
    build_book_detail,
    create_book_from_file_ids,
)
from ..services.cache_service import (
    build_book_count_cache_key,
    build_book_detail_cache_key,
    build_book_list_cache_key,
    bump_book_cache_version,
    delete_cached_public_file_meta,
    get_book_cache_version,
)
from ..services.bloom_service import mark_book_exists, may_have_book, should_trust_book_bloom
from ..services.hybrid_cache_service import EMPTY_MARKER, get_cached, set_cached, set_empty
from ..services.lock_service import acquire_lock, build_lock_value, release_lock
from ..services.metrics_service import record_timing_metric
from ..services.rate_limit_service import is_allowed

router = APIRouter(tags=["books"])
DETAIL_REBUILD_WAIT_SECONDS = 0.05
DETAIL_REBUILD_MAX_RETRIES = 3


class BookUpsertRequest(BaseModel):
    storedFileId: int
    title: str | None = None
    author: str | None = None
    isbn: str | None = None
    category: str | None = None
    year: int | None = None
    language: str | None = None
    coverFileId: int | None = None


@router.post("/api/books")
def create_book(
    payload: BookUpsertRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        book = create_book_from_file_ids(
            db=db,
            current_user=current_user,
            title=payload.title,
            author=payload.author,
            isbn=payload.isbn,
            category=payload.category,
            year=payload.year,
            language=payload.language,
            book_file_id=payload.storedFileId,
            cover_file_id=payload.coverFileId,
        )
    except ValueError as exc:
        db.rollback()
        return JSONResponse({"success": False, "message": str(exc)}, status_code=400)

    db.add(book)
    db.flush()
    db.add(UploadedBook(user_id=current_user.id, book_id=book.id))
    db.commit()
    db.refresh(book)
    bump_book_cache_version()
    mark_book_exists(book.id)
    delete_cached_public_file_meta(book.book_file_id)
    delete_cached_public_file_meta(book.cover_file_id)
    return {"success": True, "book": book_to_summary(book)}


@router.get("/api/books/count")
def get_book_count(db: Session = Depends(get_db)):
    settings = get_settings()
    route_start = time.perf_counter()
    cache_start = time.perf_counter()
    cache_key = build_book_count_cache_key()
    cached = get_cached(cache_key, local_ttl_seconds=settings.local_cache.default_ttl_seconds)
    if cached is not None:
        record_timing_metric("books_count.cache_path_ms", (time.perf_counter() - cache_start) * 1000.0)
        build_start = time.perf_counter()
        response = JSONResponse(cached)
        record_timing_metric("books_count.response_build_ms", (time.perf_counter() - build_start) * 1000.0)
        record_timing_metric("books_count.route_ms", (time.perf_counter() - route_start) * 1000.0)
        return response

    result = {"count": count_books(db)}
    set_cached(
        cache_key,
        result,
        redis_ttl_seconds=settings.redis.book_list_ttl_seconds,
        local_ttl_seconds=settings.local_cache.default_ttl_seconds,
    )
    record_timing_metric("books_count.cache_path_ms", (time.perf_counter() - cache_start) * 1000.0)
    build_start = time.perf_counter()
    response = JSONResponse(result)
    record_timing_metric("books_count.response_build_ms", (time.perf_counter() - build_start) * 1000.0)
    record_timing_metric("books_count.route_ms", (time.perf_counter() - route_start) * 1000.0)
    return response


@router.get("/api/books")
def list_books_page(
    lastId: int | None = None,
    page: int = 1,
    pageSize: int | None = None,
    db: Session = Depends(get_db),
):
    settings = get_settings()
    route_start = time.perf_counter()
    effective_page_size = pageSize or settings.pagination.default_page_size
    if effective_page_size < 1 or effective_page_size > settings.pagination.max_page_size:
        raise HTTPException(status_code=400, detail="Invalid page params")
    if lastId is None and page < 1:
        raise HTTPException(status_code=400, detail="Invalid page params")

    if lastId is not None:
        version = get_book_cache_version()
        cache_key = ("books", "list", f"v{version}", f"cursor={lastId}", f"size={effective_page_size}")
    else:
        cache_key = build_book_list_cache_key(page, effective_page_size)
    cache_start = time.perf_counter()
    cached = get_cached(cache_key, local_ttl_seconds=settings.local_cache.default_ttl_seconds)
    if cached is not None:
        record_timing_metric("books_list.cache_path_ms", (time.perf_counter() - cache_start) * 1000.0)
        build_start = time.perf_counter()
        response = JSONResponse(cached)
        record_timing_metric("books_list.response_build_ms", (time.perf_counter() - build_start) * 1000.0)
        record_timing_metric("books_list.route_ms", (time.perf_counter() - route_start) * 1000.0)
        record_timing_metric("books_list.response_bytes", len(response.body or b""))
        return response

    if lastId is not None:
        books = list_books_by_cursor(db, lastId, effective_page_size)
    else:
        books = list_books(db, page, effective_page_size)
        if not books and page != 1:
            return JSONResponse({"error": "页面不存在"}, status_code=404)

    next_last_id = books[-1].id if books else None
    result = {
        "page": page,
        "pageSize": effective_page_size,
        "lastId": lastId,
        "nextLastId": next_last_id,
        "books": [book_to_summary(book) for book in books],
    }
    set_cached(
        cache_key,
        result,
        redis_ttl_seconds=settings.redis.book_list_ttl_seconds,
        local_ttl_seconds=settings.local_cache.default_ttl_seconds,
    )
    record_timing_metric("books_list.cache_path_ms", (time.perf_counter() - cache_start) * 1000.0)
    build_start = time.perf_counter()
    response = JSONResponse(result)
    record_timing_metric("books_list.response_build_ms", (time.perf_counter() - build_start) * 1000.0)
    record_timing_metric("books_list.route_ms", (time.perf_counter() - route_start) * 1000.0)
    record_timing_metric("books_list.response_bytes", len(response.body or b""))
    return response


@router.get("/api/books/search")
def book_search(
    request: Request,
    query: str = "",
    page: int = 1,
    pageSize: int | None = None,
    db: Session = Depends(get_db),
):
    settings = get_settings()
    normalized_query = query.strip()
    effective_page_size = pageSize or settings.search.default_page_size
    if page < 1 or effective_page_size < 1 or effective_page_size > settings.search.max_page_size:
        raise HTTPException(status_code=400, detail="Invalid page params")
    if len(normalized_query) < settings.search.min_query_length:
        return {
            "query": normalized_query,
            "page": page,
            "pageSize": effective_page_size,
            "books": [],
        }
    if settings.search.rate_limit_enabled:
        client_host = getattr(request.client, "host", None) or "unknown"
        if not is_allowed(
            scope="books_search",
            identifier=client_host,
            max_requests=settings.search.rate_limit_max_requests,
            window_seconds=settings.search.rate_limit_window_seconds,
        ):
            raise HTTPException(status_code=429, detail="Search requests are too frequent")

    books = search_books(db, normalized_query, page, effective_page_size)
    return {
        "query": normalized_query,
        "page": page,
        "pageSize": effective_page_size,
        "books": [book_to_summary(book) for book in books],
    }


@router.get("/api/books/{book_id}")
def get_book_detail(book_id: int, db: Session = Depends(get_db)):
    settings = get_settings()
    if should_trust_book_bloom() and not may_have_book(book_id):
        raise HTTPException(status_code=404, detail="书籍不存在")

    cache_key = build_book_detail_cache_key(book_id)
    cached = get_cached(cache_key, local_ttl_seconds=settings.local_cache.default_ttl_seconds)
    if cached is not None:
        if cached == EMPTY_MARKER:
            raise HTTPException(status_code=404, detail="书籍不存在")
        return cached

    lock_key = f"{settings.redis.prefix}:books:detail:rebuild:{book_id}"
    lock_value = build_lock_value()
    if acquire_lock(lock_key, lock_value, ttl_seconds=settings.redis.lock_ttl_seconds):
        try:
            cached = get_cached(cache_key, local_ttl_seconds=settings.local_cache.default_ttl_seconds)
            if cached is not None:
                if cached == EMPTY_MARKER:
                    raise HTTPException(status_code=404, detail="书籍不存在")
                return cached

            book = get_book(db, book_id)
            if not book:
                set_empty(cache_key, local_ttl_seconds=settings.local_cache.empty_ttl_seconds)
                raise HTTPException(status_code=404, detail="书籍不存在")
            result = build_book_detail(book)
            set_cached(
                cache_key,
                result,
                redis_ttl_seconds=settings.redis.book_detail_ttl_seconds,
                local_ttl_seconds=settings.local_cache.default_ttl_seconds,
            )
            return result
        finally:
            release_lock(lock_key, lock_value)

    for _ in range(DETAIL_REBUILD_MAX_RETRIES):
        time.sleep(DETAIL_REBUILD_WAIT_SECONDS)
        cached = get_cached(cache_key, local_ttl_seconds=settings.local_cache.default_ttl_seconds)
        if cached is None:
            continue
        if cached == EMPTY_MARKER:
            raise HTTPException(status_code=404, detail="书籍不存在")
        return cached

    book = get_book(db, book_id)
    if not book:
        set_empty(cache_key, local_ttl_seconds=settings.local_cache.empty_ttl_seconds)
        raise HTTPException(status_code=404, detail="书籍不存在")
    result = build_book_detail(book)
    set_cached(
        cache_key,
        result,
        redis_ttl_seconds=settings.redis.book_detail_ttl_seconds,
        local_ttl_seconds=settings.local_cache.default_ttl_seconds,
    )
    return result
