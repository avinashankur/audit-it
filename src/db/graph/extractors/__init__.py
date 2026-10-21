"""Graph entity and causal relationship extraction strategies."""

from typing import Any

from src.db.graph.extractors.base import BaseExtractor
from src.db.graph.extractors.financial_rule_extractor import (
    STANDARD_ACCOUNTING_RULES,
    FinancialRuleExtractor,
)

__all__ = [
    "BaseExtractor",
    "FinancialRuleExtractor",
    "LLMExtractor",
    "STANDARD_ACCOUNTING_RULES",
]


def __getattr__(name: str) -> Any:
    if name == "LLMExtractor":
        from src.db.graph.extractors.llm_extractor import LLMExtractor

        return LLMExtractor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
