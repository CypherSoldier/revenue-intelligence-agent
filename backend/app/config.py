from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.6-flash"
    analytics_db_path: Path = BACKEND_DIR / "data" / "analytics.sqlite3"
    run_metadata_db_path: Path = BACKEND_DIR / "data" / "run-metadata.sqlite3"
    query_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    query_row_limit: int = Field(default=100, ge=1, le=1000)

    @model_validator(mode="after")
    def resolve_database_paths(self) -> "Settings":
        if not self.analytics_db_path.is_absolute():
            self.analytics_db_path = BACKEND_DIR / self.analytics_db_path
        if not self.run_metadata_db_path.is_absolute():
            self.run_metadata_db_path = BACKEND_DIR / self.run_metadata_db_path
        return self

    @property
    def gemini_configured(self) -> bool:
        return (
            self.gemini_api_key is not None
            and bool(self.gemini_api_key.get_secret_value().strip())
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
