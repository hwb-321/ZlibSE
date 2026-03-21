from ..captcha_store import CaptchaStore, render_captcha_png

captcha_store = CaptchaStore()


def generate_captcha_payload() -> dict:
    key, _ = captcha_store.generate()
    return {
        "key": key,
        "image_url": f"/user/captcha/image/{key}",
    }


def render_captcha_image(captcha_key: str) -> bytes | None:
    value = captcha_store.get(captcha_key)
    if not value:
        return None
    return render_captcha_png(value)


def validate_captcha(captcha_key: str, captcha_value: str, consume: bool = True) -> bool:
    return captcha_store.validate(captcha_key, captcha_value, consume=consume)
