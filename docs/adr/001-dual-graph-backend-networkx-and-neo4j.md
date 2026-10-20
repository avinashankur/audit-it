# 001-ADR: Adopt Dual Graph Backend Architecture with NetworkX and Neo4j

**Date:** 2026-10-19 (Updated: 2026-10-20)  
**Status:** Accepted  
**Deciders:** AuditIt Engineering Team  
**Tags:** graph, storage, database, architecture  

---

## Context

AuditIt models causal relationships among financial metrics, ratios, and report disclosures as a directed property graph. The system must support two distinct execution environments:

1. **Local development and automated testing:** Fast, zero-configuration execution where developers and CI pipelines run tests and analyze single reports without starting external database servers.
2. **Enterprise multi-report analysis:** Persistent, cross-document graph storage where teams query multi-quarter trends across multiple companies using standardized graph query languages like Cypher.

Coupling the application strictly to an external graph database increases onboarding overhead and complicates unit testing. Conversely, relying solely on an in-memory graph prevents long-term persistence and cross-report querying.

## Decision

We have implemented a dual graph backend architecture centered on an abstract storage port (`src/db/graph/storage/base.py`):

- **NetworkXBackend** (`src/db/graph/storage/networkx_store.py`) serves as the default in-memory graph engine for local execution, unit tests, and single-document analysis.
- **Neo4jBackend** (`src/db/graph/storage/neo4j_adapter.py`) serves as the pluggable adapter for persistent storage, executing native Cypher queries with automatic in-memory fallback when offline.
- **GraphStore** (`src/db/graph/store.py`) acts as the deep module owning domain logic, canonical entity normalization, accounting causal rules, and neighborhood traversal queries, shielding callers and storage adapters from leaked internals.

All extraction and retrieval components interact exclusively with `GraphStore`, ensuring graph construction and traversal logic remain independent of the underlying storage engine.

## Alternatives Considered

### Option A: Pure Neo4j Backend (Mandatory Database)

This approach uses Neo4j as the sole graph engine for all environments.

- **Pros:** Native Cypher query execution, robust graph indexing, built-in graph visualization tools (Neo4j Browser), and proven persistence for large-scale property graphs.
- **Cons:** Requires a running Neo4j container or cloud instance for every test run and local development session. Increases memory requirements and adds setup friction for new contributors.
- **Why we did not choose it:** Forcing a database dependency on local dev and CI runs introduces unnecessary friction for lightweight analysis and unit testing.

### Option B: Pure In-Memory NetworkX

This approach stores all graph nodes and edges in Python memory using NetworkX.

- **Pros:** Zero external dependencies, pure Python execution, fast in-memory operations, and access to NetworkX's extensive graph algorithm library.
- **Cons:** No native persistence across process restarts, memory footprint scales linearly with total document volume, and no support for standardized declarative query languages like Cypher.
- **Why we did not choose it:** Pure in-memory graphs cannot fulfill enterprise requirements for multi-company comparisons and cross-filing persistence.

### Option C (chosen): Dual Backend with Storage Abstraction Interface

This approach establishes a common contract for graph operations, implemented by both `NetworkXBackend` and `Neo4jBackend`.

- **Why this one:** It provides the best developer experience for local iteration and testing while maintaining an enterprise-grade path to scale out persistence and advanced querying with Neo4j.

## Consequences

### Positive

- Zero external infrastructure dependencies required for local development and unit tests.
- Pluggable architecture permits adding other backends (such as Memgraph or AWS Neptune) later with minimal effort.
- Separation of concerns between graph data modeling and physical persistence.
- High leverage for callers: `HybridRetriever` and `app.py` interact with a unified `GraphStore` interface.

### Negative

- Requires maintaining two storage adapters and ensuring behavioral parity between them.
- Graph queries must conform to the common abstraction layer, limiting the direct use of vendor-specific Cypher extensions in core business logic.

### Neutral

- Development requires maintaining dual adapter parity tests to verify that `NetworkXBackend` and `Neo4jBackend` produce identical traversal results.

## Follow-up Actions

- [x] Define the base storage contract in `src/db/graph/storage/base.py`.
- [x] Implement `NetworkXBackend` in `src/db/graph/storage/networkx_store.py`.
- [x] Implement `Neo4jBackend` with native Cypher in `src/db/graph/storage/neo4j_adapter.py`.
- [x] Implement deep `GraphStore` module in `src/db/graph/store.py`.
- [x] Write integration test suite to verify adapter parity in `tests/test_graph_backend_parity.py`.

## References

- [ARCHITECTURE.md](file:///E:/dev/auditit/ARCHITECTURE.md#L35-L55)
- [CONTEXT.md](file:///E:/dev/auditit/CONTEXT.md#L88-L92)
- [GLOSSARY.md](file:///E:/dev/auditit/GLOSSARY.md)
