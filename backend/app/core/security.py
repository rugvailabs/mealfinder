"""Token and secret primitives. No database access here; sessions live in the identity module."""

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.core.errors import UnauthorizedError
from app.core.settings import get_settings


def create_access_token(user_id: uuid.UUID, session_id: uuid.UUID, roles: list[str]) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "typ": "access",
        "sub": str(user_id),
        "sid": str(session_id),
        # A convenience for the frontend. Authorization re-reads roles from the database.
        "roles": roles,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub", "sid"]},
        )
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Invalid or expired token") from exc
    if claims.get("typ") != "access":
        raise UnauthorizedError("Invalid or expired token")
    return claims


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Refresh tokens are high-entropy, so a plain SHA-256 is enough to store them safely."""
    return hashlib.sha256(token.encode()).hexdigest()


def new_otp(length: int) -> str:
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


def hash_otp(phone: str, code: str) -> str:
    """OTPs are low-entropy, so they're keyed with the server secret and bound to the phone."""
    key = get_settings().jwt_secret.encode()
    return hmac.new(key, f"otp:{phone}:{code}".encode(), hashlib.sha256).hexdigest()


def otp_matches(phone: str, code: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_otp(phone, code), expected_hash)
