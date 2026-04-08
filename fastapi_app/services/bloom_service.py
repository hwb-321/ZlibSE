from __future__ import annotations

from functools import lru_cache
import time

from bloom_filter2 import BloomFilter
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..models import Book


@lru_cache(maxsize=1)
def get_book_bloom() -> BloomFilter:
    settings = get_settings().redis
    return BloomFilter(
        max_elements=settings.bloom_expected_items,
        error_rate=settings.bloom_error_rate,
    )


@lru_cache(maxsize=1)
def _get_book_bloom_state() -> dict[str, float | None]:
    return {"trusted_until": None}


def _refresh_trusted_window() -> None:
    ttl_seconds = get_settings().redis.bloom_trusted_ttl_seconds
    _get_book_bloom_state()["trusted_until"] = time.monotonic() + ttl_seconds


def warm_book_bloom(db: Session) -> None:
    bloom = get_book_bloom()
    for (book_id,) in db.query(Book.id).all():
        bloom.add(str(book_id))
    _refresh_trusted_window()


def may_have_book(book_id: int) -> bool:
    return str(book_id) in get_book_bloom()


def should_trust_book_bloom() -> bool:
    trusted_until = _get_book_bloom_state().get("trusted_until")
    return trusted_until is not None and time.monotonic() <= trusted_until


def mark_book_exists(book_id: int) -> None:
    get_book_bloom().add(str(book_id))
    _refresh_trusted_window()
