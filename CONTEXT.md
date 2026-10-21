# CONTEXT.md

> Essential context for AI coding assistants and contributors. Read fully before making changes.
> Last updated: 2026-10-21

---

## What this is

AuditIt is a financial report analysis system that converts corporate filings (such as 10-K and annual reports) into queryable causal knowledge graphs. It extracts financial metrics, accounting disclosures, and tabular statements, links them by causal dependencies, and provides grounded question answering with page-level citations.

The system runs locally without required API keys in **Offline Grounded** mode, and supports bring-your-own-key (BYOK) cloud reasoning with Google Gemini (default: `gemini-3.8-flash`), OpenAI, and Anthropic.

---

## Tech Stack

| Layer | Technology | Version | Notes |
| --- | --- | --- | --- |
| Architecture | Decoupled Monorepo | - | `backend/` and `frontend/` with root npm orchestrator |
| Frontend Framework | React, Vite | React 19, Vite 8 | Single-page application in strict TypeScript |
| Frontend UI & Style | Tailwind CSS, shadcn/ui | Tailwind v4 | Achromatic Ledger editorial design system |
| Graph Visualization | React Flow, @dagrejs/dagre | React Flow 12 | Interactive node canvas with directed acyclic layout |
| Backend Framework | FastAPI, Uvicorn | FastAPI 0.115+, Python 3.13 | Async REST and Server-Sent Events (SSE) streaming |
| Package Manager | uv (backend), npm (frontend) | uv 0.11+, Node 20+ | Fast dependency resolution; do not invoke pip directly |
| Graph Engines | NetworkX, Neo4j | NetworkX 3.4+, Neo4j 5.x | NetworkX is default in-memory; Neo4j is optional persistent adapter |
| Ingestion & PDF | PyMuPDF, pdfplumber, pypdf | Current | Structural layout parsing and financial table extraction |
| Retrieval | In-memory BM25 + Graph Traversal | Custom | Hybrid lexical and multi-hop neighborhood retrieval |
| Reasoning Models | Gemini 3.8 Flash, GPT-4o-mini, Claude 3.5 Sonnet | API | BYOK header injection or server environment fallback |
| Testing | pytest | pytest 9.1+ | Strict asyncio test suite across all backend layers |

---

## Codebase Map

```text
auditit/
├── package.json                 - Root development orchestrator (concurrently)
├── README.md                    - Project overview, quick start, and user guide
├── ARCHITECTURE.md              - System architecture (C4 levels 1-3)
├── CONTEXT.md                   - AI assistant and developer context primer
├── backend/
│   ├── pyproject.toml           - Python project metadata, dependencies, and tool settings
│   ├── Dockerfile               - Container build with uv and dynamic PORT binding
│   ├── ARCHITECTURE.md          - Backend-specific architectural details
│   ├── CONTEXT.md               - Backend engine invariants and execution guidelines
│   ├── GLOSSARY.md              - Domain definitions and accounting terms
│   ├── scripts/
│   │   └── generate_demo_report.py - Synthetic report generator for Northwind Cloud FY2024
│   ├── data/
│   │   └── sample_reports/      - Bundled financial PDFs for local demonstration
│   ├── src/
│   │   ├── api/
│   │   │   ├── main.py          - FastAPI application factory, CORS, and router registration
│   │   │   ├── dependencies.py  - Session ID extraction and dependency injection
│   │   │   ├── session_mgr.py   - In-memory document and job lifecycle manager
│   │   │   ├── schemas.py       - Pydantic DTO request and response models
│   │   │   └── routes/          - Endpoints: health, samples, documents, graph, query
│   │   ├── core/
│   │   │   ├── env.py           - Settings validation via pydantic-settings
│   │   │   ├── exceptions.py    - Domain exception hierarchy
│   │   │   └── logging.py       - Structured logger and execution timer
│   │   ├── db/
│   │   │   ├── models/entities.py - FinancialMetricNode, DisclosureNode, CausalGraphPath
│   │   │   └── graph/
│   │   │       ├── store.py     - Deep GraphStore module (rules, normalization, aliases)
│   │   │       └── storage/     - GraphBackend interface, NetworkX store, Neo4j adapter
│   │   ├── ingestion/
│   │   │   ├── pipeline.py      - End-to-end ingestion orchestrator
│   │   │   ├── pdf_parser.py    - PyMuPDF text and page geometry extractor
│   │   │   ├── table_extractor.py - Financial statement table parser
│   │   │   └── chunker.py       - Recursive text splitter with page metadata
│   │   ├── retrieval/
│   │   │   ├── hybrid_retriever.py - BM25 keyword ranker coupled with graph traversal
│   │   │   ├── context_builder.py  - LLM prompt context assembly with citations
│   │   │   └── vector_store.py     - In-memory chunk index
│   │   └── reasoning/
│   │       ├── qa_service.py    - Question answering pipeline with error fallback
│   │       ├── llm_client.py    - Multi-provider adapters (Gemini, OpenAI, Anthropic, Mock)
│   │       ├── offline_engine.py - Deterministic rule-based response generator
│   │       └── prompts.py       - System prompts and extraction templates
│   └── tests/                   - 61 unit and integration tests
└── frontend/
    ├── package.json             - Frontend dependencies and build scripts
    ├── vite.config.ts           - Vite build config and `/api` reverse proxy
    ├── Dockerfile               - Multi-stage build with Nginx reverse proxy
    ├── nginx.conf               - Production reverse proxy routing
    ├── .env.example             - Template for custom VITE_API_BASE_URL
    ├── components.json          - shadcn/ui configuration
    └── src/
        ├── App.tsx              - Application router and shell layout
        ├── main.tsx             - DOM mount and font imports
        ├── index.css            - Tailwind v4 theme variables and base styling
        ├── api/
        │   └── client.ts        - Typed API client with session header injection
        ├── state/
        │   └── session.tsx      - SessionProvider (documents, jobs, settings, reactive state)
        ├── routes/
        │   ├── overview.tsx     - Global workspace dashboard and balance summaries
        │   ├── filings.tsx      - Filing library, upload trigger, sample loader feedback
        │   ├── filing-layout.tsx - Sub-navigation tabs (Overview, Graph, Q&A, Tables)
        │   ├── filing-overview.tsx - Hub with feature cards, quick ask bar, table preview
        │   ├── filing-graph.tsx - React Flow graph visualization and dependency inspector
        │   ├── filing-qa.tsx    - Grounded Q&A console with streaming markdown and citations
        │   ├── filing-tables.tsx - Searchable statement and balance sheet viewer
        │   └── settings.tsx     - Provider choice, API key persistence, storage adapter
        ├── features/graph/      - Causal graph canvas, nodes, and dagre layout
        └── components/          - UI primitives (shadcn) and shared app components
```

---

## Key Invariants and Rules

1. **No business logic in UI components:** Frontend components only render state and trigger API actions. Graph traversal, causal inference, and extraction live exclusively in the backend.
2. **Never make direct LLM calls from retrieval or ingestion:** All LLM prompts route through `QAService` and `LLMClient` in `src/reasoning/`.
3. **Deep module boundary for GraphStore:** Callers interact with `GraphStore` via its domain methods (`add_metric`, `add_causal_relation`, `get_neighborhood`). Callers must never touch internal storage backend dictionaries directly.
4. **Offline first capability:** Every feature must run without an internet connection or external API key when using the default NetworkX backend and Offline Grounded engine.
5. **Zero em dashes in documentation:** Use commas, periods, colons, or parentheses. Never write em dashes (unicode U+2014).
6. **Session isolation:** Requests carry an `X-Session-ID` header. Ingestion and document lists are scoped to the active session.
7. **BYOK security:** User API keys are stored in browser `localStorage` and sent per request via the `X-LLM-Key` header. They are never written to disk by the backend.

---

## Canonical Commands

```bash
# Development (starts both backend :8000 and frontend :5173)
npm run dev

# Backend only
npm run dev:backend

# Frontend only
npm run dev:frontend

# Run backend test suite
npm run test:backend

# Production frontend build
npm run build:frontend
```
