"""Deterministic rule-based extractor for standard GAAP/IFRS financial statement relationships."""

from __future__ import annotations

import uuid
from typing import Sequence

from src.core.logging import get_logger, profile_stage
from src.db.graph.extractors.base import BaseExtractor
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
        "Cost of Goods Sold",
        "Gross Margin",
        CausalRelationType.IMPACTS,
        CausalDirection.INVERSE,
        1.0,
        "Cost of Goods Sold contracts Gross Margin through production and procurement costs.",
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

    @profile_stage("rule_extractor_extract")
    def extract(
        self,
        data: Sequence[FinancialMetricNode] | dict[str, FinancialMetricNode],
        **kwargs: Any,
    ) -> list[CausalRelationshipEdge]:
        """Extract causal relationships among metrics matching standard accounting rules."""
        if isinstance(data, dict):
            metric_map = {k.lower(): v for k, v in data.items()}
        else:
            metric_map = {m.name.lower(): m for m in data}

        edges: list[CausalRelationshipEdge] = []

        for src_name, tgt_name, rel_type, direction, conf, explanation in self.rules:
            src_node = metric_map.get(src_name.lower())
            tgt_node = metric_map.get(tgt_name.lower())

            if src_node is not None and tgt_node is not None:
                # Ensure metrics share same or compatible period
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
