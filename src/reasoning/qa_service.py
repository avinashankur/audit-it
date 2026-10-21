"""Question answering orchestration service with both offline and live LLM grounding."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any
import uuid

from src.core.env import get_settings
from src.core.exceptions import LLMProviderError
from src.core.logging import get_logger, profile_stage
from src.db.models.entities import (
    AuditCitation,
    AuditQueryResponse,
)
from src.reasoning.llm_client import LLMClient
from src.reasoning.offline_engine import OfflineEngine, generate_offline_answer
from src.reasoning.prompts import AUDIT_SYSTEM_PROMPT, build_audit_prompt
from src.retrieval.context_builder import ContextBuilder

if TYPE_CHECKING:
    from src.retrieval.hybrid_retriever import HybridRetriever

logger = get_logger(__name__)

# Re-export generate_offline_answer for backwards compatibility with any existing imports
__all__ = ["QAService", "generate_offline_answer"]


class QAService:
    """Answers financial audit inquiries using hybrid retrieval, causal paths, and source citations."""

    def __init__(
        self,
        retriever: HybridRetriever | None = None,
        llm_client: LLMClient | None = None,
        offline_engine: OfflineEngine | None = None,
    ) -> None:
        if retriever is None:
            from src.retrieval.hybrid_retriever import HybridRetriever

            self.retriever = HybridRetriever()
        else:
            self.retriever = retriever
        self.llm_client = llm_client
        self.offline_engine = offline_engine or OfflineEngine()

    @profile_stage("qa_service_answer")
    def answer_query(
        self,
        query: str,
        provider: str = "Offline",
        api_key: str | None = None,
        model: str | None = None,
        top_k: int = 4,
    ) -> AuditQueryResponse:
        """Execute hybrid retrieval, assemble context, and synthesize an audit response."""
        start_time = time.perf_counter()

        # 1. Hybrid Retrieval
        ret_result = self.retriever.retrieve(query=query, top_k_chunks=top_k)

        # 2. Context & Citation Building
        context_str, citations = ContextBuilder.build_context(ret_result)

        # 3. Answer Generation (Deterministic Offline or Live BYOK LLM)
        answer_text: str
        provider_clean = (provider or "offline").strip().lower()
        is_offline_mode = provider_clean in ("offline", "offline grounded", "mock")

        # Resolve API key if not supplied in method call
        resolved_api_key = api_key
        if not resolved_api_key and not is_offline_mode:
            resolved_api_key = get_settings().get_api_key(provider_clean)

        # Allow an injected llm_client to satisfy the live-call condition even without a raw api_key string
        can_call_live = not is_offline_mode and (self.llm_client is not None or bool(resolved_api_key))

        if can_call_live:
            try:
                client = self.llm_client or LLMClient(
                    provider=provider_clean,
                    api_key=resolved_api_key,
                    model=model,
                )
                prompt = build_audit_prompt(query=query, context_str=context_str)
                generated_response = client.generate(
                    prompt=prompt,
                    system_prompt=AUDIT_SYSTEM_PROMPT,
                    model=model,
                )
                if generated_response and generated_response.strip():
                    answer_text = generated_response.strip()
                else:
                    answer_text = self.offline_engine.generate_answer(
                        query=query,
                        context_str=context_str,
                        citations=citations,
                        causal_paths=ret_result.causal_paths,
                    )
            except Exception as exc:
                logger.warning(
                    f"Live {provider} call encountered an error: {exc}. "
                    "Falling back to verified offline answer."
                )
                answer_text = (
                    f"*(Note: Live {provider} call encountered an error: {exc}. "
                    "Displaying verified local analysis)*\n\n"
                    + self.offline_engine.generate_answer(
                        query=query,
                        context_str=context_str,
                        citations=citations,
                        causal_paths=ret_result.causal_paths,
                    )
                )
        else:
            # Deterministic Offline Mode (Runs instantly with zero API keys or external network dependencies)
            answer_text = self.offline_engine.generate_answer(
                query=query,
                context_str=context_str,
                citations=citations,
                causal_paths=ret_result.causal_paths,
            )

        latency = (time.perf_counter() - start_time) * 1000.0

        return AuditQueryResponse(
            query_id=str(uuid.uuid4()),
            query_text=query,
            answer_text=answer_text,
            citations=citations,
            causal_paths=ret_result.causal_paths,
            retrieved_chunks=ret_result.text_chunks,
            latency_ms={"total": latency},
            model_provider=provider,
        )
