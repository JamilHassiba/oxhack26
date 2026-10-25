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
    call_number: str = ""  # E.164: every call rings this phone, whatever business the user names
    # The Twilio account behind the ElevenLabs phone number. Only used by the Hang up button.
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    # Google Calendar: a service account's JSON key file, and the calendar shared with it (usually your Gmail
    # address). Both empty = the calendar tool can't add events.
    google_service_account_file: str = ""
    google_calendar_id: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
