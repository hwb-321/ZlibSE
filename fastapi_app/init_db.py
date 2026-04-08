from .core.database import SessionLocal
from .core.schema import init_schema
from .services.bloom_service import warm_book_bloom


def main() -> None:
    init_schema()
    db = SessionLocal()
    try:
        warm_book_bloom(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
