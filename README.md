# AuditIt

> Turn financial filings into a causal graph you can explore, inspect, and question.

AuditIt is a web app for financial report analysis. It reads a PDF, extracts financial metrics, tables, and narrative disclosures, and connects them in a causal knowledge graph. You can inspect the graph, read the extracted statements, or ask questions and get answers with page-level citations.

The app works without an API key in **Offline Grounded** mode. Gemini, OpenAI, and Anthropic are optional.

## What it does

- **Reads PDF filings.** Extracts text, page numbers, financial tables, metrics, and footnote disclosures.
- **Builds a causal graph.** Connects metrics and disclosures with directed cause-to-effect relationships.
- **Explores dependencies.** Click a node to trace its upstream and downstream drivers. Adjust graph depth and footnote visibility in Settings.
- **Shows financial tables.** Search, filter, and inspect extracted balance sheets, income statements, and cash flow tables.
- **Answers questions with citations.** Combines keyword search with graph traversal, then returns an answer with source snippets and page numbers. Answers stream into the UI.
- **Runs locally.** The default graph backend is in-memory NetworkX. Offline Grounded mode makes no external model calls. Neo4j is optional for graph persistence.
- **Supports bring-your-own-key.** Use Gemini, OpenAI, or Anthropic from Settings, or set server-side API keys in `backend/.env`.

## Quick start

### Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)
- Node.js 20.19+ and npm
- Optional: Neo4j 5.x if you want persistent graph storage

### 1. Install

```bash
git clone https://github.com/avinashankur/audit-it.git
cd audit-it

# Root development runner
npm install

# Backend
cd backend
uv sync
cd ..

# Frontend
cd frontend
npm install
cd ..
```

### 2. Run

From the repository root:

```bash
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

The API runs at [http://localhost:8000](http://localhost:8000), and its interactive API docs are at [http://localhost:8000/docs](http://localhost:8000/docs).

No environment file is needed for the demo. You can load a sample filing immediately.

### 3. Optional configuration

Create `backend/.env` if you want server-side model keys or Neo4j:

```env
# Optional model providers
GEMINI_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=

# Optional Neo4j graph persistence
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
```

You can also enter a model key in the app Settings. Restart the backend after changing `backend/.env`.

## Basic usage

The app starts on **Overview**, which summarizes all filings in the current session, highlights the largest balance, and lists recent filings. Use **Filings** to load data, then open a filing for its overview, graph, Q&A, and tables.

### 1. Load a filing

Open **Filings** from the sidebar, then either:

- Choose **Load sample filing** and select `AuditIt Demo - Northwind Cloud FY2024`, or
- Select **Upload filing** and choose a PDF from your computer.

The default upload limit is 50 MB. Ingestion runs as a background job, and the progress bar shows the current stage. Wait for the filing status to become ready.

### 2. Open the filing overview

Click the filing name in the library. The filing overview gives you three entry points:

- **Causal graph**: inspect metric nodes and their dependencies.
- **Q&A**: ask questions about the filing.
- **Financial tables**: review extracted statements.

It also shows a preview of the extracted tables and a quick question box.

### 3. Explore the causal graph

Open **Causal graph** in the sidebar or from the filing overview.

- Nodes represent financial metrics and disclosure or footnote context.
- Edges point from cause to effect.
- Click a node to load its dependency neighborhood and evidence.
- Use **Default hop depth** in Settings to control how far the graph expands.
- Use **Show footnote nodes** to include or hide narrative disclosures.

If a PDF has no causal edges, the graph still shows extracted metrics. Edge extraction depends on the report structure and the relationships the extractor can verify.

### 4. Check the financial tables

Open **Tables** to see every structured table found in the filing. You can:

- Search by table title, header, or page number.
- Jump to a specific table.
- Inspect rows, columns, and page references.

### 5. Ask questions

Open **Q&A** and type a question, or choose one of the starter questions.

Answers are built from retrieved report excerpts and graph paths. Each answer shows:

- A written analysis.
- The causal chain when one is available.
- Source snippets with page numbers.

**Offline Grounded** answers locally without an external model call. Choosing Gemini, OpenAI, or Anthropic sends the retrieved report context to that provider and uses your key to synthesize the answer.

### 6. Adjust Settings

| Setting | What it controls |
| --- | --- |
| LLM reasoning engine | Offline Grounded, Gemini, OpenAI, or Anthropic |
| API key | Your provider key. If empty, the backend environment key is used. |
| Graph storage adapter | NetworkX (in memory) or Neo4j (persistent graph) |
| Show footnote nodes | Whether disclosure nodes appear in the graph |
| Default hop depth | How many graph hops are loaded from a selected node |
| Theme | Light, dark, or system |

The graph backend is selected per ingestion. Choose Neo4j in Settings **before** loading a filing if you want that filing stored in Neo4j. Existing NetworkX filings are not migrated.

## How it works

```text
PDF filing
   |
   +--> text chunks ---------------------------> BM25 search index
   |
   +--> tables, metrics, disclosures ---------> causal graph
                                                   |
Question ------------------------------------------+
   |
   +--> BM25 retrieval + graph traversal
   |
   +--> grounded context, causal paths, citations
   |
   +--> Offline Grounded answer or LLM answer
```

The backend exposes REST endpoints for ingestion, graph inspection, tables, and Q&A. Q&A also has a Server-Sent Events endpoint for streaming tokens and citations to the frontend. The frontend talks to the API through `/api`; Vite proxies that path to the backend during development.

### Stack

- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS, shadcn/ui, React Flow
- **Backend:** Python 3.13, FastAPI, Pydantic
- **Graph:** NetworkX by default, Neo4j optional
- **Retrieval:** In-memory BM25 text ranking plus graph traversal
- **Reasoning:** Deterministic offline engine or Gemini, OpenAI, and Anthropic

## Optional Neo4j setup

NetworkX is the default and requires no extra service. To keep graph nodes and edges in Neo4j:

```bash
docker run -d --name auditit-neo4j \
  --restart unless-stopped \
  -p 127.0.0.1:7474:7474 \
  -p 127.0.0.1:7687:7687 \
  -e NEO4J_AUTH=neo4j/your-password \
  -v auditit_neo4j_data:/data \
  neo4j:5
```

Set `NEO4J_URI`, `NEO4J_USER`, and `NEO4J_PASSWORD` in `backend/.env`, restart the backend, then select **Neo4j** in Settings before loading a filing.

Neo4j persists graph nodes and edges. The filing registry, chunks, tables, and retrieval index are still held in the backend process. If the backend restarts, re-ingest the filing even if its graph remains in Neo4j.

If Neo4j cannot be reached, the current adapter falls back to in-memory NetworkX and logs a warning. Check the backend logs if a filing does not appear in Neo4j.

## Commands

| Command | Action |
| --- | --- |
| `npm run dev` | Run the backend and frontend together |
| `npm run dev:backend` | Run FastAPI on port 8000 with reload |
| `npm run dev:frontend` | Run Vite on port 5173 |
| `npm run test:backend` | Run the backend test suite |
| `npm run build:frontend` | Build the production frontend bundle |
| `cd frontend && npm run lint` | Lint the frontend |

## Project layout

```text
auditit/
├── backend/
│   ├── src/api/             FastAPI routes, schemas, and session manager
│   ├── src/ingestion/       PDF parsing, chunking, and table extraction
│   ├── src/db/graph/        Graph store, NetworkX backend, Neo4j adapter
│   ├── src/retrieval/       BM25 index, graph retrieval, context building
│   ├── src/reasoning/       Offline engine and LLM provider clients
│   ├── data/sample_reports/ Demo and public-company sample filings
│   └── tests/               Backend test suite
├── frontend/
│   ├── src/routes/          Overview, filings, graph, Q&A, tables, settings
│   ├── src/features/graph/  Causal graph canvas
│   ├── src/components/      Layout and UI components
│   ├── src/api/             Typed API client
│   └── src/state/           Session and settings state
├── package.json             Root development commands
└── README.md
```

## Troubleshooting

**The status bar says "Engine unreachable".**
Check that the backend is running and open [http://localhost:8000/api/health](http://localhost:8000/api/health).

**The library is empty after restarting the backend.**
The default session registry is in memory. Re-ingest the filing. Neo4j keeps graph data, but it does not restore the filing list or retrieval index.

**A PDF produces no causal edges.**
Not every filing contains explicit relationships the extractor can verify. Start with the bundled Northwind Cloud demo to see a fully connected example.

**Neo4j is selected but new data does not appear there.**
Check the URI and credentials, confirm the container is running, and check the backend logs for a fallback warning. The backend must be restarted after changing `backend/.env`.

**An upload is rejected.**
The default limit is 50 MB. Check that the file is a valid PDF and that the backend health endpoint is responding.

## Current limitations

- Filings and sessions are process-local and in memory by default. A backend restart clears the filing library, tables, and retrieval index.
- Neo4j persists the graph only, not the complete application state.
- The app has no user authentication. Do not expose it publicly without adding authentication and per-user access control.
- Multiple backend workers do not share in-memory sessions. Run one backend process unless you add shared state.
- Extraction quality depends on the PDF. Digitally generated financial reports work better than scanned images.

## Documentation

- [System architecture](ARCHITECTURE.md)
- [Developer context guide](CONTEXT.md)
- [Backend architecture](backend/ARCHITECTURE.md)
- [Backend context guide](backend/CONTEXT.md)
- [Architecture decision records](backend/docs/adr/)
- Interactive API reference: [http://localhost:8000/docs](http://localhost:8000/docs)
