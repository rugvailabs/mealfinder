from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MF_", env_file=".env", extra="ignore")

    env: Literal["local", "test", "staging", "production"] = "local"
    app_name: str = "Meal Finder API"
    api_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://mealfinder:mealfinder@localhost:5432/mealfinder"
    db_echo: bool = False

    jwt_secret: str = Field(default="dev-only-secret-never-use-outside-local", min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30

    cors_origins: list[str] = ["http://localhost:3000"]
    log_level: str = "INFO"
    log_json: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
