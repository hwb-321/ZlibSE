from sqlalchemy.orm import Session

from ..models import Book, UploadedBook


def get_upload_relation(db: Session, user_id: int, book_id: int) -> UploadedBook | None:
    return (
        db.query(UploadedBook)
        .filter(UploadedBook.user_id == user_id, UploadedBook.book_id == book_id)
        .first()
    )


def list_uploaded_books(db: Session, user_id: int, is_superuser: bool) -> list[Book]:
    query = db.query(Book).join(UploadedBook, UploadedBook.book_id == Book.id)
    if not is_superuser:
        query = query.filter(UploadedBook.user_id == user_id)
    return query.all()
