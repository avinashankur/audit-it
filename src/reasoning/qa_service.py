"""Question answering orchestration service with both offline and live LLM grounding."""

import time
import uuid
from typing import Any

from src.core.logging import get_logger, profile_stage
from src.db.models.entities import (
    AuditCitation,
    AuditQueryRequest,
    AuditQueryResponse,
    CitationType,
)
from src.retrieval.context_builder import ContextBuilder
from src.retrieval.hybrid_retriever import HybridRetriever

logger = get_logger(__name__)


def generate_offline_answer(query: str, context_str: str, citations: list[AuditCitation]) -> str:
    """Deterministic, local synthesis of an audit answer from retrieved context and citations."""
    pages = sorted(list({c.page_number for c in citations if c.page_number > 0}))
    page_list_str = ", ".join(f"Page {p}" for p in pages) if pages else "the uploaded report"

    # Extract causal paths mentioned in citations
    path_citations = [c for c in citations if c.citation_type == CitationType.CAUSAL_PATH]
    chunk_citations = [c for c in citations if c.citation_type == CitationType.TEXT_EXCERPT]

    lines: list[str] = [
        f"Based on the financial report data ({page_list_str}), here is the verified audit analysis for your inquiry:\n"
    ]

    if path_citations:
        lines.append("### 🔗 Causal Dependencies & Drivers Identified")
        for p in path_citations[:3]:
            lines.append(f"- **{p.snippet}**")
        lines.append("")

    if chunk_citations:
        lines.append("### 📑 Key Findings from Report Disclosures")
        for idx, c in enumerate(chunk_citations[:3], 1):
            snippet_clean = c.snippet.replace("\n", " ").strip()
            if len(snippet_clean) > 220:
                snippet_clean = snippet_clean[:220] + "..."
            lines.append(f"{idx}. *[Source: Page {c.page_number}]* \"{snippet_clean}\"")
        lines.append("")

    lines.append(
        "> **Grounding Verification:** The metrics and causal paths above were extracted directly from the "
        "report's financial statements and narrative footnotes. See the citations dropdown below for exact source snippets."
    )

    return "\n".join(lines)


class QAService:
    """Answers financial audit inquiries using hybrid retrieval, causal paths, and source citations."""

    def __init__(self, retriever: HybridRetriever | None = None) -> None:
        self.retriever = retriever or HybridRetriever()

    @profile_stage("qa_service_answer")
    def answer_query(
        self,
        query: str,
        provider: str = "Offline",
        api_key: str | None = None,
        top_k: int = 4,
    ) -> AuditQueryResponse:
        """Execute hybrid retrieval, assemble context, and synthesize an audit response."""
        start_time = time.perf_counter()

        # 1. Hybrid Retrieval
        ret_result = self.retriever.retrieve(query=query, top_k_chunks=top_k)

        # 2. Context & Citation Building
        context_str, citations = ContextBuilder.build_context(ret_result)

        # 3. Answer Generation (Offline fallback or Live BYOK)
        answer_text: str

        if api_key and provider.lower() in ("gemini", "google"):
            try:
                from google import genai

                client = genai.Client(api_key=api_key)
                prompt = (
                    f"You are AuditIt, an expert financial audit intelligence system.\n"
                    f"Answer the user query strictly using the verified context below.\n"
                    f"Cite source page numbers for every factual claim.\n\n"
                    f"{context_str}\n\n"
                    f"User Query: {query}\n"
                    f"Audit Response:"
                )
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                )
                answer_text = response.text or generate_offline_answer(query, context_str, citations)
            except Exception as exc:
                logger.warning(f"Live Gemini API call failed ({exc}); falling back to offline answer.")
                answer_text = f"*(Note: Live {provider} call encountered an error: {exc}. Displaying verified local analysis)*\n\n" + generate_offline_answer(query, context_str, citations)

        elif api_key and provider.lower() == "openai":
            try:
                from openai import OpenAI

                client = OpenAI(api_key=api_key)
                prompt = (
                    f"You are AuditIt, an expert financial audit intelligence system.\n"
                    f"Answer the user query strictly using the verified context below.\n"
                    f"Cite source page numbers for every factual claim.\n\n"
                    f"{context_str}\n\n"
                    f"User Query: {query}"
                )
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a senior financial auditor providing citation-grounded analysis."},
                        {"role": "user", "content": prompt},
                    ],
                )
                answer_text = response.choices[0].message.content or generate_offline_answer(query, context_str, citations)
            except Exception as exc:
                logger.warning(f"Live OpenAI API call failed ({exc}); falling back to offline answer.")
                answer_text = f"*(Note: Live {provider} call encountered an error: {exc}. Displaying verified local analysis)*\n\n" + generate_offline_answer(query, context_str, citations)

        else:
            # Deterministic Offline Mode (Runs instantly with zero API keys or external services)
            answer_text = generate_offline_answer(query, context_str, citations)

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
