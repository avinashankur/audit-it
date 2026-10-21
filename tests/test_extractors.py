"""Test suite for financial rule extractor, LLM narrative extractor, and GraphBuilder coordinator."""

import json
from unittest.mock import MagicMock
import pytest

from src.db.graph.builder import GraphBuilder
from src.db.graph.extractors.base import BaseExtractor
from src.db.graph.extractors.financial_rule_extractor import (
    STANDARD_ACCOUNTING_RULES,
    FinancialRuleExtractor,
)
from src.db.graph.extractors.llm_extractor import LLMExtractor
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


def test_financial_rule_extractor_multi_period_grouping():
    """Verify metrics across multiple periods are grouped cleanly and both 2023 and 2024 pairs are extracted."""
    extractor = FinancialRuleExtractor()

    rev_2023 = FinancialMetricNode(
        node_id="m_rev_2023",
        name="Revenue",
        normalized_key="revenue",
        value=1500.0,
        period="2023",
        source_doc_id="doc1",
        table_id="tbl_inc",
        source_page=10,
    )
    gm_2023 = FinancialMetricNode(
        node_id="m_gm_2023",
        name="Gross Margin",
        normalized_key="gross_margin",
        value=600.0,
        period="2023",
        source_doc_id="doc1",
        table_id="tbl_inc",
        source_page=10,
    )
    rev_2024 = FinancialMetricNode(
        node_id="m_rev_2024",
        name="Revenue",
        normalized_key="revenue",
        value=1800.0,
        period="2024",
        source_doc_id="doc1",
        table_id="tbl_inc",
        source_page=10,
    )
    gm_2024 = FinancialMetricNode(
        node_id="m_gm_2024",
        name="Gross Margin",
        normalized_key="gross_margin",
        value=750.0,
        period="2024",
        source_doc_id="doc1",
        table_id="tbl_inc",
        source_page=10,
    )

    # Different document metric that shares 2024 period
    rev_doc2 = FinancialMetricNode(
        node_id="m_rev_doc2",
        name="Revenue",
        normalized_key="revenue",
        value=999.0,
        period="2024",
        source_doc_id="doc2",
        table_id="tbl_inc",
        source_page=5,
    )

    edges = extractor.extract([rev_2023, gm_2023, rev_2024, gm_2024, rev_doc2])

    # Must extract exactly 2 edges: one for 2023 in doc1, and one for 2024 in doc1
    assert len(edges) == 2

    edge_2023 = next((e for e in edges if e.source_node_id == "m_rev_2023" and e.target_node_id == "m_gm_2023"), None)
    assert edge_2023 is not None

    edge_2024 = next((e for e in edges if e.source_node_id == "m_rev_2024" and e.target_node_id == "m_gm_2024"), None)
    assert edge_2024 is not None

    # doc2 revenue must NOT link to doc1 gross margin
    doc2_cross = next((e for e in edges if e.source_node_id == "m_rev_doc2"), None)
    assert doc2_cross is None


def test_financial_rule_extractor_matches_cost_of_sales_canonical_alias():
    """Verify that normalized Cost of Sales matches the default cost-to-margin rule."""
    extractor = FinancialRuleExtractor()

    cos = FinancialMetricNode(
        node_id="m_cos",
        name="Cost of Sales",
        normalized_key="cost_of_sales",
        value=1100.0,
        period="2024",
        source_doc_id="doc1",
        source_page=12,
    )
    gm = FinancialMetricNode(
        node_id="m_gm",
        name="Gross Margin",
        normalized_key="gross_margin",
        value=700.0,
        period="2024",
        source_doc_id="doc1",
        source_page=12,
    )

    edges = extractor.extract([cos, gm])
    assert len(edges) == 1
    edge = edges[0]
    assert edge.source_node_id == "m_cos"
    assert edge.target_node_id == "m_gm"
    assert edge.relation_type == CausalRelationType.IMPACTS
    assert edge.direction == CausalDirection.INVERSE


def test_llm_extractor_rejects_ungrounded_quotes():
    """Verify that model-invented quotes not present in the chunk text are rejected."""
    mock_json = json.dumps([
        {
            "source_entity": "Marketing Spend",
            "target_entity": "Revenue",
            "relationship_type": "DRIVES",
            "evidence_quote": "Marketing spend surged 80% leading to exponential adoption.",  # Not in text
            "confidence": 0.9,
        }
    ])
    mock_client = LLMClient.create_mock(mock_json)
    extractor = LLMExtractor(llm_client=mock_client)

    chunk = TextChunk(
        chunk_id="chk_ungrounded",
        doc_id="doc1",
        page_number=5,
        text="Administrative costs remained flat during the fiscal period.",
    )

    disclosure, edges = extractor.extract_from_chunk(chunk)
    assert disclosure is None
    assert edges == []


def test_llm_extractor_isolates_confidence_and_quote_errors_per_item():
    """Verify null/string confidence and null quotes do not drop earlier/later valid disclosures."""
    mock_json = json.dumps([
        # Item 1: null confidence and string confidence
        {
            "source_entity": "Inflation",
            "target_entity": "COGS",
            "relationship_type": "DRIVES",
            "evidence_quote": "Inflation increased transportation costs.",
            "confidence": "high",  # string confidence
        },
        # Item 2: null quote (should be skipped without error)
        {
            "source_entity": "Interest Rates",
            "target_entity": "Net Income",
            "relationship_type": "IMPACTS",
            "evidence_quote": None,
            "confidence": None,
        },
        # Item 3: valid quote and numeric confidence
        {
            "source_entity": "Volume Growth",
            "target_entity": "Revenue",
            "relationship_type": "DRIVES",
            "evidence_quote": "Higher volume drove revenue higher.",
            "confidence": 0.85,
        },
    ])
    mock_client = LLMClient.create_mock(mock_json)
    extractor = LLMExtractor(llm_client=mock_client)

    chunk = TextChunk(
        chunk_id="chk_robust",
        doc_id="doc1",
        page_number=7,
        text="Inflation increased transportation costs. Meanwhile, higher volume drove revenue higher.",
    )

    disclosure, edges = extractor.extract_from_chunk(chunk)
    assert disclosure is not None
    assert len(edges) == 2
    assert edges[0].source_node_id == "Inflation"
    assert edges[0].confidence == 0.9  # parsed "high"
    assert edges[1].source_node_id == "Volume Growth"
    assert edges[1].confidence == 0.85


def test_graph_builder_executes_custom_base_extractor_subclasses():
    """Verify GraphBuilder polymorphically executes any BaseExtractor subclass."""
    class CustomFootnoteExtractor(BaseExtractor):
        def extract(self, data, **kwargs):
            return []

        def apply(self, store, ingest_result):
            # Custom logic creates a specific custom edge
            edge = CausalRelationshipEdge(
                edge_id="custom_edge_1",
                source_node_id="SupplyChain",
                target_node_id="Inventory",
                relation_type=CausalRelationType.CONSTRAINS,
                evidence_text="Custom footnote evidence",
                source_page=1,
            )
            store.add_causal_edge(edge)

    store = GraphStore.create(backend_type="networkx")
    custom_ext = CustomFootnoteExtractor()
    builder = GraphBuilder(store=store, extractors=[custom_ext])

    ingest_result = IngestionResult(
        metadata=DocumentMetadata(
            doc_id="doc_cust",
            filename="Doc.pdf",
            file_hash="hash_c",
            total_pages=5,
            file_size_bytes=1000,
        ),
        pages=[],
        chunks=[],
        tables=[],
    )

    builder.build(ingest_result)
    assert store.get_stats()["causal_edges"] == 1

    # Verify invalid extractor registration raises TypeError
    with pytest.raises(TypeError) as exc_info:
        builder.register_extractor("not_an_extractor")  # type: ignore[arg-type]
    assert "Unsupported extractor type" in str(exc_info.value)
