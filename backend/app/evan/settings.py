"""Additive service settings; no edits to Alex's shared config are needed."""

from functools import lru_cache
from pathlib import Path
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class EvanSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT.parent / ".env", ROOT / ".env"), extra="ignore"
    )
    database_url: SecretStr = SecretStr("")
    resend_api_key: SecretStr = SecretStr("")
    email_from: str = ""


@lru_cache
def get_settings():
    return EvanSettings()
