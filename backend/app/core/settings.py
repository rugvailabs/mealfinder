from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-secret-never-use-outside-local"  # noqa: S105  refused outside local/test


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MF_", env_file=".env", extra="ignore")

    env: Literal["local", "test", "staging", "production"] = "local"
    app_name: str = "Meal Finder API"
    api_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://mealfinder:mealfinder@localhost:5432/mealfinder"
    db_echo: bool = False

    jwt_secret: str = Field(default=DEV_JWT_SECRET, min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    refresh_cookie_name: str = "mf_refresh"
    # None means "secure everywhere except local and test", where the API runs on plain http.
    cookie_secure: bool | None = None

    otp_length: int = 6
    otp_ttl_seconds: int = 300
    otp_resend_seconds: int = 30
    otp_max_attempts: int = 5
    otp_max_sends_per_hour: int = 5

    sms_provider: Literal["console", "msg91"] = "console"
    msg91_auth_key: str = ""
    msg91_otp_template_id: str = ""
    msg91_base_url: str = "https://control.msg91.com"

    cors_origins: list[str] = ["http://localhost:3000"]
    log_level: str = "INFO"
    log_json: bool = True

    @property
    def is_dev(self) -> bool:
        return self.env in ("local", "test")

    @property
    def refresh_cookie_secure(self) -> bool:
        return not self.is_dev if self.cookie_secure is None else self.cookie_secure

    @model_validator(mode="after")
    def _deployed_environments_are_locked_down(self) -> Self:
        if self.is_dev:
            return self
        if self.jwt_secret == DEV_JWT_SECRET:
            raise ValueError("MF_JWT_SECRET must be set outside local/test")
        if self.sms_provider != "msg91":
            raise ValueError("MF_SMS_PROVIDER must be msg91 outside local/test")
        if not (self.msg91_auth_key and self.msg91_otp_template_id):
            raise ValueError("MF_MSG91_AUTH_KEY and MF_MSG91_OTP_TEMPLATE_ID are required")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
