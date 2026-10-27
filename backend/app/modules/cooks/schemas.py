"""Public schemas of the cooks module.

Address-bearing schemas are only for the cook themself and admins. tests/unit/
test_address_leak.py fails if an address-like field reaches any other response.
"""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.modules.cooks.models import ApprovalStatus as ApprovalStatus  # re-exported

DisplayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
Bio = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]


class CookProfileCreate(BaseModel):
    display_name: DisplayName
    bio: Bio | None = None


class CookProfileUpdate(BaseModel):
    display_name: DisplayName | None = None
    bio: Bio | None = None


class CookProfileOut(BaseModel):
    """The cook's own view of their profile."""

    id: uuid.UUID
    display_name: str
    bio: str | None
    approval_status: ApprovalStatus
    submitted_at: datetime
    approved_at: datetime | None
    rejection_reason: str | None
    suspension_reason: str | None


class HomeAddressIn(BaseModel):
    line1: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]
    line2: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None
    city: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
    pincode: Annotated[str, StringConstraints(pattern=r"^[1-9]\d{5}$")]
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class HomeAddressOut(HomeAddressIn):
    cook_id: uuid.UUID
    updated_at: datetime


class CookAdminOut(BaseModel):
    """What an admin sees when reviewing cooks. No address: that is a separate, audited read."""

    id: uuid.UUID
    user_id: uuid.UUID
    phone: str
    display_name: str
    bio: str | None
    approval_status: ApprovalStatus
    submitted_at: datetime
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    rejection_reason: str | None
    rejected_at: datetime | None
    suspension_reason: str | None
    suspended_at: datetime | None
    has_address: bool


class ReasonIn(BaseModel):
    reason: Reason
