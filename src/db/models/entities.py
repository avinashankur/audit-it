"""Core domain models and schemas for AuditIt."""

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class DocumentStatus(str, Enum):
    PENDING = "PENDING"
    PARSING = "PARSING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"


class StatementType(str, Enum):
    INCOME_STATEMENT = "INCOME_STATEMENT"
    BALANCE_SHEET = "BALANCE_SHEET"
    CASH_FLOW = "CASH_FLOW"
    FOOTNOTE_DISCLOSURE = "FOOTNOTE_DISCLOSURE"
    MDA = "MDA"
    GENERAL = "GENERAL"

# disclosure nodes - narrative sections
# metric nodes in the graph
class MetricUnit(str, Enum):
    USD = "USD"
    PERCENTAGE = "PERCENTAGE"
    BASIS_POINTS = "BASIS_POINTS"
    RATIO = "RATIO"
    COUNT = "COUNT"
    SHARES = "SHARES"
    CURRENCY = "CURRENCY"

# disclosure nodes and metric nodes will be linked here
class CausalRelationType(str, Enum):
    DRIVES = "DRIVES"
    OFFSETS = "OFFSETS"
    CALCULATED_FROM = "CALCULATED_FROM"
    CONSTRAINS = "CONSTRAINS"
    IMPACTS = "IMPACTS"
    ATTRIBUTED_TO = "ATTRIBUTED_TO"


class CausalDirection(str, Enum):
    DIRECT = "DIRECT"
    INVERSE = "INVERSE"
    CORRELATED = "CORRELATED"
    NEUTRAL = "NEUTRAL"


class CitationType(str, Enum):
    TEXT_EXCERPT = "TEXT_EXCERPT"
    FINANCIAL_TABLE = "FINANCIAL_TABLE"
    CAUSAL_PATH = "CAUSAL_PATH"


# Ingestion
class DocumentMetadata(BaseModel):
    doc_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    file_hash: str  # sha-256 for provenance & dedupe
    total_pages: int = Field(ge=1)
    file_size_bytes: int = Field(ge=0)
    upload_timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: DocumentStatus = DocumentStatus.PENDING


class TextChunk(BaseModel):
    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    doc_id: str
    text: str = Field(min_length=1)
    page_number: int = Field(ge=1)  # 1-indexed source page
    section_header: str | None = None
    token_count: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TableData(BaseModel):
    table_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    doc_id: str
    page_number: int = Field(ge=1)
    title: str | None = None
    headers: list[str] = Field(min_length=1)
    rows: list[list[str]] = Field(default_factory=list)
    markdown: str


# Graph
class FinancialMetricNode(BaseModel):
    node_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    normalized_key: str  # e.g. gross_margin
    value: float | None = None
    unit: MetricUnit = MetricUnit.USD
    scale: str | None = None  # e.g. "M", "B", "K", or None
    currency_symbol: str | None = None  # e.g. "$", "€", "£"
    period: str  # e.g. FY2025, Q3_2025
    statement_type: StatementType = StatementType.GENERAL
    source_doc_id: str
    source_page: int = Field(ge=1)
    table_id: str | None = None
    table_title: str | None = None
    raw_text: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_filename: str | None = None

    @field_validator("normalized_key")
    @classmethod
    def normalize_key(cls, v: str) -> str:
        return v.strip().lower().replace(" ", "_")

    def format_value(self) -> str:
        """Format metric value preserving unit, currency symbol, and scale."""
        if self.value is None:
            return self.raw_text or "N/A"

        unit_str = self.unit.value if hasattr(self.unit, "value") else str(self.unit)

        if unit_str == MetricUnit.PERCENTAGE.value:
            if self.value.is_integer() if hasattr(self.value, "is_integer") else self.value == int(self.value):
                return f"{self.value:,.0f}%"
            formatted_num = f"{self.value:.2f}".rstrip("0").rstrip(".")
            return f"{formatted_num}%"

        if unit_str == MetricUnit.BASIS_POINTS.value:
            return f"{self.value:,.0f} bps"

        if unit_str in (MetricUnit.SHARES.value, MetricUnit.COUNT.value):
            scale_part = f" {self.scale}" if self.scale else ""
            return f"{self.value:,.0f}{scale_part}"

        # Currency or standard number
        symbol = self.currency_symbol or ("$" if unit_str == MetricUnit.USD.value else "")
        scale_part = self.scale or ""

        if self.value.is_integer() if hasattr(self.value, "is_integer") else self.value == int(self.value):
            return f"{symbol}{self.value:,.0f}{scale_part}"
        formatted_num = f"{self.value:,.2f}".rstrip("0").rstrip(".")
        return f"{symbol}{formatted_num}{scale_part}"


class DisclosureNode(BaseModel):
    node_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    topic: str
    summary: str
    source_doc_id: str
    source_page: int = Field(ge=1)
    snippet: str


class CausalRelationshipEdge(BaseModel):
    edge_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_node_id: str
    target_node_id: str
    relation_type: CausalRelationType
    direction: CausalDirection = CausalDirection.DIRECT
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    evidence_text: str
    source_page: int = Field(ge=1)
    impact_magnitude: str | None = None  # e.g. -180 bps
    source_doc_id: str | None = None
    source_filename: str | None = None


class CausalGraphPath(BaseModel):
    path_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_node_name: str
    target_node_name: str
    node_sequence: list[str]
    relationship_sequence: list[str]
    narrative_explanation: str
    source_page: int | None = None
    source_pages: list[int] = Field(default_factory=list)
    evidence_text: str | None = None
    evidence_texts: list[str] = Field(default_factory=list)
    page_evidence_map: dict[int, str] = Field(default_factory=dict)
    source_doc_id: str | None = None
    source_filename: str | None = None


# Retrieval
class AuditCitation(BaseModel):
    citation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_doc_id: str
    source_filename: str
    page_number: int = Field(ge=1)
    citation_type: CitationType
    snippet: str
    relevance_score: float | None = None


class HybridRetrievalResult(BaseModel):
    query: str
    text_chunks: list[TextChunk] = Field(default_factory=list)
    metric_nodes: list[FinancialMetricNode] = Field(default_factory=list)
    causal_paths: list[CausalGraphPath] = Field(default_factory=list)
    rrf_scores: dict[str, float] = Field(default_factory=dict)


# QA
class AuditQueryRequest(BaseModel):
    query_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query_text: str = Field(min_length=3)
    target_period: str | None = None
    focus_metric: str | None = None
    model_provider: str = "Gemini"


class AuditQueryResponse(BaseModel):
    query_id: str
    query_text: str
    answer_text: str
    citations: list[AuditCitation] = Field(default_factory=list)
    causal_paths: list[CausalGraphPath] = Field(default_factory=list)
    retrieved_chunks: list[TextChunk] = Field(default_factory=list)
    latency_ms: dict[str, float] = Field(default_factory=dict)
    model_provider: str
    tokens_used: int | None = None
