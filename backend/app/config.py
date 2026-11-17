"""App settings, read from environment variables and `.env` once at startup.

Like reading `process.env` in Node, except every value is typed and checked: a missing or invalid
setting stops the app at startup with a clear message, instead of failing in the middle of a
request. The full list and the reasons behind each default are in docs/BACKEND.md, section 10.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),  # the repo-root .env, or one next to the backend
        extra="ignore",  # .env also holds settings for docker compose (POSTGRES_*, WORKER_*)
        env_ignore_empty=True,  # `OPENAI_API_KEY=` in .env counts as "not set"
        # A settings error names the field but never prints values: pydantic would otherwise
        # echo the input, which can include API keys.
        hide_input_in_errors=True,
    )

    app_env: Literal["development", "production", "test"] = "development"
    app_version: str = "0.1.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Postgres. The default is the local `docker compose up -d db` database (POSTGRES_* defaults);
    # inside Docker, compose sets it to the `db` service.
    database_url: str = "postgresql://blundertrace:blundertrace@localhost:5432/blundertrace"

    # AI providers. Optional: without them the weakness cards use fixed glossary text.
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    main_model: str = "claude-haiku-5-5"
    fallback_model: str = "gpt-6-luna"
    embedding_model: str = "text-embedding-3-small"
    # USD per 1M tokens as (input, output), for the cost log. Checked 18 Nov 2026.
    model_prices: dict[str, tuple[float, float]] = {
        "claude-haiku-5-5": (0.10, 0.50),
        "gpt-6-luna": (0.10, 0.50),
        "text-embedding-3-small": (0.02, 0.0),
    }

    # Capacity and the engine. One worker = one Stockfish = one CPU core.
    workers: int = Field(default=2, ge=1, le=64)
    stockfish_path: str = "stockfish"
    engine_nodes: int = Field(default=100_000, ge=10_000, le=5_000_000)
    engine_hash_mb: int = Field(default=64, ge=16, le=1024)

    # Reports.
    report_reuse_minutes: int = Field(default=10, ge=0, le=1440)
    max_active_reports: int = Field(default=20, ge=1, le=1000)

    @field_validator("database_url")
    @classmethod
    def plain_postgres_url(cls, value: str) -> str:
        # Older .env files use SQLAlchemy's "postgresql+psycopg://" form; psycopg wants plain
        # "postgresql://". Accept both so an existing .env keeps working.
        value = value.replace("postgresql+psycopg://", "postgresql://", 1)
        if not value.startswith(("postgresql://", "postgres://")):
            raise ValueError("must start with postgresql://")
        return value


@lru_cache  # read the environment once, reuse the same object everywhere
def get_settings() -> Settings:
    return Settings()
