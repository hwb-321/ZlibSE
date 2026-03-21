from fastapi import APIRouter
from fastapi.responses import FileResponse

from ..core.paths import STATIC_DIR

router = APIRouter(tags=["spa"])


@router.get("/{full_path:path}")
def serve_spa(full_path: str):
    _ = full_path
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"detail": "FastAPI backend is running"}
