import re
import uuid
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, StringConstraints

from app.core.auth import Role

_E164 = re.compile(r"^\+[1-9]\d{7,14}$")


def _normalise_phone(value: str) -> str:
    phone = re.sub(r"[\s\-()]", "", value)
    if not _E164.fullmatch(phone):
        raise ValueError("Use international format, for example +919876543210")
    return phone


Phone = Annotated[str, AfterValidator(_normalise_phone)]
OtpCode = Annotated[str, StringConstraints(pattern=r"^\d{4,9}$")]


class OtpRequest(BaseModel):
    phone: Phone


class OtpRequested(BaseModel):
    expires_in: int
    resend_after: int


class OtpVerify(BaseModel):
    phone: Phone
    code: OtpCode


class UserOut(BaseModel):
    id: uuid.UUID
    phone: str
    name: str | None
    roles: list[Role]


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105  OAuth token type, not a secret
    expires_in: int
    user: UserOut
