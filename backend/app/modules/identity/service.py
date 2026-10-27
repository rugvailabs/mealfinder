"""Identity's public API: OTP sign-in, session rotation and revocation, and role management.

Other modules (cooks on approval, admin) call `grant_role`, `revoke_role`, `get_user` and
`suspend_user`. Route protection uses app.core.auth, which `load_principal` backs.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import CursorResult, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal, Role
from app.core.db import utcnow
from app.core.errors import ForbiddenError, NotFoundError, RateLimitedError, UnauthorizedError
from app.core.security import (
    create_access_token,
    hash_otp,
    hash_token,
    new_otp,
    new_refresh_token,
    otp_matches,
)
from app.core.settings import get_settings
from app.core.sms import SmsSender
from app.modules.identity.models import (
    AuthSession,
    OtpChallenge,
    RefreshToken,
    User,
    UserRole,
)
from app.modules.identity.schemas import OtpRequested, TokenOut, UserOut

INVALID_CODE = "That code is invalid or has expired"
INVALID_SESSION = "Your session has ended, please sign in again"


@dataclass(frozen=True)
class SignedIn:
    tokens: TokenOut
    refresh_token: str


def _aware(value: datetime) -> datetime:
    # SQLite (used in tests) returns naive datetimes; Postgres returns aware ones.
    return value if value.tzinfo else value.replace(tzinfo=UTC)


# --- OTP -------------------------------------------------------------------------------------


async def request_otp(db: AsyncSession, sms: SmsSender, phone: str) -> OtpRequested:
    settings = get_settings()
    now = utcnow()

    recent = (
        await db.scalars(
            select(OtpChallenge.created_at)
            .where(OtpChallenge.phone == phone, OtpChallenge.created_at > now - timedelta(hours=1))
            .order_by(OtpChallenge.created_at)
        )
    ).all()
    if recent:
        wait = settings.otp_resend_seconds - (now - _aware(recent[-1])).total_seconds()
        if wait > 0:
            raise RateLimitedError(
                "Please wait before asking for another code", retry_after=int(wait) + 1
            )
    if len(recent) >= settings.otp_max_sends_per_hour:
        wait = 3600 - (now - _aware(recent[0])).total_seconds()
        raise RateLimitedError(
            "Too many codes requested, try again later", retry_after=int(wait) + 1
        )

    code = new_otp(settings.otp_length)
    db.add(
        OtpChallenge(
            phone=phone,
            code_hash=hash_otp(phone, code),
            created_at=now,
            expires_at=now + timedelta(seconds=settings.otp_ttl_seconds),
            attempts=0,
        )
    )
    await db.flush()
    await sms.send_otp(phone, code, settings.otp_ttl_seconds)
    return OtpRequested(
        expires_in=settings.otp_ttl_seconds, resend_after=settings.otp_resend_seconds
    )


async def verify_otp(
    db: AsyncSession, phone: str, code: str, *, user_agent: str | None, ip: str | None
) -> SignedIn:
    settings = get_settings()
    now = utcnow()
    challenge = await db.scalar(
        select(OtpChallenge)
        .where(OtpChallenge.phone == phone, OtpChallenge.consumed_at.is_(None))
        .order_by(OtpChallenge.created_at.desc())
        .limit(1)
        .with_for_update()
    )
    if (
        challenge is None
        or _aware(challenge.expires_at) <= now
        or challenge.attempts >= settings.otp_max_attempts
    ):
        raise UnauthorizedError(INVALID_CODE, code="invalid_code")

    challenge.attempts += 1
    if not otp_matches(phone, code, challenge.code_hash):
        # Commit the failed attempt before raising, or the rollback would undo the count.
        await db.commit()
        raise UnauthorizedError(INVALID_CODE, code="invalid_code")
    challenge.consumed_at = now

    user = await db.scalar(select(User).where(User.phone == phone))
    if user is None:
        user = User(phone=phone, status="active")
        db.add(user)
        await db.flush()
        await grant_role(db, user.id, Role.CUSTOMER)
    elif user.status != "active":
        await db.commit()
        raise ForbiddenError("This account is suspended", code="account_suspended")

    session = AuthSession(user_id=user.id, user_agent=(user_agent or "")[:255] or None, ip=ip)
    db.add(session)
    await db.flush()
    return await _issue(db, user, session)


# --- Sessions --------------------------------------------------------------------------------


async def _issue(db: AsyncSession, user: User, session: AuthSession) -> SignedIn:
    settings = get_settings()
    raw = new_refresh_token()
    db.add(
        RefreshToken(
            session_id=session.id,
            token_hash=hash_token(raw),
            expires_at=utcnow() + timedelta(days=settings.refresh_token_days),
        )
    )
    session.last_seen_at = utcnow()
    roles = await roles_for(db, user.id)
    access = create_access_token(user.id, session.id, [r.value for r in roles])
    tokens = TokenOut(
        access_token=access,
        expires_in=settings.access_token_minutes * 60,
        user=UserOut(id=user.id, phone=user.phone, name=user.name, roles=roles),
    )
    return SignedIn(tokens=tokens, refresh_token=raw)


async def rotate_refresh_token(db: AsyncSession, raw: str | None) -> SignedIn:
    if not raw:
        raise UnauthorizedError(INVALID_SESSION, code="invalid_session")
    token = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw)))
    if token is None:
        raise UnauthorizedError(INVALID_SESSION, code="invalid_session")

    # Atomic claim: only one request can use a given refresh token.
    claimed = cast(
        CursorResult[Any],
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.id == token.id, RefreshToken.used_at.is_(None))
            .values(used_at=utcnow())
        ),
    )
    if claimed.rowcount == 0:
        # A used token came back: assume it was stolen and end the whole session.
        await _revoke_sessions(db, AuthSession.id == token.session_id, "refresh_reuse")
        await db.commit()
        raise UnauthorizedError(INVALID_SESSION, code="invalid_session")

    session = await db.get(AuthSession, token.session_id)
    user = await db.get(User, session.user_id) if session else None
    if (
        session is None
        or user is None
        or session.revoked_at is not None
        or _aware(token.expires_at) <= utcnow()
        or user.status != "active"
    ):
        raise UnauthorizedError(INVALID_SESSION, code="invalid_session")
    return await _issue(db, user, session)


async def _revoke_sessions(db: AsyncSession, condition: Any, reason: str) -> None:
    await db.execute(
        update(AuthSession)
        .where(condition, AuthSession.revoked_at.is_(None))
        .values(revoked_at=utcnow(), revoke_reason=reason)
    )


async def logout(db: AsyncSession, raw: str | None) -> None:
    """End the session behind a refresh token. Unknown tokens are ignored."""
    if not raw:
        return
    session_id = await db.scalar(
        select(RefreshToken.session_id).where(RefreshToken.token_hash == hash_token(raw))
    )
    if session_id is not None:
        await _revoke_sessions(db, AuthSession.id == session_id, "logout")


async def logout_all(db: AsyncSession, user_id: uuid.UUID) -> None:
    await _revoke_sessions(db, AuthSession.user_id == user_id, "logout_all")


async def load_principal(
    db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID
) -> Principal | None:
    live = await db.scalar(
        select(func.count())
        .select_from(AuthSession)
        .join(User, User.id == AuthSession.user_id)
        .where(
            AuthSession.id == session_id,
            AuthSession.user_id == user_id,
            AuthSession.revoked_at.is_(None),
            User.status == "active",
        )
    )
    if not live:
        return None
    return Principal(
        user_id=user_id, session_id=session_id, roles=frozenset(await roles_for(db, user_id))
    )


# --- Users and roles -------------------------------------------------------------------------


async def roles_for(db: AsyncSession, user_id: uuid.UUID) -> list[Role]:
    rows = await db.scalars(select(UserRole.role).where(UserRole.user_id == user_id))
    return sorted(Role(r) for r in rows)


async def get_user(db: AsyncSession, user_id: uuid.UUID) -> UserOut:
    user = await db.get(User, user_id)
    if user is None:
        raise NotFoundError("No such user")
    return UserOut(id=user.id, phone=user.phone, name=user.name, roles=await roles_for(db, user.id))


async def phones_for(db: AsyncSession, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not user_ids:
        return {}
    rows = await db.execute(select(User.id, User.phone).where(User.id.in_(user_ids)))
    return {user_id: phone for user_id, phone in rows.all()}


async def get_or_create_user(db: AsyncSession, phone: str) -> UserOut:
    user = await db.scalar(select(User).where(User.phone == phone))
    if user is None:
        user = User(phone=phone, status="active")
        db.add(user)
        await db.flush()
        await grant_role(db, user.id, Role.CUSTOMER)
    return await get_user(db, user.id)


async def grant_role(
    db: AsyncSession, user_id: uuid.UUID, role: Role, granted_by: uuid.UUID | None = None
) -> None:
    if await db.get(UserRole, (user_id, role.value)) is None:
        db.add(UserRole(user_id=user_id, role=role.value, granted_by=granted_by))
        await db.flush()


async def revoke_role(db: AsyncSession, user_id: uuid.UUID, role: Role) -> None:
    existing = await db.get(UserRole, (user_id, role.value))
    if existing is not None:
        await db.delete(existing)
        await db.flush()


async def suspend_user(db: AsyncSession, user_id: uuid.UUID) -> None:
    user = await db.get(User, user_id)
    if user is None:
        raise NotFoundError("No such user")
    user.status = "suspended"
    await _revoke_sessions(db, AuthSession.user_id == user_id, "suspended")
