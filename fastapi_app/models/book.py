from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base
from .user import User


class StoredFile(Base):
    __tablename__ = "stored_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    bucket: Mapped[str] = mapped_column(String(100))
    region: Mapped[str] = mapped_column(String(50))
    object_key: Mapped[str] = mapped_column(String(500))
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100), default="application/octet-stream")
    size: Mapped[int] = mapped_column(Integer, default=0)
    etag: Mapped[str] = mapped_column(String(100), default="")
    kind: Mapped[str] = mapped_column(String(50))


class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    author: Mapped[str | None] = mapped_column(String(100), nullable=True)
    isbn: Mapped[str | None] = mapped_column(String(20), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    book_file_id: Mapped[int] = mapped_column(ForeignKey("stored_files.id"), index=True)
    cover_file_id: Mapped[int | None] = mapped_column(ForeignKey("stored_files.id"), nullable=True)

    book_file: Mapped[StoredFile] = relationship(foreign_keys=[book_file_id])
    cover_file: Mapped[StoredFile | None] = relationship(foreign_keys=[cover_file_id])


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
