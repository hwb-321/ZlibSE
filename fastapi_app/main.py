import os
import shutil
import time
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from .captcha_store import CaptchaStore, render_captcha_png
from .database import Base, engine, get_db
from .models import Book, UploadedBook, User, UserCollectedBook
from .security import hash_password, verify_password

BASE_DIR = Path(__file__).resolve().parent.parent
MEDIA_DIR = BASE_DIR / "media"
BOOKS_DIR = MEDIA_DIR / "books"
COVERS_DIR = MEDIA_DIR / "covers"
STATIC_DIR = BASE_DIR / "static"

for folder in (MEDIA_DIR, BOOKS_DIR, COVERS_DIR):
    folder.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="ZlibSE FastAPI")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "dev-session-secret-change-me"),
    same_site="lax",
    https_only=False,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://192.168.157.177:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if MEDIA_DIR.exists():
    app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

captcha_store = CaptchaStore()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


@app.on_event("startup")
def startup_event() -> None:
    init_db()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = db.get(User, user_id)
    if not user:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def save_upload_file(upload: UploadFile, target_dir: Path) -> tuple[str, str]:
    ext = Path(upload.filename or "").suffix or ""
    filename = f"{uuid.uuid4()}{ext}"
    output_path = target_dir / filename
    with output_path.open("wb") as buffer:
        shutil.copyfileobj(upload.file, buffer)
    return filename, str(output_path)


def book_to_dict(book: Book) -> dict:
    return {
        "id": book.id,
        "title": book.title,
        "author": book.author,
        "isbn": book.isbn,
        "category": book.category,
        "year": book.year,
        "language": book.language,
        "file_type": book.file_type,
        "file_path": f"/media/books/{Path(book.file_path).name}" if book.file_path else "",
        "file_size": book.file_size,
        "cover_image_path": f"/media/covers/{Path(book.cover_image_path).name}" if book.cover_image_path else "",
    }


@app.get("/user/init_csrf")
def init_csrf() -> dict:
    return {"detail": "CSRF cookie set"}


@app.get("/user/generate_captcha")
def generate_captcha() -> dict:
    key, _ = captcha_store.generate()
    return {
        "key": key,
        "image_url": f"/user/captcha/image/{key}",
    }


@app.get("/user/captcha/image/{captcha_key}")
def get_captcha_image(captcha_key: str) -> Response:
    value = captcha_store.get(captcha_key)
    if not value:
        raise HTTPException(status_code=404, detail="Captcha expired")
    png = render_captcha_png(value)
    return Response(content=png, media_type="image/png")


@app.post("/user/register_user")
def register_user(
    username: str = Form(...),
    email: str = Form(""),
    password: str = Form(...),
    captcha_key: str = Form(...),
    captcha_value: str = Form(...),
    db: Session = Depends(get_db),
):
    if not captcha_store.validate(captcha_key, captcha_value, consume=True):
        return JSONResponse({"success": False, "message": "无效的验证码"})

    exists = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if exists:
        return JSONResponse({"success": False, "message": "用户名已存在"})

    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        is_superuser=False,
    )
    db.add(user)
    db.commit()
    return {"success": True, "message": "注册成功"}


@app.post("/user/login_user")
def login_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    captcha_key: str = Form(...),
    captcha_value: str = Form(...),
    db: Session = Depends(get_db),
):
    if not captcha_store.validate(captcha_key, captcha_value, consume=True):
        return JSONResponse({"success": False, "error": "验证码错误"})

    login_attempts = int(request.session.get("login_attempts", 0))
    last_attempt_ts = float(request.session.get("last_attempt_ts", 0.0))
    if login_attempts >= 5 and time.time() < last_attempt_ts + 60:
        return JSONResponse({"success": False, "error": "短期内尝试登陆次数太多，请稍后重试！"})

    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        request.session["login_attempts"] = login_attempts + 1
        request.session["last_attempt_ts"] = time.time()
        return JSONResponse({"success": False, "error": "Invalid credentials"})

    request.session["user_id"] = user.id
    request.session["login_attempts"] = 0
    request.session["last_attempt_ts"] = 0.0
    return {"success": True}


@app.post("/user/logout_user")
def logout_user(request: Request):
    request.session.clear()
    return {"success": True}


@app.get("/user/check_session")
def check_session(request: Request):
    return {"isLoggedIn": bool(request.session.get("user_id"))}


@app.post("/book/upload_book")
def upload_book(
    title: str = Form(...),
    author: str = Form(...),
    isbn: str = Form(...),
    category: str = Form(...),
    year: int = Form(...),
    language: str = Form(...),
    file_path: UploadFile = File(...),
    cover_image_path: UploadFile = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    file_bytes = file_path.file.read()
    file_path.file.seek(0)
    file_size = len(file_bytes)
    if file_size > 1024 * 1024 * 1024:
        return JSONResponse({"success": False, "message": "文件大小不能超过1GB"})

    file_name, saved_file = save_upload_file(file_path, BOOKS_DIR)
    cover_saved = None
    if cover_image_path:
        _, cover_saved = save_upload_file(cover_image_path, COVERS_DIR)

    ext = Path(file_name).suffix.lstrip(".").lower()
    book = Book(
        title=title,
        author=author,
        isbn=isbn,
        category=category,
        year=year,
        language=language,
        file_type=ext,
        file_path=saved_file,
        file_size=round(file_size / (1024 * 1024), 2),
        cover_image_path=cover_saved,
    )
    db.add(book)
    db.flush()

    uploaded = UploadedBook(user_id=current_user.id, book_id=book.id)
    db.add(uploaded)
    db.commit()

    return {"success": True, "message": "上传成功"}


@app.get("/book/count")
def count_book(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ = current_user
    count = db.query(Book).count()
    return {"count": count}


@app.get("/book/list")
def list_book(
    page: int = 1,
    pageSize: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = current_user
    if page < 1 or pageSize < 1:
        raise HTTPException(status_code=400, detail="Invalid page params")

    offset = (page - 1) * pageSize
    books = db.query(Book).order_by(Book.id.desc()).offset(offset).limit(pageSize).all()
    if not books and page != 1:
        return JSONResponse({"error": "页面不存在"}, status_code=404)
    return {"books": [book_to_dict(book) for book in books]}


@app.get("/book/cover/{book_id}")
def book_cover(book_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ = current_user
    book = db.get(Book, book_id)
    if not book or not book.cover_image_path or not os.path.exists(book.cover_image_path):
        raise HTTPException(status_code=404, detail="封面图片不存在")
    return FileResponse(book.cover_image_path)


@app.get("/book/get_descriptions/{book_id}")
def get_descriptions(book_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ = current_user
    book = db.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")
    return {
        "title": book.title,
        "author": book.author,
        "isbn": book.isbn,
        "category": book.category,
        "year": book.year,
        "language": book.language,
        "file_type": book.file_type,
        "file_path": f"/media/books/{Path(book.file_path).name}" if book.file_path else "",
        "file_size": book.file_size,
        "cover_image_path": f"/media/covers/{Path(book.cover_image_path).name}" if book.cover_image_path else "",
    }


@app.get("/book/search")
def book_search(
    query: str = "",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = current_user
    pattern = f"%{query}%"
    books = (
        db.query(Book)
        .filter(
            or_(
                Book.title.ilike(pattern),
                Book.author.ilike(pattern),
                Book.isbn.ilike(pattern),
                Book.category.ilike(pattern),
                Book.language.ilike(pattern),
                Book.file_type.ilike(pattern),
            )
        )
        .all()
    )
    return {"query": query, "books": [book_to_dict(book) for book in books]}


@app.get("/book/download/{book_id}")
@app.get("/book/download/{book_id}.epub")
def download_book(book_id: int, db: Session = Depends(get_db)):
    book = db.get(Book, book_id)
    if not book or not os.path.exists(book.file_path):
        raise HTTPException(status_code=404, detail="书籍不存在")

    ext = Path(book.file_path).suffix.lower()
    media_type = "application/epub+zip" if ext == ".epub" else "application/octet-stream"
    filename = f"{book.title}{ext}"
    return FileResponse(book.file_path, media_type=media_type, filename=filename)


@app.post("/user/add_to_favorites/{book_id}")
def add_to_favorites(
    book_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = db.get(Book, book_id)
    if not book:
        return JSONResponse({"success": False, "message": "书籍不存在"}, status_code=404)

    exists = (
        db.query(UserCollectedBook)
        .filter(UserCollectedBook.user_id == current_user.id, UserCollectedBook.book_id == book_id)
        .first()
    )
    if exists:
        return {"success": False, "message": "已经收藏过这本书"}

    db.add(UserCollectedBook(user_id=current_user.id, book_id=book_id))
    db.commit()
    return {"success": True, "message": "书籍收藏成功"}


@app.post("/user/remove_from_favorites/{book_id}")
def remove_from_favorites(
    book_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    relation = (
        db.query(UserCollectedBook)
        .filter(UserCollectedBook.user_id == current_user.id, UserCollectedBook.book_id == book_id)
        .first()
    )
    if not relation:
        return {"success": False, "message": "书籍未收藏"}

    db.delete(relation)
    db.commit()
    return {"success": True, "message": "已取消收藏"}


@app.get("/user/check_favorite/{book_id}")
def check_favorite(
    book_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    exists = (
        db.query(UserCollectedBook)
        .filter(UserCollectedBook.user_id == current_user.id, UserCollectedBook.book_id == book_id)
        .first()
        is not None
    )
    return {"isFavorited": exists}


@app.get("/user/favorites")
def get_favorites(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(Book)
        .join(UserCollectedBook, UserCollectedBook.book_id == Book.id)
        .filter(UserCollectedBook.user_id == current_user.id)
        .all()
    )
    return {"favorites": [book_to_dict(book) for book in rows]}


@app.get("/user/get_upload_book_list")
def get_upload_book_list(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(Book).join(UploadedBook, UploadedBook.book_id == Book.id)
    if not current_user.is_superuser:
        query = query.filter(UploadedBook.user_id == current_user.id)
    books = query.all()
    return {"uploadedBooks": [book_to_dict(book) for book in books]}


@app.post("/user/delete_uploaded_book/{book_id}")
def delete_uploaded_book(
    book_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = db.get(Book, book_id)
    if not book:
        return JSONResponse({"success": False, "message": "书籍不存在"}, status_code=404)

    if not current_user.is_superuser:
        own_upload = (
            db.query(UploadedBook)
            .filter(UploadedBook.user_id == current_user.id, UploadedBook.book_id == book_id)
            .first()
        )
        if not own_upload:
            return JSONResponse({"success": False, "message": "无权删除此书籍"}, status_code=403)

    if book.file_path and os.path.exists(book.file_path):
        os.remove(book.file_path)
    if book.cover_image_path and os.path.exists(book.cover_image_path):
        os.remove(book.cover_image_path)

    db.query(UserCollectedBook).filter(UserCollectedBook.book_id == book_id).delete()
    db.query(UploadedBook).filter(UploadedBook.book_id == book_id).delete()
    db.delete(book)
    db.commit()
    return {"success": True, "message": "书籍及相关文件已删除"}


@app.post("/user/change_password_user")
def change_password_user(
    current_password: str = Form(...),
    new_password: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(current_password, current_user.password_hash):
        return JSONResponse({"success": False, "message": "当前密码不正确"}, status_code=400)

    current_user.password_hash = hash_password(new_password)
    db.add(current_user)
    db.commit()
    return {"success": True, "message": "密码已更新"}


@app.post("/user/change_uploaded_book/{book_id}")
def change_uploaded_book(
    book_id: int,
    title: str = Form(...),
    author: str = Form(...),
    isbn: str = Form(...),
    category: str = Form(...),
    year: int = Form(...),
    language: str = Form(...),
    file_path: UploadFile = File(None),
    cover_image_path: UploadFile = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = db.get(Book, book_id)
    if not book:
        return JSONResponse({"success": False, "message": "书籍不存在"}, status_code=404)

    if not current_user.is_superuser:
        own_upload = (
            db.query(UploadedBook)
            .filter(UploadedBook.user_id == current_user.id, UploadedBook.book_id == book_id)
            .first()
        )
        if not own_upload:
            return JSONResponse({"success": False, "message": "无权修改此书籍或书籍不存在"}, status_code=403)

    book.title = title
    book.author = author
    book.isbn = isbn
    book.category = category
    book.year = year
    book.language = language

    if file_path:
        if book.file_path and os.path.exists(book.file_path):
            os.remove(book.file_path)
        file_name, saved_file = save_upload_file(file_path, BOOKS_DIR)
        ext = Path(file_name).suffix.lstrip(".").lower()
        size_bytes = os.path.getsize(saved_file)
        book.file_type = ext
        book.file_path = saved_file
        book.file_size = round(size_bytes / (1024 * 1024), 2)

    if cover_image_path:
        if book.cover_image_path and os.path.exists(book.cover_image_path):
            os.remove(book.cover_image_path)
        _, cover_saved = save_upload_file(cover_image_path, COVERS_DIR)
        book.cover_image_path = cover_saved

    db.add(book)
    db.commit()
    return {"success": True, "message": "书籍信息更新成功"}


@app.get("/{full_path:path}")
def serve_spa(full_path: str):
    _ = full_path
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"detail": "FastAPI backend is running"}
