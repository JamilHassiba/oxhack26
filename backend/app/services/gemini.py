"""Gemini client. Owner: Alex."""

from functools import lru_cache

from google import genai

from app.config import get_settings


@lru_cache
def get_client() -> genai.Client:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=settings.gemini_api_key)
