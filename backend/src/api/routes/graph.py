"""Graph visualization and dependency inspection routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_session_id
from src.api.schemas import (
    GraphEdgeDataDto,
    GraphEdgeDto,
    GraphNodeDataDto,
    GraphNodeDto,
    GraphResponseDto,
    SubgraphResponseDto,
)
from src.api.session_mgr import SessionManager, get_session_manager

router = APIRouter(prefix="/documents/{doc_id}/graph", tags=["Graph"])


def _format_node_value(n: dict[str, Any]) -> str:
    val = n.get("value")
    if val is None:
        return n.get("raw_text") or "N/A"
    unit = str(n.get("unit") or "")
    scale = n.get("scale") or ""
    symbol = n.get("currency_symbol") or ("$" if "usd" in unit.lower() else "")

    if "percentage" in unit.lower() or "%" in unit:
        return f"{val:.1f}%"
    if "basis_points" in unit.lower() or "bps" in unit.lower():
        return f"{val:,.0f} bps"

    try:
        val_float = float(val)
        if val_float.is_integer():
            return f"{symbol}{int(val_float):,}{scale}"
        return f"{symbol}{val_float:,.2f}{scale}"
    except Exception:
        return f"{symbol}{val}{scale}"


def _map_node(n: dict[str, Any]) -> GraphNodeDto:
    nid = str(n.get("node_id") or n.get("id") or "")
    name = n.get("name") or n.get("label") or nid
    node_type = str(n.get("node_type") or "").lower()
    is_disclosure = "disclosure" in node_type or "footnote" in node_type

    formatted_val = _format_node_value(n)

    data = GraphNodeDataDto(
        name=name,
        normalized_key=n.get("normalized_key"),
        node_type="disclosure" if is_disclosure else "metric",
        value=n.get("value"),
        formatted_value=formatted_val,
        unit=str(n.get("unit")) if n.get("unit") else None,
        scale=n.get("scale"),
        currency_symbol=n.get("currency_symbol"),
        period=n.get("period"),
        statement_type=str(n.get("statement_type")) if n.get("statement_type") else None,
        source_page=n.get("source_page"),
        table_title=n.get("table_title"),
        raw_text=n.get("raw_text"),
        confidence=float(n.get("confidence", 1.0)),
        snippet=n.get("snippet"),
        summary=n.get("summary"),
    )
    return GraphNodeDto(
        id=nid,
        type="disclosureNode" if is_disclosure else "metricNode",
        label=name,
        data=data,
    )


def _map_edge(idx: int, e: dict[str, Any]) -> GraphEdgeDto:
    src = str(e.get("source") or "")
    tgt = str(e.get("target") or "")
    rel_type = str(e.get("relation_type") or e.get("type") or "CAUSES")
    edge_id = str(e.get("edge_id") or f"e_{src}_{tgt}_{idx}")

    data = GraphEdgeDataDto(
        relation_type=rel_type,
        direction=str(e.get("direction") or "DIRECT"),
        confidence=float(e.get("confidence", 0.8)),
        evidence_text=str(e.get("evidence_text") or ""),
        source_page=e.get("source_page"),
        impact_magnitude=e.get("impact_magnitude"),
    )
    return GraphEdgeDto(
        id=edge_id,
        source=src,
        target=tgt,
        label=rel_type,
        data=data,
    )


@router.get("", response_model=GraphResponseDto)
async def get_document_graph(
    doc_id: str,
    root_node: str | None = None,
    hops: int = 2,
    session_id: str = Depends(get_session_id),
    session_mgr: SessionManager = Depends(get_session_manager),
) -> GraphResponseDto:
    doc = session_mgr.get_document(doc_id, owner_id=session_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")

    raw_subgraph = doc.graph_store.get_subgraph_data(root_node=root_node, hops=hops)
    raw_nodes = raw_subgraph.get("nodes", [])
    raw_edges = raw_subgraph.get("edges", [])

    nodes = [_map_node(n) for n in raw_nodes]
    edges = [_map_edge(i, e) for i, e in enumerate(raw_edges)]

    return GraphResponseDto(
        document_id=doc_id,
        filename=doc.filename,
        nodes=nodes,
        edges=edges,
        stats=doc.stats,
    )


@router.get("/dependencies/{node_id}", response_model=SubgraphResponseDto)
async def get_node_dependencies(
    doc_id: str,
    node_id: str,
    session_id: str = Depends(get_session_id),
    session_mgr: SessionManager = Depends(get_session_manager),
) -> SubgraphResponseDto:
    doc = session_mgr.get_document(doc_id, owner_id=session_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")

    upstream = doc.graph_store.get_neighbors(node_id, direction="upstream")
    downstream = doc.graph_store.get_neighbors(node_id, direction="downstream")

    upstream_ids = [str(item["node"]["node_id"]) for item in upstream]
    downstream_ids = [str(item["node"]["node_id"]) for item in downstream]

    raw_subgraph = doc.graph_store.get_subgraph_data(root_node=node_id, hops=1)
    nodes = [_map_node(n) for n in raw_subgraph.get("nodes", [])]
    edges = [_map_edge(i, e) for i, e in enumerate(raw_subgraph.get("edges", []))]

    return SubgraphResponseDto(
        root_node_id=node_id,
        upstream_node_ids=upstream_ids,
        downstream_node_ids=downstream_ids,
        nodes=nodes,
        edges=edges,
    )
