"""Application settings, loaded from environment variables (prefix FINPILOT_) or .env."""

from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FINPILOT_", env_file=".env", extra="ignore"
    )

    env: str = "dev"
    log_level: str = "INFO"
    scoring_config_path: Path = _REPO_ROOT / "config" / "scoring.yaml"
    provider_max_retries: int = 2
    provider_backoff_seconds: float = 0.5
    database_url: str = "sqlite:///./finpilot.db"
    openai_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("FINPILOT_OPENAI_API_KEY", "OPENAI_API_KEY")
    )
    openai_model: str = "gpt-4o-mini"
    openai_timeout_seconds: float = 30.0
    report_cache_ttl_hours: float = 24.0
    data_cache_ttl_hours: float = 24.0
