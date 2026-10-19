"""Session state management for the Streamlit application."""

from typing import Any
import streamlit as st


def init_session_state() -> None:
    """Initialize default session state keys if they do not exist."""
    defaults: dict[str, Any] = {
        "messages": [
            {
                "role": "assistant",
                "content": "Welcome to AuditIt. Upload a financial report (10-K, annual report) or ask questions about financial metrics, ratios, and causal dependencies.",
                "citations": [],
            }
        ],
        "ingested_documents": [],
        "current_document": None,
        "graph_stats": {
            "total_nodes": 0,
            "metric_nodes": 0,
            "disclosure_nodes": 0,
            "causal_edges": 0,
        },
        "selected_provider": "Gemini",
        "graph_backend": "NetworkX (In-Memory)",
    }

    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def add_message(role: str, content: str, citations: list[dict[str, Any]] | None = None) -> None:
    """Append a new message to the conversation history."""
    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    st.session_state["messages"].append(
        {
            "role": role,
            "content": content,
            "citations": citations or [],
        }
    )


def clear_chat() -> None:
    """Reset the chat history."""
    st.session_state["messages"] = [
        {
            "role": "assistant",
            "content": "Chat history cleared. How can I assist with your financial audit today?",
            "citations": [],
        }
    ]
