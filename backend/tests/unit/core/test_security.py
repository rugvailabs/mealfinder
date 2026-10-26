import pytest

from app.core.errors import UnauthorizedError
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_round_trip() -> None:
    hashed = hash_password("s3cret-pass")
    assert hashed != "s3cret-pass"
    assert verify_password("s3cret-pass", hashed)
    assert not verify_password("wrong", hashed)


def test_token_round_trip() -> None:
    claims = decode_access_token(create_access_token("user-1", ["cook"]))
    assert claims["sub"] == "user-1"
    assert claims["roles"] == ["cook"]


def test_tampered_token_is_rejected() -> None:
    token = create_access_token("user-1", ["customer"])
    with pytest.raises(UnauthorizedError):
        decode_access_token(token[:-2] + "xx")
