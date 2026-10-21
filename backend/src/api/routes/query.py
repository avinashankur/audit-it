"""Financial audit question-answering and streaming routes."""

from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from src.api.dependencies import get_llm_api_key, get_llm_provider, get_session_id
from src.api.schemas import QueryRequestDto, QueryResponseDto
from src.api.session_mgr import SessionManager, get_session_manager

router = APIRouter(prefix="/documents/{doc_id}/query", tags=["Query"])


@router.post("", response_model=QueryResponseDto)
async def execute_query(
    doc_id: str,
    payload: QueryRequestDto,
    header_provider: str | None = Depends(get_llm_provider),
    header_api_key: str | None = Depends(get_llm_api_key),
    session_id: str = Depends(get_session_id),
    session_mgr: SessionManager = Depends(get_session_manager),
) -> QueryResponseDto:
    doc = session_mgr.get_document(doc_id, owner_id=session_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")

    provider = payload.model_provider or header_provider or "Offline Grounded"

    resp = await asyncio.to_thread(
        doc.qa_service.answer_query,
        query=payload.query_text,
        provider=provider,
        api_key=header_api_key,
        top_k=payload.top_k,
    )

    return QueryResponseDto(
        query_id=resp.query_id,
        query_text=resp.query_text,
        answer_text=resp.answer_text,
        citations=resp.citations,
        causal_paths=resp.causal_paths,
        retrieved_chunks=resp.retrieved_chunks,
        latency_ms=resp.latency_ms,
        model_provider=resp.model_provider,
    )


@router.post("/stream")
async def execute_query_stream(
    doc_id: str,
    payload: QueryRequestDto,
    header_provider: str | None = Depends(get_llm_provider),
    header_api_key: str | None = Depends(get_llm_api_key),
    session_id: str = Depends(get_session_id),
    session_mgr: SessionManager = Depends(get_session_manager),
) -> StreamingResponse:
    doc = session_mgr.get_document(doc_id, owner_id=session_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")

    provider = payload.model_provider or header_provider or "Offline Grounded"

    async def event_generator() -> AsyncGenerator[str, None]:
        # 1. Start event
        yield f"event: start\ndata: {json.dumps({'status': 'reasoning', 'provider': provider})}\n\n"
        await asyncio.sleep(0.05)

        # 2. Run retrieval & reasoning
        resp = await asyncio.to_thread(
            doc.qa_service.answer_query,
            query=payload.query_text,
            provider=provider,
            api_key=header_api_key,
            top_k=payload.top_k,
        )

        # 3. Stream answer tokens in readable chunks
        words = resp.answer_text.split(" ")
        chunk_size = 3
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i : i + chunk_size])
            if i + chunk_size < len(words):
                chunk += " "
            payload_data = json.dumps({"delta": chunk})
            yield f"event: token\ndata: {payload_data}\n\n"
            await asyncio.sleep(0.015)

        # 4. Stream citations
        citations_data = [
            {
                "citation_id": c.citation_id,
                "source_doc_id": c.source_doc_id,
                "source_filename": c.source_filename,
                "page_number": c.page_number,
                "citation_type": (
                    c.citation_type.value
                    if hasattr(c.citation_type, "value")
                    else str(c.citation_type)
                ),
                "snippet": c.snippet,
                "relevance_score": c.relevance_score,
            }
            for c in resp.citations
        ]
        yield f"event: citations\ndata: {json.dumps(citations_data)}\n\n"

        # 5. Stream causal paths
        paths_data = [
            {
                "path_id": p.path_id,
                "source_node_name": p.source_node_name,
                "target_node_name": p.target_node_name,
                "node_sequence": p.node_sequence,
                "relationship_sequence": p.relationship_sequence,
                "narrative_explanation": p.narrative_explanation,
            }
            for p in resp.causal_paths
        ]
        yield f"event: causal_paths\ndata: {json.dumps(paths_data)}\n\n"

        # 6. Stream completion event
        yield f"event: done\ndata: {json.dumps({'query_id': resp.query_id, 'latency_ms': resp.latency_ms})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
