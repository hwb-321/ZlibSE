from sqlalchemy.orm import Session

from ..models import Book, UserCollectedBook


def get_favorite_relation(db: Session, user_id: int, book_id: int) -> UserCollectedBook | None:
    return (
        db.query(UserCollectedBook)
        .filter(UserCollectedBook.user_id == user_id, UserCollectedBook.book_id == book_id)
        .first()
    )


def list_favorite_books(db: Session, user_id: int) -> list[Book]:
    return (
        db.query(Book)
        .join(UserCollectedBook, UserCollectedBook.book_id == Book.id)
        .filter(UserCollectedBook.user_id == user_id)
        .all()
    )
