"""Core domain models and schemas for AuditIt."""

import uuid
from datetime import datetime
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


class MetricUnit(str, Enum):
    USD = "USD"
    PERCENTAGE = "PERCENTAGE"
    BASIS_POINTS = "BASIS_POINTS"
    RATIO = "RATIO"
    COUNT = "COUNT"
    SHARES = "SHARES"
    CURRENCY = "CURRENCY"


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
    upload_timestamp: datetime = Field(default_factory=datetime.utcnow)
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
    period: str  # e.g. FY2025, Q3_2025
    statement_type: StatementType = StatementType.GENERAL
    source_doc_id: str
    source_page: int = Field(ge=1)
    raw_text: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("normalized_key")
    @classmethod
    def normalize_key(cls, v: str) -> str:
        return v.strip().lower().replace(" ", "_")


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


class CausalGraphPath(BaseModel):
    path_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_node_name: str
    target_node_name: str
    node_sequence: list[str]
    relationship_sequence: list[str]
    narrative_explanation: str


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
