"""Cooks' public API: profiles, the approval lifecycle, shop assignment and address access.

Approval lifecycle (only these transitions exist; anything else is a 409):

    pending   --approve-->  approved     (admin; needs an address on file)
    pending   --reject--->  rejected     (admin, with a reason)
    approved  --suspend-->  suspended    (admin, with a reason)
    suspended --approve-->  approved     (admin reinstates)
    rejected  --resubmit->  pending      (the cook; the rejection reason stays visible)

Editing a profile never changes its status. Applying grants the cook role at once, so the
cook can reach the cook portal and see their status. Being *approved* is what unlocks
selling, enforced by `require_approved_cook`.
"""

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

import app.modules.identity.service as identity
from app.core import audit
from app.core.auth import CurrentPrincipal, Principal, Role
from app.core.db import SessionDep, utcnow
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.modules.cooks import address as _address
from app.modules.cooks.models import ApprovalStatus, CookProfile, CookShopAssignment
from app.modules.cooks.schemas import (
    CookAdminOut,
    CookProfileCreate,
    CookProfileOut,
    CookProfileUpdate,
    HomeAddressIn,
    HomeAddressOut,
)

# Re-exported: the one way other modules (logistics in Phase 4, admin) read an address.
read_cook_address = _address.read_cook_address

SUBJECT = "cook"


def _own_view(profile: CookProfile) -> CookProfileOut:
    return CookProfileOut(
        id=profile.id,
        display_name=profile.display_name,
        bio=profile.bio,
        approval_status=ApprovalStatus(profile.approval_status),
        submitted_at=profile.submitted_at,
        approved_at=profile.approved_at,
        rejection_reason=profile.rejection_reason,
        suspension_reason=profile.suspension_reason,
    )


async def _profile_for_user(db: AsyncSession, user_id: uuid.UUID) -> CookProfile | None:
    return await db.scalar(select(CookProfile).where(CookProfile.user_id == user_id))


async def _own_profile(db: AsyncSession, actor: Principal) -> CookProfile:
    profile = await _profile_for_user(db, actor.user_id)
    if profile is None:
        raise NotFoundError("You haven't applied as a cook yet", code="no_cook_profile")
    return profile


# --- The cook's own profile and address ------------------------------------------------------


async def apply(db: AsyncSession, actor: Principal, data: CookProfileCreate) -> CookProfileOut:
    if await _profile_for_user(db, actor.user_id) is not None:
        raise ConflictError("You already have a cook profile", code="cook_profile_exists")
    profile = CookProfile(
        user_id=actor.user_id,
        display_name=data.display_name,
        bio=data.bio,
        approval_status=ApprovalStatus.PENDING.value,
        submitted_at=utcnow(),
    )
    db.add(profile)
    await db.flush()
    await identity.grant_role(db, actor.user_id, Role.COOK)
    audit.record(
        db,
        actor_id=actor.user_id,
        action="cook.applied",
        subject_type=SUBJECT,
        subject_id=profile.id,
    )
    return _own_view(profile)


async def get_own_profile(db: AsyncSession, actor: Principal) -> CookProfileOut:
    return _own_view(await _own_profile(db, actor))


async def update_own_profile(
    db: AsyncSession, actor: Principal, data: CookProfileUpdate
) -> CookProfileOut:
    profile = await _own_profile(db, actor)
    if data.display_name is not None:
        profile.display_name = data.display_name
    if "bio" in data.model_fields_set:
        profile.bio = data.bio or None
    await db.flush()
    return _own_view(profile)


async def resubmit(db: AsyncSession, actor: Principal) -> CookProfileOut:
    profile = await _own_profile(db, actor)
    _transition(profile, "resubmit", {ApprovalStatus.REJECTED}, ApprovalStatus.PENDING)
    profile.submitted_at = utcnow()
    audit.record(
        db,
        actor_id=actor.user_id,
        action="cook.resubmitted",
        subject_type=SUBJECT,
        subject_id=profile.id,
    )
    await db.flush()
    return _own_view(profile)


async def read_own_address(db: AsyncSession, actor: Principal) -> HomeAddressOut:
    profile = await _own_profile(db, actor)
    return await _address.read_cook_address(db, actor, profile.id)


async def save_own_address(db: AsyncSession, actor: Principal, data: HomeAddressIn) -> None:
    profile = await _own_profile(db, actor)
    await _address.save_own_address(db, actor, profile.id, data)


# --- Approval (admin) ------------------------------------------------------------------------


def _transition(
    profile: CookProfile, action: str, allowed_from: set[ApprovalStatus], to: ApprovalStatus
) -> None:
    current = ApprovalStatus(profile.approval_status)
    if current not in allowed_from:
        raise ConflictError(
            f"Can't {action} a cook who is {current.value}", code="invalid_transition"
        )
    profile.approval_status = to.value


async def _get(db: AsyncSession, cook_id: uuid.UUID) -> CookProfile:
    profile = await db.get(CookProfile, cook_id)
    if profile is None:
        raise NotFoundError("No such cook")
    return profile


async def _admin_views(db: AsyncSession, profiles: list[CookProfile]) -> list[CookAdminOut]:
    phones = await identity.phones_for(db, [p.user_id for p in profiles])
    with_address = await _address.cooks_with_address(db, [p.id for p in profiles])
    return [
        CookAdminOut(
            id=p.id,
            user_id=p.user_id,
            phone=phones.get(p.user_id, ""),
            display_name=p.display_name,
            bio=p.bio,
            approval_status=ApprovalStatus(p.approval_status),
            submitted_at=p.submitted_at,
            approved_by=p.approved_by,
            approved_at=p.approved_at,
            rejection_reason=p.rejection_reason,
            rejected_at=p.rejected_at,
            suspension_reason=p.suspension_reason,
            suspended_at=p.suspended_at,
            has_address=p.id in with_address,
        )
        for p in profiles
    ]


async def list_cooks(db: AsyncSession, status: ApprovalStatus | None = None) -> list[CookAdminOut]:
    stmt = select(CookProfile).order_by(CookProfile.submitted_at)
    if status is not None:
        stmt = stmt.where(CookProfile.approval_status == status.value)
    return await _admin_views(db, list(await db.scalars(stmt)))


async def _decided(
    db: AsyncSession, admin: Principal, profile: CookProfile, action: str, reason: str | None
) -> CookAdminOut:
    audit.record(
        db,
        actor_id=admin.user_id,
        action=f"cook.{action}",
        subject_type=SUBJECT,
        subject_id=profile.id,
        detail=reason,
    )
    await db.flush()
    return (await _admin_views(db, [profile]))[0]


async def approve(db: AsyncSession, admin: Principal, cook_id: uuid.UUID) -> CookAdminOut:
    profile = await _get(db, cook_id)
    if not await _address.cooks_with_address(db, [cook_id]):
        raise ConflictError("The cook hasn't added their address yet", code="address_required")
    _transition(
        profile,
        "approve",
        {ApprovalStatus.PENDING, ApprovalStatus.SUSPENDED},
        ApprovalStatus.APPROVED,
    )
    profile.approved_by = admin.user_id
    profile.approved_at = utcnow()
    return await _decided(db, admin, profile, "approved", None)


async def reject(
    db: AsyncSession, admin: Principal, cook_id: uuid.UUID, reason: str
) -> CookAdminOut:
    profile = await _get(db, cook_id)
    _transition(profile, "reject", {ApprovalStatus.PENDING}, ApprovalStatus.REJECTED)
    profile.rejection_reason = reason
    profile.rejected_at = utcnow()
    return await _decided(db, admin, profile, "rejected", reason)


async def suspend(
    db: AsyncSession, admin: Principal, cook_id: uuid.UUID, reason: str
) -> CookAdminOut:
    profile = await _get(db, cook_id)
    _transition(profile, "suspend", {ApprovalStatus.APPROVED}, ApprovalStatus.SUSPENDED)
    profile.suspension_reason = reason
    profile.suspended_at = utcnow()
    return await _decided(db, admin, profile, "suspended", reason)


# --- Shop assignment -------------------------------------------------------------------------


async def assign_shop(
    db: AsyncSession, admin: Principal, cook_id: uuid.UUID, shop_id: uuid.UUID
) -> None:
    """Make `shop_id` the cook's active handover shop, ending any previous assignment."""
    await _get(db, cook_id)
    await db.execute(
        update(CookShopAssignment)
        .where(CookShopAssignment.cook_id == cook_id, CookShopAssignment.active.is_(True))
        .values(active=False)
    )
    db.add(
        CookShopAssignment(cook_id=cook_id, shop_id=shop_id, active=True, assigned_by=admin.user_id)
    )
    audit.record(
        db,
        actor_id=admin.user_id,
        action="cook.shop_assigned",
        subject_type=SUBJECT,
        subject_id=cook_id,
        detail=str(shop_id),
    )
    await db.flush()


async def active_shop(db: AsyncSession, cook_id: uuid.UUID) -> uuid.UUID | None:
    return await db.scalar(
        select(CookShopAssignment.shop_id).where(
            CookShopAssignment.cook_id == cook_id, CookShopAssignment.active.is_(True)
        )
    )


# --- Authorization for other modules ---------------------------------------------------------


@dataclass(frozen=True)
class ApprovedCook:
    principal: Principal
    cook_id: uuid.UUID


async def _approved_cook(principal: CurrentPrincipal, db: SessionDep) -> ApprovedCook:
    profile = await _profile_for_user(db, principal.user_id)
    if profile is None or profile.approval_status != ApprovalStatus.APPROVED.value:
        raise ForbiddenError("Only approved cooks can do this", code="cook_not_approved")
    return ApprovedCook(principal=principal, cook_id=profile.id)


# Route dependency: the caller is a cook whose profile is currently approved.
require_approved_cook = Depends(_approved_cook)
RequireApprovedCook = Annotated[ApprovedCook, require_approved_cook]
