# AuditIt

> Graph-based financial audit and causal analysis platform for corporate disclosures and metrics.

---

## What is this?

AuditIt is a financial report analysis tool that extracts causal relationships among financial metrics, ratios, and footnote disclosures. By structuring report data into a knowledge graph, AuditIt enables auditors and analysts to trace dependencies between numbers, visualize metric drivers, and perform hybrid retrieval (graph traversal plus semantic search) to answer complex financial queries with exact source citations.

## Features

- **Causal Knowledge Graph**: Models relationships among financial metrics and ratios using NetworkX and an optional Neo4j storage adapter.
- **Hybrid Retrieval**: Combines vector similarity search with graph traversal to ground answers in connected financial context.
- **Bring Your Own Key (BYOK)**: Supports Google Gemini, OpenAI, and Anthropic API keys.
- **Interactive Streamlit Interface**: Visualizes causal graphs, inspects citations, and tracks financial metrics.
- **Automated Report Ingestion**: Parses PDF annual reports and financial statements with chunking and table extraction.

## Quick Start

### Prerequisites

- Python >= 3.11
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
uv pip install -r requirements.txt
# (or: uv sync)

# Configure environment variables
cp .env.example .env
# Edit .env with your LLM API keys
```

### Run

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

## Running Tests

```bash
uv run pytest
```

---

## Project Structure

```
app.py                  - Streamlit application entry point
config/                 - Application configuration and environment settings
src/
  core/                 - Environment, exceptions, logging, and core models
  ingestion/            - Document loading, PDF parsing, chunking, and table extraction
  db/
    graph/              - Graph builders, extractors, storage adapters, and visualizer
  retrieval/            - Graph traversal, vector store, hybrid retrieval, context builder
  reasoning/            - LLM clients, prompt templates, offline engine, and QA service
  ui/                   - Streamlit components and session state management
data/
  sample_reports/       - Sample financial report PDFs
tests/                  - Test suite
docs/
  adr/                  - Architecture Decision Records
  concepts/             - Technical concept deep-dives
  runbooks/             - Operational runbooks
```

---

## Documentation

- [Architecture Overview](ARCHITECTURE.md)
- [AI & Contributor Context](CONTEXT.md)
- [Architecture Decision Records (ADRs)](docs/adr/)
- [Concept Deep-Dives](docs/concepts/)
- [Runbooks](docs/runbooks/)

---

## Contributing

Review [CONTEXT.md](CONTEXT.md) and [ARCHITECTURE.md](ARCHITECTURE.md) before submitting code changes or opening pull requests.

---

## License

<!-- TODO: fill in license (e.g. MIT, Apache 2.0, or Proprietary) -->
