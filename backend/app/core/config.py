"""Application settings, loaded from environment variables (and an optional .env)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    app_name: str = "RoboSense"
    environment: str = "development"

    # --- Database ---
    database_url: str = "postgresql+asyncpg://robosense:robosense@db:5432/robosense"

    # --- Auth (used from Milestone 2 onward) ---
    jwt_secret: str = "dev-only-change-me-to-a-long-random-secret-min-32-bytes"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
