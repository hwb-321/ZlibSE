from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile

from pypdf import PdfReader

from ..models import StoredFile
from .storage_service import download_object_bytes


def _parse_epub_bytes(payload: bytes) -> dict:
    from ebooklib import epub

    with NamedTemporaryFile(suffix=".epub") as tmp:
        tmp.write(payload)
        tmp.flush()
        book = epub.read_epub(tmp.name)

    title = _first_or_none(book.get_metadata("DC", "title"))
    author = _first_or_none(book.get_metadata("DC", "creator"))
    language = _first_or_none(book.get_metadata("DC", "language"))
    cover_name = None
    cover_bytes = None

    for item in book.get_items():
        if getattr(item, "media_type", "") and str(item.media_type).startswith("image/"):
            cover_name = Path(getattr(item, "file_name", "cover.jpg")).name
            cover_bytes = item.get_content()
            break

    return {
        "title": _metadata_text(title),
        "author": _metadata_text(author),
        "language": _metadata_text(language),
        "page_count": None,
        "raw_metadata": json.dumps(
            {
                "title": title,
                "author": author,
                "language": language,
            },
            ensure_ascii=False,
        ),
        "cover_filename": cover_name,
        "cover_bytes": cover_bytes,
        "cover_content_type": _guess_image_type(cover_name),
    }


def _parse_pdf_bytes(payload: bytes) -> dict:
    reader = PdfReader(BytesIO(payload))
    metadata = reader.metadata or {}
    title = getattr(metadata, "title", None) or metadata.get("/Title")
    author = getattr(metadata, "author", None) or metadata.get("/Author")
    page_count = len(reader.pages)

    cover_bytes = None
    cover_name = "cover.png"
    try:
        import fitz

        document = fitz.open(stream=payload, filetype="pdf")
        page = document.load_page(0)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
        cover_bytes = pixmap.tobytes("png")
    except Exception:
        cover_bytes = None

    return {
        "title": title,
        "author": author,
        "language": None,
        "page_count": page_count,
        "raw_metadata": json.dumps(
            {
                "title": title,
                "author": author,
                "page_count": page_count,
            },
            ensure_ascii=False,
        ),
        "cover_filename": cover_name if cover_bytes else None,
        "cover_bytes": cover_bytes,
        "cover_content_type": "image/png" if cover_bytes else None,
    }


def _build_mock_result(stored_file: StoredFile) -> dict:
    stem = Path(stored_file.original_filename).stem
    return {
        "title": stem,
        "author": "Mock Parser",
        "language": "zh-CN",
        "page_count": 0,
        "raw_metadata": json.dumps(
            {
                "filename": stored_file.original_filename,
                "mode": "mock",
            },
            ensure_ascii=False,
        ),
        "cover_filename": None,
        "cover_bytes": None,
        "cover_content_type": None,
    }


def parse_file_metadata(stored_file: StoredFile, *, mode: str) -> dict:
    if mode == "mock":
        return _build_mock_result(stored_file)
    if mode == "off":
        raise ValueError("Parser mode is disabled")

    payload = download_object_bytes(stored_file)
    suffix = Path(stored_file.original_filename).suffix.lower()
    if suffix == ".epub":
        return _parse_epub_bytes(payload)
    if suffix == ".pdf":
        return _parse_pdf_bytes(payload)
    raise ValueError(f"Unsupported parse format: {suffix}")


def _first_or_none(values):
    if not values:
        return None
    return values[0]


def _metadata_text(value):
    if value is None:
        return None
    if isinstance(value, tuple):
        return str(value[0])
    return str(value)


def _guess_image_type(filename: str | None) -> str | None:
    if not filename:
        return None
    suffix = Path(filename).suffix.lower()
    if suffix in {".png"}:
        return "image/png"
    if suffix in {".jpeg", ".jpg"}:
        return "image/jpeg"
    if suffix in {".webp"}:
        return "image/webp"
    return "application/octet-stream"
