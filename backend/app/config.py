from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
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

    @property
    def gemini_configured(self) -> bool:
        return (
            self.gemini_api_key is not None
            and bool(self.gemini_api_key.get_secret_value().strip())
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
