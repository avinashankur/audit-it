# Implementation Walkthrough: AuditIt

> **Audience:** Developers implementing the AuditIt financial audit platform  
> **Last updated:** 2026-10-19  
> **Package Manager:** `uv`  
> **Target Python:** 3.11+  

This document provides a sequential, phased blueprint for building AuditIt from the current scaffold into a fully functional system. Each phase defines target files, required dependencies, implementation contracts, and verification commands.

---

## Architecture Blueprint at a Glance

The application executes a 4-stage pipeline:
1. **Ingestion**: PDF Parser -> Text Chunker -> Table Extractor
2. **Knowledge Graph Construction**: Metric & Causal Extractor -> Storage Adapter (NetworkX / Neo4j)
3. **Hybrid Retrieval**: Dense Vector Search + Graph Traversal -> Context Builder
4. **Reasoning**: BYOK LLM Client (Gemini / OpenAI / Anthropic) -> Citations & Q&A Service -> Streamlit UI

```
PDF Upload -> Text Chunks + Tables -> Graph Extraction -> In-Memory NetworkX Store
                                  \                 /
                                   -> Vector Store -
                                          |
User Query -> Hybrid Retriever (Vector + Graph) -> Context Builder -> LLM Client -> Response + Citations
```

---

## Phase 0: Dependency & Core Environment Setup

### 1. Pin Required Dependencies
Add the initial libraries using `uv`:

```bash
uv add networkx pypdf langchain-text-splitters python-dotenv pydantic
```

For optional or subsequent provider integrations:
```bash
uv add google-genai openai anthropic neo4j
```

### 2. Configure Environment Secrets
Create `.env` based on `.env.example`:

```bash
cp .env.example .env
```

Ensure `.env` contains placeholder keys:
```ini
GEMINI_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
LOG_LEVEL=INFO
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=
```

### 3. Verify Environment
```bash
uv run python -c "import networkx, pypdf; print('Dependencies ready')"
```

---

## Phase 1: Core Foundation & Shared Domain Models

### Goal
Define application configuration, structured logging, custom error types, and core domain data models before writing business logic.

### Target Files
- `src/core/env.py`: Environment variable loading and validation.
- `src/core/logging.py`: Structured logger setup using Python's standard `logging` module.
- `src/core/exceptions.py`: Domain exception hierarchy (`AuditItError`, `IngestionError`, `ExtractionError`, `RetrievalError`).
- `src/core/models.py`: Pydantic data schemas for entities passed between pipeline stages.

### Implementation Checklist
1. **In `src/core/models.py`**, declare core dataclasses or Pydantic models:
   - `DocumentMetadata`: `doc_id`, `filename`, `upload_timestamp`, `total_pages`.
   - `TextChunk`: `chunk_id`, `doc_id`, `text`, `page_number`, `token_count`.
   - `FinancialMetricNode`: `metric_id`, `name`, `value`, `unit`, `period`, `source_page`.
   - `CausalRelationshipEdge`: `source_metric_id`, `target_metric_id`, `relationship_type` (e.g. `DRIVES`, `IMPACTS`, `OFFSETS`), `confidence`, `evidence_text`.
   - `AuditCitation`: `source`, `page_number`, `citation_type`, `snippet`.
   - `AuditAnswer`: `query`, `answer_text`, `citations`, `causal_paths`.

2. **In `src/core/env.py`**, implement settings validation reading from `.env`.

### Verification
```bash
uv run python -c "from src.core.models import TextChunk, FinancialMetricNode; print('Core models valid')"
```

---

## Phase 2: Document Ingestion & PDF Parsing

### Goal
Parse financial filings (10-K, annual reports), preserve page numbers, and split text into semantically cohesive chunks for retrieval.

### Target Files
- `src/ingestion/document_loader.py`: File validation, disk caching, and memory buffer handling.
- `src/ingestion/pdf_parser.py`: PDF text and page boundary extraction using `pypdf`.
- `src/ingestion/chunker.py`: Recursive token/character splitting using `langchain-text-splitters`.
- `src/ingestion/table_extractor.py`: Basic table isolation for financial statement data.

### Implementation Steps
1. In `src/ingestion/pdf_parser.py`, extract text on a per-page basis to guarantee exact citation page numbers:
   ```python
   # Pattern: Per-page extraction
   from pypdf import PdfReader
   def parse_pdf_pages(file_path: str) -> list[tuple[int, str]]:
       reader = PdfReader(file_path)
       return [(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]
   ```
2. In `src/ingestion/chunker.py`, split page texts with reasonable overlap (e.g. 500-800 tokens, 100 token overlap) while preserving `page_number` in chunk metadata.
3. Validate ingestion pipeline end-to-end on sample documents in `data/sample_reports/`.

### Verification
```bash
uv run python -c "from src.ingestion import IngestionPipeline; print('Ingestion pipeline ready')"
```

---

## Phase 3: Dual Graph Backend (NetworkX & Neo4j)

### Goal
Implement ADR-001: an abstract storage interface with default in-memory NetworkX execution and an optional Neo4j adapter.

### Target Files
- `src/db/graph/storage/base.py`: `BaseGraphStore` abstract base class.
- `src/db/graph/storage/networkx_store.py`: In-memory NetworkX graph implementation.
- `src/db/graph/storage/neo4j_adapter.py`: Pluggable Neo4j property graph adapter.
- `src/db/graph/builder.py`: High-level graph constructor.

### Implementation Steps
1. Define the storage interface in `src/db/graph/storage/base.py`:
   - `add_node(node_id: str, node_type: str, properties: dict) -> None`
   - `add_edge(source_id: str, target_id: str, relationship: str, properties: dict) -> None`
   - `get_neighbors(node_id: str, direction: str = "out") -> list[dict]`
   - `find_paths(source_id: str, target_id: str, max_depth: int = 3) -> list[list[str]]`
   - `get_subgraph(node_id: str, hops: int = 2) -> dict`
2. Implement `NetworkXStore` wrapping `networkx.DiGraph`.
3. Implement `Neo4jAdapter` using the official `neo4j` Python driver (with graceful fallback if Neo4j is offline).
4. Verify adapter traversal parity using in-memory graphs.

### Verification
```bash
uv run python -c "from src.db.graph.storage.networkx_store import NetworkXStore; print('Graph storage ready')"
```

---

## Phase 4: Financial Metric & Causal Relationship Extraction

### Goal
Extract nodes (e.g. Revenue, Operating Expenses, Gross Margin) and directed edges (e.g. `Revenue -> Gross Profit`, `Inflation -> COGS -> Margin Contraction`) from parsed financial text.

### Target Files
- `src/db/graph/extractors/financial_rule_extractor.py`: Deterministic rule/regex extractor for standard financial line items.
- `src/db/graph/extractors/llm_extractor.py`: LLM-assisted extractor for nuanced causal relationships in MD&A narrative sections.
- `src/db/graph/builder.py`: Orchestrates both extractors and writes into the active graph store.

### Implementation Steps
1. Implement `financial_rule_extractor.py` first:
   - Identify standard metrics: Revenue, Cost of Goods Sold, Gross Profit, Operating Expenses, Net Income.
   - Establish known accounting causal links: `Cost of Goods Sold -> Gross Profit`, `Operating Expenses -> Operating Income`.
2. Implement `llm_extractor.py` for narrative text:
   - Construct prompt template asking for JSON output: `{"source": "Supply Chain Disruptions", "target": "Gross Margin", "relation": "DECREASED_BY", "evidence": "..."}`.
   - Parse and validate JSON responses into `CausalRelationshipEdge` objects.
3. Verify extraction on sample text excerpts in `data/sample_reports/`.

### Verification
```bash
uv run python -c "from src.db.graph.builder import GraphBuilder; print('Graph builder ready')"
```

---

## Phase 5: Hybrid Retrieval Engine

### Goal
Implement ADR-002: combine dense vector similarity search with structured graph traversal to assemble grounded prompt contexts.

### Target Files
- `src/retrieval/vector_store.py`: In-memory or lightweight vector store for `TextChunk` embeddings.
- `src/retrieval/graph_traversal.py`: Multi-hop neighborhood expansion and path search on the graph store.
- `src/retrieval/hybrid_retriever.py`: Coordinates vector retrieval and graph search in parallel.
- `src/retrieval/context_builder.py`: Deduplicates and formats text excerpts and graph triples into structured prompt context with citations.

### Implementation Steps
1. **Vector Retrieval**:
   - Embed incoming queries and compute cosine similarity against stored `TextChunk` records.
   - Return top-k text chunks with `page_number` and `text`.
2. **Graph Traversal**:
   - Extract mentioned financial entities from the query.
   - Traverse 1 to 2 hops out from matching nodes to collect causal predecessors and successors.
3. **Context Assembly (`src/retrieval/context_builder.py`)**:
   - Format graph paths as structured text blocks:
     `[Causal Path]: Revenue (+$12M) -> Gross Margin (-120 bps) via Supply Chain Inflation (Page 18)`.
   - Append relevant text chunks with markdown citation tags `[Doc: Page N]`.

### Verification
```bash
uv run python -c "from src.retrieval.hybrid_retriever import HybridRetriever; print('Hybrid retriever ready')"
```

---

## Phase 6: BYOK Multi-Provider LLM Client & QA Service

### Goal
Integrate Google Gemini, OpenAI, and Anthropic APIs through a unified client, and implement the question-answering workflow with strict citation enforcement.

### Target Files
- `src/reasoning/llm_client.py`: Multi-provider client abstraction with fallback handling.
- `src/reasoning/prompts.py`: Audit prompt templates requiring cited reasoning.
- `src/reasoning/qa_service.py`: Orchestrator tying retrieval, prompt construction, and response parsing together.

### Implementation Steps
1. Implement `LLMClient` with a common `generate(prompt: str, model_provider: str, api_key: str) -> str` signature.
2. Formulate strict system instructions in `src/reasoning/prompts.py`:
   - Answers must cite source page numbers for all factual claims.
   - Numerical statements must explain the underlying causal path derived from the knowledge graph.
   - Refuse to fabricate relationships not present in the retrieved context.
3. In `src/reasoning/qa_service.py`, execute the full loop:
   `User Query -> Hybrid Retriever -> Context Builder -> LLM Client -> AuditAnswer`.

### Verification
```bash
uv run python -c "from src.reasoning.qa_service import QAService; print('QA service ready')"
```

---

## Phase 7: Streamlit UI Integration

### Goal
Connect the user interface in `app.py` to the underlying domain services.

### Target Files
- `app.py`: Main Streamlit dashboard.
- `src/ui/components/chat.py`: Message history and streaming responses.
- `src/ui/components/citations.py`: Citation badges and expandable source inspection.
- `src/ui/components/graph_view.py`: Graph visualization rendering (NetworkX + PyVis or Graphviz).
- `src/ui/components/sidebar.py`: Upload controls and provider credentials.

### Implementation Steps
1. Replace mock data in `app.py` with real invocations:
   - When a PDF is uploaded, pass the buffer to `src/ingestion/document_loader.py` and trigger `GraphBuilder`.
   - Update `st.session_state["graph_stats"]` from the real `BaseGraphStore.node_count` and `edge_count`.
2. Connect the chat input to `QAService.ask(user_query)`.
3. Render interactive graph views using `graphviz` or `streamlit-agraph` in the Graph Explorer tab.

### Verification
```bash
uv run streamlit run app.py
```

---

## Phase 8: End-to-End Report Verification

### Goal
Validate complete workflows from PDF upload through graph extraction to question answering on a real report.

### Steps
1. Place a sample PDF (e.g. an annual report or 10-K filing) into `data/sample_reports/`.
2. Run the application via Streamlit:
   - Ingest sample PDF.
   - Verify graph nodes and causal edges are generated.
   - Run sample audit queries (e.g. "What caused gross margin compression?").
   - Confirm returned answer contains valid page citations and causal paths.

---

## Recommended Implementation Order

Follow this sequence to ensure every component builds on verified foundations:

| Step | Component | Key Output | Verification Command |
| --- | --- | --- | --- |
| 1 | Dependencies & Core Models | `src/core/models.py`, `src/core/env.py` | `uv run python -c "from src.core.models import TextChunk"` |
| 2 | Ingestion & PDF Parser | `src/ingestion/pdf_parser.py`, `chunker.py` | `uv run python -c "from src.ingestion import IngestionPipeline"` |
| 3 | In-Memory Graph Store | `src/db/graph/storage/networkx_store.py` | `uv run python -c "from src.db.graph.storage.networkx_store import NetworkXStore"` |
| 4 | Causal Extraction | `src/db/graph/extractors/` | `uv run python -c "from src.db.graph.builder import GraphBuilder"` |
| 5 | Hybrid Retriever | `src/retrieval/hybrid_retriever.py` | `uv run python -c "from src.retrieval.hybrid_retriever import HybridRetriever"` |
| 6 | Unified LLM Client | `src/reasoning/llm_client.py`, `qa_service.py` | `uv run python -c "from src.reasoning.qa_service import QAService"` |
| 7 | UI Wiring | Connect `app.py` to `QAService` | `uv run streamlit run app.py` |
| 8 | End-to-End Report | Upload and query sample PDF in UI | `uv run streamlit run app.py` |
