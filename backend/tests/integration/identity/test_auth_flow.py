import uuid
from datetime import timedelta
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from httpx import AsyncClient, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal, Role, require_roles
from app.core.db import utcnow
from app.core.settings import get_settings
from app.core.sms import ConsoleSmsSender
from app.modules.identity import service
from app.modules.identity.models import AuthSession, OtpChallenge

PHONE = "+919876543210"
AUTH = "/api/v1/auth"


async def _request_code(client: AsyncClient, sms: ConsoleSmsSender, phone: str = PHONE) -> str:
    response = await client.post(f"{AUTH}/otp/request", json={"phone": phone})
    assert response.status_code == 202, response.text
    return sms.sent[phone]


async def _sign_in(client: AsyncClient, sms: ConsoleSmsSender, phone: str = PHONE) -> Response:
    code = await _request_code(client, sms, phone)
    response = await client.post(f"{AUTH}/otp/verify", json={"phone": phone, "code": code})
    assert response.status_code == 200, response.text
    return response


def _bearer(response: Response) -> dict[str, str]:
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _cookie(response: Response) -> str:
    return response.cookies[get_settings().refresh_cookie_name]


def _use_cookie(client: AsyncClient, cookie: str) -> None:
    """Send exactly this refresh cookie next, as a browser (or a thief who copied it) would."""
    client.cookies.clear()
    client.cookies.set(get_settings().refresh_cookie_name, cookie)


async def _refresh(client: AsyncClient, cookie: str) -> Response:
    _use_cookie(client, cookie)
    return await client.post(f"{AUTH}/refresh")


# --- sign in ---------------------------------------------------------------------------------


async def test_new_number_signs_up_as_customer(client: AsyncClient, sms: ConsoleSmsSender) -> None:
    # Spaces and dashes are normalised away, so the code goes to (and is stored for) PHONE.
    formatted = "+91 98765-43210"
    await client.post(f"{AUTH}/otp/request", json={"phone": formatted})
    response = await client.post(
        f"{AUTH}/otp/verify", json={"phone": formatted, "code": sms.sent[PHONE]}
    )
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["phone"] == PHONE
    assert body["user"]["roles"] == ["customer"]

    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert "path=/api/v1/auth" in cookie

    me = await client.get(f"{AUTH}/me", headers=_bearer(response))
    assert me.status_code == 200
    assert me.json()["id"] == body["user"]["id"]


async def test_returning_number_gets_the_same_account(
    client: AsyncClient, sms: ConsoleSmsSender, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "otp_resend_seconds", 0)
    first = await _sign_in(client, sms)
    second = await _sign_in(client, sms)
    assert first.json()["user"]["id"] == second.json()["user"]["id"]


async def test_invalid_phone_is_rejected(client: AsyncClient) -> None:
    response = await client.post(f"{AUTH}/otp/request", json={"phone": "98765"})
    assert response.status_code == 422


async def test_wrong_codes_lock_the_challenge(client: AsyncClient, sms: ConsoleSmsSender) -> None:
    code = await _request_code(client, sms)
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(get_settings().otp_max_attempts):
        response = await client.post(f"{AUTH}/otp/verify", json={"phone": PHONE, "code": wrong})
        assert response.status_code == 401
        assert response.json()["title"] == "Invalid code"

    # Even the right code fails once the attempts are used up.
    response = await client.post(f"{AUTH}/otp/verify", json={"phone": PHONE, "code": code})
    assert response.status_code == 401


async def test_codes_are_single_use(client: AsyncClient, sms: ConsoleSmsSender) -> None:
    code = await _request_code(client, sms)
    payload = {"phone": PHONE, "code": code}
    assert (await client.post(f"{AUTH}/otp/verify", json=payload)).status_code == 200
    assert (await client.post(f"{AUTH}/otp/verify", json=payload)).status_code == 401


async def test_expired_code_is_rejected(
    client: AsyncClient, sms: ConsoleSmsSender, session: AsyncSession
) -> None:
    code = await _request_code(client, sms)
    await session.execute(update(OtpChallenge).values(expires_at=utcnow() - timedelta(seconds=1)))
    await session.commit()
    response = await client.post(f"{AUTH}/otp/verify", json={"phone": PHONE, "code": code})
    assert response.status_code == 401


async def test_resend_cooldown(client: AsyncClient, sms: ConsoleSmsSender) -> None:
    await _request_code(client, sms)
    response = await client.post(f"{AUTH}/otp/request", json={"phone": PHONE})
    assert response.status_code == 429
    assert 0 < int(response.headers["retry-after"]) <= get_settings().otp_resend_seconds


async def test_hourly_send_cap(
    client: AsyncClient, sms: ConsoleSmsSender, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "otp_resend_seconds", 0)
    for _ in range(get_settings().otp_max_sends_per_hour):
        await _request_code(client, sms)
    response = await client.post(f"{AUTH}/otp/request", json={"phone": PHONE})
    assert response.status_code == 429
    assert int(response.headers["retry-after"]) > 3000


# --- refresh rotation and revocation ---------------------------------------------------------


async def test_refresh_rotates_the_cookie(client: AsyncClient, sms: ConsoleSmsSender) -> None:
    signed_in = await _sign_in(client, sms)
    refreshed = await _refresh(client, _cookie(signed_in))
    assert refreshed.status_code == 200
    assert _cookie(refreshed) != _cookie(signed_in)
    assert (await client.get(f"{AUTH}/me", headers=_bearer(refreshed))).status_code == 200


async def test_reusing_a_refresh_token_revokes_the_session(
    client: AsyncClient, sms: ConsoleSmsSender
) -> None:
    signed_in = await _sign_in(client, sms)
    refreshed = await _refresh(client, _cookie(signed_in))
    assert refreshed.status_code == 200

    # The old token comes back: treat it as stolen.
    assert (await _refresh(client, _cookie(signed_in))).status_code == 401
    # The legitimate newer token and every access token of that session are now dead too.
    assert (await _refresh(client, _cookie(refreshed))).status_code == 401
    assert (await client.get(f"{AUTH}/me", headers=_bearer(refreshed))).status_code == 401


async def test_refresh_without_cookie_is_rejected(client: AsyncClient) -> None:
    assert (await client.post(f"{AUTH}/refresh")).status_code == 401


async def test_logout_ends_the_session_immediately(
    client: AsyncClient, sms: ConsoleSmsSender
) -> None:
    signed_in = await _sign_in(client, sms)
    _use_cookie(client, _cookie(signed_in))
    response = await client.post(f"{AUTH}/logout")
    assert response.status_code == 204
    # The access token hasn't expired, but its session has.
    assert (await client.get(f"{AUTH}/me", headers=_bearer(signed_in))).status_code == 401
    assert (await _refresh(client, _cookie(signed_in))).status_code == 401


async def test_logout_all_ends_every_device(
    client: AsyncClient, sms: ConsoleSmsSender, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "otp_resend_seconds", 0)
    phone_a = await _sign_in(client, sms)
    phone_b = await _sign_in(client, sms)

    response = await client.post(f"{AUTH}/logout-all", headers=_bearer(phone_a))
    assert response.status_code == 204
    for device in (phone_a, phone_b):
        assert (await client.get(f"{AUTH}/me", headers=_bearer(device))).status_code == 401


async def test_tampered_or_missing_access_token(client: AsyncClient) -> None:
    assert (await client.get(f"{AUTH}/me")).status_code == 401
    response = await client.get(f"{AUTH}/me", headers={"Authorization": "Bearer nope"})
    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"


# --- roles -----------------------------------------------------------------------------------


@pytest.fixture
def cook_route(app: FastAPI) -> str:
    @app.get("/test/cook-only")
    async def cook_only(
        principal: Annotated[Principal, Depends(require_roles(Role.COOK))],
    ) -> dict[str, str]:
        return {"user": str(principal.user_id)}

    return "/test/cook-only"


async def test_one_account_holds_several_roles_and_changes_apply_immediately(
    client: AsyncClient, sms: ConsoleSmsSender, session: AsyncSession, cook_route: str
) -> None:
    signed_in = await _sign_in(client, sms)
    user_id = uuid.UUID(signed_in.json()["user"]["id"])
    headers = _bearer(signed_in)

    assert (await client.get(cook_route, headers=headers)).status_code == 403

    await service.grant_role(session, user_id, Role.COOK)
    await session.commit()
    # Same access token, no refresh: roles are read per request.
    assert (await client.get(cook_route, headers=headers)).status_code == 200
    me = await client.get(f"{AUTH}/me", headers=headers)
    assert me.json()["roles"] == ["cook", "customer"]

    await service.revoke_role(session, user_id, Role.COOK)
    await session.commit()
    assert (await client.get(cook_route, headers=headers)).status_code == 403


async def test_suspension_ends_sessions_and_blocks_sign_in(
    client: AsyncClient,
    sms: ConsoleSmsSender,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "otp_resend_seconds", 0)
    signed_in = await _sign_in(client, sms)
    await service.suspend_user(session, uuid.UUID(signed_in.json()["user"]["id"]))
    await session.commit()

    assert (await client.get(f"{AUTH}/me", headers=_bearer(signed_in))).status_code == 401
    reasons = (await session.scalars(select(AuthSession.revoke_reason))).all()
    assert reasons == ["suspended"]

    code = await _request_code(client, sms)
    response = await client.post(f"{AUTH}/otp/verify", json={"phone": PHONE, "code": code})
    assert response.status_code == 403
    assert response.json()["title"] == "Account suspended"


# --- dev helper ------------------------------------------------------------------------------


async def test_dev_otp_endpoint_reads_the_console_provider(
    client: AsyncClient, sms: ConsoleSmsSender
) -> None:
    code = await _request_code(client, sms)
    response = await client.get(f"{AUTH}/_dev/last-otp", params={"phone": PHONE})
    assert response.json() == {"code": code}
