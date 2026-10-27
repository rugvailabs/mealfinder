import uuid
from collections.abc import Awaitable, Callable

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Role
from app.core.sms import ConsoleSmsSender
from app.modules.identity import service as identity

SignIn = Callable[..., Awaitable[dict[str, str]]]


@pytest.fixture
def sign_in(client: AsyncClient, sms: ConsoleSmsSender, session: AsyncSession) -> SignIn:
    """Sign a phone number in through the API and return its bearer header.

    Extra roles are granted directly; the API reads roles fresh on every request.
    """

    async def _sign_in(phone: str, *roles: Role) -> dict[str, str]:
        await client.post("/api/v1/auth/otp/request", json={"phone": phone})
        response = await client.post(
            "/api/v1/auth/otp/verify", json={"phone": phone, "code": sms.sent[phone]}
        )
        assert response.status_code == 200, response.text
        user_id = uuid.UUID(response.json()["user"]["id"])
        for role in roles:
            await identity.grant_role(session, user_id, role)
        await session.commit()
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return _sign_in
