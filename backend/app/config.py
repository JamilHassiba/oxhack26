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
    # Shared secret ElevenLabs sends as X-Tool-Secret on server-tool requests (required when set).
    elevenlabs_tool_secret: str = ""
    # How long request_payment_approval waits for the user's click before telling the voice agent "pending".
    payment_wait_seconds: float = 25.0
    cors_origins: list[str] = ["http://localhost:5173"]

    # Voice (Jamil). With no API key, start_call falls back to a practice run that dials nobody.
    elevenlabs_api_key: str = ""
    elevenlabs_agent_id: str = ""
    elevenlabs_phone_number_id: str = ""
    elevenlabs_webhook_secret: str = ""
    call_allowlist: str = ""  # comma-separated E.164 numbers; empty = any number from the contacts table


@lru_cache
def get_settings() -> Settings:
    return Settings()
