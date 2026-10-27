"""Part 3: cook-to-shop assignments against the minimal partner_shops table."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal, Role
from app.core.geo import LatLng
from app.modules.cooks import service as cooks
from app.modules.cooks.models import CookShopAssignment
from app.modules.logistics.models import PartnerShop
from tests.integration.conftest import SignIn
from tests.integration.cooks.helpers import apply


async def _admin(client: AsyncClient, sign_in: SignIn) -> Principal:
    headers = await sign_in("+919800000099", Role.ADMIN)
    me = (await client.get("/api/v1/auth/me", headers=headers)).json()
    return Principal(uuid.UUID(me["id"]), uuid.uuid4(), frozenset({Role.ADMIN}))


async def _shop(session: AsyncSession, name: str) -> uuid.UUID:
    shop = PartnerShop(name=name, status="active", geom=LatLng(17.4, 78.5).to_ewkt())
    session.add(shop)
    await session.flush()
    return shop.id


async def test_assigning_a_new_shop_ends_the_previous_assignment(
    client: AsyncClient, sign_in: SignIn, session: AsyncSession
) -> None:
    admin = await _admin(client, sign_in)
    cook_id = uuid.UUID(await apply(client, await sign_in("+919800000001")))
    first, second = await _shop(session, "Ravi Stores"), await _shop(session, "Lakshmi Mart")

    assert await cooks.active_shop(session, cook_id) is None
    await cooks.assign_shop(session, admin, cook_id, first)
    assert await cooks.active_shop(session, cook_id) == first
    await cooks.assign_shop(session, admin, cook_id, second)
    assert await cooks.active_shop(session, cook_id) == second
    await session.commit()

    rows = (
        await session.scalars(select(CookShopAssignment).order_by(CookShopAssignment.created_at))
    ).all()
    assert [(r.shop_id, r.active) for r in rows] == [(first, False), (second, True)]


async def test_database_allows_one_active_assignment_per_cook(
    client: AsyncClient, sign_in: SignIn, session: AsyncSession
) -> None:
    cook_id = uuid.UUID(await apply(client, await sign_in("+919800000001")))
    first, second = await _shop(session, "Ravi Stores"), await _shop(session, "Lakshmi Mart")
    session.add(CookShopAssignment(cook_id=cook_id, shop_id=first, active=True))
    session.add(CookShopAssignment(cook_id=cook_id, shop_id=second, active=True))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_assignment_needs_a_real_shop(
    client: AsyncClient, sign_in: SignIn, session: AsyncSession
) -> None:
    if session.get_bind().dialect.name != "postgresql":
        pytest.skip("SQLite doesn't enforce foreign keys by default")
    admin = await _admin(client, sign_in)
    cook_id = uuid.UUID(await apply(client, await sign_in("+919800000001")))
    with pytest.raises(IntegrityError):
        await cooks.assign_shop(session, admin, cook_id, uuid.uuid4())


async def test_shop_location_round_trips(session: AsyncSession) -> None:
    shop_id = await _shop(session, "Ravi Stores")
    await session.commit()
    session.expunge_all()
    shop = await session.get(PartnerShop, shop_id)
    assert shop is not None
    point = LatLng.from_db(shop.geom)
    assert (point.lat, point.lng) == pytest.approx((17.4, 78.5))
