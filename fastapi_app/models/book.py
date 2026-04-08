from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base
from .user import User


class StoredFile(Base):
    __tablename__ = "stored_files"
    __table_args__ = (UniqueConstraint("object_key", name="uq_stored_files_object_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    bucket: Mapped[str] = mapped_column(String(100), default="")
    region: Mapped[str] = mapped_column(String(50), default="")
    object_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100), default="application/octet-stream")
    size: Mapped[int] = mapped_column(Integer, default=0)
    etag: Mapped[str] = mapped_column(String(100), default="")
    kind: Mapped[str] = mapped_column(String(50))
    file_hash: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    ref_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    upload_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    upload_status: Mapped[str] = mapped_column(String(50), default="init", nullable=False, index=True)
    parse_status: Mapped[str] = mapped_column(String(50), default="not_started", nullable=False, index=True)
    bind_status: Mapped[str] = mapped_column(String(50), default="unbound", nullable=False, index=True)
    upload_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User | None] = relationship()


class FileParseResult(Base):
    __tablename__ = "file_parse_results"
    __table_args__ = (UniqueConstraint("file_id", name="uq_file_parse_result_file_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("stored_files.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    parser_mode: Mapped[str] = mapped_column(String(20), default="off")
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cover_file_id: Mapped[int | None] = mapped_column(ForeignKey("stored_files.id", ondelete="SET NULL"), nullable=True)
    raw_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    file: Mapped[StoredFile] = relationship(foreign_keys=[file_id])
    cover_file: Mapped[StoredFile | None] = relationship(foreign_keys=[cover_file_id])


class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    author: Mapped[str | None] = mapped_column(String(100), nullable=True)
    isbn: Mapped[str | None] = mapped_column(String(50), nullable=True)
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
