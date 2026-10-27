"""The only code that touches cook home addresses (ADR 0003).

`read_cook_address` is the single way to read one. Every call writes an audit row, whether
it returns the address or refuses. Refusals answer 404 rather than 403, so a caller can't
tell whether the cook or the address exists.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.audit import Outcome
from app.core.auth import Principal, Role
from app.core.errors import NotFoundError
from app.core.geo import LatLng
from app.modules.cooks.models import CookAddress, CookProfile
from app.modules.cooks.schemas import HomeAddressIn, HomeAddressOut

READ_ACTION = "cook_address.read"
SUBJECT = "cook"


def _purpose(actor: Principal, profile: CookProfile | None) -> str | None:
    if profile is not None and profile.user_id == actor.user_id:
        return "cook_self"
    if actor.has(Role.ADMIN):
        return "admin"
    # Logistics adds "assigned_run" for agents in Phase 4.
    return None


async def read_cook_address(
    db: AsyncSession, actor: Principal, cook_id: uuid.UUID
) -> HomeAddressOut:
    profile = await db.get(CookProfile, cook_id)
    purpose = _purpose(actor, profile)
    if purpose is None:
        await audit.record_now(
            db,
            actor_id=actor.user_id,
            action=READ_ACTION,
            subject_type=SUBJECT,
            subject_id=cook_id,
            outcome=Outcome.DENIED,
        )
        raise NotFoundError("Address not found")

    address = await db.get(CookAddress, cook_id)
    if address is None:
        await audit.record_now(
            db,
            actor_id=actor.user_id,
            action=READ_ACTION,
            subject_type=SUBJECT,
            subject_id=cook_id,
            outcome=Outcome.NOT_FOUND,
            purpose=purpose,
        )
        raise NotFoundError("Address not found")

    audit.record(
        db,
        actor_id=actor.user_id,
        action=READ_ACTION,
        subject_type=SUBJECT,
        subject_id=cook_id,
        purpose=purpose,
    )
    point = LatLng.from_db(address.geom)
    return HomeAddressOut(
        cook_id=address.cook_id,
        line1=address.line1,
        line2=address.line2,
        city=address.city,
        pincode=address.pincode,
        lat=point.lat,
        lng=point.lng,
        updated_at=address.updated_at,
    )


async def save_own_address(
    db: AsyncSession, actor: Principal, cook_id: uuid.UUID, data: HomeAddressIn
) -> None:
    """Create or replace the cook's address. The caller has checked `actor` owns `cook_id`."""
    address = await db.get(CookAddress, cook_id)
    if address is None:
        address = CookAddress(cook_id=cook_id)
        db.add(address)
    address.line1 = data.line1
    address.line2 = data.line2
    address.city = data.city
    address.pincode = data.pincode
    address.geom = LatLng(lat=data.lat, lng=data.lng).to_ewkt()
    audit.record(
        db,
        actor_id=actor.user_id,
        action="cook_address.write",
        subject_type=SUBJECT,
        subject_id=cook_id,
        purpose="cook_self",
    )
    await db.flush()


async def cooks_with_address(db: AsyncSession, cook_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    """Which of these cooks have an address on file. Reads ids only, never address content."""
    if not cook_ids:
        return set()
    rows = await db.scalars(select(CookAddress.cook_id).where(CookAddress.cook_id.in_(cook_ids)))
    return set(rows)
