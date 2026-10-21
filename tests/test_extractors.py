"""Test suite for financial rule extractor, LLM narrative extractor, and GraphBuilder coordinator."""

import json
from unittest.mock import MagicMock

from src.db.graph.builder import GraphBuilder
from src.db.graph.extractors.financial_rule_extractor import (
    STANDARD_ACCOUNTING_RULES,
    FinancialRuleExtractor,
)
from src.db.graph.extractors.llm_extractor import LLMExtractor
from src.db.graph.store import GraphStore
from src.db.models.entities import (
    CausalDirection,
    CausalRelationType,
    DocumentMetadata,
    FinancialMetricNode,
    MetricUnit,
    StatementType,
    TableData,
    TextChunk,
)
from src.ingestion import IngestionResult
from src.reasoning.llm_client import LLMClient


def test_financial_rule_extractor_links_standard_accounting_items():
    """Verify FinancialRuleExtractor applies canonical accounting dependencies between matching metrics."""
    extractor = FinancialRuleExtractor()

    rev = FinancialMetricNode(
        node_id="m_rev",
        name="Revenue",
        normalized_key="revenue",
        value=2000.0,
        unit=MetricUnit.USD,
        period="2024",
        statement_type=StatementType.INCOME_STATEMENT,
        source_doc_id="doc1",
        source_page=10,
    )
    gm = FinancialMetricNode(
        node_id="m_gm",
        name="Gross Margin",
        normalized_key="gross_margin",
        value=800.0,
        unit=MetricUnit.USD,
        period="2024",
        statement_type=StatementType.INCOME_STATEMENT,
        source_doc_id="doc1",
        source_page=10,
    )
    opinc = FinancialMetricNode(
        node_id="m_opinc",
        name="Operating Income",
        normalized_key="operating_income",
        value=400.0,
        unit=MetricUnit.USD,
        period="2024",
        statement_type=StatementType.INCOME_STATEMENT,
        source_doc_id="doc1",
        source_page=10,
    )

    edges = extractor.extract([rev, gm, opinc])
    assert len(edges) >= 2

    # Revenue -> Gross Margin
    rev_to_gm = next((e for e in edges if e.source_node_id == "m_rev" and e.target_node_id == "m_gm"), None)
    assert rev_to_gm is not None
    assert rev_to_gm.relation_type == CausalRelationType.DRIVES
    assert rev_to_gm.direction == CausalDirection.DIRECT
    assert rev_to_gm.confidence == 1.0
    assert "Revenue directly drives Gross Margin" in rev_to_gm.evidence_text

    # Gross Margin -> Operating Income
    gm_to_op = next((e for e in edges if e.source_node_id == "m_gm" and e.target_node_id == "m_opinc"), None)
    assert gm_to_op is not None
    assert gm_to_op.relation_type == CausalRelationType.DRIVES


def test_financial_rule_extractor_ignores_different_periods():
    """Verify FinancialRuleExtractor does not link metrics from incompatible periods."""
    extractor = FinancialRuleExtractor()

    rev_2024 = FinancialMetricNode(
        node_id="m_rev_2024",
        name="Revenue",
        normalized_key="revenue",
        value=2000.0,
        unit=MetricUnit.USD,
        period="2024",
        statement_type=StatementType.INCOME_STATEMENT,
        source_doc_id="doc1",
        source_page=10,
    )
    gm_2023 = FinancialMetricNode(
        node_id="m_gm_2023",
        name="Gross Margin",
        normalized_key="gross_margin",
        value=700.0,
        unit=MetricUnit.USD,
        period="2023",
        statement_type=StatementType.INCOME_STATEMENT,
        source_doc_id="doc1",
        source_page=10,
    )

    edges = extractor.extract([rev_2024, gm_2023])
    assert len(edges) == 0


def test_llm_extractor_parses_json_and_extracts_causal_edges():
    """Verify LLMExtractor accurately extracts narrative causal edges from TextChunk."""
    mock_json = json.dumps([
        {
            "source_entity": "Supply Chain Inflation",
            "target_entity": "Gross Margin",
            "relationship_type": "IMPACTS",
            "direction": "inverse",
            "evidence_quote": "Supply chain disruption increased freight costs, reducing gross margin by 120 bps.",
            "confidence": 0.95,
        }
    ])

    mock_client = LLMClient.create_mock(f"```json\n{mock_json}\n```")
    extractor = LLMExtractor(llm_client=mock_client)

    chunk = TextChunk(
        chunk_id="chk_narrative_1",
        doc_id="doc_mda_1",
        page_number=22,
        text="Supply chain disruption increased freight costs, reducing gross margin by 120 bps.",
        metadata={"filename": "Annual_Report.pdf"},
    )

    disclosure, edges = extractor.extract_from_chunk(chunk, source_filename="Annual_Report.pdf")

    assert disclosure is not None
    assert "Supply Chain Inflation" in disclosure.topic
    assert disclosure.source_page == 22

    assert len(edges) == 1
    edge = edges[0]
    assert edge.source_node_id == "Supply Chain Inflation"
    assert edge.target_node_id == "Gross Margin"
    assert edge.relation_type == CausalRelationType.IMPACTS
    assert edge.direction == CausalDirection.INVERSE
    assert edge.confidence == 0.95
    assert edge.source_page == 22
    assert edge.source_filename == "Annual_Report.pdf"


def test_llm_extractor_handles_empty_or_malformed_json_gracefully():
    """Verify LLMExtractor handles invalid outputs without crashing."""
    mock_client = LLMClient.create_mock("Not valid JSON response")
    extractor = LLMExtractor(llm_client=mock_client)

    chunk = TextChunk(
        chunk_id="chk_err",
        doc_id="doc_err",
        page_number=1,
        text="Normal report text without causal relations.",
    )

    disclosure, edges = extractor.extract_from_chunk(chunk)
    assert disclosure is None
    assert edges == []


def test_graph_builder_coordinates_ingestion_and_extractors():
    """Verify GraphBuilder populates store and coordinates registered extractors."""
    mock_json = json.dumps([
        {
            "source_entity": "Raw Material Price Surge",
            "target_entity": "Cost of Goods Sold",
            "relationship_type": "DRIVES",
            "direction": "direct",
            "evidence_quote": "Higher resin prices drove cost of goods sold up 14%.",
            "confidence": 0.9,
        }
    ])
    mock_client = LLMClient.create_mock(mock_json)
    llm_extractor = LLMExtractor(llm_client=mock_client)
    rule_extractor = FinancialRuleExtractor()

    store = GraphStore.create(backend_type="networkx")
    builder = GraphBuilder(store=store, extractors=[rule_extractor, llm_extractor])

    table = TableData(
        table_id="tbl_builder",
        doc_id="doc_builder_1",
        page_number=8,
        title="Income Statement",
        headers=["Metric", "2024"],
        rows=[
            ["Revenue", "$1,000.00"],
            ["Cost of Goods Sold", "$600.00"],
            ["Gross Margin", "$400.00"],
        ],
        markdown="| Metric | 2024 |\n| Revenue | $1,000.00 |",
    )

    chunk = TextChunk(
        chunk_id="chk_builder_1",
        doc_id="doc_builder_1",
        page_number=15,
        text="Higher resin prices drove cost of goods sold up 14%.",
        metadata={"filename": "BuilderReport.pdf"},
    )

    ingest_result = IngestionResult(
        metadata=DocumentMetadata(
            doc_id="doc_builder_1",
            filename="BuilderReport.pdf",
            file_hash="hash_b1",
            total_pages=20,
            file_size_bytes=40000,
        ),
        pages=[],
        chunks=[chunk],
        tables=[table],
    )

    populated_store = builder.build(ingest_result, run_extractors=True)
    assert populated_store is store

    # Verify nodes and edges are populated
    stats = store.get_stats()
    assert stats["metric_nodes"] >= 3
    assert stats["disclosure_nodes"] >= 1
    assert stats["causal_edges"] >= 2
