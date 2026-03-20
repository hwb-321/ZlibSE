import hashlib
import hmac
import os


def hash_password(password: str, iterations: int = 260000) -> str:
    salt = os.urandom(16).hex()
    pwd_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        iterations,
    ).hex()
    return f"pbkdf2_sha256${iterations}${salt}${pwd_hash}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iter_str, salt, expected = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iter_str)
    except (ValueError, TypeError):
        return False

    pwd_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        iterations,
    ).hex()
    return hmac.compare_digest(pwd_hash, expected)
