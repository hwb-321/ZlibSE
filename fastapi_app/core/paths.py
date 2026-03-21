from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MEDIA_DIR = BASE_DIR / "media"
BOOKS_DIR = MEDIA_DIR / "books"
COVERS_DIR = MEDIA_DIR / "covers"
STATIC_DIR = BASE_DIR / "static"


def ensure_runtime_dirs() -> None:
    for folder in (MEDIA_DIR, BOOKS_DIR, COVERS_DIR):
        folder.mkdir(parents=True, exist_ok=True)
