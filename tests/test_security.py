import uuid

from jose import jwt

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_password():
    hashed = hash_password("secret123")

    assert hashed != "secret123"
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong", hashed)


def test_create_and_decode_access_token():
    user_id = uuid.uuid4()
    token = create_access_token(user_id)

    assert decode_access_token(token) == str(user_id)


def test_decode_invalid_token_returns_none():
    assert decode_access_token("not-a-valid-jwt") is None


def test_token_uses_configured_secret():
    settings = get_settings()
    token = create_access_token(uuid.uuid4())
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])

    assert "sub" in payload
    assert "exp" in payload
