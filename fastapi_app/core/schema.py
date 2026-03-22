from __future__ import annotations

import mimetypes
from pathlib import Path

from sqlalchemy import inspect, text

from .database import Base, engine
from .. import models  # noqa: F401


LEGACY_LOCAL_BUCKET = "legacy-local"
LEGACY_LOCAL_REGION = "local"


def _guess_content_type(filename: str, fallback: str = "application/octet-stream") -> str:
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or fallback


def _add_column_if_missing(table_name: str, column_name: str, ddl: str) -> None:
    inspector = inspect(engine)
    existing = {column["name"] for column in inspector.get_columns(table_name)}
    if column_name in existing:
        return
    with engine.begin() as connection:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}"))


def _insert_legacy_file(connection, *, object_key: str, original_filename: str, content_type: str, size: int, kind: str) -> int:
    connection.execute(
        text(
            """
            INSERT INTO stored_files (
                bucket, region, object_key, original_filename, content_type, size, etag, kind
            ) VALUES (
                :bucket, :region, :object_key, :original_filename, :content_type, :size, :etag, :kind
            )
            """
        ),
        {
            "bucket": LEGACY_LOCAL_BUCKET,
            "region": LEGACY_LOCAL_REGION,
            "object_key": object_key,
            "original_filename": original_filename,
            "content_type": content_type,
            "size": size,
            "etag": "",
            "kind": kind,
        },
    )
    return connection.execute(text("SELECT last_insert_rowid()")).scalar_one()


def _backfill_legacy_local_files() -> None:
    inspector = inspect(engine)
    if "books" not in inspector.get_table_names() or "stored_files" not in inspector.get_table_names():
        return

    book_columns = {column["name"] for column in inspector.get_columns("books")}
    required_old_columns = {"file_path", "file_size", "cover_image_path", "file_type", "book_file_id", "cover_file_id"}
    if not required_old_columns.issubset(book_columns):
        return

    with engine.begin() as connection:
        rows = connection.execute(
            text(
                """
                SELECT id, file_type, file_path, file_size, cover_image_path, book_file_id, cover_file_id
                FROM books
                """
            )
        ).mappings()

        for row in rows:
            updates: dict[str, int] = {}

            if row["file_path"] and row["book_file_id"] is None:
                size_bytes = int(float(row["file_size"] or 0) * 1024 * 1024)
                file_id = _insert_legacy_file(
                    connection,
                    object_key=row["file_path"],
                    original_filename=Path(row["file_path"]).name,
                    content_type=_guess_content_type(row["file_path"]),
                    size=size_bytes,
                    kind="book",
                )
                updates["book_file_id"] = file_id

            if row["cover_image_path"] and row["cover_file_id"] is None:
                cover_id = _insert_legacy_file(
                    connection,
                    object_key=row["cover_image_path"],
                    original_filename=Path(row["cover_image_path"]).name,
                    content_type=_guess_content_type(row["cover_image_path"], "image/jpeg"),
                    size=0,
                    kind="cover",
                )
                updates["cover_file_id"] = cover_id

            if updates:
                set_clause = ", ".join(f"{column} = :{column}" for column in updates)
                connection.execute(
                    text(f"UPDATE books SET {set_clause} WHERE id = :book_id"),
                    {**updates, "book_id": row["id"]},
                )


def _backfill_stored_file_owners() -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    required_tables = {"stored_files", "books", "uploaded_books"}
    if not required_tables.issubset(table_names):
        return

    stored_file_columns = {column["name"] for column in inspector.get_columns("stored_files")}
    if "user_id" not in stored_file_columns:
        return

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                UPDATE stored_files
                SET user_id = (
                    SELECT uploaded_books.user_id
                    FROM books
                    JOIN uploaded_books ON uploaded_books.book_id = books.id
                    WHERE books.book_file_id = stored_files.id OR books.cover_file_id = stored_files.id
                    ORDER BY uploaded_books.id ASC
                    LIMIT 1
                )
                WHERE user_id IS NULL
                """
            )
        )


def init_schema() -> None:
    Base.metadata.create_all(bind=engine)
    if "users" in inspect(engine).get_table_names():
        _add_column_if_missing("users", "token_version", "INTEGER NOT NULL DEFAULT 0")
    if "stored_files" in inspect(engine).get_table_names():
        _add_column_if_missing("stored_files", "user_id", "INTEGER")
    if "books" in inspect(engine).get_table_names():
        _add_column_if_missing("books", "book_file_id", "INTEGER")
        _add_column_if_missing("books", "cover_file_id", "INTEGER")
    Base.metadata.create_all(bind=engine)
    _backfill_legacy_local_files()
    _backfill_stored_file_owners()
