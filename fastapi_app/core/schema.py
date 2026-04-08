from __future__ import annotations

from sqlalchemy import inspect, text

from .database import Base, engine
from .. import models  # noqa: F401


def _add_column_if_missing(table_name: str, column_name: str, ddl: str) -> None:
    inspector = inspect(engine)
    existing = {column["name"] for column in inspector.get_columns(table_name)}
    if column_name in existing:
        return
    with engine.begin() as connection:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}"))


def _drop_unique_if_exists(table_name: str, constraint_name: str) -> None:
    inspector = inspect(engine)
    unique_constraints = {item["name"] for item in inspector.get_unique_constraints(table_name) if item.get("name")}
    if constraint_name not in unique_constraints:
        return
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "mysql":
            connection.execute(text(f"ALTER TABLE {table_name} DROP INDEX {constraint_name}"))


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


def _backfill_stored_file_ref_counts() -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    required_tables = {"stored_files", "books"}
    if not required_tables.issubset(table_names):
        return

    stored_file_columns = {column["name"] for column in inspector.get_columns("stored_files")}
    if "ref_count" not in stored_file_columns:
        return

    with engine.begin() as connection:
        connection.execute(text("UPDATE stored_files SET ref_count = 0"))
        connection.execute(
            text(
                """
                UPDATE stored_files
                SET ref_count = (
                    SELECT COUNT(*)
                    FROM books
                    WHERE books.book_file_id = stored_files.id OR books.cover_file_id = stored_files.id
                )
                """
            )
        )


def init_schema() -> None:
    Base.metadata.create_all(bind=engine)
    if "users" in inspect(engine).get_table_names():
        _add_column_if_missing("users", "auth_token_version", "INTEGER NOT NULL DEFAULT 0")
        user_columns = {column["name"] for column in inspect(engine).get_columns("users")}
        if "token_version" in user_columns and "auth_token_version" in user_columns:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        UPDATE users
                        SET auth_token_version = token_version
                        WHERE auth_token_version = 0
                        """
                    )
                )
    if "stored_files" in inspect(engine).get_table_names():
        _drop_unique_if_exists("stored_files", "uq_stored_files_user_kind_hash")
        _add_column_if_missing("stored_files", "user_id", "INTEGER")
        _add_column_if_missing("stored_files", "file_hash", "VARCHAR(128)")
        _add_column_if_missing("stored_files", "ref_count", "INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing("stored_files", "upload_url", "TEXT")
        _add_column_if_missing("stored_files", "upload_status", "VARCHAR(50) NOT NULL DEFAULT 'init'")
        _add_column_if_missing("stored_files", "parse_status", "VARCHAR(50) NOT NULL DEFAULT 'not_started'")
        _add_column_if_missing("stored_files", "bind_status", "VARCHAR(50) NOT NULL DEFAULT 'unbound'")
        _add_column_if_missing("stored_files", "upload_expires_at", "DATETIME")
    if "books" in inspect(engine).get_table_names():
        _add_column_if_missing("books", "book_file_id", "INTEGER")
        _add_column_if_missing("books", "cover_file_id", "INTEGER")
    Base.metadata.create_all(bind=engine)
    _backfill_stored_file_owners()
    _backfill_stored_file_ref_counts()
