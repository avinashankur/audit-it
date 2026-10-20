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


def test_graph_store_subgraph_data_metric_names():
    """Verify that subgraph_data returns metric names rather than node kind labels."""
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
            name="Cost of Sales",
            normalized_key="cost_of_sales",
            value=60.0,
            unit=MetricUnit.USD,
            period="2023",
            statement_type=StatementType.INCOME_STATEMENT,
            source_doc_id="d1",
            source_page=1,
        )
    )

    data = store.get_subgraph_data()
    metric_names = [
        n["name"]
        for n in data["nodes"]
        if (n.get("node_type") == "METRIC" or n.get("label") == "METRIC") and n.get("name")
    ]
    assert "Revenue" in metric_names
    assert "Cost of Sales" in metric_names
    # Verify that 'label' in backend is 'METRIC', which is why app.py must read 'name'
    for n in data["nodes"]:
        assert n["label"] == "METRIC"


def test_graph_store_create_neo4j_passes_credentials(monkeypatch):
    """Verify that GraphStore.create passes configured Neo4j credentials from settings."""
    from unittest.mock import MagicMock

    monkeypatch.setenv("NEO4J_PASSWORD", "secret_pass")
    monkeypatch.setenv("NEO4J_URI", "bolt://custom:7687")
    monkeypatch.setenv("NEO4J_USER", "custom_user")

    mock_driver = MagicMock()
    monkeypatch.setattr("neo4j.GraphDatabase.driver", MagicMock(return_value=mock_driver))

    # Clear cached settings
    from src.core.env import get_settings
    get_settings.cache_clear()

    store = GraphStore.create(backend_type="neo4j")
    backend = store.backend
    assert backend.uri == "bolt://custom:7687"
    assert backend.user == "custom_user"
    assert backend.is_connected is True


def test_financial_unit_and_scale_preservation():
    """Verify that financial values preserve unit and scale without unconditionally appending '$' or 'M'."""
    from src.db.graph.store import parse_financial_cell
    from src.retrieval.context_builder import ContextBuilder
    from src.db.models.entities import HybridRetrievalResult

    # 1. Unscaled full dollar amount
    val1, unit1, scale1, sym1 = parse_financial_cell("$1,200,000")
    node1 = FinancialMetricNode(
        node_id="m1",
        name="Gross Revenue",
        normalized_key="gross_revenue",
        value=val1,
        unit=unit1,
        scale=scale1,
        currency_symbol=sym1,
        period="2023",
        source_doc_id="d1",
        source_page=1,
    )
    assert node1.format_value() == "$1,200,000"

    # 2. Scaled dollar amount from table context (in millions)
    val2, unit2, scale2, sym2 = parse_financial_cell(
        "1,200", table_title="Consolidated Statement of Income (in millions)"
    )
    node2 = FinancialMetricNode(
        node_id="m2",
        name="Net Sales",
        normalized_key="net_sales",
        value=val2,
        unit=unit2,
        scale=scale2,
        currency_symbol=sym2,
        period="2023",
        source_doc_id="d1",
        source_page=1,
    )
    assert node2.format_value() == "$1,200M"

    # 3. Percentage cell
    val3, unit3, scale3, sym3 = parse_financial_cell("45.2%")
    node3 = FinancialMetricNode(
        node_id="m3",
        name="Gross Margin Rate",
        normalized_key="gross_margin_rate",
        value=val3,
        unit=unit3,
        scale=scale3,
        currency_symbol=sym3,
        period="2023",
        source_doc_id="d1",
        source_page=1,
    )
    assert node3.format_value() == "45.2%"

    # 4. Basis points cell
    val4, unit4, scale4, sym4 = parse_financial_cell("150 bps")
    node4 = FinancialMetricNode(
        node_id="m4",
        name="Margin Expansion",
        normalized_key="margin_expansion",
        value=val4,
        unit=unit4,
        scale=scale4,
        currency_symbol=sym4,
        period="2023",
        source_doc_id="d1",
        source_page=1,
    )
    assert node4.format_value() == "150 bps"

    # 5. ContextBuilder formatting
    retrieval_result = HybridRetrievalResult(
        query="test",
        text_chunks=[],
        metric_nodes=[node1, node2, node3, node4],
        causal_paths=[],
    )
    context_str, _ = ContextBuilder.build_context(retrieval_result)
    assert "$1,200,000" in context_str
    assert "$1,200,000M" not in context_str
    assert "$1,200M" in context_str
    assert "45.2%" in context_str
    assert "$45M" not in context_str
    assert "150 bps" in context_str


def test_populate_from_ingestion_preserves_earlier_periods():
    """Verify comparative columns (e.g. 2024 and 2023) are all ingested and queryable."""
    store = GraphStore.create(backend_type="networkx")

    table = TableData(
        table_id="tbl_comp",
        doc_id="doc_multi_year",
        page_number=10,
        title="Consolidated Statements of Income",
        headers=["Metric", "2024", "2023"],
        rows=[
            ["Net Sales", "$1,200.00", "$1,000.00"],
            ["Cost of Sales", "$800.00", "$700.00"],
            ["Gross Margin", "$400.00", "$300.00"],
            ["Operating Income", "$250.00", "$200.00"],
        ],
        markdown="| Metric | 2024 | 2023 |\n| --- | --- | --- |\n| Net Sales | $1,200.00 | $1,000.00 |",
    )

    ingest_result = IngestionResult(
        metadata=DocumentMetadata(
            doc_id="doc_multi_year",
            filename="MultiYearReport.pdf",
            file_hash="hash_multi",
            total_pages=20,
            file_size_bytes=50000,
        ),
        pages=[],
        chunks=[],
        tables=[table],
    )

    stats = store.populate_from_ingestion(ingest_result)
    # 4 metrics * 2 periods = 8 metric nodes
    assert stats["metric_nodes"] == 8
    assert stats["total_nodes"] == 8
    assert stats["causal_edges"] >= 2

    # 1. Query for prior year (2023) specifically
    metrics_2023, paths_2023 = store.find_causal_neighborhood("What was the net sales for 2023?")
    assert len(metrics_2023) == 1
    assert metrics_2023[0].name == "Revenue"
    assert metrics_2023[0].period == "2023"
    assert metrics_2023[0].value == 1000.0

    # 2. Query for current year (2024) specifically
    metrics_2024, paths_2024 = store.find_causal_neighborhood("What was the net sales for 2024?")
    assert len(metrics_2024) == 1
    assert metrics_2024[0].name == "Revenue"
    assert metrics_2024[0].period == "2024"
    assert metrics_2024[0].value == 1200.0

    # 3. Query comparative years (2024 and 2023)
    metrics_comp, _ = store.find_causal_neighborhood("Compare net sales between 2024 and 2023")
    assert len(metrics_comp) == 2
    period_to_val = {m.period: m.value for m in metrics_comp}
    assert period_to_val["2024"] == 1200.0
    assert period_to_val["2023"] == 1000.0

    # 4. Causal paths for multi-metric queries in prior year
    metrics_prior_driver, paths_prior = store.find_causal_neighborhood(
        "How does net sales impact gross margin for 2023?",
        max_hops=2,
    )
    assert len(metrics_prior_driver) >= 2
    assert all(m.period == "2023" for m in metrics_prior_driver)
    assert len(paths_prior) >= 1
    assert "Revenue" in paths_prior[0].narrative_explanation
    assert "Gross Margin" in paths_prior[0].narrative_explanation

    # 5. Full date headers (e.g. "September 30, 2024" and "September 30, 2023")
    store_dates = GraphStore.create(backend_type="networkx")
    table_dates = TableData(
        table_id="tbl_dates",
        doc_id="doc_dates",
        page_number=5,
        title="Three Months Ended",
        headers=["Item", "September 30, 2024", "September 30, 2023"],
        rows=[
            ["Revenue", "$1,500.00", "$1,300.00"],
        ],
        markdown="| Item | September 30, 2024 | September 30, 2023 |\n| --- | --- | --- |",
    )
    store_dates.populate_from_ingestion(
        IngestionResult(
            metadata=DocumentMetadata(
                doc_id="doc_dates",
                filename="DatesReport.pdf",
                file_hash="hash_dates",
                total_pages=10,
                file_size_bytes=10000,
            ),
            pages=[],
            chunks=[],
            tables=[table_dates],
        )
    )
    res_2023, _ = store_dates.find_causal_neighborhood("What was the revenue in 2023?")
    assert len(res_2023) == 1
    assert res_2023[0].value == 1300.0
    assert "2023" in res_2023[0].period


def test_repeated_metrics_distinguished_by_report_period_and_table_scope():
    """Verify that repeated metric names across tables and reports do not overwrite each other."""
    store = GraphStore.create(backend_type="networkx")

    # Table 1: Consolidated Income Statement
    tbl_consolidated = TableData(
        table_id="tbl_consol",
        doc_id="report_q3",
        page_number=12,
        title="Consolidated Statements of Operations",
        headers=["Metric", "2024"],
        rows=[
            ["Net Sales", "$100,000.00"],
            ["Cost of Sales", "$60,000.00"],
            ["Gross Margin", "$40,000.00"],
        ],
        markdown="| Metric | 2024 |\n| --- | --- |\n| Net Sales | $100,000.00 |",
    )

    # Table 2: Segment Reporting (repeats 'Revenue' / 'Net Sales' but has no Gross Margin)
    tbl_segment = TableData(
        table_id="tbl_seg",
        doc_id="report_q3",
        page_number=28,
        title="Segment Information - Geographic Revenues",
        headers=["Metric", "2024"],
        rows=[
            ["Net Sales", "$25,000.00"],
            ["Operating Expenses", "$5,000.00"],
        ],
        markdown="| Metric | 2024 |\n| --- | --- |\n| Net Sales | $25,000.00 |",
    )

    ingest_result = IngestionResult(
        metadata=DocumentMetadata(
            doc_id="report_q3",
            filename="Q3Report.pdf",
            file_hash="hash_q3",
            total_pages=40,
            file_size_bytes=80000,
        ),
        pages=[],
        chunks=[],
        tables=[tbl_consolidated, tbl_segment],
    )

    store.populate_from_ingestion(ingest_result)

    # 1. Verify all matching node IDs are preserved (both consolidated and segment)
    rev_nodes = store.get_metric_nodes("Revenue")
    assert len(rev_nodes) == 2
    node_values = {n.value for n in rev_nodes}
    assert 100000.0 in node_values
    assert 25000.0 in node_values

    # 2. Scope by table title
    consol_rev = store.get_metric_nodes("Revenue", table_title="Consolidated")
    assert len(consol_rev) == 1
    assert consol_rev[0].value == 100000.0
    assert consol_rev[0].table_id == "tbl_consol"

    seg_rev = store.get_metric_nodes("Revenue", table_title="Segment")
    assert len(seg_rev) == 1
    assert seg_rev[0].value == 25000.0
    assert seg_rev[0].table_id == "tbl_seg"

    # 3. Scope by table ID
    assert len(store.get_metric_nodes("Revenue", table_id="tbl_consol")) == 1
    assert len(store.get_metric_nodes("Revenue", table_id="tbl_seg")) == 1

    # 4. Scope by report (doc_id)
    assert len(store.get_metric_nodes("Revenue", doc_id="report_q3")) == 2
    assert len(store.get_metric_nodes("Revenue", doc_id="unknown_report")) == 0

    # 5. Verify accounting links do NOT join values from different tables
    # Consolidated Revenue -> Consolidated Gross Margin MUST exist
    consol_rev_id = consol_rev[0].node_id
    consol_gm = store.get_metric_nodes("Gross Margin", table_id="tbl_consol")[0]
    consol_paths = store.backend.find_paths(consol_rev_id, consol_gm.node_id)
    assert len(consol_paths) >= 1

    # Segment Revenue -> Consolidated Gross Margin MUST NOT exist
    seg_rev_id = seg_rev[0].node_id
    cross_table_paths = store.backend.find_paths(seg_rev_id, consol_gm.node_id)
    assert len(cross_table_paths) == 0

    # 6. Scoped resolution
    assert store._resolve_id("Revenue", table_title="Consolidated") == consol_rev_id
    assert store._resolve_id("Revenue", table_title="Segment") == seg_rev_id


def test_driver_questions_search_incoming_links_and_honor_max_hops():
    """Verify that driver queries search incoming causal links and honor max_hops depth."""
    store = GraphStore.create(backend_type="networkx")

    table = TableData(
        table_id="tbl_chain",
        doc_id="doc_chain",
        page_number=1,
        title="Consolidated Statements of Operations",
        headers=["Metric", "2024"],
        rows=[
            ["Net Sales", "$1,000.00"],
            ["Cost of Sales", "$600.00"],
            ["Gross Margin", "$400.00"],
            ["Operating Income", "$250.00"],
            ["Net Income", "$200.00"],
        ],
        markdown="| Metric | 2024 |\n| --- | --- |",
    )

    store.populate_from_ingestion(
        IngestionResult(
            metadata=DocumentMetadata(
                doc_id="doc_chain",
                filename="ChainReport.pdf",
                file_hash="hash_chain",
                total_pages=5,
                file_size_bytes=10000,
            ),
            pages=[],
            chunks=[],
            tables=[table],
        )
    )

    # 1. Asking what drives Gross Margin MUST return Revenue and Cost of Sales (incoming drivers)
    # and MUST NOT return Operating Income (downstream consequence)
    _, driver_paths = store.find_causal_neighborhood("What drives gross margin?", max_hops=1)
    assert len(driver_paths) >= 2
    driver_sources = {p.source_node_name for p in driver_paths}
    driver_targets = {p.target_node_name for p in driver_paths}

    assert "Revenue" in driver_sources
    assert "Cost of Sales" in driver_sources
    assert "Operating Income" not in driver_sources
    assert driver_targets == {"Gross Margin"}

    # 2. Asking about impacts MUST return downstream consequence (Operating Income)
    _, impact_paths = store.find_causal_neighborhood("What does gross margin impact?", max_hops=1)
    assert len(impact_paths) >= 1
    assert any(p.target_node_name == "Operating Income" for p in impact_paths)
    assert not any(p.target_node_name == "Revenue" for p in impact_paths)

    # 3. Depth honoring: what drives Net Income with max_hops=1 vs max_hops=2 vs max_hops=3
    # 1 hop: Operating Income -> Net Income
    _, hops_1_paths = store.find_causal_neighborhood("What drives net income?", max_hops=1)
    assert len(hops_1_paths) == 1
    assert hops_1_paths[0].source_node_name == "Operating Income"
    assert hops_1_paths[0].target_node_name == "Net Income"

    # 2 hops: Operating Income -> Net Income AND Gross Margin -> Operating Income -> Net Income
    _, hops_2_paths = store.find_causal_neighborhood("What drives net income?", max_hops=2)
    assert len(hops_2_paths) >= 2
    h2_sources = {p.source_node_name for p in hops_2_paths}
    assert "Operating Income" in h2_sources
    assert "Gross Margin" in h2_sources
    assert "Revenue" not in h2_sources  # Revenue is 3 hops away

    # 3 hops: reaches Revenue -> Gross Margin -> Operating Income -> Net Income
    _, hops_3_paths = store.find_causal_neighborhood("What drives net income?", max_hops=3)
    assert len(hops_3_paths) >= 3
    h3_sources = {p.source_node_name for p in hops_3_paths}
    assert "Revenue" in h3_sources


def test_graph_store_rebuilds_index_from_persisted_backend():
    """Verify that a new GraphStore or HybridRetriever wrapping an already populated backend rebuilds indexes."""
    from src.db.graph.storage.networkx_store import NetworkXBackend
    from src.retrieval.hybrid_retriever import HybridRetriever
    from src.retrieval.vector_store import VectorStore

    backend = NetworkXBackend()
    store1 = GraphStore(backend=backend)

    rev_node = FinancialMetricNode(
        node_id="m_rev",
        name="Revenue",
        normalized_key="revenue",
        value=1500000.0,
        unit=MetricUnit.USD,
        scale="M",
        currency_symbol="$",
        period="2024",
        statement_type=StatementType.INCOME_STATEMENT,
        source_doc_id="doc_persisted",
        source_page=3,
        table_id="tbl_inc",
        table_title="Consolidated Statement of Operations",
    )
    gm_node = FinancialMetricNode(
        node_id="m_gm",
        name="Gross Margin",
        normalized_key="gross_margin",
        value=600000.0,
        unit=MetricUnit.USD,
        scale="M",
        currency_symbol="$",
        period="2024",
        statement_type=StatementType.INCOME_STATEMENT,
        source_doc_id="doc_persisted",
        source_page=3,
        table_id="tbl_inc",
        table_title="Consolidated Statement of Operations",
    )

    store1.add_metric_node(rev_node)
    store1.add_metric_node(gm_node)
    store1.add_causal_edge(
        CausalRelationshipEdge(
            edge_id="e_rev_gm",
            source_node_id=rev_node.node_id,
            target_node_id=gm_node.node_id,
            relation_type=CausalRelationType.DRIVES,
            direction=CausalDirection.DIRECT,
            confidence=1.0,
            evidence_text="Revenue increases gross margin.",
            source_page=3,
        )
    )

    # Now create a brand new GraphStore instance wrapping the same persisted backend
    store2 = GraphStore(backend=backend)

    # Check that in-memory indexes and caches were rebuilt upon initialization
    assert len(store2._name_map) > 0
    assert len(store2._metric_nodes_by_name) > 0
    assert "revenue" in store2._metric_nodes_by_name
    assert "gross margin" in store2._metric_nodes_by_name

    # Check ID resolution
    assert store2._resolve_id("Revenue") == "m_rev"
    assert store2._resolve_id("Gross Margin") == "m_gm"

    # Check get_metric_nodes retrieval
    retrieved_metrics = store2.get_metric_nodes("Revenue")
    assert len(retrieved_metrics) == 1
    assert retrieved_metrics[0].node_id == "m_rev"
    assert retrieved_metrics[0].value == 1500000.0
    assert retrieved_metrics[0].scale == "M"

    # Check find_causal_neighborhood returns metric nodes and causal paths
    matched_nodes, causal_paths = store2.find_causal_neighborhood(
        "How does revenue impact gross margin in 2024?",
        max_hops=2,
    )
    assert len(matched_nodes) == 2
    matched_names = {m.name for m in matched_nodes}
    assert "Revenue" in matched_names
    assert "Gross Margin" in matched_names
    assert len(causal_paths) >= 1
    assert causal_paths[0].source_node_name == "Revenue"
    assert causal_paths[0].target_node_name == "Gross Margin"

    # Check passing populated backend to HybridRetriever
    vec_store = VectorStore()
    vec_store.add_chunks([
        TextChunk(
            chunk_id="c_persisted",
            doc_id="doc_persisted",
            page_number=3,
            text="Revenue growth in 2024 significantly improved gross margin across all segments.",
        )
    ])
    retriever = HybridRetriever(vector_store=vec_store, graph_store=backend)
    result = retriever.retrieve("How does revenue impact gross margin in 2024?")

    assert len(result.metric_nodes) >= 2
    assert len(result.causal_paths) >= 1
    assert result.causal_paths[0].source_node_name == "Revenue"
    assert result.causal_paths[0].target_node_name == "Gross Margin"

