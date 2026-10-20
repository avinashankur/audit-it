"""Test suite for HybridRetriever with deep GraphStore module."""

from src.db.graph.store import GraphStore
from src.db.models.entities import (
    CausalDirection,
    CausalRelationshipEdge,
    CausalRelationType,
    FinancialMetricNode,
    MetricUnit,
    StatementType,
    TextChunk,
)
from src.retrieval.hybrid_retriever import HybridRetriever
from src.retrieval.vector_store import VectorStore


def test_hybrid_retriever_clean_seam():
    """Verify retriever obtains both text chunks and causal paths via GraphStore without leaking internals."""
    graph_store = GraphStore.create(backend_type="networkx")

    # Add metrics
    graph_store.add_metric_node(
        FinancialMetricNode(
            node_id="n_rev",
            name="Revenue",
            normalized_key="revenue",
            value=1000.0,
            unit=MetricUnit.USD,
            period="2023",
            statement_type=StatementType.INCOME_STATEMENT,
            source_doc_id="doc1",
            source_page=5,
        )
    )
    graph_store.add_metric_node(
        FinancialMetricNode(
            node_id="n_gm",
            name="Gross Margin",
            normalized_key="gross_margin",
            value=450.0,
            unit=MetricUnit.USD,
            period="2023",
            statement_type=StatementType.INCOME_STATEMENT,
            source_doc_id="doc1",
            source_page=5,
        )
    )
    graph_store.add_causal_edge(
        CausalRelationshipEdge(
            edge_id="e_rev_gm",
            source_node_id="Revenue",
            target_node_id="Gross Margin",
            relation_type=CausalRelationType.DRIVES,
            direction=CausalDirection.DIRECT,
            confidence=1.0,
            evidence_text="Revenue directly drives gross margin",
            source_page=5,
        )
    )

    vec_store = VectorStore()
    vec_store.add_chunks([
        TextChunk(
            chunk_id="c1",
            doc_id="doc1",
            page_number=5,
            text="Revenue increased primarily due to strong beverage sales in North America.",
            char_count=73,
            token_estimate=15,
        )
    ])

    retriever = HybridRetriever(vector_store=vec_store, graph_store=graph_store)
    result = retriever.retrieve("How did revenue growth drive gross margin?")

    assert len(result.text_chunks) >= 1
    assert len(result.metric_nodes) >= 2
    assert len(result.causal_paths) >= 1
    assert "Revenue" in result.causal_paths[0].narrative_explanation
    assert "Gross Margin" in result.causal_paths[0].narrative_explanation
