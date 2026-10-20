
import uuid

from src.core.logging import get_logger
from src.db.models.entities import (
    AuditCitation,
    CitationType,
    HybridRetrievalResult,
)

logger = get_logger(__name__)


class ContextBuilder:

    @staticmethod
    def build_context(
        result: HybridRetrievalResult,
        max_chunk_chars: int = 2000,
    ) -> tuple[str, list[AuditCitation]]:
        
        sections: list[str] = ["=== VERIFIED AUDIT CONTEXT ==="]
        citations: list[AuditCitation] = []

        if result.causal_paths or result.metric_nodes:
            sections.append("\n[KNOWLEDGE GRAPH: CAUSAL PATHS & FINANCIAL METRICS]")

            if result.causal_paths:
                sections.append("Verified Causal Dependencies:")
                for p in result.causal_paths:
                    sections.append(f"- [Causal Path]: {p.narrative_explanation}")
                    citations.append(
                        AuditCitation(
                            citation_id=str(uuid.uuid4()),
                            source_doc_id="knowledge_graph",
                            source_filename="Knowledge Graph",
                            page_number=1,
                            citation_type=CitationType.CAUSAL_PATH,
                            snippet=p.narrative_explanation,
                            relevance_score=1.0,
                        )
                    )

            if result.metric_nodes:
                sections.append("\nReported Financial Metrics:")
                for m in result.metric_nodes:
                    val_str = f"${m.value:,.0f}M" if isinstance(m.value, (int, float)) else str(m.value)
                    sections.append(f"- {m.name}: {val_str} (Period: {m.period}, Page {m.source_page})")

        if result.text_chunks:
            sections.append("\n[VERIFIED REPORT EXCERPTS]")
            for c in result.text_chunks:
                header_part = f" | {c.section_header}" if c.section_header else ""
                clean_text = c.text[:max_chunk_chars].strip()
                sections.append(f"\n[Source: Page {c.page_number}{header_part}]:\n\"{clean_text}\"")

                citations.append(
                    AuditCitation(
                        citation_id=str(uuid.uuid4()),
                        source_doc_id=c.doc_id,
                        source_filename=c.metadata.get("filename", "Report.pdf"),
                        page_number=c.page_number,
                        citation_type=CitationType.TEXT_EXCERPT,
                        snippet=clean_text[:200] + ("..." if len(clean_text) > 200 else ""),
                        relevance_score=result.rrf_scores.get(c.chunk_id, 0.5),
                    )
                )

        if len(sections) == 1:
            sections.append("No directly matching report excerpts or graph metrics found.")

        context_str = "\n".join(sections)
        return context_str, citations
