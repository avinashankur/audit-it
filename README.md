# AuditIt

> Graph-based financial audit and causal analysis platform for corporate disclosures and metrics.

---

## What is this?

AuditIt is a financial report analysis tool that extracts causal relationships among financial metrics, ratios, and footnote disclosures. By structuring report data into a knowledge graph, AuditIt enables auditors and analysts to trace dependencies between numbers, visualize metric drivers, and perform hybrid retrieval (graph traversal plus semantic search) to answer complex financial queries with exact source citations.

## Features

- **Causal Knowledge Graph**: Models relationships among financial metrics and ratios using a deep `GraphStore` module backed by NetworkX and persistent Neo4j adapters.
- **Hybrid Retrieval**: Combines BM25 vector similarity search with multi-hop graph traversal to ground answers in connected financial context.
- **Bring Your Own Key (BYOK)**: Supports Google Gemini, OpenAI, and Anthropic API keys, with offline deterministic reasoning fallback.
- **Interactive Streamlit Interface**: Visualizes causal graphs with Mermaid, inspects citations, and tracks financial metrics.
- **Automated Report Ingestion**: Parses PDF annual reports and financial statements with chunking and table extraction.

## Quick Start

### Prerequisites

- Python >= 3.13
- uv package manager
- (Optional) Neo4j Database >= 5.x for persistent graph storage
- API key for at least one LLM provider (Google Gemini, OpenAI, or Anthropic)

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd auditit

# Set up virtual environment with uv
uv venv
# On Windows PowerShell:
.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies using uv
uv sync

# Configure environment variables
cp .env.example .env
# Edit .env with your LLM API keys
```

### Run Tests

```bash
# Execute automated test suite (unit, integration, and adapter parity)
uv run pytest
```

### Run Application

```bash
# Start Streamlit application
uv run streamlit run app.py
```

The application runs at http://localhost:8501.

---

## Configuration

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `GEMINI_API_KEY` | No | - | Google Gemini API key |
| `OPENAI_API_KEY` | No | - | OpenAI API key |
| `ANTHROPIC_API_KEY` | No | - | Anthropic API key |
| `NEO4J_URI` | No | `bolt://localhost:7687` | Neo4j connection URI (if using Neo4j) |
| `NEO4J_USER` | No | `neo4j` | Neo4j database user |
| `NEO4J_PASSWORD` | No | - | Neo4j database password |
| `LOG_LEVEL` | No | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

---

## Project Structure

```
app.py                  - Streamlit application entry point
GLOSSARY.md             - Domain glossary and business terminology
src/
  core/                 - Environment, exceptions, and structured logging
  ingestion/            - Document loading, PDF parsing, chunking, and table extraction
  db/
    graph/              - Deep GraphStore module, builders, and storage adapters (NetworkX, Neo4j)
  retrieval/            - Vector store, hybrid retriever, and context builder
  reasoning/            - QA orchestration service (offline fallback + BYOK live models)
  ui/                   - Streamlit state management and UI components
data/
  sample_reports/       - Sample financial report PDFs
docs/
  adr/                  - Architecture Decision Records
  concepts/             - Technical concept deep-dives
  runbooks/             - Operational runbooks
tests/
  test_graph_backend_parity.py - Behavioral parity tests across storage adapters
  test_graph_store.py          - Domain rule and ingestion tests for GraphStore
  test_hybrid_retriever.py     - End-to-end hybrid retrieval tests
```

---

## Documentation

- [Domain Glossary](GLOSSARY.md)
- [Architecture Overview](ARCHITECTURE.md)
- [AI & Contributor Context](CONTEXT.md)
- [Architecture Decision Records (ADRs)](docs/adr/)
- [Concept Deep-Dives](docs/concepts/)
- [Runbooks](docs/runbooks/)
- [Implementation Walkthrough](walkthrough.md)

---

## Contributing

Review [CONTEXT.md](CONTEXT.md) and [ARCHITECTURE.md](ARCHITECTURE.md) before submitting code changes or opening pull requests.

---

## License

MIT
