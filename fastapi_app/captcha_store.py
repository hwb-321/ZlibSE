import io
import secrets
import string
import threading
import time
from typing import Dict, Tuple

from PIL import Image, ImageDraw, ImageFont


class CaptchaStore:
    def __init__(self) -> None:
        self._store: Dict[str, Tuple[str, float]] = {}
        self._lock = threading.Lock()

    def generate(self, ttl_seconds: int = 300) -> tuple[str, str]:
        key = secrets.token_urlsafe(16)
        value = "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(4))
        expires_at = time.time() + ttl_seconds
        with self._lock:
            self._store[key] = (value, expires_at)
        return key, value

    def get(self, key: str) -> str | None:
        with self._lock:
            item = self._store.get(key)
            if not item:
                return None
            value, expires_at = item
            if time.time() > expires_at:
                self._store.pop(key, None)
                return None
            return value

    def validate(self, key: str, answer: str, consume: bool = True) -> bool:
        with self._lock:
            item = self._store.get(key)
            if not item:
                return False
            value, expires_at = item
            if time.time() > expires_at:
                self._store.pop(key, None)
                return False
            ok = value.lower() == (answer or "").lower()
            if consume:
                self._store.pop(key, None)
            return ok


def render_captcha_png(text: str) -> bytes:
    img = Image.new("RGB", (120, 45), color=(245, 247, 250))
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    draw.text((20, 12), text, fill=(40, 40, 40), font=font)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
