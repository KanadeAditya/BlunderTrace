"""App configuration, read from environment variables (and .env) once at startup.

Like reading process.env in Node, but every value is typed and validated: a missing or invalid
required setting stops the app immediately with a clear error instead of failing mid-request.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    app_env: str = "development"
    app_version: str = "0.1.0"


@lru_cache  # read the environment once, reuse the same object everywhere
def get_settings() -> Settings:
    return Settings()
