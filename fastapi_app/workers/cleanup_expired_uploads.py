from __future__ import annotations

from fastapi_app.core.config import get_settings
from fastapi_app.core.database import SessionLocal
from fastapi_app.repositories.upload_task_repository import list_expired_unfinished_tasks
from fastapi_app.services.storage_service import delete_object_by_key


def cleanup_expired_uploads(*, older_than_seconds: int | None = None) -> int:
    settings = get_settings()
    threshold = older_than_seconds or settings.storage.upload_expires
    db = SessionLocal()
    deleted = 0
    try:
        tasks = list_expired_unfinished_tasks(db, older_than_seconds=threshold)
        for task in tasks:
            try:
                delete_object_by_key(task.object_key)
            except Exception:
                continue
            task.status = "deleted"
            task.error_message = "Expired upload task cleaned up"
            db.add(task)
            deleted += 1
        db.commit()
        return deleted
    finally:
        db.close()


if __name__ == "__main__":
    count = cleanup_expired_uploads()
    print(f"cleaned_upload_tasks={count}")
