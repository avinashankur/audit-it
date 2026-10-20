"""Test suite for the deep GraphStore module."""

from src.db.graph.store import GraphStore
from src.db.models.entities import (
    CausalDirection,
    CausalRelationshipEdge,
    CausalRelationType,
    DocumentMetadata,
    FinancialMetricNode,
    MetricUnit,
    StatementType,
    TableData,
    TextChunk,
)
from src.ingestion import IngestionResult


def test_graph_store_factory_and_entity_matching():
    """Verify GraphStore creation, entity matching, and alias resolution."""
    store = GraphStore.create(backend_type="networkx")

    node = FinancialMetricNode(
        node_id="m1",
        name="Revenue",
        normalized_key="revenue",
        value=5000000.0,
        unit=MetricUnit.USD,
        period="2023",
        statement_type=StatementType.INCOME_STATEMENT,
        source_doc_id="doc-123",
        source_page=12,
    )
    store.add_metric_node(node)

    # Test alias resolution
    assert store._resolve_id("Revenue") == "m1"
    assert store._resolve_id("revenue") == "m1"

    # Test neighborhood retrieval by query string
    metrics, paths = store.find_causal_neighborhood("What was the net revenue for 2023?")
    assert len(metrics) == 1
    assert metrics[0].name == "Revenue"
    assert metrics[0].value == 5000000.0


def test_graph_store_populate_from_ingestion():
    """Verify domain rules and graph population from IngestionResult."""
    store = GraphStore.create(backend_type="networkx")

    table = TableData(
        table_id="tbl_1",
        doc_id="doc_abc",
        page_number=15,
        title="Consolidated Statements of Income",
        headers=["Metric", "2023"],
        rows=[
            ["Net Sales", "$1,200.00"],
            ["Cost of Sales", "$800.00"],
            ["Gross Margin", "$400.00"],
            ["Operating Income", "$250.00"],
        ],
        markdown="| Metric | 2023 |\n| --- | --- |\n| Net Sales | $1,200.00 |",
    )

    chunk = TextChunk(
        chunk_id="chk_1",
        doc_id="doc_abc",
        page_number=16,
        text="Gross margin expanded by 150 bps due to favorable product mix and higher sales.",
        char_count=82,
        token_estimate=20,
    )

    ingest_result = IngestionResult(
        metadata=DocumentMetadata(
            doc_id="doc_abc",
            filename="AuditReport.pdf",
            file_hash="hash123",
            total_pages=20,
            file_size_bytes=50000,
        ),
        pages=[],
        chunks=[chunk],
        tables=[table],
    )

    stats = store.populate_from_ingestion(ingest_result)
    assert stats["total_nodes"] >= 4
    assert stats["causal_edges"] >= 2  # Accounting rules (Revenue -> Gross Margin, etc.)

    # Query causal chain
    matched_metrics, causal_paths = store.find_causal_neighborhood(
        "How does net sales impact gross margin?",
        max_hops=2,
    )
    assert len(matched_metrics) >= 2
    metric_names = {m.name for m in matched_metrics}
    assert "Revenue" in metric_names
    assert "Gross Margin" in metric_names
    assert len(causal_paths) >= 1


def test_graph_store_to_mermaid():
    """Verify Mermaid diagram definition generation."""
    store = GraphStore.create(backend_type="networkx")
    store.add_metric_node(
        FinancialMetricNode(
            node_id="n1",
            name="Revenue",
            normalized_key="revenue",
            value=100.0,
            unit=MetricUnit.USD,
            period="2023",
            statement_type=StatementType.INCOME_STATEMENT,
            source_doc_id="d1",
            source_page=1,
        )
    )
    store.add_metric_node(
        FinancialMetricNode(
            node_id="n2",
            name="Gross Margin",
            normalized_key="gross_margin",
            value=40.0,
            unit=MetricUnit.USD,
            period="2023",
            statement_type=StatementType.INCOME_STATEMENT,
            source_doc_id="d1",
            source_page=1,
        )
    )
    store.add_causal_edge(
        CausalRelationshipEdge(
            edge_id="e1",
            source_node_id="Revenue",
            target_node_id="Gross Margin",
            relation_type=CausalRelationType.DRIVES,
            direction=CausalDirection.DIRECT,
            confidence=1.0,
            evidence_text="Top-line drives margin",
            source_page=1,
        )
    )

    mermaid_code = store.to_mermaid(root_node="Revenue", hops=1)
    assert "graph TD" in mermaid_code
    assert "Revenue" in mermaid_code
    assert "Gross Margin" in mermaid_code
