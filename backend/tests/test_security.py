from jose import JWTError

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    parse_token_email_uid,
    verify_password,
)


def test_password_roundtrip() -> None:
    h = hash_password("secret12345")
    assert verify_password("secret12345", h)
    assert not verify_password("wrong", h)


def test_jwt_roundtrip() -> None:
    token = create_access_token(email="a@example.com", user_id=42)
    payload = decode_access_token(token)
    email, uid = parse_token_email_uid(payload)
    assert email == "a@example.com"
    assert uid == 42


def test_parse_token_uid_string_coercion() -> None:
    from jose import jwt

    from app.config import get_settings

    settings = get_settings()
    payload = {
        "sub": "a@example.com",
        "uid": "42",
        "exp": 9_999_999_999,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    decoded = decode_access_token(token)
    email, uid = parse_token_email_uid(decoded)
    assert email == "a@example.com"
    assert uid == 42


def test_parse_token_uid_whole_float_coercion() -> None:
    from jose import jwt

    from app.config import get_settings

    settings = get_settings()
    payload = {
        "sub": "a@example.com",
        "uid": 42.0,
        "exp": 9_999_999_999,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    decoded = decode_access_token(token)
    _, uid = parse_token_email_uid(decoded)
    assert uid == 42


def test_parse_token_rejects_bool_uid() -> None:
    try:
        parse_token_email_uid({"sub": "a@example.com", "uid": True})
    except JWTError:
        return
    raise AssertionError("expected JWTError")


def test_jwt_invalid() -> None:
    try:
        decode_access_token("not-a-token")
    except JWTError:
        return
    raise AssertionError("expected JWTError")
