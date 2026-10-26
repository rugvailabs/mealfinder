"""Authentication dependencies every module can use without depending on the identity module.

Identity owns users, sessions and roles. At startup it registers a principal loader here
(see app.main), and routes in any module protect themselves with `CurrentPrincipal` or
`require_roles(...)`. Every request re-checks the session in the database, so revocation,
suspension and role changes take effect immediately rather than when the token expires.
"""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token


class Role(StrEnum):
    CUSTOMER = "customer"
    COOK = "cook"
    AGENT = "agent"
    SHOP = "shop"
    ADMIN = "admin"


@dataclass(frozen=True)
class Principal:
    user_id: uuid.UUID
    session_id: uuid.UUID
    roles: frozenset[Role]

    def has(self, *roles: Role) -> bool:
        return bool(self.roles.intersection(roles))


# Returns the principal if the session is live and the user active, else None.
PrincipalLoader = Callable[[AsyncSession, uuid.UUID, uuid.UUID], Awaitable[Principal | None]]
_loader: PrincipalLoader | None = None


def set_principal_loader(loader: PrincipalLoader) -> None:
    global _loader
    _loader = loader


_bearer = HTTPBearer(auto_error=False)


async def get_principal(
    db: Annotated[AsyncSession, Depends(get_session)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal:
    if credentials is None:
        raise UnauthorizedError("Sign in required", headers={"WWW-Authenticate": "Bearer"})
    claims = decode_access_token(credentials.credentials)
    if _loader is None:
        raise RuntimeError("no principal loader registered; is the identity module wired up?")
    try:
        user_id, session_id = uuid.UUID(claims["sub"]), uuid.UUID(claims["sid"])
    except ValueError as exc:
        raise UnauthorizedError("Invalid or expired token") from exc
    principal = await _loader(db, user_id, session_id)
    if principal is None:
        raise UnauthorizedError("Session has ended", headers={"WWW-Authenticate": "Bearer"})
    return principal


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]


def require_roles(*roles: Role) -> Callable[[Principal], Awaitable[Principal]]:
    """Dependency that allows the request if the principal holds any of `roles`."""

    async def check(principal: CurrentPrincipal) -> Principal:
        if not principal.has(*roles):
            raise ForbiddenError("You don't have access to this")
        return principal

    return check
