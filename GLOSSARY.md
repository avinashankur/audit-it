# AuditIt Domain Glossary

This glossary defines the shared domain vocabulary for the AuditIt financial audit intelligence platform. Use these exact terms across architecture designs, modules, and documentation.

---

### Core Domain Concepts

#### Financial Metric
A quantitative numerical item extracted from primary financial statements (Income Statement, Balance Sheet, Cash Flows). Examples include *Revenue*, *Cost of Sales*, *Gross Margin*, *Operating Income*, and *Net Income*. Each metric has a normalized canonical key, a reported currency unit, and an associated reporting period.

#### Causal Relationship
A verified, directed relationship between two financial metrics or disclosure concepts indicating impact direction:
- **Drives (Direct)**: Positive change in source increases target (e.g., *Revenue* directly drives *Gross Margin*).
- **Offsets (Inverse)**: Positive change in source decreases target (e.g., *Cost of Sales* offsets *Gross Margin*).

#### Disclosure
A qualitative explanatory note, accounting policy explanation, or MD&A excerpt cited from the annual report that provides narrative context for metric movements.

#### Graph Store
The deep module responsible for constructing, maintaining, and querying the causal financial knowledge graph. Encapsulates entity matching, canonical aliases, accounting rules, and graph neighborhood traversals.

#### Graph Backend
The internal storage port at the graph seam. Satisfied by two concrete adapters:
- **NetworkX Backend**: In-memory, zero-dependency graph engine optimized for fast local analysis and automated tests.
- **Neo4j Backend**: Persistent property graph engine executing Cypher statements for cross-report aggregation and enterprise scale.

#### Hybrid Retrieval
The unified query process that executes vector similarity search across narrative chunks and graph traversal across causal paths in tandem, producing grounded audit context.
