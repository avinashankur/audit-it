"""FastAPI dependencies for AuditIt API."""

from __future__ import annotations

from typing import Annotated
import uuid

from fastapi import Header, Request, Response

from src.api.session_mgr import SessionManager, get_session_manager


def get_llm_provider(
    x_llm_provider: Annotated[str | None, Header()] = None,
) -> str | None:
    """Extract LLM provider from X-LLM-Provider header."""
    if x_llm_provider and x_llm_provider.strip():
        return x_llm_provider.strip()
    return None


def get_llm_api_key(
    x_llm_key: Annotated[str | None, Header()] = None,
) -> str | None:
    """Extract BYOK API key from X-LLM-Key header."""
    return x_llm_key


def get_session_id(
    request: Request,
    response: Response,
    x_session_id: Annotated[str | None, Header()] = None,
) -> str:
    """Resolve browser session or user ID from header or cookie, minting and setting one if absent."""
    # 1. Header takes precedence (for programmatic API callers or explicit SPA clients)
    if x_session_id and x_session_id.strip():
        session_id = x_session_id.strip()
    else:
        # 2. Cookie fallback (for browser clients)
        cookie_val = request.cookies.get("auditit_session_id")
        if cookie_val and cookie_val.strip():
            session_id = cookie_val.strip()
        else:
            # 3. Mint new session ID
            session_id = str(uuid.uuid4())

    response.set_cookie(
        key="auditit_session_id",
        value=session_id,
        httponly=True,
        samesite="lax",
        path="/",
    )
    response.headers["X-Session-ID"] = session_id
    return session_id
