from sqlalchemy.orm import Session

from ..models import Book, UserCollectedBook


def get_favorite_relation(db: Session, user_id: int, book_id: int) -> UserCollectedBook | None:
    return (
        db.query(UserCollectedBook)
        .filter(UserCollectedBook.user_id == user_id, UserCollectedBook.book_id == book_id)
        .first()
    )


def list_favorite_book_ids(db: Session, user_id: int) -> list[int]:
    rows = (
        db.query(UserCollectedBook.book_id)
        .filter(UserCollectedBook.user_id == user_id)
        .all()
    )
    return [book_id for (book_id,) in rows]


def list_favorite_books(db: Session, user_id: int, page: int, page_size: int) -> list[Book]:
    offset = (page - 1) * page_size
    return (
        db.query(Book)
        .join(UserCollectedBook, UserCollectedBook.book_id == Book.id)
        .filter(UserCollectedBook.user_id == user_id)
        .order_by(UserCollectedBook.id.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
