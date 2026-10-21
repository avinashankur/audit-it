
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

        fallback_filename = None
        for c in result.text_chunks:
            if c.metadata and c.metadata.get("filename"):
                fallback_filename = c.metadata["filename"]
                break

        if result.causal_paths or result.metric_nodes:
            sections.append("\n[KNOWLEDGE GRAPH: CAUSAL PATHS & FINANCIAL METRICS]")

            if result.causal_paths:
                sections.append("Verified Causal Dependencies:")
                for p in result.causal_paths:
                    sections.append(f"- [Causal Path id={p.path_id}]: {p.narrative_explanation}")

                    doc_id = p.source_doc_id or "knowledge_graph"
                    filename = (
                        p.source_filename
                        or fallback_filename
                        or (f"Page {p.source_page}" if p.source_page else "Knowledge Graph")
                    )
                    pages = p.source_pages if p.source_pages else ([p.source_page] if p.source_page else [1])

                    for pg in pages:
                        ev_text = (
                            p.page_evidence_map.get(pg)
                            or p.evidence_text
                        )
                        snippet_text = (
                            f"{p.narrative_explanation}: {ev_text}"
                            if ev_text and ev_text not in p.narrative_explanation
                            else (ev_text or p.narrative_explanation)
                        )
                        citations.append(
                            AuditCitation(
                                citation_id=str(uuid.uuid4()),
                                source_doc_id=doc_id,
                                source_filename=filename,
                                page_number=pg,
                                citation_type=CitationType.CAUSAL_PATH,
                                snippet=snippet_text,
                                relevance_score=1.0,
                                path_id=p.path_id,
                            )
                        )

            if result.metric_nodes:
                sections.append("\nReported Financial Metrics:")
                for m in result.metric_nodes:
                    val_str = (
                        m.format_value()
                        if hasattr(m, "format_value")
                        else (str(m.value) if m.value is not None else "N/A")
                    )
                    table_str = f", Table: {m.table_title}" if getattr(m, "table_title", None) else ""
                    sections.append(f"- {m.name}: {val_str} (Period: {m.period}{table_str}, Page {m.source_page})")

                    m_filename = (
                        getattr(m, "source_filename", None)
                        or fallback_filename
                        or (f"Page {m.source_page}" if m.source_page else "Financial Report")
                    )
                    m_doc_id = getattr(m, "source_doc_id", None) or "financial_table"
                    snippet = f"{m.name}: {val_str} (Period: {m.period}{table_str})"

                    citations.append(
                        AuditCitation(
                            citation_id=str(uuid.uuid4()),
                            source_doc_id=m_doc_id,
                            source_filename=m_filename,
                            page_number=m.source_page,
                            citation_type=CitationType.FINANCIAL_TABLE,
                            snippet=snippet,
                            relevance_score=1.0,
                        )
                    )

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
