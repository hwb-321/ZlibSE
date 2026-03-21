import shutil
import uuid
from pathlib import Path

from fastapi import UploadFile


def save_upload_file(upload: UploadFile, target_dir: Path) -> tuple[str, str]:
    ext = Path(upload.filename or "").suffix or ""
    filename = f"{uuid.uuid4()}{ext}"
    output_path = target_dir / filename
    with output_path.open("wb") as buffer:
        shutil.copyfileobj(upload.file, buffer)
    return filename, str(output_path)
