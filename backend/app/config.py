"""App settings loaded from environment variables / .env. See .env.example."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    # Later files win, so backend/.env can override the shared repo-root .env.
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_DIR / ".env"),
        extra="ignore",
    )

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.1-flash-lite"
    database_url: str = ""
    stripe_secret_key: str = ""  # test mode only: sk_test_...
    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
