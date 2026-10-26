import uuid

import jwt
import pytest

from app.core.errors import UnauthorizedError
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_otp,
    hash_token,
    new_otp,
    new_refresh_token,
    otp_matches,
)
from app.core.settings import get_settings

USER, SESSION = uuid.uuid4(), uuid.uuid4()


def test_access_token_round_trip() -> None:
    claims = decode_access_token(create_access_token(USER, SESSION, ["cook"]))
    assert claims["sub"] == str(USER)
    assert claims["sid"] == str(SESSION)
    assert claims["roles"] == ["cook"]


def test_tampered_token_is_rejected() -> None:
    token = create_access_token(USER, SESSION, ["customer"])
    with pytest.raises(UnauthorizedError):
        decode_access_token(token[:-2] + "xx")


def test_token_without_access_type_is_rejected() -> None:
    settings = get_settings()
    other = jwt.encode(
        {"sub": str(USER), "sid": str(SESSION), "exp": 9999999999},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(UnauthorizedError):
        decode_access_token(other)


def test_refresh_tokens_are_random_and_stored_hashed() -> None:
    a, b = new_refresh_token(), new_refresh_token()
    assert a != b
    assert len(hash_token(a)) == 64
    assert hash_token(a) != a


def test_otp_hash_is_bound_to_the_phone() -> None:
    code = new_otp(6)
    assert len(code) == 6 and code.isdigit()
    stored = hash_otp("+911111111111", code)
    assert otp_matches("+911111111111", code, stored)
    assert not otp_matches("+912222222222", code, stored)
