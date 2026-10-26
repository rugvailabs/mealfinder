"""SMS provider adapter. Callers depend on `SmsSender`; the provider is picked by settings."""

import logging
from functools import lru_cache
from typing import Protocol

import httpx

from app.core.errors import UpstreamError
from app.core.settings import Settings, get_settings

log = logging.getLogger(__name__)


class SmsSender(Protocol):
    async def send_otp(self, phone: str, code: str, ttl_seconds: int) -> None:
        """Deliver `code` to `phone` (E.164). Raises UpstreamError if the provider fails."""
        ...


class ConsoleSmsSender:
    """Local and test only (settings refuse it elsewhere). Keeps the last code per phone so
    the dev-only endpoint and tests can read it."""

    def __init__(self) -> None:
        self.sent: dict[str, str] = {}

    async def send_otp(self, phone: str, code: str, ttl_seconds: int) -> None:
        self.sent[phone] = code
        log.info("OTP for %s is %s (console SMS provider)", phone, code)


class Msg91SmsSender:
    """MSG91 v5 OTP API, sending our own code so verification stays provider-independent.

    POST {base}/api/v5/otp with the `authkey` header and query params template_id, mobile
    (country code + number, no "+"), otp and otp_expiry (minutes). Replies
    {"type": "success", "request_id": ...} or {"type": "error", "message": ...}.

    Unverified against a live account: confirm the template's OTP variable and DLT setup
    with MSG91 before launch.
    """

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._auth_key = settings.msg91_auth_key
        self._template_id = settings.msg91_otp_template_id
        self._client = client or httpx.AsyncClient(base_url=settings.msg91_base_url, timeout=10)

    async def send_otp(self, phone: str, code: str, ttl_seconds: int) -> None:
        params = {
            "template_id": self._template_id,
            "mobile": phone.removeprefix("+"),
            "otp": code,
            "otp_expiry": str(max(1, ttl_seconds // 60)),
        }
        try:
            response = await self._client.post(
                "/api/v5/otp", params=params, headers={"authkey": self._auth_key}, json={}
            )
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("MSG91 request failed: %r", exc)
            raise UpstreamError("Could not send the code, please try again") from exc
        if response.status_code >= 400 or body.get("type") != "success":
            log.warning("MSG91 rejected OTP send: %s %s", response.status_code, body)
            raise UpstreamError("Could not send the code, please try again")


@lru_cache
def get_sms_sender() -> SmsSender:
    settings = get_settings()
    if settings.sms_provider == "msg91":
        return Msg91SmsSender(settings)
    return ConsoleSmsSender()
