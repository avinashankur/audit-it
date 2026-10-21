"""Pydantic request and response schemas for AuditIt API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from src.db.models.entities import (
    AuditCitation,
    CausalGraphPath,
    CausalRelationshipEdge,
    FinancialMetricNode,
    TableData,
    TextChunk,
)


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    backends_available: list[str] = Field(default_factory=lambda: ["networkx", "neo4j"])
    sample_reports_count: int = 0
    active_documents_count: int = 0


class SampleReportDto(BaseModel):
    name: str
    size_kb: float


class IngestJobResponse(BaseModel):
    job_id: str
    document_id: str
    filename: str
    status: str = "PENDING"
    message: str = "Ingestion started"


class IngestJobStatus(BaseModel):
    job_id: str
    document_id: str
    filename: str
    status: str  # "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED"
    stage: str  # "parsing" | "tables" | "graph" | "indexing" | "ready"
    progress: int  # 0 to 100
    error: str | None = None
    stats: dict[str, Any] | None = None


class DocumentSummaryDto(BaseModel):
    document_id: str
    filename: str
    size_kb: float
    total_pages: int
    chunks_count: int
    tables_count: int
    metric_nodes_count: int = 0
    disclosure_nodes_count: int = 0
    causal_edges_count: int = 0
    uploaded_at: str
    status: str = "Ready"


class GraphNodeDataDto(BaseModel):
    name: str
    normalized_key: str | None = None
    node_type: str  # "metric" | "disclosure"
    value: float | None = None
    formatted_value: str | None = None
    unit: str | None = None
    scale: str | None = None
    currency_symbol: str | None = None
    period: str | None = None
    statement_type: str | None = None
    source_page: int | None = None
    table_title: str | None = None
    raw_text: str | None = None
    confidence: float = 1.0
    snippet: str | None = None
    summary: str | None = None


class GraphNodeDto(BaseModel):
    id: str
    type: str  # "metricNode" | "disclosureNode"
    label: str
    data: GraphNodeDataDto


class GraphEdgeDataDto(BaseModel):
    relation_type: str
    direction: str = "DIRECT"
    confidence: float = 0.8
    evidence_text: str = ""
    source_page: int | None = None
    impact_magnitude: str | None = None


class GraphEdgeDto(BaseModel):
    id: str
    source: str
    target: str
    label: str
    data: GraphEdgeDataDto


class GraphResponseDto(BaseModel):
    document_id: str
    filename: str
    nodes: list[GraphNodeDto] = Field(default_factory=list)
    edges: list[GraphEdgeDto] = Field(default_factory=list)
    stats: dict[str, Any] = Field(default_factory=dict)


class SubgraphResponseDto(BaseModel):
    root_node_id: str
    upstream_node_ids: list[str] = Field(default_factory=list)
    downstream_node_ids: list[str] = Field(default_factory=list)
    nodes: list[GraphNodeDto] = Field(default_factory=list)
    edges: list[GraphEdgeDto] = Field(default_factory=list)


class QueryRequestDto(BaseModel):
    query_text: str = Field(min_length=2)
    target_period: str | None = None
    focus_metric: str | None = None
    model_provider: str = "Offline Grounded"
    top_k: int = 4


class QueryResponseDto(BaseModel):
    query_id: str
    query_text: str
    answer_text: str
    citations: list[AuditCitation] = Field(default_factory=list)
    causal_paths: list[CausalGraphPath] = Field(default_factory=list)
    retrieved_chunks: list[TextChunk] = Field(default_factory=list)
    latency_ms: dict[str, float] = Field(default_factory=dict)
    model_provider: str
