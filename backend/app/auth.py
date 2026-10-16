"""Passwords, login tokens and invite codes (stdlib only)."""
import hashlib
import hmac
import re
import secrets

from . import db

TOKEN_DAYS = 30
COOKIE = "ls_token"
_ITERATIONS = 200_000
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I


class AuthError(ValueError):
    pass


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _ITERATIONS).hex()
    return f"pbkdf2_sha256${_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, digest = stored.split("$")
        check = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations)).hex()
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(check, digest)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_token(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    db.save_token(_token_hash(token), user_id, TOKEN_DAYS)
    db.touch_login(user_id)
    return token


def user_for_token(token: str):
    return db.user_for_token(_token_hash(token)) if token else None


def revoke_token(token: str):
    if token:
        db.delete_token(_token_hash(token))


def new_invite_code() -> str:
    raw = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


def normalize_code(code: str) -> str:
    raw = re.sub(r"[^A-Za-z0-9]", "", code or "").upper()
    return f"{raw[:4]}-{raw[4:]}" if len(raw) == 8 else raw


def check_credentials(username: str, password: str):
    username = (username or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_\-.一-龥]{2,32}", username):
        raise AuthError("用户名 2–32 个字符，可以用中英文、数字、下划线、点和短横线")
    if len(password or "") < 8:
        raise AuthError("密码至少 8 位")
    return username


def login(username: str, password: str) -> dict:
    user = db.get_login((username or "").strip())
    if not user or not verify_password(password or "", user["passwordHash"]):
        raise AuthError("用户名或密码不对")
    if user["disabled"]:
        raise AuthError("这个账号已被管理员停用")
    user.pop("passwordHash")
    return user


def temp_password() -> str:
    return "".join(secrets.choice(_CODE_ALPHABET.lower() + "23456789") for _ in range(10))
