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


def test_jwt_invalid() -> None:
    try:
        decode_access_token("not-a-token")
    except JWTError:
        return
    raise AssertionError("expected JWTError")
