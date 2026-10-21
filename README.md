# AuditIt Monorepo

> Graph-based financial audit and causal analysis platform.

AuditIt is structured as a clean monorepo containing two dedicated workspaces:

- **[`backend/`](backend/)**: FastAPI REST & Server-Sent Events service, Ingestion Pipeline, Deep Knowledge Graph Store (NetworkX & Neo4j), and Hybrid Retrieval Reasoning Engine.
- **[`frontend/`](frontend/)**: Interactive React 19 + TypeScript Single-Page Application (SPA) powered by Vite, Tailwind CSS, and React Flow for causal graph visualization.

---

## Quick Start

### Prerequisites
- [uv](https://docs.astral.sh/uv/) (Python >= 3.13)
- Node.js >= 18 and npm

### 1. Install Dependencies

```bash
# Install root orchestration dependencies
npm install

# Setup backend environment & dependencies
cd backend
uv sync
cd ..

# Setup frontend dependencies
cd frontend
npm install
cd ..
```

### 2. Run the Full Stack

Launch both the FastAPI backend (`http://localhost:8000`) and Vite frontend (`http://localhost:5173`) with a single command from root:

```bash
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## Workspace Navigation

- [Backend Documentation & Setup](backend/README.md)
- [Backend Architecture Specification](backend/ARCHITECTURE.md)
- [Backend Concepts & ADRs](backend/docs/)
- [Domain Glossary](backend/GLOSSARY.md)
- [Frontend Documentation](frontend/README.md)

---

## Root Commands

| Command | Action |
| --- | --- |
| `npm run dev` | Concurrently run FastAPI backend & Vite frontend |
| `npm run dev:backend` | Run FastAPI backend on port 8000 with auto-reload |
| `npm run dev:frontend` | Run Vite React frontend on port 5173 |
| `npm run test:backend` | Execute backend pytest test suite (56 tests) |
| `npm run build:frontend` | Compile frontend TypeScript and build static bundle |
