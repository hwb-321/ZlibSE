from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile

from pypdf import PdfReader

from ..core.config import get_settings
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
    cover_name, cover_bytes = _extract_epub_cover(book)

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


def _extract_epub_cover(book) -> tuple[str | None, bytes | None]:
    image_items = []
    for item in book.get_items():
        media_type = str(getattr(item, "media_type", "") or "")
        if media_type.startswith("image/"):
            image_items.append(item)

    if not image_items:
        return None, None

    cover_id = _find_epub_cover_id(book)
    if cover_id:
        matched = _match_epub_image(image_items, cover_id)
        if matched is not None:
            return Path(getattr(matched, "file_name", "cover.jpg")).name, matched.get_content()

    named_cover = _match_named_cover_image(image_items)
    if named_cover is not None:
        return Path(getattr(named_cover, "file_name", "cover.jpg")).name, named_cover.get_content()

    cover_href = _find_epub_cover_href(book)
    if cover_href:
        matched = _match_epub_image(image_items, cover_href)
        if matched is not None:
            return Path(getattr(matched, "file_name", "cover.jpg")).name, matched.get_content()

    largest = max(image_items, key=lambda item: len(item.get_content()), default=None)
    if largest is None:
        return None, None
    return Path(getattr(largest, "file_name", "cover.jpg")).name, largest.get_content()


def _find_epub_cover_id(book) -> str | None:
    for _value, attrs in book.get_metadata("OPF", "meta"):
        if attrs.get("name") == "cover" and attrs.get("content"):
            return str(attrs["content"])
    return None


def _find_epub_cover_href(book) -> str | None:
    for item in book.get_items():
        file_name = str(getattr(item, "file_name", "") or "").lower()
        if file_name.endswith("cover.xhtml") or file_name.endswith("cover.html"):
            text = item.get_content().decode("utf-8", errors="ignore").lower()
            marker = "href=\""
            idx = text.find(marker)
            if idx == -1:
                continue
            href = text[idx + len(marker):].split("\"", 1)[0]
            return Path(href).name
    return None


def _match_epub_image(image_items, target: str):
    normalized = str(target).lower()
    normalized_name = Path(normalized).name
    for item in image_items:
        item_id = str(getattr(item, "id", "") or "").lower()
        item_name = str(getattr(item, "file_name", "") or "").lower()
        if item_id == normalized or Path(item_name).name == normalized_name:
            return item
    return None


def _match_named_cover_image(image_items):
    for item in image_items:
        item_name = str(getattr(item, "file_name", "") or "").lower()
        basename = Path(item_name).stem
        if basename == "cover" or basename.endswith("_cover") or basename.endswith("-cover"):
            return item
    return None


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


def build_server_mock_parse_result(stored_file: StoredFile) -> dict:
    settings = get_settings().benchmark
    stem = Path(stored_file.original_filename).stem or "Mock Book"
    return {
        "title": stem,
        "author": settings.mock_author,
        "language": settings.mock_language,
        "page_count": settings.mock_page_count,
        "raw_metadata": json.dumps(
            {
                "mode": "server-mock",
                "filename": stored_file.original_filename,
                "kind": stored_file.kind,
            },
            ensure_ascii=False,
        ),
        "cover_filename": None,
        "cover_bytes": None,
        "cover_content_type": None,
    }


def parse_file_metadata(stored_file: StoredFile, *, mode: str) -> dict:
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
