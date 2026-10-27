import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

import app.modules.cooks.service as cooks
from app.core.auth import Principal, Role, require_roles
from app.core.db import SessionDep
from app.modules.cooks.schemas import ApprovalStatus, CookAdminOut, ReasonIn

router = APIRouter(prefix="/admin", tags=["admin"])

AdminDep = Annotated[Principal, Depends(require_roles(Role.ADMIN))]


@router.get("/cooks")
async def list_cooks(
    _: AdminDep, db: SessionDep, status: ApprovalStatus | None = None
) -> list[CookAdminOut]:
    """Cooks, oldest submission first, optionally filtered by approval status."""
    return await cooks.list_cooks(db, status)


@router.post("/cooks/{cook_id}/approve")
async def approve_cook(cook_id: uuid.UUID, admin: AdminDep, db: SessionDep) -> CookAdminOut:
    """Approve a pending cook, or reinstate a suspended one. The cook needs an address."""
    return await cooks.approve(db, admin, cook_id)


@router.post("/cooks/{cook_id}/reject")
async def reject_cook(
    cook_id: uuid.UUID, body: ReasonIn, admin: AdminDep, db: SessionDep
) -> CookAdminOut:
    return await cooks.reject(db, admin, cook_id, body.reason)


@router.post("/cooks/{cook_id}/suspend")
async def suspend_cook(
    cook_id: uuid.UUID, body: ReasonIn, admin: AdminDep, db: SessionDep
) -> CookAdminOut:
    return await cooks.suspend(db, admin, cook_id, body.reason)
