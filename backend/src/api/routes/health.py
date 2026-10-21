"""Health and configuration routes."""

from fastapi import APIRouter, Depends

from src.api.schemas import HealthResponse
from src.api.session_mgr import SessionManager, get_session_manager

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", response_model=HealthResponse)
async def check_health(
    session_mgr: SessionManager = Depends(get_session_manager),
) -> HealthResponse:
    samples = session_mgr.list_sample_reports()
    docs = session_mgr.list_documents()
    return HealthResponse(
        status="ok",
        version="0.1.0",
        backends_available=["networkx", "neo4j"],
        sample_reports_count=len(samples),
        active_documents_count=len(docs),
    )
