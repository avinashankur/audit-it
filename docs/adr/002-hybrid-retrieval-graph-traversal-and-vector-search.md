# 002-ADR: Implement Hybrid Retrieval Combining Graph Traversal and Vector Search

**Date:** 2026-10-19
**Status:** Proposed
**Deciders:** AuditIt Engineering Team
**Tags:** retrieval, rag, graph, vector-search, reasoning

---

## Context

Financial audit and disclosure analysis involves two distinct types of data within annual reports:

1. **Unstructured narrative disclosures:** Management Discussion and Analysis (MD&A), accounting policy footnotes, risk factors, and auditor notes.
2. **Structured causal dependencies:** Hierarchical relationships between financial line items, ratios, and operating drivers (e.g. higher raw material costs leading to gross margin contraction).

Traditional Retrieval-Augmented Generation (RAG) relies on dense vector embeddings over chunked text. While vector search is effective for finding relevant narrative paragraphs, it fails to reliably follow multi-hop causal chains across financial tables. Conversely, pure graph traversal finds connected metrics and ratios deterministically, but cannot answer qualitative questions that rely on text that was not extracted into discrete graph entities.

## Decision

We will implement a hybrid retrieval architecture that combines dense vector similarity search with structured graph neighborhood traversal (`src/retrieval/hybrid_retriever.py`).

- **Vector retrieval** (`src/retrieval/vector_store.py`) will index document chunks to retrieve relevant qualitative context and narrative disclosures.
- **Graph traversal** (`src/retrieval/graph_traversal.py`) will resolve causal paths, upstream dependencies, and downstream impacts around identified financial entities.
- **Context builder** (`src/retrieval/context_builder.py`) will assemble and deduplicate findings from both retrieval paths into a structured prompt context for the LLM, maintaining explicit citation links to both source text chunks and graph relationship edges.

## Alternatives Considered

### Option A: Pure Vector Search RAG

This approach indexes all parsed PDF text chunks into a vector database and performs cosine similarity search based on the user's query.

- **Pros:** Standardized architecture, simple implementation using commodity vector stores, and broad coverage of natural language queries.
- **Cons:** Fails to trace multi-step causal paths between distant financial metrics. Semantically similar chunks often miss the concrete numerical formulas or balance sheet equations that explain metric movements.
- **Why we did not choose it:** Financial auditing requires deterministic attribution of metric drivers, which pure semantic similarity cannot reliably guarantee.

### Option B: Pure Knowledge Graph Retrieval

This approach converts all report disclosures into graph triples and answers queries solely by traversing entity nodes and edges.

- **Pros:** Completely deterministic and explainable reasoning paths with zero hallucination along modeled causal links.
- **Cons:** Extremely high sensitivity to extraction errors during ingestion. Complex, nuanced narrative explanations (such as litigation risks or macroeconomic commentary) resist clean graph triple representation and get lost.
- **Why we did not choose it:** A significant portion of critical audit context lives in narrative text that cannot be fully converted into graph nodes without loss of essential nuance.

### Option C (chosen): Hybrid Retrieval (Graph Traversal + Vector Search)

This approach executes semantic search over text chunks and graph neighborhood expansion over causal nodes in tandem.

- **Why this one:** It provides the breadth of text-based retrieval alongside the structural rigor of causal relationship modeling. Auditors obtain both the exact narrative disclosure and the quantitative dependency graph explaining the metric.

## Consequences

### Positive

- Accurate context assembly for both qualitative disclosures and quantitative metric relationships.
- Grounded citations linking answers to both source document page chunks and verified causal graph paths.
- Resilient to graph extraction gaps: questions not fully modeled in the graph still receive relevant textual context via vector search.

### Negative

- Increased retrieval latency due to executing two separate query pipelines per request.
- Added complexity in the context builder layer, which must rank, filter, and balance graph relationships against text chunks within token budget limits.

### Neutral

- Prompts must be designed with explicit templates to present both relational graph tuples and text excerpts clearly to the LLM.

## Follow-up Actions

- [ ] Implement vector index and embedding interface in `src/retrieval/vector_store.py`.
- [ ] Implement graph traversal and neighbor extraction in `src/retrieval/graph_traversal.py`.
- [ ] Build the unified query coordinator in `src/retrieval/hybrid_retriever.py`.
- [ ] Implement prompt context formatting and citation synthesis in `src/retrieval/context_builder.py`.

## References

- [ARCHITECTURE.md](file:///E:/dev/auditit/ARCHITECTURE.md#L60-L80)
- [CONTEXT.md](file:///E:/dev/auditit/CONTEXT.md#L104-L113)
- [001-ADR: Adopt Dual Graph Backend Architecture with NetworkX and Neo4j](file:///E:/dev/auditit/docs/adr/001-dual-graph-backend-networkx-and-neo4j.md)
