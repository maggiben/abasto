from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.config import get_settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(*, email: str, user_id: int) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        "sub": email,
        "uid": user_id,
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def parse_token_email_uid(payload: dict) -> tuple[str, int]:
    """Return JWT `sub` (email) and `uid` (user pk). Accepts int-like str/float `uid`; rejects bool."""
    sub = payload.get("sub")
    uid_raw = payload.get("uid")
    if not isinstance(sub, str) or not sub:
        raise JWTError("Invalid token payload")
    if isinstance(uid_raw, bool) or uid_raw is None:
        raise JWTError("Invalid token payload")
    if isinstance(uid_raw, int):
        uid = uid_raw
    elif isinstance(uid_raw, float) and uid_raw.is_integer():
        uid = int(uid_raw)
    elif isinstance(uid_raw, str) and uid_raw.isdigit():
        uid = int(uid_raw)
    else:
        raise JWTError("Invalid token payload")
    if uid < 1:
        raise JWTError("Invalid token payload")
    return sub, uid
