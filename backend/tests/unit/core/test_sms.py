import httpx
import pytest

from app.core.errors import UpstreamError
from app.core.settings import Settings
from app.core.sms import Msg91SmsSender

SETTINGS = Settings(msg91_auth_key="secret-key", msg91_otp_template_id="tpl-1")


def _sender(handler: httpx.MockTransport) -> Msg91SmsSender:
    client = httpx.AsyncClient(transport=handler, base_url=SETTINGS.msg91_base_url)
    return Msg91SmsSender(SETTINGS, client)


async def test_msg91_request_shape() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"type": "success", "request_id": "r1"})

    await _sender(httpx.MockTransport(handle)).send_otp("+919876543210", "123456", 300)

    (request,) = seen
    assert request.method == "POST"
    # The auth key travels in a header, never in the URL that proxies and logs record.
    assert request.url.path == "/api/v5/otp"
    assert request.headers["authkey"] == "secret-key"
    assert dict(request.url.params) == {
        "template_id": "tpl-1",
        "mobile": "919876543210",
        "otp": "123456",
        "otp_expiry": "5",
    }


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, json={"type": "error", "message": "Invalid template"}),
        httpx.Response(401, json={"type": "error", "message": "Authentication failure"}),
        httpx.Response(502, text="bad gateway"),
    ],
)
async def test_msg91_failures_raise_upstream_error(response: httpx.Response) -> None:
    sender = _sender(httpx.MockTransport(lambda _: response))
    with pytest.raises(UpstreamError):
        await sender.send_otp("+919876543210", "123456", 300)


async def test_msg91_network_error_raises_upstream_error() -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    with pytest.raises(UpstreamError):
        await _sender(httpx.MockTransport(boom)).send_otp("+919876543210", "123456", 300)
