from __future__ import annotations

from functools import lru_cache

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


def warm_book_bloom(db: Session) -> None:
    bloom = get_book_bloom()
    for (book_id,) in db.query(Book.id).all():
        bloom.add(str(book_id))


def may_have_book(book_id: int) -> bool:
    return str(book_id) in get_book_bloom()


def mark_book_exists(book_id: int) -> None:
    get_book_bloom().add(str(book_id))
