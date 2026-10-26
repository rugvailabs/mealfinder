import pytest
from pydantic import ValidationError

from app.core.settings import Settings

PROD_SECRET = "p" * 40
PROD = {
    "env": "production",
    "jwt_secret": PROD_SECRET,
    "sms_provider": "msg91",
    "msg91_auth_key": "key",
    "msg91_otp_template_id": "tpl",
}


def test_complete_production_settings_are_accepted() -> None:
    settings = Settings(**PROD)  # type: ignore[arg-type]
    assert settings.refresh_cookie_secure


@pytest.mark.parametrize(
    "override",
    [
        {"jwt_secret": "dev-only-secret-never-use-outside-local"},
        {"sms_provider": "console"},
        {"msg91_auth_key": ""},
        {"msg91_otp_template_id": ""},
    ],
)
def test_production_refuses_dev_defaults(override: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        Settings(**{**PROD, **override})  # type: ignore[arg-type]


def test_local_cookies_work_over_http() -> None:
    assert not Settings(env="local").refresh_cookie_secure
