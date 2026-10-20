"""Deep GraphStore module managing domain entities, causal rules, and storage backends."""

from __future__ import annotations

import re
import uuid
from collections import defaultdict
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

DRIVER_KEYWORDS: set[str] = {
    "drive", "drives", "driver", "drivers", "driven", "drove",
    "cause", "causes", "caused", "causing",
    "why", "reason", "reasons",
    "contribute", "contributes", "contributed", "contributing", "contributor", "contributors",
    "source", "sources", "origin", "upstream",
    "input", "inputs", "factor", "factors",
}

IMPACT_KEYWORDS: set[str] = {
    "impact", "impacts", "impacted", "impacting",
    "affect", "affects", "affected", "affecting",
    "effect", "effects",
    "influence", "influences", "influenced", "influencing",
    "flow", "flows", "downstream",
    "lead", "leads", "outcome", "outcomes",
}

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


def parse_financial_cell(
    cell_str: str,
    table_title: str = "",
    table_header: str = "",
) -> tuple[float | None, MetricUnit, str | None, str | None]:
    """Parse raw financial cell string into numeric value, MetricUnit, scale, and currency symbol."""
    if not cell_str or cell_str.strip() in ("-", "—", "–", "N/A", "", "None"):
        return None, MetricUnit.USD, None, None

    raw = cell_str.strip()
    unit = MetricUnit.USD
    scale = None
    symbol = "$" if "$" in raw else None

    # Detect currency symbols
    if "€" in raw:
        unit = MetricUnit.CURRENCY
        symbol = "€"
    elif "£" in raw:
        unit = MetricUnit.CURRENCY
        symbol = "£"
    elif "$" in raw or "usd" in raw.lower():
        unit = MetricUnit.USD
        symbol = "$"

    # Detect percentage
    if "%" in raw:
        unit = MetricUnit.PERCENTAGE
        symbol = None

    # Detect basis points
    if "bps" in raw.lower() or "basis point" in raw.lower():
        unit = MetricUnit.BASIS_POINTS
        symbol = None

    # Detect shares / count
    if "shares" in raw.lower():
        unit = MetricUnit.SHARES
        symbol = None

    # Detect scale in cell text
    lower_cell = raw.lower()
    if re.search(r"\b(?:billion|b)\b", lower_cell):
        scale = "B"
    elif re.search(r"\b(?:million|m)\b", lower_cell):
        scale = "M"
    elif re.search(r"\b(?:thousand|k)\b", lower_cell):
        scale = "K"

    # If cell has no explicit scale, check table context (title / headers)
    if scale is None and unit not in (MetricUnit.PERCENTAGE, MetricUnit.BASIS_POINTS):
        context = f"{table_title} {table_header}".lower()
        if "in billion" in context or "($ in billion" in context or "($ billions)" in context:
            scale = "B"
        elif "in million" in context or "($ in million" in context or "($ millions)" in context:
            scale = "M"
        elif "in thousand" in context or "($ in thousand" in context or "($ thousands)" in context:
            scale = "K"

    # Clean numeric characters
    cleaned = raw.replace("$", "").replace("€", "").replace("£", "").replace(",", "").replace("%", "")
    cleaned = re.sub(r"(?i)\b(?:bps|basis points|billion|million|thousand|shares|[bmk])\b", "", cleaned).strip()
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = f"-{cleaned[1:-1].strip()}"
    try:
        num_val = float(cleaned)
    except ValueError:
        num_val = None

    return num_val, unit, scale, symbol


def clean_number(value_str: str) -> float | None:
    val, _, _, _ = parse_financial_cell(value_str)
    return val


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
        self._metric_nodes_by_name: dict[str, list[str]] = defaultdict(list)
        self._node_scopes: dict[str, dict[str, Any]] = {}
        self._metrics_cache: dict[str, FinancialMetricNode] = {}
        self._doc_filenames: dict[str, str] = {}
        self.rebuild_index()

    def rebuild_index(self) -> None:
        """Rebuild in-memory name mappings, node scopes, and metric caches from the backend."""
        try:
            subgraph = self.backend.get_subgraph(root_id=None)
        except Exception as e:
            logger.warning(f"Failed to query backend for existing graph elements: {e}")
            return

        nodes = subgraph.get("nodes", [])
        edges = subgraph.get("edges", [])
        if not nodes and not edges:
            return

        for edge_data in edges:
            if isinstance(edge_data, dict):
                props = edge_data.get("properties") if isinstance(edge_data.get("properties"), dict) else edge_data
                d_id = props.get("source_doc_id")
                f_name = props.get("source_filename")
                if d_id and f_name:
                    self._doc_filenames[str(d_id)] = str(f_name)

        for node_data in nodes:
            if not isinstance(node_data, dict):
                continue
            nid = node_data.get("node_id") or node_data.get("id")
            if not nid:
                continue

            name = node_data.get("name") or node_data.get("topic")
            period = node_data.get("period")
            table_id = node_data.get("table_id")
            table_title = node_data.get("table_title")
            doc_id = node_data.get("source_doc_id")
            source_filename = node_data.get("source_filename")
            if doc_id and source_filename:
                self._doc_filenames[str(doc_id)] = str(source_filename)

            if name:
                self._register_name_mapping(
                    name=name,
                    node_id=nid,
                    period=str(period) if period is not None else None,
                    table_id=table_id,
                    table_title=table_title,
                    doc_id=doc_id,
                )
                for alias, target in CANONICAL_METRICS.items():
                    if target.lower() == name.lower():
                        self._register_name_mapping(
                            name=alias,
                            node_id=nid,
                            period=str(period) if period is not None else None,
                            table_id=table_id,
                            table_title=table_title,
                            doc_id=doc_id,
                        )

            # Check if this node represents a financial metric
            is_metric = (
                node_data.get("label") == "METRIC"
                or node_data.get("node_type") == "METRIC"
                or "value" in node_data
                or "statement_type" in node_data
                or (name and name.lower() in [m.lower() for m in CANONICAL_METRICS.values()])
            )
            if is_metric and name:
                unit_val = node_data.get("unit", MetricUnit.USD)
                if isinstance(unit_val, str):
                    try:
                        unit_val = MetricUnit(unit_val)
                    except ValueError:
                        unit_val = MetricUnit.USD

                stmt_val = node_data.get("statement_type", StatementType.GENERAL)
                if isinstance(stmt_val, str):
                    try:
                        stmt_val = StatementType(stmt_val)
                    except ValueError:
                        stmt_val = StatementType.GENERAL

                try:
                    f_node = FinancialMetricNode(
                        node_id=nid,
                        name=name,
                        normalized_key=node_data.get("normalized_key", normalize_lookup_key(name)),
                        value=node_data.get("value"),
                        unit=unit_val,
                        scale=node_data.get("scale"),
                        currency_symbol=node_data.get("currency_symbol"),
                        period=str(period or "Current"),
                        statement_type=stmt_val,
                        source_doc_id=str(doc_id or ""),
                        source_page=int(node_data.get("source_page", 1)),
                        table_id=table_id,
                        table_title=table_title,
                        raw_text=node_data.get("raw_text"),
                        source_filename=node_data.get("source_filename") or self._doc_filenames.get(str(doc_id or "")),
                    )
                    self._metrics_cache[nid] = f_node
                    is_consolidated = bool(table_title and "consolidated" in table_title.lower())
                    current_primary = self._metrics_cache.get(name)
                    curr_is_consolidated = bool(
                        current_primary
                        and getattr(current_primary, "table_title", None)
                        and "consolidated" in current_primary.table_title.lower()
                    )
                    if name not in self._metrics_cache or (is_consolidated and not curr_is_consolidated):
                        self._metrics_cache[name] = f_node
                except Exception:
                    pass

    @classmethod
    def create(
        cls,
        backend_type: str = "networkx",
        neo4j_uri: str | None = None,
        neo4j_user: str | None = None,
        neo4j_password: str | None = None,
        fallback_to_memory: bool = True,
    ) -> GraphStore:
        """Factory method to instantiate a GraphStore with the chosen storage backend."""
        b_type = (backend_type or "networkx").lower()
        if "neo4j" in b_type:
            from src.core.env import get_settings

            settings = get_settings()
            uri = neo4j_uri or settings.NEO4J_URI
            user = neo4j_user or settings.NEO4J_USER
            pwd = (
                neo4j_password
                if neo4j_password is not None
                else (settings.NEO4J_PASSWORD.get_secret_value() if settings.NEO4J_PASSWORD else None)
            )
            backend = Neo4jBackend(
                uri=uri,
                user=user,
                password=pwd,
                fallback_to_memory=fallback_to_memory,
            )
        else:
            backend = NetworkXBackend()

        return cls(backend=backend)

    def _resolve_id(
        self,
        key: str,
        doc_id: str | None = None,
        period: str | None = None,
        table_id: str | None = None,
        table_title: str | None = None,
    ) -> str:
        """Resolve a metric name, alias, or UUID to a canonical node ID with optional scoping."""
        if not key:
            return key

        if not self._name_map and self.backend.get_stats().get("total_nodes", 0) > 0:
            self.rebuild_index()

        if key in self._node_scopes or self.backend.get_node(key) is not None:
            return key

        if doc_id or period or table_id or table_title:
            matched = self.get_metric_nodes(
                name=key,
                doc_id=doc_id,
                period=period,
                table_id=table_id,
                table_title=table_title,
            )
            if matched:
                return matched[0].node_id

        clean = normalize_lookup_key(key)
        resolved = (
            self._name_map.get(key)
            or self._name_map.get(key.lower())
            or self._name_map.get(clean)
        )
        if resolved:
            return resolved

        # Fallback to direct backend inspection
        try:
            subgraph = self.backend.get_subgraph(root_id=None)
            for n in subgraph.get("nodes", []):
                n_name = n.get("name") or n.get("topic")
                nid = n.get("node_id") or n.get("id")
                if nid and (nid == key or (n_name and (n_name.lower() == key.lower() or normalize_lookup_key(n_name) == clean))):
                    return nid
        except Exception:
            pass

        return key

    def _register_name_mapping(
        self,
        name: str,
        node_id: str,
        period: str | None = None,
        table_id: str | None = None,
        table_title: str | None = None,
        doc_id: str | None = None,
    ) -> None:
        """Register aliases preserving all matching IDs across report, period, and table scope."""
        if not name:
            return
        clean = normalize_lookup_key(name)
        name_lower = name.lower()

        # Track scope metadata for multi-dimensional filtering
        self._node_scopes[node_id] = {
            "name": name,
            "doc_id": doc_id,
            "period": period,
            "table_id": table_id,
            "table_title": table_title,
        }

        # Multi-node list index preserving all node IDs across tables, periods, and reports
        if node_id not in self._metric_nodes_by_name[name_lower]:
            self._metric_nodes_by_name[name_lower].append(node_id)
        if node_id not in self._metric_nodes_by_name[clean]:
            self._metric_nodes_by_name[clean].append(node_id)

        # Primary mapping: consolidated statements take priority over segment/footnote tables
        is_consolidated = bool(table_title and "consolidated" in table_title.lower())
        current_primary = self._name_map.get(name_lower)
        current_is_consolidated = False
        if current_primary and current_primary in self._node_scopes:
            curr_title = self._node_scopes[current_primary].get("table_title")
            current_is_consolidated = bool(curr_title and "consolidated" in curr_title.lower())

        if name not in self._name_map or (is_consolidated and not current_is_consolidated):
            self._name_map[name] = node_id
        if name_lower not in self._name_map or (is_consolidated and not current_is_consolidated):
            self._name_map[name_lower] = node_id
        if clean not in self._name_map or (is_consolidated and not current_is_consolidated):
            self._name_map[clean] = node_id
        self._name_map[node_id] = node_id

        # Period-specific scoped aliases
        if period and period.lower() != "current":
            p_clean = period.lower().strip()
            for p_alias in (f"{name_lower}@{p_clean}", f"{name_lower} {p_clean}", f"{p_clean} {name_lower}"):
                self._name_map[p_alias] = node_id
                if node_id not in self._metric_nodes_by_name[p_alias]:
                    self._metric_nodes_by_name[p_alias].append(node_id)

        # Table-specific scoped aliases
        if table_title:
            t_clean = normalize_lookup_key(table_title)
            self._name_map[f"{name_lower}@{t_clean}"] = node_id
            self._name_map[f"{t_clean}:{name_lower}"] = node_id
            if node_id not in self._metric_nodes_by_name[f"{name_lower}@{t_clean}"]:
                self._metric_nodes_by_name[f"{name_lower}@{t_clean}"].append(node_id)
            if node_id not in self._metric_nodes_by_name[f"{t_clean}:{name_lower}"]:
                self._metric_nodes_by_name[f"{t_clean}:{name_lower}"].append(node_id)

        if table_id:
            self._name_map[f"{table_id}:{name_lower}"] = node_id
            if node_id not in self._metric_nodes_by_name[f"{table_id}:{name_lower}"]:
                self._metric_nodes_by_name[f"{table_id}:{name_lower}"].append(node_id)

        # Report-specific scoped aliases
        if doc_id:
            self._name_map[f"{doc_id}:{name_lower}"] = node_id
            if node_id not in self._metric_nodes_by_name[f"{doc_id}:{name_lower}"]:
                self._metric_nodes_by_name[f"{doc_id}:{name_lower}"].append(node_id)

        # Combined table + period aliases
        if table_title and period and period.lower() != "current":
            t_clean = normalize_lookup_key(table_title)
            p_clean = period.lower().strip()
            comb_key = f"{t_clean}@{p_clean}:{name_lower}"
            self._name_map[comb_key] = node_id
            if node_id not in self._metric_nodes_by_name[comb_key]:
                self._metric_nodes_by_name[comb_key].append(node_id)

        # Combined report + table + period aliases
        if doc_id and table_id and period and period.lower() != "current":
            p_clean = period.lower().strip()
            full_key = f"{doc_id}:{table_id}@{p_clean}:{name_lower}"
            self._name_map[full_key] = node_id
            if node_id not in self._metric_nodes_by_name[full_key]:
                self._metric_nodes_by_name[full_key].append(node_id)

    def add_metric_node(self, node: FinancialMetricNode) -> None:
        """Add a validated financial metric node to storage and index its name aliases."""
        props = node.model_dump()
        if "unit" in props and hasattr(props["unit"], "value"):
            props["unit"] = props["unit"].value
        if "statement_type" in props and hasattr(props["statement_type"], "value"):
            props["statement_type"] = props["statement_type"].value

        self.backend.upsert_node(node.node_id, "METRIC", props)
        self._register_name_mapping(
            node.name,
            node.node_id,
            period=node.period,
            table_id=node.table_id,
            table_title=node.table_title,
            doc_id=node.source_doc_id,
        )
        for alias, target in CANONICAL_METRICS.items():
            if target.lower() == node.name.lower():
                self._register_name_mapping(
                    alias,
                    node.node_id,
                    period=node.period,
                    table_id=node.table_id,
                    table_title=node.table_title,
                    doc_id=node.source_doc_id,
                )
        self._metrics_cache[node.node_id] = node
        is_consolidated = bool(node.table_title and "consolidated" in node.table_title.lower())
        current_primary = self._metrics_cache.get(node.name)
        curr_is_consolidated = bool(
            current_primary
            and getattr(current_primary, "table_title", None)
            and "consolidated" in current_primary.table_title.lower()
        )
        if node.name not in self._metrics_cache or (is_consolidated and not curr_is_consolidated):
            self._metrics_cache[node.name] = node

    def add_disclosure_node(self, node: DisclosureNode) -> None:
        """Add a qualitative disclosure footnote node to storage."""
        props = node.model_dump()
        props["name"] = node.topic
        self.backend.upsert_node(node.node_id, "DISCLOSURE", props)
        self._register_name_mapping(node.topic, node.node_id, doc_id=node.source_doc_id)

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
        filename = ingest_result.metadata.filename
        self._doc_filenames[doc_id] = filename
        extracted_metric_names: set[str] = set()

        # Track metrics by (table_id, period) scope so accounting rules strictly link within table scope
        table_period_metrics: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
        table_info_map: dict[str, tuple[str, int]] = {}

        # 1. Parse tables for financial metrics across all reported period columns
        for table in ingest_result.tables:
            title_lower = (table.title or "").lower()
            stmt_type = StatementType.INCOME_STATEMENT
            if "balance" in title_lower:
                stmt_type = StatementType.BALANCE_SHEET
            elif "cash" in title_lower:
                stmt_type = StatementType.CASH_FLOW

            table_info_map[table.table_id] = (table.title or "Table", table.page_number)
            total_cols = len(table.headers)
            for row in table.rows:
                if len(row) < 2:
                    continue
                raw_name = row[0].strip()
                if not raw_name or raw_name.endswith(":"):
                    continue

                canonical_name = CANONICAL_METRICS.get(raw_name.lower(), raw_name)

                # Iterate through all reported period columns (columns 1 .. N)
                num_cols = min(total_cols, len(row)) if total_cols > 1 else len(row)
                for col_idx in range(1, num_cols):
                    if col_idx < len(table.headers) and table.headers[col_idx].strip():
                        period = table.headers[col_idx].strip()
                    else:
                        period = f"Col {col_idx}" if num_cols > 2 else "Current"

                    cell_str = row[col_idx]
                    if not cell_str or not cell_str.strip():
                        continue

                    val, unit, scale, symbol = parse_financial_cell(
                        cell_str,
                        table_title=table.title or "",
                        table_header=period,
                    )

                    node = FinancialMetricNode(
                        node_id=str(uuid.uuid4()),
                        name=canonical_name,
                        normalized_key=normalize_lookup_key(canonical_name),
                        value=val,
                        unit=unit,
                        scale=scale,
                        currency_symbol=symbol,
                        period=period,
                        statement_type=stmt_type,
                        source_doc_id=doc_id,
                        source_page=table.page_number,
                        table_id=table.table_id,
                        table_title=table.title,
                        raw_text=f"{raw_name}: {cell_str.strip()}",
                        source_filename=filename,
                    )
                    self.add_metric_node(node)
                    self._register_name_mapping(
                        raw_name,
                        node.node_id,
                        period=period,
                        table_id=table.table_id,
                        table_title=table.title,
                        doc_id=doc_id,
                    )
                    extracted_metric_names.add(canonical_name)
                    table_period_metrics[(table.table_id, period)][canonical_name] = node.node_id

        # 2. Apply accounting domain causal rules strictly within the scope of each table and period
        # This prevents causal rules from erroneously joining values across different tables (e.g. segment vs consolidated)
        for (tbl_id, period), metric_dict in table_period_metrics.items():
            tbl_title, tbl_page = table_info_map.get(tbl_id, ("Table", 1))
            for src_name, tgt_name, rel_type, direction, evidence in ACCOUNTING_CAUSAL_RULES:
                if src_name in metric_dict and tgt_name in metric_dict:
                    src_nid = metric_dict[src_name]
                    tgt_nid = metric_dict[tgt_name]
                    edge = CausalRelationshipEdge(
                        edge_id=str(uuid.uuid4()),
                        source_node_id=src_nid,
                        target_node_id=tgt_nid,
                        relation_type=rel_type,
                        direction=direction,
                        confidence=1.0,
                        evidence_text=f"{evidence} ({tbl_title}, {period})",
                        source_page=tbl_page,
                        source_doc_id=doc_id,
                        source_filename=filename,
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
                            source_doc_id=doc_id,
                            source_filename=filename,
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
        if not self._metric_nodes_by_name and self.backend.get_stats().get("total_nodes", 0) > 0:
            self.rebuild_index()

        query_lower = query_text.lower()
        matched_metrics: list[str] = []
        matched_node_ids: list[str] = []

        query_years = set(re.findall(r"\b(19\d\d|20\d\d)\b", query_lower))
        query_periods = set(re.findall(r"\b(q[1-4]|fy\d{2,4}|h[1-2])\b", query_lower))

        # 1. Match entities from internal multi-node and name index
        candidate_nodes_by_metric: dict[str, list[str]] = defaultdict(list)

        for alias, nids in self._metric_nodes_by_name.items():
            if len(alias) >= 3 and alias in query_lower:
                for nid in nids:
                    ndata = self._metrics_cache.get(nid) or self.backend.get_node(nid)
                    if not ndata:
                        continue
                    m_name = ndata.name if isinstance(ndata, FinancialMetricNode) else ndata.get("name")
                    if m_name and nid not in candidate_nodes_by_metric[m_name]:
                        candidate_nodes_by_metric[m_name].append(nid)

        # Fallback to _name_map if needed
        if not candidate_nodes_by_metric:
            for alias, nid in self._name_map.items():
                if len(alias) >= 3 and alias in query_lower:
                    ndata = self._metrics_cache.get(nid) or self.backend.get_node(nid)
                    if not ndata:
                        continue
                    m_name = ndata.name if isinstance(ndata, FinancialMetricNode) else ndata.get("name")
                    if m_name and nid not in candidate_nodes_by_metric[m_name]:
                        candidate_nodes_by_metric[m_name].append(nid)

        # Fallback to backend nodes if candidates still empty
        if not candidate_nodes_by_metric:
            try:
                subgraph = self.backend.get_subgraph(root_id=None)
                for node_data in subgraph.get("nodes", []):
                    n_name = node_data.get("name") or node_data.get("topic")
                    nid = node_data.get("node_id") or node_data.get("id")
                    if n_name and nid and len(n_name) >= 3 and n_name.lower() in query_lower:
                        if nid not in candidate_nodes_by_metric[n_name]:
                            candidate_nodes_by_metric[n_name].append(nid)
            except Exception:
                pass

        # 2. Select appropriate nodes per matched metric (filtering/prioritizing by period if requested)
        for m_name, nids in candidate_nodes_by_metric.items():
            if m_name not in matched_metrics:
                matched_metrics.append(m_name)

            matching_period_nids: list[str] = []
            for nid in nids:
                ndata = self._metrics_cache.get(nid) or self.backend.get_node(nid)
                if not ndata:
                    continue
                node_period = str(ndata.period if isinstance(ndata, FinancialMetricNode) else ndata.get("period", "")).lower()

                period_in_query = node_period in query_lower and len(node_period) >= 3
                node_years = set(re.findall(r"\b(19\d\d|20\d\d)\b", node_period))
                node_q = set(re.findall(r"\b(q[1-4]|fy\d{2,4}|h[1-2])\b", node_period))

                year_match = bool(query_years and (query_years & node_years))
                q_match = bool(query_periods and (query_periods & node_q))

                if period_in_query or year_match or q_match:
                    matching_period_nids.append(nid)

            # If period was explicitly queried and matched, return only those period nodes;
            # otherwise return all periods for the metric
            selected_nids = matching_period_nids if matching_period_nids else nids
            for nid in selected_nids:
                if nid not in matched_node_ids:
                    matched_node_ids.append(nid)

        # 3. Collect matched metric models
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
                                unit=ndata.get("unit", MetricUnit.USD),
                                scale=ndata.get("scale"),
                                currency_symbol=ndata.get("currency_symbol"),
                                period=str(ndata.get("period", "Current")),
                                statement_type=StatementType.GENERAL,
                                source_doc_id=str(ndata.get("source_doc_id", "")),
                                source_page=int(ndata.get("source_page", 1)),
                                table_id=ndata.get("table_id"),
                                table_title=ndata.get("table_title"),
                                raw_text=ndata.get("raw_text"),
                                source_filename=ndata.get("source_filename") or self._doc_filenames.get(str(ndata.get("source_doc_id", ""))),
                            )
                        )
                    except Exception:
                        pass

        # 4. Find causal paths between matched metric pairs
        causal_paths: list[CausalGraphPath] = []
        seen_path_keys: set[str] = set()
        seen_narratives: set[str] = set()

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
                        if narrative in seen_narratives:
                            continue
                        seen_narratives.add(narrative)

                        src_name = narrative_parts[0]
                        tgt_name = narrative_parts[-1]

                        rel_sequence = [e.get("relation_type", "DRIVES") for e in p.get("edges", [])]

                        path_pages: list[int] = []
                        path_evidences: list[str] = []
                        page_ev_map: dict[int, str] = {}
                        path_doc_id: str | None = None
                        path_filename: str | None = None

                        for e in p.get("edges", []):
                            e_props = e.get("properties") if isinstance(e.get("properties"), dict) else e
                            pg = e.get("source_page") or e_props.get("source_page")
                            ev = e.get("evidence_text") or e_props.get("evidence_text")
                            d_id = e.get("source_doc_id") or e_props.get("source_doc_id")
                            f_name = e.get("source_filename") or e_props.get("source_filename")

                            if pg is not None:
                                try:
                                    pg_int = int(pg)
                                    if pg_int not in path_pages:
                                        path_pages.append(pg_int)
                                    if ev and pg_int not in page_ev_map:
                                        page_ev_map[pg_int] = str(ev)
                                except (ValueError, TypeError):
                                    pass
                            if ev and str(ev) not in path_evidences:
                                path_evidences.append(str(ev))
                            if not path_doc_id and d_id:
                                path_doc_id = str(d_id)
                            if not path_filename and f_name:
                                path_filename = str(f_name)

                        for nid in path_nodes:
                            nd = self.backend.get_node(nid)
                            if isinstance(nd, dict):
                                if not path_pages and nd.get("source_page") is not None:
                                    try:
                                        pg_int = int(nd.get("source_page"))
                                        if pg_int not in path_pages:
                                            path_pages.append(pg_int)
                                    except (ValueError, TypeError):
                                        pass
                                if not path_doc_id and nd.get("source_doc_id"):
                                    path_doc_id = str(nd.get("source_doc_id"))
                                if not path_filename and nd.get("source_filename"):
                                    path_filename = str(nd.get("source_filename"))

                        if not path_filename and path_doc_id and path_doc_id in self._doc_filenames:
                            path_filename = self._doc_filenames[path_doc_id]

                        primary_page = path_pages[0] if path_pages else None
                        primary_ev = "; ".join(path_evidences) if path_evidences else None

                        causal_paths.append(
                            CausalGraphPath(
                                path_id=str(uuid.uuid4()),
                                source_node_name=src_name,
                                target_node_name=tgt_name,
                                node_sequence=narrative_parts,
                                relationship_sequence=rel_sequence,
                                narrative_explanation=f"{src_name} impacts {tgt_name} through causal chain: {narrative}",
                                source_page=primary_page,
                                source_pages=path_pages,
                                evidence_text=primary_ev,
                                evidence_texts=path_evidences,
                                page_evidence_map=page_ev_map,
                                source_doc_id=path_doc_id,
                                source_filename=path_filename,
                            )
                        )

        # 5. If no multi-metric paths found, explore causal paths for matched metric(s) honoring direction and max_hops
        if not causal_paths and matched_node_ids:
            query_tokens = set(re.findall(r"\b[a-z]+\b", query_lower))
            is_driver_query = bool(query_tokens & DRIVER_KEYWORDS) or any(
                phrase in query_lower for phrase in ("due to", "result of", "led to")
            )
            is_impact_query = bool(query_tokens & IMPACT_KEYWORDS) or any(
                phrase in query_lower for phrase in ("result in", "results in", "lead to", "leads to")
            )

            if is_driver_query and not is_impact_query:
                directions = ["upstream"]
            elif is_impact_query and not is_driver_query:
                directions = ["downstream"]
            else:
                directions = ["upstream", "downstream"]

            hops = max(1, max_hops)

            for target_nid in matched_node_ids[:2]:
                for direction in directions:
                    # BFS path exploration up to hops depth
                    queue: list[tuple[list[str], list[dict[str, Any]]]] = [([target_nid], [])]
                    for _ in range(hops):
                        next_queue: list[tuple[list[str], list[dict[str, Any]]]] = []
                        for path_nodes, path_edges in queue:
                            curr_node = path_nodes[0] if direction == "upstream" else path_nodes[-1]
                            neighbors = self.backend.get_neighbors(curr_node, direction=direction)

                            for item in neighbors:
                                neighbor_nid = item["node"].get("node_id") or item["node"].get("id")
                                if not neighbor_nid or neighbor_nid in path_nodes:
                                    continue

                                edge_data = item.get("edge", {})
                                if direction == "upstream":
                                    new_path = [neighbor_nid] + path_nodes
                                    new_edges = [edge_data] + path_edges
                                else:
                                    new_path = path_nodes + [neighbor_nid]
                                    new_edges = path_edges + [edge_data]

                                next_queue.append((new_path, new_edges))

                                # Process completed path
                                step_names: list[str] = []
                                for step_nid in new_path:
                                    step_data = self.backend.get_node(step_nid)
                                    s_name = (step_data.get("name") if step_data else None) or step_nid
                                    step_names.append(s_name)

                                narrative = " -> ".join(step_names)
                                if narrative in seen_narratives:
                                    continue
                                seen_narratives.add(narrative)

                                src_name = step_names[0]
                                tgt_name = step_names[-1]
                                rel_sequence = [e.get("relation_type", "DRIVES").upper() for e in new_edges]

                                if len(new_path) == 2:
                                    evidence = new_edges[0].get("evidence_text") or (
                                        new_edges[0].get("properties", {}).get("evidence_text")
                                        if isinstance(new_edges[0].get("properties"), dict)
                                        else None
                                    ) or f"{src_name} {rel_sequence[0].lower()} {tgt_name}"
                                    narrative_exp = f"{src_name} {rel_sequence[0].lower()} {tgt_name}: {evidence}"
                                else:
                                    narrative_exp = f"{src_name} impacts {tgt_name} through causal chain: {narrative}"

                                path_pages: list[int] = []
                                path_evidences: list[str] = []
                                page_ev_map: dict[int, str] = {}
                                path_doc_id: str | None = None
                                path_filename: str | None = None

                                for e in new_edges:
                                    e_props = e.get("properties") if isinstance(e.get("properties"), dict) else e
                                    pg = e.get("source_page") or e_props.get("source_page")
                                    ev = e.get("evidence_text") or e_props.get("evidence_text")
                                    d_id = e.get("source_doc_id") or e_props.get("source_doc_id")
                                    f_name = e.get("source_filename") or e_props.get("source_filename")

                                    if pg is not None:
                                        try:
                                            pg_int = int(pg)
                                            if pg_int not in path_pages:
                                                path_pages.append(pg_int)
                                            if ev and pg_int not in page_ev_map:
                                                page_ev_map[pg_int] = str(ev)
                                        except (ValueError, TypeError):
                                            pass
                                    if ev and str(ev) not in path_evidences:
                                        path_evidences.append(str(ev))
                                    if not path_doc_id and d_id:
                                        path_doc_id = str(d_id)
                                    if not path_filename and f_name:
                                        path_filename = str(f_name)

                                for nid in new_path:
                                    nd = self.backend.get_node(nid)
                                    if isinstance(nd, dict):
                                        if not path_pages and nd.get("source_page") is not None:
                                            try:
                                                pg_int = int(nd.get("source_page"))
                                                if pg_int not in path_pages:
                                                    path_pages.append(pg_int)
                                            except (ValueError, TypeError):
                                                pass
                                        if not path_doc_id and nd.get("source_doc_id"):
                                            path_doc_id = str(nd.get("source_doc_id"))
                                        if not path_filename and nd.get("source_filename"):
                                            path_filename = str(nd.get("source_filename"))

                                if not path_filename and path_doc_id and path_doc_id in self._doc_filenames:
                                    path_filename = self._doc_filenames[path_doc_id]

                                primary_page = path_pages[0] if path_pages else None
                                primary_ev = "; ".join(path_evidences) if path_evidences else None

                                causal_paths.append(
                                    CausalGraphPath(
                                        path_id=str(uuid.uuid4()),
                                        source_node_name=src_name,
                                        target_node_name=tgt_name,
                                        node_sequence=step_names,
                                        relationship_sequence=rel_sequence,
                                        narrative_explanation=narrative_exp,
                                        source_page=primary_page,
                                        source_pages=path_pages,
                                        evidence_text=primary_ev,
                                        evidence_texts=path_evidences,
                                        page_evidence_map=page_ev_map,
                                        source_doc_id=path_doc_id,
                                        source_filename=path_filename,
                                    )
                                )



                        queue = next_queue
                        if not queue:
                            break

        return metric_nodes, causal_paths

    def get_metric_nodes(
        self,
        name: str,
        doc_id: str | None = None,
        period: str | None = None,
        table_id: str | None = None,
        table_title: str | None = None,
    ) -> list[FinancialMetricNode]:
        """Retrieve all matching metric nodes, distinguishing and filtering by report, period, and table scope."""
        if not self._metric_nodes_by_name and self.backend.get_stats().get("total_nodes", 0) > 0:
            self.rebuild_index()

        name_lower = name.lower()
        clean = normalize_lookup_key(name)
        candidate_ids = (
            list(self._metric_nodes_by_name.get(name_lower, []))
            or list(self._metric_nodes_by_name.get(clean, []))
            or ([self._name_map[name]] if name in self._name_map else [])
        )

        if not candidate_ids:
            try:
                subgraph = self.backend.get_subgraph(root_id=None)
                for node_data in subgraph.get("nodes", []):
                    n_name = node_data.get("name") or node_data.get("topic")
                    nid = node_data.get("node_id") or node_data.get("id")
                    if n_name and nid:
                        if n_name.lower() == name_lower or normalize_lookup_key(n_name) == clean:
                            if nid not in candidate_ids:
                                candidate_ids.append(nid)
            except Exception:
                pass

        matched_nodes: list[FinancialMetricNode] = []
        seen_ids: set[str] = set()

        for nid in candidate_ids:
            if nid in seen_ids:
                continue
            seen_ids.add(nid)

            node = self._metrics_cache.get(nid)
            if not node:
                ndata = self.backend.get_node(nid)
                if not ndata:
                    continue
                try:
                    node = FinancialMetricNode(
                        node_id=ndata.get("node_id", nid),
                        name=ndata.get("name", "Metric"),
                        normalized_key=ndata.get("normalized_key", normalize_lookup_key(ndata.get("name", ""))),
                        value=ndata.get("value"),
                        unit=ndata.get("unit", MetricUnit.USD),
                        scale=ndata.get("scale"),
                        currency_symbol=ndata.get("currency_symbol"),
                        period=str(ndata.get("period", "Current")),
                        statement_type=StatementType.GENERAL,
                        source_doc_id=str(ndata.get("source_doc_id", "")),
                        source_page=int(ndata.get("source_page", 1)),
                        table_id=ndata.get("table_id"),
                        table_title=ndata.get("table_title"),
                        raw_text=ndata.get("raw_text"),
                        source_filename=ndata.get("source_filename") or self._doc_filenames.get(str(ndata.get("source_doc_id", ""))),
                    )
                except Exception:
                    continue

            # Filter by report (source_doc_id)
            if doc_id and node.source_doc_id != doc_id:
                continue

            # Filter by period
            if period:
                p_query = period.lower().strip()
                p_node = node.period.lower().strip()
                if p_query not in p_node and p_node not in p_query:
                    continue

            # Filter by table_id
            if table_id and node.table_id != table_id:
                continue

            # Filter by table_title
            if table_title:
                t_query = table_title.lower().strip()
                t_node = (node.table_title or "").lower().strip()
                if t_query not in t_node:
                    continue

            matched_nodes.append(node)

        return matched_nodes

    def get_node_ids(
        self,
        name: str,
        doc_id: str | None = None,
        period: str | None = None,
        table_id: str | None = None,
        table_title: str | None = None,
    ) -> list[str]:
        """Return all matching node IDs filtered by report, period, and table scope."""
        nodes = self.get_metric_nodes(
            name=name,
            doc_id=doc_id,
            period=period,
            table_id=table_id,
            table_title=table_title,
        )
        return [n.node_id for n in nodes]

    def get_node(
        self,
        node_id_or_name: str,
        doc_id: str | None = None,
        period: str | None = None,
        table_id: str | None = None,
        table_title: str | None = None,
    ) -> dict[str, Any] | None:
        """Retrieve node attributes by ID or canonical name, optionally filtered by scope."""
        direct = self.backend.get_node(node_id_or_name)
        if direct is not None:
            return direct

        nodes = self.get_metric_nodes(
            name=node_id_or_name,
            doc_id=doc_id,
            period=period,
            table_id=table_id,
            table_title=table_title,
        )
        if nodes:
            return self.backend.get_node(nodes[0].node_id)

        nid = self._resolve_id(
            node_id_or_name,
            doc_id=doc_id,
            period=period,
            table_id=table_id,
            table_title=table_title,
        )
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
            unit = n.get("unit")
            scale = n.get("scale")
            symbol = n.get("currency_symbol") or ("$" if str(unit) in ("USD", "MetricUnit.USD") else "")

            if isinstance(val, (int, float)):
                unit_str = unit.value if hasattr(unit, "value") else str(unit)
                if unit_str == "PERCENTAGE":
                    val_text = f"{val:,.0f}%" if (val.is_integer() if hasattr(val, "is_integer") else val == int(val)) else f"{val:.1f}%"
                elif unit_str == "BASIS_POINTS":
                    val_text = f"{val:,.0f} bps"
                elif unit_str in ("SHARES", "COUNT"):
                    scale_str = f" {scale}" if scale else ""
                    val_text = f"{val:,.0f}{scale_str}"
                else:
                    scale_str = scale or ""
                    val_formatted = f"{val:,.2f}".rstrip("0").rstrip(".")
                    val_text = (
                        f"{symbol}{val:,.0f}{scale_str}"
                        if (val.is_integer() if hasattr(val, "is_integer") else val == int(val))
                        else f"{symbol}{val_formatted}{scale_str}"
                    )
                val_str = f" ({val_text})"
            else:
                val_str = ""

            period = n.get("period")
            period_str = f" [{period}]" if period and str(period).lower() != "current" else ""
            label_text = f"{name}{period_str}{val_str}".replace('"', "'")
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
        self._metric_nodes_by_name.clear()
        self._node_scopes.clear()
        self._metrics_cache.clear()
        self._doc_filenames.clear()
