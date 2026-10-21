"""Test suite for QAService and citation payload generation."""

from src.db.graph.store import GraphStore
from src.db.models.entities import FinancialMetricNode, MetricUnit, StatementType, TextChunk
from src.reasoning.qa_service import QAService
from src.retrieval.hybrid_retriever import HybridRetriever
from src.retrieval.vector_store import VectorStore


def test_qa_service_citation_source_filename():
    """Verify that citations produced by QAService have valid source_filename attributes."""
    graph_store = GraphStore.create(backend_type="networkx")
    graph_store.add_metric_node(
        FinancialMetricNode(
            node_id="m1",
            name="Revenue",
            normalized_key="revenue",
            value=1000.0,
            unit=MetricUnit.USD,
            period="2023",
            statement_type=StatementType.INCOME_STATEMENT,
            source_doc_id="doc1",
            source_page=2,
        )
    )

    vec_store = VectorStore()
    vec_store.add_chunks([
        TextChunk(
            chunk_id="chk1",
            doc_id="doc1",
            page_number=2,
            text="Revenue increased to $1,000M.",
            char_count=30,
            token_estimate=8,
            metadata={"filename": "DrinkPAK_Report.pdf"},
        )
    ])

    retriever = HybridRetriever(vector_store=vec_store, graph_store=graph_store)
    qa = QAService(retriever=retriever)
    resp = qa.answer_query(query="What was the revenue?", provider="Offline")

    assert len(resp.citations) >= 1
    for c in resp.citations:
        assert hasattr(c, "source_filename")
        assert not hasattr(c, "source_document")
        # Simulating app.py's citation extraction
        source = c.source_filename or f"Page {c.page_number}"
        assert source in ("DrinkPAK_Report.pdf", "Knowledge Graph")


def test_causal_citations_use_actual_report_pages_and_evidence():
    """Verify that causal-path citations reflect the actual report pages and evidence text instead of inventing Page 1 of Knowledge Graph."""
    from src.db.models.entities import CitationType, DocumentMetadata, TableData
    from src.ingestion import IngestionResult

    store = GraphStore.create(backend_type="networkx")

    table = TableData(
        table_id="tbl_inc",
        doc_id="doc_audit_1",
        page_number=18,
        title="Consolidated Statements of Income",
        headers=["Metric", "2024"],
        rows=[
            ["Revenue", "$1,500.00"],
            ["Cost of Sales", "$900.00"],
            ["Gross Margin", "$600.00"],
        ],
        markdown="| Metric | 2024 |\n| --- | --- |",
    )

    chunk = TextChunk(
        chunk_id="chk_mda",
        doc_id="doc_audit_1",
        page_number=24,
        text="Gross margin expansion of 200 bps was driven by lower procurement costs.",
        char_count=74,
        token_estimate=18,
        metadata={"filename": "Company_10K.pdf"},
    )

    ingest_result = IngestionResult(
        metadata=DocumentMetadata(
            doc_id="doc_audit_1",
            filename="Company_10K.pdf",
            file_hash="hash999",
            total_pages=50,
            file_size_bytes=100000,
        ),
        pages=[],
        chunks=[chunk],
        tables=[table],
    )

    store.populate_from_ingestion(ingest_result)

    # 1. Query causal neighborhood directly on GraphStore
    metrics, causal_paths = store.find_causal_neighborhood("How does revenue drive gross margin?", max_hops=1)
    assert len(causal_paths) >= 1
    path = causal_paths[0]
    # Verify the path carries the actual report page (18) and document filename
    assert path.source_page == 18
    assert 18 in path.source_pages
    assert path.source_filename == "Company_10K.pdf"
    assert path.source_doc_id == "doc_audit_1"
    assert path.evidence_text is not None

    # 2. HybridRetriever and ContextBuilder integration
    vec_store = VectorStore()
    vec_store.add_chunks([chunk])
    retriever = HybridRetriever(vector_store=vec_store, graph_store=store)

    qa = QAService(retriever=retriever)
    resp = qa.answer_query(query="How does revenue drive gross margin?", provider="Offline")

    # Find the causal path citation
    causal_citations = [c for c in resp.citations if c.citation_type == CitationType.CAUSAL_PATH]
    assert len(causal_citations) >= 1

    for cite in causal_citations:
        # Must cite the actual report page 18, NOT invented Page 1
        assert cite.page_number == 18
        # Must cite Company_10K.pdf, NOT "Knowledge Graph"
        assert cite.source_filename == "Company_10K.pdf"
        assert cite.source_doc_id == "doc_audit_1"
        assert "gross margin" in cite.snippet.lower()

    # Verify offline answer text contains Page 18 and does NOT invent Page 1
    assert "Page 18" in resp.answer_text
    assert "Page 1," not in resp.answer_text
    assert "Page 1)" not in resp.answer_text


def test_offline_answer_includes_metric_values_and_citations():
    """Verify that offline answers include retrieved metric values and FINANCIAL_TABLE citations."""
    from src.db.models.entities import CitationType, DocumentMetadata, TableData
    from src.ingestion import IngestionResult

    store = GraphStore.create(backend_type="networkx")
    table = TableData(
        table_id="tbl_rev",
        doc_id="doc_rev_99",
        page_number=12,
        title="Consolidated Statements of Income",
        headers=["Metric", "2024"],
        rows=[
            ["Revenue", "$1,850.00"],
            ["Operating Expenses", "$1,100.00"],
            ["Operating Income", "$750.00"],
        ],
        markdown="| Metric | 2024 |\n| --- | --- |",
    )

    ingest_result = IngestionResult(
        metadata=DocumentMetadata(
            doc_id="doc_rev_99",
            filename="DrinkPAK_Annual_Report.pdf",
            file_hash="hash_rev",
            total_pages=30,
            file_size_bytes=50000,
        ),
        pages=[],
        chunks=[],
        tables=[table],
    )
    store.populate_from_ingestion(ingest_result)

    # Empty vector store (no text chunks retrieved, only graph metrics)
    vec_store = VectorStore()
    retriever = HybridRetriever(vector_store=vec_store, graph_store=store)
    qa = QAService(retriever=retriever)

    resp = qa.answer_query(query="What was revenue in 2024?", provider="Offline")

    # 1. Answer text must contain the metric value and page reference
    assert "Revenue" in resp.answer_text
    assert "$1,850" in resp.answer_text
    assert "Page 12" in resp.answer_text

    # 2. Citations must include FINANCIAL_TABLE citation
    metric_cites = [c for c in resp.citations if c.citation_type == CitationType.FINANCIAL_TABLE]
    assert len(metric_cites) >= 1
    rev_cite = next((c for c in metric_cites if "Revenue" in c.snippet), None)
    assert rev_cite is not None
    assert rev_cite.page_number == 12
    assert "$1,850" in rev_cite.snippet
    assert rev_cite.source_filename == "DrinkPAK_Annual_Report.pdf"


def test_unrelated_query_returns_no_arbitrary_excerpts_or_citations():
    """Verify that unrelated queries return no chunks and show an explicit no-evidence answer rather than arbitrary excerpts."""
    store = GraphStore.create(backend_type="networkx")
    vec_store = VectorStore()
    vec_store.add_chunks([
        TextChunk(
            chunk_id="chunk_bev",
            doc_id="doc_drink",
            page_number=5,
            text="DrinkPAK expanded aseptic beverage packaging capacity in Southern California.",
            char_count=77,
            token_estimate=12,
            metadata={"filename": "DrinkPAK.pdf"},
        ),
        TextChunk(
            chunk_id="chunk_rev",
            doc_id="doc_drink",
            page_number=6,
            text="Net revenue increased primarily from co-manufacturing packaging contracts.",
            char_count=74,
            token_estimate=11,
            metadata={"filename": "DrinkPAK.pdf"},
        ),
    ])

    # 1. Test vector store search directly: zero-matching query must return empty list
    search_results = vec_store.search("What is the capital of France?")
    assert search_results == []

    # 2. Test QAService with unrelated query
    retriever = HybridRetriever(vector_store=vec_store, graph_store=store)
    qa = QAService(retriever=retriever)
    resp = qa.answer_query(query="What is the capital of France?", provider="Offline")

    # Citations must be completely empty
    assert len(resp.citations) == 0

    # Answer text must be an explicit no-evidence statement
    assert "No relevant evidence or verified disclosures found" in resp.answer_text
    assert "capital of France" in resp.answer_text

    # Must NOT contain arbitrary excerpts or claim verified audit analysis
    assert "DrinkPAK" not in resp.answer_text
    assert "aseptic beverage" not in resp.answer_text
    assert "Key Findings from Report Disclosures" not in resp.answer_text
    assert "verified audit analysis" not in resp.answer_text





def test_offline_answer_retains_full_causal_path_and_steps():
    """Verify that offline answers retain full multi-step causal path descriptions alongside supporting citations."""
    from src.db.models.entities import CitationType, DocumentMetadata, TableData
    from src.ingestion import IngestionResult

    store = GraphStore.create(backend_type="networkx")
    table = TableData(
        table_id="tbl_inc_multi",
        doc_id="doc_multi_step",
        page_number=14,
        title="Consolidated Statements of Operations",
        headers=["Metric", "2024"],
        rows=[
            ["Net Sales", "$2,000.00"],
            ["Cost of Sales", "$1,200.00"],
            ["Gross Margin", "$800.00"],
            ["Operating Income", "$500.00"],
        ],
        markdown="| Metric | 2024 |\n| --- | --- |",
    )

    ingest_result = IngestionResult(
        metadata=DocumentMetadata(
            doc_id="doc_multi_step",
            filename="MultiStepReport.pdf",
            file_hash="hash_multi",
            total_pages=30,
            file_size_bytes=50000,
        ),
        pages=[],
        chunks=[],
        tables=[table],
    )
    store.populate_from_ingestion(ingest_result)

    vec_store = VectorStore()
    retriever = HybridRetriever(vector_store=vec_store, graph_store=store)
    qa = QAService(retriever=retriever)

    resp = qa.answer_query(query="How does revenue impact operating income?", provider="Offline")

    # 1. Answer text must contain the full path description including both intermediate Gross Margin and target Operating Income
    assert "Revenue" in resp.answer_text
    assert "Gross Margin" in resp.answer_text
    assert "Operating Income" in resp.answer_text
    assert "Revenue -> Gross Margin -> Operating Income" in resp.answer_text

    # 2. Answer text must keep supporting citation page alongside the full path description
    assert "Page 14" in resp.answer_text

    # 3. Citation snippet must preserve both steps' supporting evidence on page 14
    causal_cites = [c for c in resp.citations if c.citation_type == CitationType.CAUSAL_PATH]
    assert len(causal_cites) >= 1
    page14_cite = next(c for c in causal_cites if c.page_number == 14)
    assert "gross margin" in page14_cite.snippet.lower()
    assert "operating income" in page14_cite.snippet.lower()


def test_driver_claims_cite_own_sources_directly():
    """Verify that one-edge driver claims cite their own source pages directly without borrowing citations from other periods."""
    from src.db.models.entities import CitationType, DocumentMetadata, TableData
    from src.ingestion import IngestionResult

    store = GraphStore.create(backend_type="networkx")

    table_2024 = TableData(
        table_id="tbl_drivers_2024",
        doc_id="doc_comp_drivers",
        page_number=14,
        title="Consolidated Statements of Operations",
        headers=["Metric", "2024"],
        rows=[
            ["Net Sales", "$5,000.00"],
            ["Cost of Sales", "$3,000.00"],
            ["Gross Margin", "$2,000.00"],
        ],
        markdown="| Metric | 2024 |\n| Net Sales | $5,000.00 |",
    )

    table_2023 = TableData(
        table_id="tbl_drivers_2023",
        doc_id="doc_comp_drivers",
        page_number=24,
        title="Consolidated Statements of Operations",
        headers=["Metric", "2023"],
        rows=[
            ["Net Sales", "$4,000.00"],
            ["Cost of Sales", "$2,500.00"],
            ["Gross Margin", "$1,500.00"],
        ],
        markdown="| Metric | 2023 |\n| Net Sales | $4,000.00 |",
    )

    ingest_result = IngestionResult(
        metadata=DocumentMetadata(
            doc_id="doc_comp_drivers",
            filename="ComparativeReport.pdf",
            file_hash="hash_comp_drivers",
            total_pages=40,
            file_size_bytes=80000,
        ),
        pages=[],
        chunks=[],
        tables=[table_2024, table_2023],
    )
    store.populate_from_ingestion(ingest_result)

    vec_store = VectorStore()
    retriever = HybridRetriever(vector_store=vec_store, graph_store=store)
    qa = QAService(retriever=retriever)

    resp = qa.answer_query(query="What drives gross margin across 2024 and 2023?", provider="Offline")

    # 1. Citations must carry path_id linking to their respective path
    causal_cites = [c for c in resp.citations if c.citation_type == CitationType.CAUSAL_PATH]
    assert len(causal_cites) >= 2
    for c in causal_cites:
        assert c.path_id is not None, "Each causal citation must have a path_id linking to its path"

    # 2. In answer_text, each driver claim must cite ONLY its own period page
    assert "### 🔗 Causal Dependencies & Drivers Identified" in resp.answer_text
    causal_section = resp.answer_text.split("### 🔗 Causal Dependencies & Drivers Identified")[1]
    if "###" in causal_section:
        causal_section = causal_section.split("###")[0]

    # Find claims and their citation lines
    blocks = [b.strip() for b in causal_section.split("- **") if b.strip()]
    for block in blocks:
        first_line = block.splitlines()[0]
        cite_lines = block.splitlines()[1:]
        # If the claim is for 2024, it must cite Page 14 and must NOT cite Page 24
        if "2024" in first_line:
            assert any("Page 14" in cl for cl in cite_lines), f"2024 claim must cite Page 14: {block}"
            assert not any("Page 24" in cl for cl in cite_lines), f"2024 claim must NOT cite Page 24: {block}"
        # If the claim is for 2023, it must cite Page 24 and must NOT cite Page 14
        elif "2023" in first_line:
            assert any("Page 24" in cl for cl in cite_lines), f"2023 claim must cite Page 24: {block}"
            assert not any("Page 14" in cl for cl in cite_lines), f"2023 claim must NOT cite Page 14: {block}"
