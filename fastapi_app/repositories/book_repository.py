from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models import Book


def count_books(db: Session) -> int:
    return db.query(Book).count()


def list_books(db: Session, page: int, page_size: int) -> list[Book]:
    offset = (page - 1) * page_size
    return db.query(Book).order_by(Book.id.desc()).offset(offset).limit(page_size).all()


def list_books_by_cursor(db: Session, last_id: int | None, page_size: int) -> list[Book]:
    query = db.query(Book)
    if last_id is not None:
        query = query.filter(Book.id < last_id)
    return query.order_by(Book.id.desc()).limit(page_size).all()


def get_book(db: Session, book_id: int) -> Book | None:
    return db.get(Book, book_id)


def search_books(db: Session, query: str, page: int, page_size: int) -> list[Book]:
    pattern = f"%{query}%"
    offset = (page - 1) * page_size
    return (
        db.query(Book)
        .filter(
            or_(
                Book.title.ilike(pattern),
                Book.author.ilike(pattern),
                Book.isbn.ilike(pattern),
                Book.category.ilike(pattern),
                Book.language.ilike(pattern),
            )
        )
        .order_by(Book.id.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
