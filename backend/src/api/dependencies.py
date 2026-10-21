"""FastAPI dependencies for AuditIt API."""

from __future__ import annotations

from typing import Annotated

from fastapi import Header

from src.api.session_mgr import SessionManager, get_session_manager


def get_llm_provider(
    x_llm_provider: Annotated[str | None, Header()] = None,
) -> str:
    """Extract LLM provider from X-LLM-Provider header, defaulting to Offline Grounded."""
    return x_llm_provider or "Offline Grounded"


def get_llm_api_key(
    x_llm_key: Annotated[str | None, Header()] = None,
) -> str | None:
    """Extract BYOK API key from X-LLM-Key header."""
    return x_llm_key
