from datetime import datetime

import streamlit as st

from src.ingestion import IngestionPipeline
from src.ui.state import add_message, clear_chat, init_session_state

st.set_page_config(
    page_title="AuditIt: Causal Financial Audit",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_session_state()

# Sidebar
with st.sidebar:
    st.title("📊 AuditIt")
    st.caption("Causal Financial Audit & Disclosure Intelligence")
    st.divider()

    # Model settings
    st.subheader("Model Configuration")
    provider = st.selectbox(
        "LLM Provider",
        options=["Gemini", "OpenAI", "Anthropic"],
        index=0,
        help="Select the LLM provider for entity extraction and question answering.",
    )
    st.session_state["selected_provider"] = provider

    api_key_input = st.text_input(
        f"{provider} API Key",
        type="password",
        placeholder="Enter API key or load from .env",
        help="Bring Your Own Key (BYOK): keys are held in memory during the session only.",
    )

    backend = st.selectbox(
        "Graph Storage Backend",
        options=["NetworkX (In-Memory)", "Neo4j"],
        index=0,
        help="NetworkX operates entirely in memory. Neo4j connects to a persistent property graph.",
    )
    st.session_state["graph_backend"] = backend

    st.divider()

    # Document Ingestion
    st.subheader("Report Ingestion")
    uploaded_file = st.file_uploader(
        "Upload Financial Report (PDF)",
        type=["pdf"],
        help="Upload 10-K, 10-Q, or annual report PDF to extract causal graphs and disclosures.",
    )

    if uploaded_file is not None:
        file_size_kb = round(len(uploaded_file.getvalue()) / 1024, 1)
        st.info(f"File loaded: **{uploaded_file.name}** ({file_size_kb} KB)")

        if st.button("Process & Build Graph", type="primary", use_container_width=True):
            with st.spinner(
                "Parsing document, extracting financial tables, and chunking text..."
            ):
                try:
                    pipeline = IngestionPipeline()
                    ingest_result = pipeline.process(
                        uploaded_file.getvalue(),
                        filename=uploaded_file.name,
                        save_to_disk=True,
                    )
                    st.session_state["ingestion_result"] = ingest_result

                    # Register document in session state
                    doc_record = {
                        "name": uploaded_file.name,
                        "size_kb": file_size_kb,
                        "pages": ingest_result.metadata.total_pages,
                        "chunks": len(ingest_result.chunks),
                        "tables": len(ingest_result.tables),
                        "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "status": "Ready",
                    }
                    if doc_record not in st.session_state["ingested_documents"]:
                        st.session_state["ingested_documents"].append(doc_record)
                    st.session_state["current_document"] = doc_record

                    # Sample mock graph metrics for initialized UI until Phase 3/4
                    st.session_state["graph_stats"] = {
                        "total_nodes": 42,
                        "metric_nodes": 28,
                        "disclosure_nodes": 14,
                        "causal_edges": 36,
                    }
                    st.success(
                        f"Document parsed: {ingest_result.metadata.total_pages} page(s), "
                        f"{len(ingest_result.tables)} financial table(s), "
                        f"{len(ingest_result.chunks)} text chunk(s)."
                    )
                except Exception as exc:
                    st.error(f"Error parsing document: {exc}")

    st.divider()
    if st.button("Clear Conversation", use_container_width=True):
        clear_chat()
        st.rerun()

# Header & metrics
st.title("AuditIt: Financial Audit & Causal Graph Platform")
st.markdown(
    "Analyze corporate reports, trace causal dependencies across metrics, "
    "and audit disclosure footnotes with hybrid retrieval and verified citations."
)

stats = st.session_state["graph_stats"]
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric(label="Total Graph Nodes", value=stats["total_nodes"])
with col2:
    st.metric(label="Financial Metric Nodes", value=stats["metric_nodes"])
with col3:
    st.metric(label="Disclosure Footnotes", value=stats["disclosure_nodes"])
with col4:
    st.metric(label="Causal Dependencies", value=stats["causal_edges"])

st.divider()

# Main views
tab_chat, tab_graph, tab_docs, tab_arch = st.tabs(
    [
        "💬 Audit Q&A",
        "🕸️ Causal Graph Explorer",
        "📄 Ingested Documents",
        "📐 Architecture",
    ]
)

with tab_chat:
    st.subheader("Audit Investigation & Question Answering")

    # Sample query prompts
    st.caption("Quick Audit Inquiries:")
    quick_queries = [
        "What factors drove gross margin contraction in the latest period?",
        "Trace the causal dependency chain between R&D spend and operating income.",
        "List all footnote disclosures related to debt covenants and liquidity.",
    ]
    query_cols = st.columns(len(quick_queries))
    for idx, prompt_text in enumerate(quick_queries):
        if query_cols[idx].button(prompt_text, key=f"quick_query_{idx}"):
            add_message("user", prompt_text)
            add_message(
                "assistant",
                f"Analyzing query: '{prompt_text}'.\n\n"
                "Hybrid retrieval executed across text chunks and causal graph paths. "
                "Connect ingestion services to stream model outputs from `src/reasoning/qa_service.py`.",
                citations=[
                    {"source": "10-K Item 7 (MD&A)", "page": 42, "type": "Text Chunk"},
                    {
                        "source": "Revenue -> Gross Margin -> Operating Income",
                        "type": "Causal Graph Path",
                    },
                ],
            )
            st.rerun()

    st.divider()

    # Message stream
    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("citations"):
                with st.expander("Audit Citations & Grounding", expanded=False):
                    for cite in msg["citations"]:
                        if "page" in cite:
                            st.markdown(
                                f"- **{cite['source']}** (Page {cite['page']}, {cite['type']})"
                            )
                        else:
                            st.markdown(f"- **{cite['source']}** ({cite['type']})")

    # Chat user input
    user_query = st.chat_input("Ask an audit or financial disclosure question...")
    if user_query:
        add_message("user", user_query)
        # Placeholder response while backend service is wired up
        add_message(
            "assistant",
            f"Received query: '{user_query}'.\n\n"
            f"Active Provider: **{st.session_state['selected_provider']}** | Backend: **{st.session_state['graph_backend']}**\n\n"
            "This query will route through `src/retrieval/hybrid_retriever.py` to retrieve causal nodes "
            "and text embeddings before generating verified answers via `src/reasoning/qa_service.py`.",
            citations=[
                {"source": "System Routing", "type": "Hybrid Pipeline"},
            ],
        )
        st.rerun()

with tab_graph:
    st.subheader("Causal Knowledge Graph Explorer")
    st.markdown(
        "Explore relationships between reported metrics, accounting line items, and disclosures. "
        "Directed edges represent causal influence (e.g. `Revenue -> Gross Margin`)."
    )

    if stats["total_nodes"] == 0:
        st.info(
            "No graph data available. Upload and process a financial report in the sidebar to populate the graph."
        )
    else:
        st.success(
            f"Graph populated with {stats['total_nodes']} nodes and {stats['causal_edges']} causal relationships."
        )
        col_g1, col_g2 = st.columns([1, 2])
        with col_g1:
            st.markdown("#### Dependency Query")
            st.selectbox(
                "Select Root Metric",
                ["Revenue", "Operating Expenses", "Gross Margin", "Net Income"],
            )
            st.selectbox(
                "Traversal Direction",
                ["Downstream Impact", "Upstream Drivers", "Full Neighborhood"],
            )
            st.slider("Max Hop Distance", min_value=1, max_value=4, value=2)
            st.button("Trace Graph Path", use_container_width=True)
        with col_g2:
            st.markdown("#### Graph Visualization")
            st.code(
                """
  [ Revenue ] --------(+12.4% YoY)-------> [ Gross Profit ]
       |                                          |
   (Volume +8%)                              (-180 bps Margin)
       v                                          v
  [ Cost of Sales ] ---(-210 bps)--------> [ Operating Income ]
       |
  [ Footnote 4: Supply Chain Inflation ]
                """,
                language="text",
            )
            st.caption(
                "Interactive graph visualization renderer connects to `src/db/graph/visualizer.py`."
            )

with tab_docs:
    st.subheader("Ingested Financial Documents")
    docs = st.session_state["ingested_documents"]
    if not docs:
        st.info("No documents uploaded yet. Upload a PDF report using the sidebar.")
    else:
        st.table(docs)

    ingest_result = st.session_state.get("ingestion_result")
    if ingest_result:
        st.divider()
        st.subheader("Extracted Financial Tables")
        if not ingest_result.tables:
            st.caption("No tables detected on the parsed pages.")
        else:
            for idx, table in enumerate(ingest_result.tables):
                title = table.title or f"Table {idx + 1}"
                with st.expander(f"📊 {title} (Page {table.page_number})", expanded=(idx == 0)):
                    st.markdown(table.markdown)

        st.divider()
        st.subheader("Extracted Text Chunks")
        with st.expander(f"📑 View {len(ingest_result.chunks)} Text Chunks", expanded=False):
            for c in ingest_result.chunks[:20]:
                header = f"Page {c.page_number}"
                if c.section_header:
                    header += f" | {c.section_header}"
                if c.token_count:
                    header += f" (~{c.token_count} tokens)"
                st.markdown(f"**{header}**")
                st.text(c.text)
                st.divider()

with tab_arch:
    st.subheader("System Architecture & Processing Pipeline")
    st.markdown(
        """
        The AuditIt system operates via a decoupled pipeline adhering to the C4 specifications in [ARCHITECTURE.md](ARCHITECTURE.md):

        1. **Ingestion (`src/ingestion/`)**: Parses PDF reports (`pypdf` / `LlamaParse`), chunks text, and isolates balance sheet/income tables.
        2. **Graph Construction (`src/db/graph/`)**: Extracts financial metrics and causal links into NetworkX and optional Neo4j storage.
        3. **Hybrid Retrieval (`src/retrieval/`)**: Executes dense vector similarity search in tandem with graph neighborhood traversal.
        4. **Reasoning & QA (`src/reasoning/`)**: Constructs structured contexts and queries BYOK LLMs (Gemini, OpenAI, Anthropic) with strict source citation grounding.
        """
    )
