from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base
from .user import User


class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    author: Mapped[str] = mapped_column(String(100))
    isbn: Mapped[str] = mapped_column(String(20))
    category: Mapped[str] = mapped_column(String(100))
    year: Mapped[int] = mapped_column(Integer)
    language: Mapped[str] = mapped_column(String(50))
    file_type: Mapped[str] = mapped_column(String(50))
    file_path: Mapped[str] = mapped_column(String(500))
    file_size: Mapped[float] = mapped_column(Float)
    cover_image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)


class UserCollectedBook(Base):
    __tablename__ = "user_collected_books"
    __table_args__ = (UniqueConstraint("user_id", "book_id", name="uq_user_book_collect"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), index=True)

    user: Mapped[User] = relationship()
    book: Mapped[Book] = relationship()


class UploadedBook(Base):
    __tablename__ = "uploaded_books"
    __table_args__ = (UniqueConstraint("user_id", "book_id", name="uq_user_book_upload"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), index=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship()
    book: Mapped[Book] = relationship()
