from ..core.config import get_settings
from ..captcha_store import CaptchaStore, render_captcha_png

captcha_store = CaptchaStore()


def is_captcha_enabled() -> bool:
    return get_settings().security.captcha_enabled


def generate_captcha_payload() -> dict:
    if not is_captcha_enabled():
        return {
            "captchaEnabled": False,
            "key": None,
            "image_url": None,
        }

    key, _ = captcha_store.generate()
    return {
        "captchaEnabled": True,
        "key": key,
        "image_url": f"/api/auth/captcha/{key}/image",
    }


def render_captcha_image(captcha_key: str) -> bytes | None:
    if not is_captcha_enabled():
        return None
    value = captcha_store.get(captcha_key)
    if not value:
        return None
    return render_captcha_png(value)


def validate_captcha(captcha_key: str, captcha_value: str, consume: bool = True) -> bool:
    if not is_captcha_enabled():
        return True
    return captcha_store.validate(captcha_key, captcha_value, consume=consume)
