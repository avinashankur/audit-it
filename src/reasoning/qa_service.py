"""Question answering orchestration service with both offline and live LLM grounding."""

import re
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

    # Extract metrics, causal paths, and excerpts mentioned in citations
    metric_citations = [c for c in citations if c.citation_type == CitationType.FINANCIAL_TABLE]
    path_citations = [c for c in citations if c.citation_type == CitationType.CAUSAL_PATH]
    chunk_citations = [c for c in citations if c.citation_type == CitationType.TEXT_EXCERPT]

    # Fallback to context_str if metric_citations is empty
    context_metrics: list[str] = []
    if not metric_citations and "Reported Financial Metrics:" in context_str:
        metric_section = context_str.split("Reported Financial Metrics:")[1]
        for line in metric_section.splitlines():
            line = line.strip()
            if line.startswith("- "):
                context_metrics.append(line[2:])
            elif line.startswith("[") or line.startswith("==="):
                break

    # Extract causal paths from context_str if present
    context_paths: list[str] = []
    if "Verified Causal Dependencies:" in context_str:
        path_section = context_str.split("Verified Causal Dependencies:")[1]
        for line in path_section.splitlines():
            line = line.strip()
            if line.startswith("- [Causal Path]:"):
                desc = line[len("- [Causal Path]:"):].strip()
                if desc:
                    context_paths.append(desc)
            elif line.startswith("[") or line.startswith("==="):
                break

    if not metric_citations and not context_metrics and not path_citations and not context_paths and not chunk_citations:
        return (
            f"No relevant evidence or verified disclosures found in the report for the query: \"{query}\".\n\n"
            "Please refine your question to reference specific financial line items, periods, or disclosure topics present in the document."
        )

    lines: list[str] = [
        f"Based on the financial report data ({page_list_str}), here is the verified audit analysis for your inquiry:\n"
    ]

    if metric_citations:
        lines.append("### 📊 Reported Financial Metrics")
        query_words = set(re.findall(r"\b[a-z]{3,}\b", query.lower())) if query else set()
        sorted_metrics = sorted(
            metric_citations,
            key=lambda c: 0 if any(w in c.snippet.lower() for w in query_words) else 1,
        )
        for m in sorted_metrics:
            lines.append(f"- **{m.snippet}** *[Source: Page {m.page_number}]*")
        lines.append("")
    elif context_metrics:
        lines.append("### 📊 Reported Financial Metrics")
        for m_str in context_metrics:
            lines.append(f"- **{m_str}**")
        lines.append("")

    if context_paths or path_citations:
        lines.append("### 🔗 Causal Dependencies & Drivers Identified")
        if context_paths:
            for path_desc in context_paths[:3]:
                lines.append(f"- **{path_desc}**")
                matching_cites = [
                    c for c in path_citations
                    if c.snippet and (
                        path_desc in c.snippet
                        or any(part in c.snippet for part in path_desc.split(" -> "))
                    )
                ]
                cites = matching_cites if matching_cites else path_citations
                seen_c = set()
                for c in cites[:3]:
                    c_key = (c.page_number, c.snippet)
                    if c_key in seen_c:
                        continue
                    seen_c.add(c_key)
                    page_str = f"Page {c.page_number}" if c.page_number > 0 else c.source_filename
                    ev_text = c.snippet
                    if ev_text.startswith(path_desc + ": "):
                        ev_text = ev_text[len(path_desc) + 2:].strip()
                    if ev_text and ev_text != path_desc:
                        lines.append(f"  - *[Source: {page_str}]* {ev_text}")
                    else:
                        lines.append(f"  - *[Source: {page_str}]*")
            lines.append("")
        else:
            for p in path_citations[:3]:
                page_str = f" *[Source: Page {p.page_number}]*" if p.page_number > 0 else ""
                lines.append(f"- **{p.snippet}**{page_str}")
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
