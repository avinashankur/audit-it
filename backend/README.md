# AuditIt

> Graph-based financial audit and causal analysis platform for corporate disclosures and metrics.

---

## What is this?

AuditIt is a financial report analysis platform that extracts causal relationships among financial metrics, ratios, and footnote disclosures. By structuring report data into a property knowledge graph, AuditIt enables auditors and analysts to trace dependencies between numbers, visualize metric drivers on an interactive canvas, and perform hybrid retrieval (multi-hop graph traversal plus semantic vector search) to answer complex financial queries with exact source citations.

## Features

- **Interactive Causal Graph Canvas**: Visualizes financial drivers, ratios, and footnote disclosures using React Flow with automatic Dagre hierarchical DAG layout (`cause ➔ effect`).
- **Real-Time Grounded Q&A**: Streams reasoning tokens and source citations via Server-Sent Events (SSE) with verifiable page citations and causal path graphs.
- **Deep Graph Store**: Domain-driven graph engine backed by in-memory NetworkX and persistent Neo4j adapters.
- **Decoupled Architecture**: Clean monorepo (`backend/` FastAPI service + `frontend/` Vite React TypeScript SPA) with automated OpenAPI-to-TypeScript type safety.
- **Bring Your Own Key (BYOK)**: Supports Google Gemini, OpenAI, and Anthropic API keys with offline deterministic reasoning fallback.
- **Tabular Intelligence**: Automatically extracts and displays financial statement tables with multi-column filtering.

---

## Quick Start

### Prerequisites

- Python >= 3.13 and [uv](https://docs.astral.sh/uv/)
- Node.js >= 18 and npm
- (Optional) Neo4j Database >= 5.x for persistent graph storage

### 1. Installation

```bash
# Clone the repository
git clone <repository-url>
cd auditit

# Install root dependencies (concurrently dev runner)
npm install

# Install backend dependencies with uv
cd backend
uv sync
cd ..

# Install frontend dependencies
cd frontend
npm install
cd ..
```

### 2. Run the Full Stack Application

Launch both the FastAPI backend (`http://localhost:8000`) and Vite frontend (`http://localhost:5173`) with a single command from the root directory:

```bash
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

---

### Running Services Independently

#### Backend (FastAPI)
```bash
cd backend
uv run uvicorn src.api.main:app --reload --port 8000
```
- Interactive Swagger API docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- OpenAPI Specification: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

#### Frontend (Vite + React)
```bash
cd frontend
npm run dev
```

#### Legacy Streamlit Interface (Fallback)
```bash
cd backend
uv run streamlit run app.py
```

---

## Automated Test Suites

```bash
# Run backend test suite (56 unit, integration, and API tests)
npm run test:backend

# Or directly in backend directory
cd backend
uv run pytest
```

---

## Project Structure

```
auditit/
├── backend/
│   ├── src/
│   │   ├── api/                  # FastAPI app, routers, schemas, session manager
│   │   │   ├── routes/           # documents, graph, query, samples, health
│   │   │   ├── dependencies.py   # BYOK header extractor & session manager injection
│   │   │   ├── session_mgr.py    # In-memory document & graph registry
│   │   │   └── schemas.py        # Pydantic request/response models
│   │   ├── core/                 # Environment, exceptions, structured logging
│   │   ├── db/                   # GraphStore, NetworkX & Neo4j adapters, entity models
│   │   ├── ingestion/            # PDF parser, chunker, table extractor
│   │   ├── reasoning/            # QAService, BYOK LLM client, offline engine
│   │   ├── retrieval/            # VectorStore, HybridRetriever, ContextBuilder
│   │   └── ui/                   # Streamlit state components (legacy)
│   ├── tests/                    # 56 pytest tests (extractors, stores, API endpoints)
│   ├── data/sample_reports/      # Pre-packaged 10-K financial reports
│   ├── app.py                    # Legacy Streamlit app
│   ├── pyproject.toml            # Python package specification
│   └── uv.lock
├── frontend/
│   ├── src/
│   │   ├── api/                  # Generated schema types and fetch client
│   │   ├── components/
│   │   │   ├── graph/            # React Flow canvas, Dagre layout, CitationDrawer
│   │   │   ├── chat/             # Streaming audit assistant with SSE
│   │   │   ├── ingestion/        # Upload dropzone & sample report loader
│   │   │   ├── tables/           # Financial table viewer
│   │   │   └── layout/           # Navbar, SettingsModal
│   │   ├── types/                # Domain models re-exported from OpenAPI
│   │   ├── App.tsx               # Primary single-page application
│   │   └── main.tsx
│   ├── package.json              # React 19, Vite, Tailwind CSS, React Flow
│   └── vite.config.ts            # Development proxy: /api -> http://localhost:8000
├── package.json                  # Root monorepo orchestration (concurrently)
├── README.md
└── ARCHITECTURE.md
```
