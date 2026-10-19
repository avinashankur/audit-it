# CONTEXT.md

> This file provides essential context for AI coding assistants and new contributors. It is intentionally dense: read fully before making changes.
> Last updated: 2026-10-19

---

## What this is

AuditIt is a financial audit and analysis tool that extracts causal relationships among financial metrics, ratios, and disclosures from report documents into a knowledge graph. It provides hybrid graph-vector retrieval and LLM-powered question answering with source citations.

---

## Tech Stack

| Layer | Technology | Version | Notes |
| --- | --- | --- | --- |
| Language | Python | 3.11+ | Type hints encouraged across all modules |
| Package Manager | uv | <!-- TODO: fill in exact version --> | Virtualenv and package management; do not invoke pip directly |
| Web UI | Streamlit | 1.x <!-- TODO: fill in exact version --> | Interactive dashboard and chat interface |
| Graph Engine | NetworkX | 3.x <!-- TODO: fill in exact version --> | In-memory graph structure and analysis |
| Graph Database | Neo4j (optional) | 5.x <!-- TODO: fill in exact version --> | Property graph storage via adapter |
| Ingestion & Chunking | pypdf, LangChain | <!-- TODO: fill in exact versions --> | PDF parsing and text splitting |
| LLM Providers | Google Gemini, OpenAI, Anthropic | API | BYOK (Bring Your Own Key) architecture |
| Testing | pytest | <!-- TODO: fill in exact version --> | Unit and integration test suite |

---

## Codebase Map

```
app.py                  - Streamlit application entry point
config/
  settings.py           - Application configuration and runtime settings
src/
  core/
    env.py              - Environment variable loading and validation
    exceptions.py       - Custom domain exception classes
    logging.py          - Structured logging configuration
    models.py           - Shared core domain models and data types
  ingestion/
    chunker.py          - Document chunking and text splitting logic
    document_loader.py  - File loading and validation
    pdf_parser.py       - PDF text and layout extraction
    table_extractor.py  - Financial statement table extraction
  db/
    graph/
      builder.py        - Graph construction coordinator
      extractors/       - Extraction strategies (llm_extractor, financial_rule_extractor)
      storage/          - Storage adapters (base, networkx_store, neo4j_adapter)
      visualizer.py     - Graph rendering and visualization helpers
    models/             - Database entity schemas
    schemas/            - Schema definitions and validations
  retrieval/
    context_builder.py  - Prompt context assembly and citation linking
    graph_traversal.py  - Graph traversal and neighborhood expansion
    hybrid_retriever.py - Combined vector and graph retrieval pipeline
    vector_store.py     - Vector embedding storage and similarity search
  reasoning/
    llm_client.py       - Unified LLM API client (Gemini, OpenAI, Anthropic)
    offline_engine.py   - Local or cached execution engine
    prompts.py          - Structured prompt templates
    qa_service.py       - Question answering orchestration service
  ui/
    components/         - Streamlit UI components (chat, citations, graph_view, sidebar, metrics)
    state.py            - Session state management
data/
  sample_reports/       - Sample financial report PDFs for development and testing
tests/
  test_queries.py       - Query and retrieval test suite
docs/
  adr/                  - Architecture Decision Records
  concepts/             - Technical concept deep-dives
  runbooks/             - Operational and troubleshooting playbooks
```

Do not put business logic into UI components: UI components only render data and forward user events.
Do not make direct LLM calls from retrieval or ingestion modules: route all LLM requests through `src/reasoning/llm_client.py`.

---

## Key Patterns

**Adding a new document extractor:**
1. Define extractor interface in `src/db/graph/extractors/` implementing the base extractor contract.
2. Register the extractor in `src/db/graph/builder.py`.
3. Add unit tests covering extraction logic against sample PDF text.

**Graph storage adapters:**
- Storage backends implement the interface defined in `src/db/graph/storage/base.py`.
- NetworkX is the primary in-memory store for local execution.
- Neo4j adapter maps graph nodes and edges to Neo4j property graph format.

**Error handling:**
- Define domain-specific errors in `src/core/exceptions.py`.
- Catch and log external API failures (LLM APIs, Neo4j connection) before returning sanitized error states to UI.
- Use structured logging via `src/core/logging.py`.

**Configuration and Secrets:**
- Load all configurations via `config/settings.py` backed by `src/core/env.py`.
- Never hardcode API keys or credentials: use `.env` with validation.

---

## Glossary

| Term | Definition |
| --- | --- |
| Causal Relationship | A directed dependency between two financial metrics where changes in one metric drive changes in the other (e.g. Revenue -> Gross Margin). |
| Metric Node | A node in the knowledge graph representing a reported or calculated financial number. |
| Disclosure Node | A node in the knowledge graph representing qualitative text or footnote context explaining a metric. |
| Hybrid Retrieval | Retrieval combining vector similarity search over text chunks with graph traversal over connected causal nodes. |
| BYOK | Bring Your Own Key; users supply their own Gemini, OpenAI, or Anthropic API credentials. |

---

## Key Invariants

Things that must always be true:
- All environment and package management is executed through uv; pip is never invoked directly.
- UI layer (`src/ui`) never calls graph storage or LLM APIs directly; all requests pass through service layers.
- In-memory graph operations must work without requiring a running Neo4j instance.
- No raw API keys or tokens are stored in the graph database or logged.
- Graph node identifiers must remain stable and deterministic for a given document version.

---

## What NOT to do

- Do not use pip directly to install packages or manage virtual environments: use uv.
- Do not introduce direct database calls or API network requests inside UI component render loops.
- Do not import LLM client libraries directly in `ingestion` or `retrieval`: use `src/reasoning/llm_client.py`.
- Do not add dependencies without updating `requirements.txt` or `pyproject.toml` (once established).
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

# Install dependencies with uv <!-- TODO: create requirements.txt or pyproject.toml -->
uv pip install -r requirements.txt
# (or: uv sync)

# Configure environment
cp .env.example .env

# Run Streamlit UI
uv run streamlit run app.py

# Run test suite
uv run pytest
```

---

## Gotchas

- NetworkX operations run entirely in memory: large documents with dense relationships require monitoring memory usage.
- Neo4j connection strings require explicit protocol handling (bolt vs neo4j+s).
- Streamlit reruns scripts from top to bottom on each interaction: keep expensive graph loading cached or stored in session state.

---

## Quality Checklist

- [x] One-sentence system description is specific and accurate
- [ ] Full tech stack table includes versions <!-- TODO: lock exact versions when requirements.txt is committed -->
- [x] Codebase map reflects the target directory structure
- [x] Key patterns are written as imperative instructions
- [x] Glossary covers core domain terms
- [x] Invariants capture essential system constraints
- [x] "What not to do" list covers common traps
- [x] Gotchas section covers Streamlit and graph memory considerations
- [x] File is under 300 lines
