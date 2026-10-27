from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.auth import CurrentPrincipal, Principal, Role, require_roles
from app.core.db import SessionDep
from app.modules.cooks import service
from app.modules.cooks.schemas import (
    CookProfileCreate,
    CookProfileOut,
    CookProfileUpdate,
    HomeAddressIn,
    HomeAddressOut,
)

router = APIRouter(prefix="/cooks", tags=["cooks"])

CookDep = Annotated[Principal, Depends(require_roles(Role.COOK))]


@router.post("/me", status_code=status.HTTP_201_CREATED)
async def apply(
    body: CookProfileCreate, principal: CurrentPrincipal, db: SessionDep
) -> CookProfileOut:
    """Apply to cook. Any signed-in account can apply; it gets the cook role at once and
    waits as `pending` until an admin approves it."""
    return await service.apply(db, principal, body)


@router.get("/me")
async def get_my_profile(principal: CookDep, db: SessionDep) -> CookProfileOut:
    return await service.get_own_profile(db, principal)


@router.patch("/me")
async def update_my_profile(
    body: CookProfileUpdate, principal: CookDep, db: SessionDep
) -> CookProfileOut:
    """Edit the profile. Never changes the approval status."""
    return await service.update_own_profile(db, principal, body)


@router.post("/me/resubmit")
async def resubmit(principal: CookDep, db: SessionDep) -> CookProfileOut:
    """Ask for another review after a rejection. Allowed only while rejected."""
    return await service.resubmit(db, principal)


@router.get("/me/address")
async def get_my_address(principal: CookDep, db: SessionDep) -> HomeAddressOut:
    """Your home address. Every read is audit-logged."""
    return await service.read_own_address(db, principal)


@router.put("/me/address", status_code=status.HTTP_204_NO_CONTENT)
async def save_my_address(body: HomeAddressIn, principal: CookDep, db: SessionDep) -> None:
    await service.save_own_address(db, principal, body)
