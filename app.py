from datetime import datetime
import html
from pathlib import Path
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from src.core.env import get_settings
from src.db.graph import GraphStore
from src.ingestion import IngestionPipeline
from src.reasoning.qa_service import QAService
from src.retrieval.hybrid_retriever import HybridRetriever
from src.retrieval.vector_store import VectorStore
from src.ui.state import add_message, clear_chat, init_session_state

st.set_page_config(
    page_title="AuditIt: Causal Financial Audit",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_session_state()

SAMPLE_DIR = Path("data/sample_reports")
sample_files: list[str] = (
    sorted([f.name for f in SAMPLE_DIR.glob("*.pdf")]) if SAMPLE_DIR.exists() else []
)


def process_document(pdf_bytes: bytes, filename: str) -> None:
    """Ingest PDF, build property graph, index vector chunks, and initialize QA service."""
    try:
        pipeline = IngestionPipeline()
        ingest_result = pipeline.process(
            pdf_bytes,
            filename=filename,
            save_to_disk=False,
        )
        st.session_state["ingestion_result"] = ingest_result

        # 1. Build causal property graph with user-selected backend
        chosen_backend = st.session_state.get("graph_backend", "NetworkX")
        backend_type = "neo4j" if "neo4j" in str(chosen_backend).lower() else "networkx"
        settings = get_settings()
        neo4j_password = (
            settings.NEO4J_PASSWORD.get_secret_value() if settings.NEO4J_PASSWORD else None
        )
        graph_store = GraphStore.create(
            backend_type=backend_type,
            neo4j_uri=settings.NEO4J_URI,
            neo4j_user=settings.NEO4J_USER,
            neo4j_password=neo4j_password,
        )
        graph_store.populate_from_ingestion(ingest_result)
        st.session_state["graph_store"] = graph_store
        st.session_state["graph_stats"] = graph_store.get_stats()

        # 2. Build in-memory BM25 vector index
        vec_store = VectorStore()
        vec_store.add_chunks(ingest_result.chunks)

        # 3. Initialize hybrid retriever and question-answering service
        retriever = HybridRetriever(vector_store=vec_store, graph_store=graph_store)
        qa_service = QAService(retriever=retriever)
        st.session_state["qa_service"] = qa_service

        # 4. Record document metadata in session state
        file_size_kb = round(len(pdf_bytes) / 1024, 1)
        doc_record = {
            "name": filename,
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

        stats = st.session_state["graph_stats"]
        add_message(
            "assistant",
            f"✅ **{filename}** loaded and audited successfully!\n\n"
            f"- **Pages Parsed:** {ingest_result.metadata.total_pages}\n"
            f"- **Financial Tables Extracted:** {len(ingest_result.tables)}\n"
            f"- **Text Chunks Indexed:** {len(ingest_result.chunks)}\n"
            f"- **Graph Nodes Created:** {stats['total_nodes']} ({stats['metric_nodes']} metrics, {stats['disclosure_nodes']} disclosures)\n"
            f"- **Causal Dependencies:** {stats['causal_edges']} relationships\n\n"
            "Ask any question below or switch to the **🕸️ Causal Graph Explorer** tab to inspect drivers.",
        )
    except Exception as exc:
        st.error(f"Error processing report '{filename}': {exc}")


def execute_audit_query(query_text: str, api_key: str | None, provider: str) -> None:
    """Run hybrid retrieval and grounded audit reasoning."""
    add_message("user", query_text)
    qa_service: QAService | None = st.session_state.get("qa_service")

    if not qa_service:
        add_message(
            "assistant",
            "⚠️ **No report loaded.** Please load a sample report or upload a financial PDF in the sidebar to enable citation-grounded auditing.",
            citations=[],
        )
        return

    with st.spinner("Traversing causal graph and retrieving disclosures..."):
        resp = qa_service.answer_query(
            query=query_text,
            provider=provider,
            api_key=api_key,
        )
        citations_payload = [
            {
                "source": c.source_filename or f"Page {c.page_number}",
                "page": c.page_number,
                "type": (
                    c.citation_type.value
                    if hasattr(c.citation_type, "value")
                    else str(c.citation_type)
                ),
                "snippet": c.snippet,
            }
            for c in resp.citations
        ]
        add_message("assistant", resp.answer_text, citations=citations_payload)


# Sidebar
with st.sidebar:
    st.title("📊 AuditIt")
    st.caption("Causal Financial Audit & Disclosure Intelligence")
    st.divider()

    # Model settings
    st.subheader("Model Configuration")
    provider = st.selectbox(
        "LLM Provider",
        options=["Offline Grounded", "Gemini", "OpenAI"],
        index=0,
        help="Offline mode runs deterministically with 100% in-process grounding. Gemini/OpenAI require BYOK keys.",
    )
    st.session_state["selected_provider"] = provider

    api_key_input = ""
    if provider != "Offline Grounded":
        api_key_input = st.text_input(
            f"{provider} API Key",
            type="password",
            placeholder="Enter API key or leave blank for offline fallback",
            help="Bring Your Own Key (BYOK): keys are held in memory during the session only.",
        )

    backend = st.selectbox(
        "Graph Storage Backend",
        options=["NetworkX (In-Memory)", "Neo4j"],
        index=0,
        help="NetworkX operates entirely in memory with zero setup. Neo4j connects to a persistent property graph.",
    )
    st.session_state["graph_backend"] = backend

    st.divider()

    # Document Ingestion
    st.subheader("Report Ingestion")

    if sample_files:
        st.markdown("**Option 1: Quick Load Sample**")
        default_idx = 0
        for i, name in enumerate(sample_files):
            if "DrinkPAK" in name and "2023-22" in name:
                default_idx = i
                break

        selected_sample = st.selectbox(
            "Pre-bundled Reports",
            options=sample_files,
            index=default_idx,
            help="Select an audited report bundled in the repository.",
        )
        if st.button("🚀 Load Sample Report", type="primary", use_container_width=True):
            sample_path = SAMPLE_DIR / selected_sample
            with st.spinner(f"Ingesting {selected_sample}..."):
                process_document(sample_path.read_bytes(), filename=selected_sample)
                st.rerun()

        st.markdown("**Option 2: Upload Custom Report**")

    uploaded_file = st.file_uploader(
        "Upload Financial Report (PDF)",
        type=["pdf"],
        help="Upload 10-K, 10-Q, or annual report PDF to extract causal graphs and disclosures.",
    )

    if uploaded_file is not None:
        file_size_kb = round(len(uploaded_file.getvalue()) / 1024, 1)
        st.info(f"File loaded: **{uploaded_file.name}** ({file_size_kb} KB)")

        if st.button("Process & Build Graph", use_container_width=True):
            with st.spinner("Parsing document and constructing causal graph..."):
                process_document(uploaded_file.getvalue(), filename=uploaded_file.name)
                st.rerun()

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

# One-Click Quick Start Banner if empty
if stats["total_nodes"] == 0:
    st.divider()
    st.info(
        "💡 **No report is currently loaded.** Click below to load a pre-bundled audited report and immediately explore the causal graph, financial tables, and Q&A."
    )
    c_btn, _ = st.columns([1, 2])
    with c_btn:
        if st.button("🚀 Load DrinkPAK Sample Report (1-Click)", type="primary", use_container_width=True):
            drinkpak_path = SAMPLE_DIR / "DrinkPAK - Consolidated FS & Audit Report 2023-22.pdf"
            if drinkpak_path.exists():
                with st.spinner("Ingesting DrinkPAK 2023 audit report and building graph..."):
                    process_document(drinkpak_path.read_bytes(), filename=drinkpak_path.name)
                    st.rerun()

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
            execute_audit_query(
                prompt_text,
                api_key=api_key_input.strip() if api_key_input else None,
                provider=provider,
            )
            st.rerun()

    st.divider()

    # Message stream
    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("citations"):
                with st.expander(f"Audit Citations & Grounding ({len(msg['citations'])})", expanded=False):
                    for cite in msg["citations"]:
                        page_str = f"Page {cite['page']} | " if cite.get("page") and cite["page"] > 0 else ""
                        snippet_str = f"\n> *\"{cite['snippet']}\"*" if cite.get("snippet") else ""
                        st.markdown(f"- **{cite['source']}** ({page_str}{cite['type']}){snippet_str}")

    # Chat user input
    user_query = st.chat_input("Ask an audit or financial disclosure question...")
    if user_query:
        execute_audit_query(
            user_query,
            api_key=api_key_input.strip() if api_key_input else None,
            provider=provider,
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
            "No graph data available. Load a sample report using the button above or upload a report in the sidebar."
        )
    else:
        st.success(
            f"Graph populated with {stats['total_nodes']} node(s) and {stats['causal_edges']} causal relationship(s)."
        )
        col_g1, col_g2 = st.columns([1, 2])
        graph_store = st.session_state.get("graph_store")

        available_metrics = ["Revenue", "Cost of Sales", "Gross Margin", "Operating Income", "Net Income"]
        if graph_store:
            extracted_names = [
                n["name"]
                for n in graph_store.get_subgraph_data()["nodes"]
                if (n.get("node_type") == "METRIC" or n.get("label") == "METRIC")
                and n.get("name")
                and len(n.get("name", "")) < 35
            ]
            if extracted_names:
                available_metrics = sorted(list(set(extracted_names)))

        with col_g1:
            st.markdown("#### Dependency Query")
            selected_metric = st.selectbox(
                "Select Root Metric",
                available_metrics,
                index=0 if "Revenue" not in available_metrics else available_metrics.index("Revenue"),
            )
            direction_choice = st.selectbox(
                "Traversal Direction",
                ["Downstream Impact", "Upstream Drivers", "Full Neighborhood"],
            )
            hop_distance = st.slider("Max Hop Distance", min_value=1, max_value=4, value=2)
            trace_clicked = st.button("Trace Graph Path", use_container_width=True)

            if graph_store:
                dir_param = (
                    "downstream"
                    if "Downstream" in direction_choice
                    else ("upstream" if "Upstream" in direction_choice else "both")
                )
                neighbors = graph_store.get_neighbors(selected_metric, direction=dir_param)
                if not neighbors:
                    st.info(f"No direct {dir_param} links found for '{selected_metric}'.")
                else:
                    st.markdown(f"**Connected Nodes ({len(neighbors)}):**")
                    for n in neighbors:
                        edge_info = n.get("edge", {})
                        rel = edge_info.get("relation_type", "INFLUENCES")
                        mag = (
                            f" ({edge_info.get('impact_magnitude')})"
                            if edge_info.get("impact_magnitude")
                            else ""
                        )
                        st.markdown(f"- **{n.get('name', n.get('node_id'))}** via `{rel}{mag}`")

        with col_g2:
            st.markdown("#### Graph Visualization")
            if graph_store:
                mermaid_code = graph_store.to_mermaid(root_node=selected_metric, hops=hop_distance)
                raw_mermaid = mermaid_code.replace("```mermaid", "").replace("```", "").strip()
                escaped_mermaid = html.escape(raw_mermaid)
                mermaid_html = f"""
                <div class="mermaid" style="display:flex; justify-content:center;">
                {escaped_mermaid}
                </div>
                <script type="module">
                    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
                    mermaid.initialize({{ startOnLoad: true, theme: 'neutral' }});
                </script>
                """
                try:
                    components.html(mermaid_html, height=450, scrolling=True)
                except Exception:
                    st.markdown(mermaid_code)

                with st.expander("Mermaid Diagram Definition", expanded=False):
                    st.code(raw_mermaid, language="mermaid")
            else:
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

with tab_docs:
    st.subheader("Ingested Financial Documents")
    docs = st.session_state["ingested_documents"]
    if not docs:
        st.info("No documents uploaded yet. Load a sample report or upload a PDF report using the sidebar.")
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
            for c in ingest_result.chunks[:25]:
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

        1. **Ingestion (`src/ingestion/`)**: Parses PDF reports (`pypdf`), chunks text, and isolates balance sheet/income tables.
        2. **Graph Construction (`src/db/graph/`)**: Extracts financial metrics and causal links into in-memory NetworkX (or Neo4j) storage.
        3. **Hybrid Retrieval (`src/retrieval/`)**: Executes BM25 lexical similarity in tandem with multi-hop graph neighborhood traversal.
        4. **Reasoning & QA (`src/reasoning/`)**: Synthesizes verified audit answers with exact page citations using an offline deterministic engine or live BYOK LLMs (Gemini, OpenAI).
        """
    )
