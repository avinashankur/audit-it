"""Deep GraphStore module managing domain entities, causal rules, and storage backends."""

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING, Any

from src.core.logging import get_logger, profile_stage
from src.db.graph.storage.base import GraphBackend
from src.db.graph.storage.neo4j_adapter import Neo4jBackend
from src.db.graph.storage.networkx_store import NetworkXBackend
from src.db.models.entities import (
    CausalDirection,
    CausalGraphPath,
    CausalRelationshipEdge,
    CausalRelationType,
    DisclosureNode,
    FinancialMetricNode,
    MetricUnit,
    StatementType,
)

if TYPE_CHECKING:
    from src.ingestion import IngestionResult

logger = get_logger(__name__)

CANONICAL_METRICS: dict[str, str] = {
    "total net sales": "Revenue",
    "net sales": "Revenue",
    "revenue": "Revenue",
    "total revenue": "Revenue",
    "cost of sales": "Cost of Sales",
    "cost of goods sold": "Cost of Sales",
    "cogs": "Cost of Sales",
    "gross margin": "Gross Margin",
    "gross profit": "Gross Margin",
    "research and development": "Research & Development",
    "r&d": "Research & Development",
    "selling, general and administrative": "SG&A",
    "selling, general and admin": "SG&A",
    "sg&a": "SG&A",
    "operating income": "Operating Income",
    "operating profit": "Operating Income",
    "total operating expenses": "Operating Expenses",
    "operating expenses": "Operating Expenses",
    "net income": "Net Income",
    "cash and cash equivalents": "Cash & Equivalents",
    "cash and equivalents": "Cash & Equivalents",
    "marketable securities": "Marketable Securities",
    "total assets": "Total Assets",
    "long-term debt": "Long-Term Debt",
    "term debt": "Long-Term Debt",
}

ACCOUNTING_CAUSAL_RULES: list[tuple[str, str, CausalRelationType, CausalDirection, str]] = [
    ("Revenue", "Gross Margin", CausalRelationType.DRIVES, CausalDirection.DIRECT, "Top-line revenue expansion directly drives gross margin"),
    ("Cost of Sales", "Gross Margin", CausalRelationType.OFFSETS, CausalDirection.INVERSE, "Cost of sales increases directly reduce gross margin"),
    ("Gross Margin", "Operating Income", CausalRelationType.DRIVES, CausalDirection.DIRECT, "Gross margin flows down to generate operating income"),
    ("Research & Development", "Operating Income", CausalRelationType.OFFSETS, CausalDirection.INVERSE, "R&D investments reduce operating income"),
    ("SG&A", "Operating Income", CausalRelationType.OFFSETS, CausalDirection.INVERSE, "Selling and administrative expenses reduce operating income"),
    ("Operating Expenses", "Operating Income", CausalRelationType.OFFSETS, CausalDirection.INVERSE, "Aggregate operating expenses reduce operating income"),
    ("Operating Income", "Net Income", CausalRelationType.DRIVES, CausalDirection.DIRECT, "Operating income is the primary driver of bottom-line net income"),
]

CAUSAL_PATTERNS = [
    re.compile(
        r"([A-Za-z\s]{3,35}?)\s+(?:was\s+)?driven\s+by\s+([A-Za-z\s]{3,45})",
        re.IGNORECASE,
    ),
    re.compile(
        r"([A-Za-z\s]{3,35}?)\s+(?:expanded|contracted|increased|decreased)\s+(?:by\s+[^\,\.]+\s+)?(?:due\s+to|driven\s+by)\s+([A-Za-z\s]{3,45})",
        re.IGNORECASE,
    ),
    re.compile(
        r"([A-Za-z\s]{3,35}?)\s+(?:was\s+)?offset\s+by\s+([A-Za-z\s]{3,45})",
        re.IGNORECASE,
    ),
]

MAGNITUDE_PATTERN = re.compile(
    r"\b(?:by\s+)?([+-]?\d+(?:\.\d+)?\s*(?:bps|basis\s+points|%|billion|million|B|M))\b",
    re.IGNORECASE,
)


def clean_number(value_str: str) -> float | None:
    if not value_str or value_str in ("-", "—", "–", "N/A", ""):
        return None
    raw = value_str.replace("$", "").replace("€", "").replace("£", "").replace(",", "").replace("%", "").strip()
    if raw.startswith("(") and raw.endswith(")"):
        raw = f"-{raw[1:-1].strip()}"
    try:
        return float(raw)
    except ValueError:
        return None


def clean_concept_phrase(phrase: str) -> str:
    cleaned = phrase.strip()
    cleaned = re.sub(r"^(?:the|a|an|primarily|favorable|unfavorable|higher|lower)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[\.,;:\n]+$", "", cleaned).strip()
    return cleaned.title() if len(cleaned) <= 30 else cleaned


def normalize_lookup_key(text: str) -> str:
    return text.strip().lower().replace(" ", "_").replace("-", "_").replace(".", "")


class GraphStore:
    """Deep module for causal financial property graphs, encapsulating domain rules and storage adapters."""

    def __init__(self, backend: GraphBackend | None = None) -> None:
        self.backend: GraphBackend = backend or NetworkXBackend()
        self._name_map: dict[str, str] = {}
        self._metrics_cache: dict[str, FinancialMetricNode] = {}

    @classmethod
    def create(
        cls,
        backend_type: str = "networkx",
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_user: str = "neo4j",
        neo4j_password: str | None = None,
        fallback_to_memory: bool = True,
    ) -> GraphStore:
        """Factory method to instantiate a GraphStore with the chosen storage backend."""
        b_type = (backend_type or "networkx").lower()
        if "neo4j" in b_type:
            backend = Neo4jBackend(
                uri=neo4j_uri,
                user=neo4j_user,
                password=neo4j_password,
                fallback_to_memory=fallback_to_memory,
            )
        else:
            backend = NetworkXBackend()

        return cls(backend=backend)

    def _resolve_id(self, key: str) -> str:
        """Resolve a metric name, alias, or UUID to a canonical node ID."""
        if not key:
            return key
        clean = normalize_lookup_key(key)
        return (
            self._name_map.get(key)
            or self._name_map.get(key.lower())
            or self._name_map.get(clean)
            or key
        )

    def _register_name_mapping(self, name: str, node_id: str) -> None:
        """Register aliases for deterministic query-time entity extraction."""
        self._name_map[name] = node_id
        self._name_map[name.lower()] = node_id
        self._name_map[normalize_lookup_key(name)] = node_id
        self._name_map[node_id] = node_id

    def add_metric_node(self, node: FinancialMetricNode) -> None:
        """Add a validated financial metric node to storage and index its name aliases."""
        props = node.model_dump()
        if "unit" in props and hasattr(props["unit"], "value"):
            props["unit"] = props["unit"].value
        if "statement_type" in props and hasattr(props["statement_type"], "value"):
            props["statement_type"] = props["statement_type"].value

        self.backend.upsert_node(node.node_id, "METRIC", props)
        self._register_name_mapping(node.name, node.node_id)
        for alias, target in CANONICAL_METRICS.items():
            if target.lower() == node.name.lower():
                self._register_name_mapping(alias, node.node_id)
        self._metrics_cache[node.node_id] = node
        self._metrics_cache[node.name] = node

    def add_disclosure_node(self, node: DisclosureNode) -> None:
        """Add a qualitative disclosure footnote node to storage."""
        props = node.model_dump()
        props["name"] = node.topic
        self.backend.upsert_node(node.node_id, "DISCLOSURE", props)
        self._register_name_mapping(node.topic, node.node_id)

    def add_causal_edge(self, edge: CausalRelationshipEdge) -> None:
        """Add a causal relationship edge between two nodes."""
        src_id = self._resolve_id(edge.source_node_id)
        tgt_id = self._resolve_id(edge.target_node_id)

        props = edge.model_dump()
        rel = edge.relation_type.value if hasattr(edge.relation_type, "value") else str(edge.relation_type)
        if "direction" in props and hasattr(props["direction"], "value"):
            props["direction"] = props["direction"].value

        self.backend.upsert_edge(src_id, tgt_id, rel, props)

    @profile_stage("graph_store_populate")
    def populate_from_ingestion(self, ingest_result: IngestionResult) -> dict[str, int]:
        """Construct the property graph directly from document tables, text chunks, and accounting rules."""
        doc_id = ingest_result.metadata.doc_id
        extracted_metric_names: set[str] = set()

        # 1. Parse tables for financial metrics
        for table in ingest_result.tables:
            period = table.headers[1] if len(table.headers) > 1 else "Current"
            title_lower = (table.title or "").lower()
            stmt_type = StatementType.INCOME_STATEMENT
            if "balance" in title_lower:
                stmt_type = StatementType.BALANCE_SHEET
            elif "cash" in title_lower:
                stmt_type = StatementType.CASH_FLOW

            for row in table.rows:
                if len(row) < 2:
                    continue
                raw_name = row[0].strip()
                if not raw_name or raw_name.endswith(":"):
                    continue

                canonical_name = CANONICAL_METRICS.get(raw_name.lower(), raw_name)
                val = clean_number(row[1])

                node = FinancialMetricNode(
                    node_id=str(uuid.uuid4()),
                    name=canonical_name,
                    normalized_key=normalize_lookup_key(canonical_name),
                    value=val,
                    unit=MetricUnit.USD,
                    period=period,
                    statement_type=stmt_type,
                    source_doc_id=doc_id,
                    source_page=table.page_number,
                    raw_text=f"{raw_name}: {row[1]}",
                )
                self.add_metric_node(node)
                self._register_name_mapping(raw_name, node.node_id)
                extracted_metric_names.add(canonical_name)

        primary_page = ingest_result.tables[0].page_number if ingest_result.tables else 1

        # 2. Apply accounting domain causal rules
        for src_name, tgt_name, rel_type, direction, evidence in ACCOUNTING_CAUSAL_RULES:
            if src_name in extracted_metric_names and tgt_name in extracted_metric_names:
                edge = CausalRelationshipEdge(
                    edge_id=str(uuid.uuid4()),
                    source_node_id=src_name,
                    target_node_id=tgt_name,
                    relation_type=rel_type,
                    direction=direction,
                    confidence=1.0,
                    evidence_text=evidence,
                    source_page=primary_page,
                )
                self.add_causal_edge(edge)

        # 3. Extract disclosures & regex causal patterns from text chunks
        for chunk in ingest_result.chunks:
            if chunk.section_header and "note" in chunk.section_header.lower():
                disc_node = DisclosureNode(
                    node_id=str(uuid.uuid4()),
                    topic=chunk.section_header,
                    summary=chunk.text[:120].strip() + "...",
                    snippet=chunk.text[:300].strip(),
                    source_doc_id=doc_id,
                    source_page=chunk.page_number,
                )
                self.add_disclosure_node(disc_node)

            for pattern in CAUSAL_PATTERNS:
                for match in pattern.finditer(chunk.text):
                    raw_target, raw_source = match.group(1).strip(), match.group(2).strip()
                    target_concept = clean_concept_phrase(raw_target)
                    source_concept = clean_concept_phrase(raw_source)

                    if 2 < len(source_concept) < 40 and 2 < len(target_concept) < 40:
                        mag_match = MAGNITUDE_PATTERN.search(match.group(0))
                        magnitude = mag_match.group(1).strip() if mag_match else None

                        rel_type = (
                            CausalRelationType.OFFSETS
                            if "offset" in match.group(0).lower()
                            else CausalRelationType.DRIVES
                        )

                        edge = CausalRelationshipEdge(
                            edge_id=str(uuid.uuid4()),
                            source_node_id=source_concept,
                            target_node_id=target_concept,
                            relation_type=rel_type,
                            direction=CausalDirection.DIRECT if rel_type == CausalRelationType.DRIVES else CausalDirection.INVERSE,
                            confidence=0.85,
                            evidence_text=match.group(0).strip(),
                            source_page=chunk.page_number,
                            impact_magnitude=magnitude,
                        )
                        self.add_causal_edge(edge)

        stats = self.get_stats()
        logger.info(
            f"Graph constructed for doc {doc_id}: {stats['total_nodes']} nodes, "
            f"{stats['causal_edges']} causal edges."
        )
        return stats

    def find_causal_neighborhood(
        self,
        query_text: str,
        max_hops: int = 2,
    ) -> tuple[list[FinancialMetricNode], list[CausalGraphPath]]:
        """Identify mentioned metrics, resolve aliases, and return verified causal paths in one call."""
        query_lower = query_text.lower()
        matched_metrics: list[str] = []
        matched_node_ids: list[str] = []

        # 1. Match entities from internal name index (encapsulated, no leak)
        for alias, nid in self._name_map.items():
            if len(alias) >= 3 and alias in query_lower:
                ndata = self.backend.get_node(nid)
                if ndata and ndata.get("name"):
                    name = ndata["name"]
                    if name not in matched_metrics:
                        matched_metrics.append(name)
                        matched_node_ids.append(nid)

        # 2. Collect matched metric models
        metric_nodes: list[FinancialMetricNode] = []
        seen_ids: set[str] = set()

        for nid in matched_node_ids:
            if nid in seen_ids:
                continue
            seen_ids.add(nid)
            cached = self._metrics_cache.get(nid)
            if cached:
                metric_nodes.append(cached)
            else:
                ndata = self.backend.get_node(nid)
                if ndata:
                    try:
                        metric_nodes.append(
                            FinancialMetricNode(
                                node_id=ndata.get("node_id", nid),
                                name=ndata.get("name", "Metric"),
                                normalized_key=ndata.get("normalized_key", normalize_lookup_key(ndata.get("name", ""))),
                                value=ndata.get("value"),
                                unit=MetricUnit.USD,
                                period=str(ndata.get("period", "Current")),
                                statement_type=StatementType.GENERAL,
                                source_doc_id=str(ndata.get("source_doc_id", "")),
                                source_page=int(ndata.get("source_page", 1)),
                            )
                        )
                    except Exception:
                        pass

        # 3. Find causal paths between matched metric pairs
        causal_paths: list[CausalGraphPath] = []
        seen_path_keys: set[str] = set()

        if len(matched_node_ids) >= 2:
            for i in range(len(matched_node_ids)):
                for j in range(len(matched_node_ids)):
                    if i == j:
                        continue
                    src_id = matched_node_ids[i]
                    tgt_id = matched_node_ids[j]
                    paths = self.backend.find_paths(src_id, tgt_id, max_depth=max_hops)

                    for p in paths:
                        path_nodes = p["nodes"]
                        path_key = "->".join(path_nodes)
                        if path_key in seen_path_keys:
                            continue
                        seen_path_keys.add(path_key)

                        # Build narrative string
                        narrative_parts: list[str] = []
                        for step_nid in path_nodes:
                            step_data = self.backend.get_node(step_nid)
                            step_name = (step_data.get("name") if step_data else None) or step_nid
                            narrative_parts.append(step_name)

                        narrative = " -> ".join(narrative_parts)
                        src_name = narrative_parts[0]
                        tgt_name = narrative_parts[-1]

                        rel_sequence = [e.get("relation_type", "DRIVES") for e in p.get("edges", [])]
                        causal_paths.append(
                            CausalGraphPath(
                                path_id=str(uuid.uuid4()),
                                source_node_name=src_name,
                                target_node_name=tgt_name,
                                node_sequence=narrative_parts,
                                relationship_sequence=rel_sequence,
                                narrative_explanation=f"{src_name} impacts {tgt_name} through causal chain: {narrative}",
                            )
                        )

        # 4. If no pairs, search neighbors of individual metrics
        elif len(matched_node_ids) == 1:
            nid = matched_node_ids[0]
            neighbors = self.backend.get_neighbors(nid, direction="downstream")
            src_data = self.backend.get_node(nid)
            src_name = (src_data.get("name") if src_data else None) or nid

            for item in neighbors[:3]:
                tgt_node = item["node"]
                tgt_name = tgt_node.get("name", "Driver")
                edge_data = item["edge"]
                rel = edge_data.get("relation_type", "drives").lower()
                evidence = edge_data.get("evidence_text", f"{src_name} {rel} {tgt_name}")

                causal_paths.append(
                    CausalGraphPath(
                        path_id=str(uuid.uuid4()),
                        source_node_name=src_name,
                        target_node_name=tgt_name,
                        node_sequence=[src_name, tgt_name],
                        relationship_sequence=[rel.upper()],
                        narrative_explanation=f"{src_name} {rel} {tgt_name}: {evidence}",
                    )
                )

        return metric_nodes, causal_paths

    def get_node(self, node_id_or_name: str) -> dict[str, Any] | None:
        """Retrieve node attributes by ID or canonical name."""
        nid = self._resolve_id(node_id_or_name)
        return self.backend.get_node(nid)

    def get_neighbors(
        self,
        node_id_or_name: str,
        direction: str = "downstream",
    ) -> list[dict[str, Any]]:
        """Retrieve immediate neighbor nodes and connecting relationships."""
        nid = self._resolve_id(node_id_or_name)
        return self.backend.get_neighbors(nid, direction=direction)

    def get_subgraph(self, metric_or_root: str | None = None, hops: int = 2) -> dict[str, Any]:
        """Return visual subgraph data around an optional root node."""
        root_id = self._resolve_id(metric_or_root) if metric_or_root else None
        return self.backend.get_subgraph(root_id=root_id, hops=hops)

    def get_subgraph_data(self, root_node: str | None = None, hops: int = 2) -> dict[str, Any]:
        """Convenience method returning subgraph data with label and node_type populated for UI."""
        data = self.get_subgraph(metric_or_root=root_node, hops=hops)
        for n in data.get("nodes", []):
            if "label" not in n:
                n["label"] = n.get("name") or n.get("node_id")
            if "node_type" not in n:
                n["node_type"] = n.get("label") or "METRIC"
        return data

    def to_mermaid(self, root_node: str | None = None, hops: int = 2) -> str:
        """Render a Mermaid flowchart string for the subgraph around root_node."""
        subgraph = self.get_subgraph(metric_or_root=root_node, hops=hops)
        nodes = subgraph.get("nodes", [])
        edges = subgraph.get("edges", [])

        if not nodes and not edges:
            return "graph TD\n    empty[Empty Graph]"

        lines: list[str] = ["graph TD"]
        id_map: dict[str, str] = {}
        for idx, n in enumerate(nodes):
            nid = str(n.get("node_id") or n.get("id") or f"node_{idx}")
            clean_id = f"N{idx}"
            id_map[nid] = clean_id
            name = n.get("name") or n.get("label") or nid
            val = n.get("value")
            val_str = f" (${val:,.0f}M)" if isinstance(val, (int, float)) else ""
            label_text = f"{name}{val_str}".replace('"', "'")
            lines.append(f'    {clean_id}["{label_text}"]')

        for e in edges:
            src = str(e.get("source"))
            tgt = str(e.get("target"))
            rel = str(e.get("relation_type", "INFLUENCES"))
            src_alias = id_map.get(src) or id_map.get(self._resolve_id(src))
            tgt_alias = id_map.get(tgt) or id_map.get(self._resolve_id(tgt))
            if src_alias and tgt_alias:
                lines.append(f'    {src_alias} -->|"{rel}"| {tgt_alias}')

        return "\n".join(lines)

    def get_stats(self) -> dict[str, int]:
        """Return counts of total nodes, metrics, disclosures, and causal edges."""
        return self.backend.get_stats()

    def clear(self) -> None:
        """Clear graph storage and in-memory caches."""
        self.backend.clear()
        self._name_map.clear()
        self._metrics_cache.clear()
