"""Deterministic rule-based extractor for standard GAAP/IFRS financial statement relationships."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Sequence
import uuid

from src.core.logging import get_logger, profile_stage
from src.db.graph.extractors.base import BaseExtractor
from src.db.graph.store import CANONICAL_METRICS
from src.db.models.entities import (
    CausalDirection,
    CausalRelationshipEdge,
    CausalRelationType,
    FinancialMetricNode,
)

logger = get_logger(__name__)

# Standard causal dependency definitions: (source_metric, target_metric, relation_type, direction, confidence, explanation_template)
STANDARD_ACCOUNTING_RULES: list[tuple[str, str, CausalRelationType, CausalDirection, float, str]] = [
    (
        "Revenue",
        "Gross Margin",
        CausalRelationType.DRIVES,
        CausalDirection.DIRECT,
        1.0,
        "Revenue directly drives Gross Margin as the top-line inflow before cost deduction.",
    ),
    (
        "Cost of Sales",
        "Gross Margin",
        CausalRelationType.IMPACTS,
        CausalDirection.INVERSE,
        1.0,
        "Cost of Sales contracts Gross Margin through production and procurement costs.",
    ),
    (
        "Gross Margin",
        "Operating Income",
        CausalRelationType.DRIVES,
        CausalDirection.DIRECT,
        1.0,
        "Gross Margin provides the gross profit pool that drives Operating Income.",
    ),
    (
        "Operating Expenses",
        "Operating Income",
        CausalRelationType.IMPACTS,
        CausalDirection.INVERSE,
        1.0,
        "Operating Expenses (SG&A, R&D) reduce Operating Income.",
    ),
    (
        "Operating Income",
        "Net Income",
        CausalRelationType.DRIVES,
        CausalDirection.DIRECT,
        1.0,
        "Operating Income is the core operational driver of Net Income.",
    ),
    (
        "Interest Expense",
        "Net Income",
        CausalRelationType.IMPACTS,
        CausalDirection.INVERSE,
        1.0,
        "Interest Expense decreases Net Income via financing costs.",
    ),
    (
        "Tax Expense",
        "Net Income",
        CausalRelationType.IMPACTS,
        CausalDirection.INVERSE,
        1.0,
        "Income Tax Expense reduces pre-tax earnings to determine Net Income.",
    ),
    (
        "Current Assets",
        "Working Capital",
        CausalRelationType.CALCULATED_FROM,
        CausalDirection.DIRECT,
        1.0,
        "Current Assets expand Working Capital.",
    ),
    (
        "Current Liabilities",
        "Working Capital",
        CausalRelationType.IMPACTS,
        CausalDirection.INVERSE,
        1.0,
        "Current Liabilities diminish Working Capital obligations.",
    ),
    (
        "Total Debt",
        "Debt to Equity",
        CausalRelationType.DRIVES,
        CausalDirection.DIRECT,
        1.0,
        "Higher Total Debt increases financial leverage ratio.",
    ),
]


class FinancialRuleExtractor(BaseExtractor):
    """Extracts deterministic causal edges between financial metrics based on accounting rules."""

    def __init__(
        self,
        rules: list[tuple[str, str, CausalRelationType, CausalDirection, float, str]] | None = None,
    ) -> None:
        self.rules = rules or STANDARD_ACCOUNTING_RULES

    @staticmethod
    def _canonicalize_name(name: str) -> str:
        """Resolve a raw metric name to its canonical financial accounting term."""
        lowered = name.strip().lower()
        return CANONICAL_METRICS.get(lowered, name.strip()).lower()

    @profile_stage("rule_extractor_extract")
    def extract(
        self,
        data: Sequence[FinancialMetricNode] | dict[str, FinancialMetricNode],
        **kwargs: Any,
    ) -> list[CausalRelationshipEdge]:
        """Extract causal relationships among metrics matching standard accounting rules.

        Metrics are partitioned by (source_doc_id, table_id, period) before applying rules,
        preventing metrics across distinct statements, years, or filings from mixing.
        """
        nodes: list[FinancialMetricNode]
        if isinstance(data, dict):
            nodes = list(data.values())
        else:
            nodes = list(data)

        # Partition metrics by (doc_id, table_id, period)
        metric_groups: dict[tuple[str, str, str], dict[str, FinancialMetricNode]] = defaultdict(dict)
        for node in nodes:
            group_key = (
                node.source_doc_id or "",
                node.table_id or "",
                node.period or "",
            )
            canonical_key = self._canonicalize_name(node.name)
            # Retain first or higher-confidence entry for the same canonical item in the same statement block
            if canonical_key not in metric_groups[group_key]:
                metric_groups[group_key][canonical_key] = node

        edges: list[CausalRelationshipEdge] = []

        for group_key, group_metrics in metric_groups.items():
            for src_name, tgt_name, rel_type, direction, conf, explanation in self.rules:
                norm_src = self._canonicalize_name(src_name)
                norm_tgt = self._canonicalize_name(tgt_name)

                src_node = group_metrics.get(norm_src)
                tgt_node = group_metrics.get(norm_tgt)

                if src_node is not None and tgt_node is not None:
                    # Period matching confirmation
                    if src_node.period and tgt_node.period and src_node.period != tgt_node.period:
                        continue

                    source_page = src_node.source_page or tgt_node.source_page
                    evidence = f"{explanation} [Reported: {src_node.name} ({src_node.format_value()}) -> {tgt_node.name} ({tgt_node.format_value()})]"

                    edge = CausalRelationshipEdge(
                        edge_id=str(uuid.uuid4()),
                        source_node_id=src_node.node_id,
                        target_node_id=tgt_node.node_id,
                        relation_type=rel_type,
                        direction=direction,
                        confidence=conf,
                        evidence_text=evidence,
                        source_page=source_page,
                        source_doc_id=src_node.source_doc_id or tgt_node.source_doc_id,
                        source_filename=src_node.source_filename or tgt_node.source_filename,
                    )
                    edges.append(edge)

        return edges

    def apply(self, store: Any, ingest_result: Any) -> None:
        """Execute rule-based causal extraction across all stored metric nodes."""
        metrics: list[FinancialMetricNode] = []
        if hasattr(store, "_metrics_cache"):
            metrics = list(store._metrics_cache.values())
        elif hasattr(store, "backend"):
            nodes = store.backend.get_nodes_by_type("METRIC")
            metrics = [FinancialMetricNode(**n["properties"]) for n in nodes if "properties" in n]

        edges = self.extract(metrics)
        for edge in edges:
            store.add_causal_edge(edge)
