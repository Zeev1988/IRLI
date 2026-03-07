"""
Shared LLM client for extraction and discovery.

Supports OpenAI (gpt-4o-mini) and Gemini (gemini-1.5-flash) via LLM_PROVIDER env var.
Only configured when DEBUG_MODE is false.
"""
import os
from typing import Any

from app.config import DEBUG_MODE

_PROVIDER: str = "debug"
_MODEL: str = "stub"
_client: Any = None


def _init_client() -> None:
    global _PROVIDER, _MODEL, _client
    if _client is not None:
        return
    if DEBUG_MODE:
        _PROVIDER = "debug"
        _MODEL = "stub"
        _client = None
        return

    import instructor
    from openai import AsyncOpenAI
    import google.generativeai as genai

    _PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()

    if _PROVIDER == "gemini":
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        gemini_model = genai.GenerativeModel("gemini-1.5-flash")
        _client = instructor.from_gemini(
            client=gemini_model,
            mode=instructor.Mode.GEMINI_JSON,
        )
        _MODEL = "gemini-1.5-flash"
    else:
        raw = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
        _client = instructor.from_openai(raw)
        _MODEL = "gpt-4o-mini"


def get_client_and_model() -> tuple[Any, str]:
    """
    Return (instructor client, model name). Lazy-init on first call.
    In DEBUG_MODE, returns (None, "stub") — callers must check before use.
    """
    _init_client()
    return _client, _MODEL


def get_provider() -> str:
    """Return current provider name (openai, gemini, or debug)."""
    _init_client()
    return _PROVIDER
