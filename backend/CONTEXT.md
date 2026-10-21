# CONTEXT.md

> This file provides essential context for AI coding assistants and new contributors. It is intentionally dense: read fully before making changes.
> Last updated: 2026-10-21

---

## What this is

AuditIt is a financial audit and analysis tool that extracts causal relationships among financial metrics, ratios, and disclosures from report documents into a knowledge graph. It provides hybrid graph-vector retrieval and LLM-powered question answering with source citations.

The backend exposes an asynchronous FastAPI service delivering REST and Server-Sent Events (SSE) streaming endpoints to the React SPA frontend.

---

## Tech Stack

| Layer | Technology | Version | Notes |
| --- | --- | --- | --- |
| Language | Python | >= 3.13 | Type hints encouraged across all modules |
| Package Manager | uv | >= 0.11 | Virtualenv and package management; do not invoke pip directly |
| Test Runner | pytest | >= 9.1 | Automated test execution with pythonpath configuration |
| API Service | FastAPI, Uvicorn | >= 0.115, >= 0.34 | Asynchronous REST and Server-Sent Events (SSE) streaming |
| Graph Engine | NetworkX | >= 3.4 | In-memory graph structure and analysis |
| Graph Database | Neo4j (optional) | 5.x | Property graph storage via Cypher adapter |
| Ingestion & Chunking | PyMuPDF, pdfplumber, pypdf, langchain-text-splitters | Current | PDF parsing, table extraction, and recursive text splitting |
| Configuration | Pydantic & Pydantic-Settings | >= 2.14, >= 2.16 | Settings validation and domain schemas |
| LLM Providers | Google Gemini (default: gemini-3.8-flash), OpenAI, Anthropic | API | BYOK (Bring Your Own Key) architecture |
| Legacy UI | Streamlit | >= 1.40 | Prototype UI preserved for standalone local exploration |

---

## Codebase Map

```
Dockerfile              - Container specification with uv and dynamic PORT binding
GLOSSARY.md             - Domain glossary and canonical business terms
app.py                  - Legacy Streamlit prototype entry point
scripts/
  generate_demo_report.py - Synthetic report generator for Northwind Cloud FY2024
src/
  api/
    main.py             - FastAPI application factory, CORS, and router registration
    dependencies.py     - Session ID extraction and dependency injection
    session_mgr.py      - In-memory document and job lifecycle manager
    schemas.py          - Pydantic DTO request and response models
    routes/             - Endpoints: health, samples, documents, graph, query
  core/
    env.py              - Environment variable loading and runtime settings validation
    exceptions.py       - Custom domain exception classes
    logging.py          - Structured logging configuration and latency profiler
  ingestion/
    pipeline.py         - Ingestion orchestrator coordinating parsing, tables, and graphs
    chunker.py          - Document chunking and text splitting logic
    document_loader.py  - File loading and validation
    pdf_parser.py       - PDF text and layout extraction
    table_extractor.py  - Financial statement table extraction
  db/
    graph/
      store.py          - Deep GraphStore module (domain rules, entity matching, traversal)
      builder.py        - Backwards-compatible builder wrapper
      storage/
        base.py         - Storage port (GraphBackend abstract contract)
        networkx_store.py - In-memory NetworkX storage adapter
        neo4j_adapter.py  - Native Cypher Neo4j storage adapter with fallback
    models/
      entities.py       - Domain models and graph entities
  retrieval/
    context_builder.py  - Prompt context assembly and citation linking
    hybrid_retriever.py - Combined vector and graph retrieval coordinator
    vector_store.py     - In-memory BM25 chunk index and similarity search
  reasoning/
    qa_service.py       - Question answering orchestration service (offline + BYOK)
    llm_client.py       - Multi-provider client adapter (Gemini, OpenAI, Anthropic, Mock)
    offline_engine.py   - Deterministic rule-based response generator
    prompts.py          - System prompts and extraction templates
  ui/
    state.py            - Legacy Streamlit session state management and message storage
data/
  sample_reports/       - Sample financial report PDFs for development and verification
docs/
  adr/                  - Architecture Decision Records (001-dual-backend, 002-hybrid-retrieval)
  concepts/             - Technical concept deep-dives
  runbooks/             - Operational and troubleshooting playbooks
tests/
  test_graph_backend_parity.py - Behavioral parity test suite across storage backends
  test_graph_store.py          - Domain rules and ingestion tests for GraphStore
  test_hybrid_retriever.py     - End-to-end hybrid retrieval verification
```

Do not put domain business logic into API route handlers: routes only validate schemas and forward events to service managers.
Do not make direct LLM calls from retrieval or ingestion modules: route all LLM requests through the reasoning service.

---

## Key Patterns

**Graph storage architecture (Ports & Adapters):**
- `GraphStore` (`src/db/graph/store.py`) is the deep domain module. It owns entity matching, canonical metric aliases, accounting causal rules, and query neighborhood resolution.
- Storage backends implement the primitive `GraphBackend` contract defined in `src/db/graph/storage/base.py`.
- `NetworkXBackend` provides fast local execution and zero-dependency CI testing.
- `Neo4jBackend` executes native Cypher statements with automatic in-memory fallback when offline.
- Callers and retrieval modules query `GraphStore` directly; they never access internal storage dictionaries or private attributes.

**Adding a new document extractor or rule:**
1. Register canonical metric mappings in `CANONICAL_METRICS` within `src/db/graph/store.py`.
2. Add accounting domain causal dependencies to `ACCOUNTING_CAUSAL_RULES`.
3. Verify extraction against test cases in `tests/test_graph_store.py`.

**Error handling:**
- Define domain-specific errors in `src/core/exceptions.py`.
- Catch and log external API failures (LLM APIs, Neo4j connection) before returning sanitized error states to API clients.
- Use structured logging via `src/core/logging.py`.

**Configuration and Secrets:**
- Load all configurations via `src/core/env.py` using `Settings` and `get_settings()`.
- Never hardcode API keys or credentials: use `.env` with validation.
- User-supplied BYOK credentials arriving in `X-LLM-Key` request headers are applied per request and never stored on disk.

---

## Glossary

| Term | Definition |
| --- | --- |
| Financial Metric | A quantitative numerical item extracted from financial statements (Revenue, Gross Margin, Operating Income). |
| Causal Relationship | A directed dependency between two financial metrics where changes in one metric drive or offset changes in the other. |
| Disclosure Node | A node in the knowledge graph representing qualitative text or footnote context explaining a metric. |
| Graph Store | The deep module managing causal financial relationships, metric nodes, and disclosure nodes. |
| Graph Backend | The internal storage port satisfied by interchangeable adapters (NetworkX, Neo4j). |
| Hybrid Retrieval | Retrieval combining vector similarity search over text chunks with graph traversal over connected causal nodes. |
| BYOK | Bring Your Own Key; users supply their own Gemini, OpenAI, or Anthropic API credentials. |

---

## Key Invariants

Things that must always be true:
- All environment and package management is executed through uv; pip is never invoked directly.
- All unit and parity tests must pass via `uv run pytest`.
- API route handlers never execute graph storage mutations or LLM calls directly; all requests pass through service layers.
- In-memory graph operations must work without requiring a running Neo4j instance.
- No raw API keys or tokens are stored in the graph database or logged.
- Graph node identifiers must remain stable and deterministic for a given document version.

---

## What NOT to do

- Do not use pip directly to install packages or manage virtual environments: use uv.
- Do not introduce direct database calls or API network requests inside route handlers without service encapsulation.
- Do not bypass `GraphStore` to access storage adapter internals or private dictionaries.
- Do not add dependencies without updating `pyproject.toml`.
- Do not hardcode filesystem paths: use paths resolved relative to project root or configured data directory.

---

## Development Workflow

```bash
# Setup virtual environment with uv
uv venv
# On Windows:
.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies with uv
uv sync

# Run test suite
uv run pytest

# Configure environment
cp .env.example .env

# Run FastAPI API server (reloads on changes)
uv run uvicorn src.api.main:app --reload --port 8000

# Legacy prototype: Run Streamlit UI
uv run streamlit run app.py
```

---

## Gotchas

- NetworkX operations run entirely in memory: large documents with dense relationships require monitoring memory usage.
- Neo4j connection strings require explicit protocol handling (bolt vs neo4j+s).
- Session state is process-local: restarting the FastAPI server clears in-memory filings and retrieval indexes.
- Container port binding: the Docker container reads `${PORT:-8000}` for compatibility with cloud container platforms (Render, Railway, Cloud Run).
- CORS origins: when frontend and backend run on different domains or ports, configure `CORS_ORIGINS` in `.env`.

---

## Quality Checklist

- [x] One-sentence system description is specific and accurate
- [x] Full tech stack table includes versions and test runner
- [x] Codebase map reflects the current directory structure including FastAPI routes and Dockerfile
- [x] Key patterns document the Ports & Adapters architecture
- [x] Glossary covers core domain terms and matches GLOSSARY.md
- [x] Invariants capture essential system constraints
- [x] "What not to do" list covers common traps
- [x] Gotchas section covers memory, session state, container port, and CORS considerations
- [x] File is under 300 lines
