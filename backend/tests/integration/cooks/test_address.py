"""Part 2 and part 6: the protected address, its single read path and the audit trail."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import AuditLog
from app.core.auth import Principal, Role
from app.core.errors import NotFoundError
from app.modules.cooks import service as cooks
from tests.integration.conftest import SignIn
from tests.integration.cooks.helpers import ADDRESS, COOKS, add_address, apply

COOK = "+919800000001"
OTHER_COOK = "+919800000002"
CUSTOMER = "+919800000003"
ADMIN_PHONE = "+919800000099"


async def _principal(client: AsyncClient, headers: dict[str, str]) -> Principal:
    me = (await client.get("/api/v1/auth/me", headers=headers)).json()
    return Principal(
        user_id=uuid.UUID(me["id"]),
        session_id=uuid.uuid4(),
        roles=frozenset(Role(r) for r in me["roles"]),
    )


async def _reads(sessionmaker: async_sessionmaker[AsyncSession], cook_id: str) -> list[AuditLog]:
    async with sessionmaker() as s:
        rows = await s.scalars(
            select(AuditLog)
            .where(
                AuditLog.action == "cook_address.read", AuditLog.subject_id == uuid.UUID(cook_id)
            )
            .order_by(AuditLog.created_at)
        )
        return list(rows)


async def test_cook_saves_and_reads_back_their_address(
    client: AsyncClient, sign_in: SignIn
) -> None:
    headers = await sign_in(COOK)
    cook_id = await apply(client, headers)

    missing = await client.get(f"{COOKS}/me/address", headers=headers)
    assert missing.status_code == 404

    await add_address(client, headers)
    response = await client.get(f"{COOKS}/me/address", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["cook_id"] == cook_id
    assert {k: body[k] for k in ADDRESS} == pytest.approx(ADDRESS)

    # Saving again replaces the single row.
    moved = {**ADDRESS, "line1": "4 Lake View Road", "lat": 17.4, "lng": 78.5}
    assert (await client.put(f"{COOKS}/me/address", json=moved, headers=headers)).status_code == 204
    body = (await client.get(f"{COOKS}/me/address", headers=headers)).json()
    assert body["line1"] == "4 Lake View Road"
    assert body["lat"] == pytest.approx(17.4)
    assert body["lng"] == pytest.approx(78.5)


async def test_address_validation(client: AsyncClient, sign_in: SignIn) -> None:
    headers = await sign_in(COOK)
    await apply(client, headers)
    for bad in ({"pincode": "12345"}, {"pincode": "012345"}, {"lat": 91}, {"lng": -181}):
        response = await client.put(f"{COOKS}/me/address", json={**ADDRESS, **bad}, headers=headers)
        assert response.status_code == 422, bad


async def test_customer_reading_an_address_gets_404(
    client: AsyncClient, sign_in: SignIn, session: AsyncSession
) -> None:
    cook = await sign_in(COOK)
    cook_id = await apply(client, cook)
    await add_address(client, cook)

    customer_headers = await sign_in(CUSTOMER)
    customer = await _principal(client, customer_headers)
    with pytest.raises(NotFoundError) as refused:
        await cooks.read_cook_address(session, customer, uuid.UUID(cook_id))
    assert refused.value.status_code == 404

    # Over HTTP a customer can't reach the cook-self address route at all.
    response = await client.get(f"{COOKS}/me/address", headers=customer_headers)
    assert response.status_code == 403


async def test_another_cook_cannot_read_it_either(
    client: AsyncClient, sign_in: SignIn, session: AsyncSession
) -> None:
    cook = await sign_in(COOK)
    cook_id = await apply(client, cook)
    await add_address(client, cook)
    other_headers = await sign_in(OTHER_COOK)
    await apply(client, other_headers, "Other Kitchen")

    other = await _principal(client, other_headers)
    with pytest.raises(NotFoundError):
        await cooks.read_cook_address(session, other, uuid.UUID(cook_id))
    # Nor can anyone tell a missing cook from a hidden one.
    with pytest.raises(NotFoundError):
        await cooks.read_cook_address(session, other, uuid.uuid4())


async def test_admin_can_read_it(
    client: AsyncClient, sign_in: SignIn, session: AsyncSession
) -> None:
    cook = await sign_in(COOK)
    cook_id = await apply(client, cook)
    await add_address(client, cook)

    admin = await _principal(client, await sign_in(ADMIN_PHONE, Role.ADMIN))
    address = await cooks.read_cook_address(session, admin, uuid.UUID(cook_id))
    assert address.pincode == ADDRESS["pincode"]


async def test_every_address_read_produces_an_audit_row(
    client: AsyncClient,
    sign_in: SignIn,
    session: AsyncSession,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    cook_headers = await sign_in(COOK)
    cook_id = await apply(client, cook_headers)

    # 1: the cook, before an address exists.
    assert (await client.get(f"{COOKS}/me/address", headers=cook_headers)).status_code == 404
    await add_address(client, cook_headers)
    # 2 and 3: the cook, twice.
    for _ in range(2):
        assert (await client.get(f"{COOKS}/me/address", headers=cook_headers)).status_code == 200

    # 4: an admin.
    admin = await _principal(client, await sign_in(ADMIN_PHONE, Role.ADMIN))
    await cooks.read_cook_address(session, admin, uuid.UUID(cook_id))
    await session.commit()

    # 5: a customer, refused. The refusal is recorded even though the caller's own
    # transaction rolls back with the error.
    customer = await _principal(client, await sign_in(CUSTOMER))
    with pytest.raises(NotFoundError):
        await cooks.read_cook_address(session, customer, uuid.UUID(cook_id))
    await session.rollback()

    rows = await _reads(sessionmaker, cook_id)
    cook_user = (await _principal(client, cook_headers)).user_id
    assert [(r.actor_id, r.purpose, r.outcome) for r in rows] == [
        (cook_user, "cook_self", "not_found"),
        (cook_user, "cook_self", "allowed"),
        (cook_user, "cook_self", "allowed"),
        (admin.user_id, "admin", "allowed"),
        (customer.user_id, None, "denied"),
    ]


async def test_address_never_appears_in_other_cook_responses(
    client: AsyncClient, sign_in: SignIn, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    headers = await sign_in(COOK)
    await apply(client, headers)
    await add_address(client, headers)
    profile = (await client.get(f"{COOKS}/me", headers=headers)).text
    for value in ("Temple Street", "500001", "Hyderabad"):
        assert value not in profile

    # Writing an address isn't a read, so it adds no read rows.
    async with sessionmaker() as s:
        count = await s.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.action == "cook_address.read")
        )
    assert count == 0
