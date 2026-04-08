from sqlalchemy.orm import Session

from ..models import FileParseResult


def get_file_parse_result(db: Session, file_id: int) -> FileParseResult | None:
    return db.query(FileParseResult).filter(FileParseResult.file_id == file_id).first()


def get_or_create_file_parse_result(db: Session, file_id: int, *, parser_mode: str) -> FileParseResult:
    existing = get_file_parse_result(db, file_id)
    if existing:
        return existing
    result = FileParseResult(file_id=file_id, status="pending", parser_mode=parser_mode)
    db.add(result)
    db.flush()
    return result
