from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.core.auth import CurrentPrincipal
from app.core.db import SessionDep
from app.core.errors import NotFoundError
from app.core.settings import get_settings
from app.core.sms import ConsoleSmsSender, SmsSender, get_sms_sender
from app.modules.identity import service
from app.modules.identity.schemas import OtpRequest, OtpRequested, OtpVerify, TokenOut, UserOut

router = APIRouter(prefix="/auth", tags=["identity"])

SmsDep = Annotated[SmsSender, Depends(get_sms_sender)]


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        settings.refresh_cookie_name,
        token,
        max_age=settings.refresh_token_days * 86400,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite="strict",
        path=f"{settings.api_prefix}/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        settings.refresh_cookie_name,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite="strict",
        path=f"{settings.api_prefix}/auth",
    )


def _refresh_cookie(request: Request) -> str | None:
    return request.cookies.get(get_settings().refresh_cookie_name)


@router.post("/otp/request", status_code=status.HTTP_202_ACCEPTED)
async def request_otp(body: OtpRequest, db: SessionDep, sms: SmsDep) -> OtpRequested:
    """Text a sign-in code. Works the same for new and existing numbers."""
    return await service.request_otp(db, sms, body.phone)


@router.post("/otp/verify")
async def verify_otp(
    body: OtpVerify, request: Request, response: Response, db: SessionDep
) -> TokenOut:
    """Exchange a code for an access token; the refresh token is set as an httpOnly cookie.
    A number signing in for the first time gets an account with the customer role."""
    signed_in = await service.verify_otp(
        db,
        body.phone,
        body.code,
        user_agent=request.headers.get("user-agent"),
        ip=request.client.host if request.client else None,
    )
    _set_refresh_cookie(response, signed_in.refresh_token)
    return signed_in.tokens


@router.post("/refresh")
async def refresh(request: Request, response: Response, db: SessionDep) -> TokenOut:
    """Rotate the refresh cookie and return a new access token. Reusing an old refresh
    token ends the session."""
    signed_in = await service.rotate_refresh_token(db, _refresh_cookie(request))
    _set_refresh_cookie(response, signed_in.refresh_token)
    return signed_in.tokens


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, db: SessionDep) -> None:
    await service.logout(db, _refresh_cookie(request))
    _clear_refresh_cookie(response)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(principal: CurrentPrincipal, response: Response, db: SessionDep) -> None:
    """Sign out every device on this account."""
    await service.logout_all(db, principal.user_id)
    _clear_refresh_cookie(response)


@router.get("/me")
async def me(principal: CurrentPrincipal, db: SessionDep) -> UserOut:
    return await service.get_user(db, principal.user_id)


# Mounted by app.main only in local/test with the console SMS provider, so e2e tests and
# developers can sign in without a phone. Settings refuse the console provider elsewhere.
dev_router = APIRouter(prefix="/auth/_dev", tags=["identity"], include_in_schema=False)


@dev_router.get("/last-otp")
async def last_otp(phone: str, sms: SmsDep) -> dict[str, str]:
    code = sms.sent.get(phone) if isinstance(sms, ConsoleSmsSender) else None
    if code is None:
        raise NotFoundError("No code sent to that number")
    return {"code": code}
