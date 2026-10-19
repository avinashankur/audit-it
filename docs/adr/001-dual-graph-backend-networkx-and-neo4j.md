# 001-ADR: Adopt Dual Graph Backend Architecture with NetworkX and Neo4j

**Date:** 2026-10-19
**Status:** Proposed
**Deciders:** AuditIt Engineering Team
**Tags:** graph, storage, database, architecture

---

## Context

AuditIt models causal relationships among financial metrics, ratios, and report disclosures as a directed property graph. The system must support two distinct execution environments:

1. **Local development and automated testing:** Fast, zero-configuration execution where developers and CI pipelines run tests and analyze single reports without starting external database servers.
2. **Enterprise multi-report analysis:** Persistent, cross-document graph storage where teams query multi-quarter trends across multiple companies using standardized graph query languages like Cypher.

Coupling the application strictly to an external graph database increases onboarding overhead and complicates unit testing. Conversely, relying solely on an in-memory graph prevents long-term persistence and cross-report querying.

## Decision

We will implement a dual graph backend architecture centered on an abstract storage interface (`src/db/graph/storage/base.py`).

- **NetworkX** will serve as the default in-memory graph engine for local execution, unit tests, and single-document analysis.
- **Neo4j** will serve as an optional, pluggable adapter for persistent storage, multi-document graph aggregation, and Cypher querying.

All extraction and retrieval components will interact exclusively with the base storage interface, ensuring graph construction and traversal logic remain independent of the underlying storage backend.

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

This approach establishes a common contract for graph operations, implemented by both `NetworkXStore` and `Neo4jAdapter`.

- **Why this one:** It provides the best developer experience for local iteration and testing while maintaining an enterprise-grade path to scale out persistence and advanced querying with Neo4j.

## Consequences

### Positive

- Zero external infrastructure dependencies required for local development and unit tests.
- Pluggable architecture permits adding other backends (such as Memgraph or AWS Neptune) later with minimal effort.
- Separation of concerns between graph data modeling and physical persistence.

### Negative

- Requires maintaining two storage adapters and ensuring behavioral parity between them.
- Graph queries must conform to the common abstraction layer, limiting the direct use of vendor-specific Cypher extensions in core business logic.

### Neutral

- Development requires writing dual adapter tests to verify that `NetworkXStore` and `Neo4jAdapter` produce identical traversal results.

## Follow-up Actions

- [ ] Define the base storage contract in `src/db/graph/storage/base.py`.
- [ ] Implement `NetworkXStore` in `src/db/graph/storage/networkx_store.py`.
- [ ] Implement `Neo4jAdapter` in `src/db/graph/storage/neo4j_adapter.py`.
- [ ] Write integration test suite to verify adapter parity.

## References

- [ARCHITECTURE.md](file:///E:/dev/auditit/ARCHITECTURE.md#L35-L55)
- [CONTEXT.md](file:///E:/dev/auditit/CONTEXT.md#L88-L92)
