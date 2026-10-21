"""Document management and ingestion routes."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from src.api.schemas import (
    DocumentSummaryDto,
    IngestJobResponse,
    IngestJobStatus,
)
from src.api.session_mgr import SessionManager, get_session_manager
from src.db.models.entities import TableData

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/upload", response_model=IngestJobResponse)
async def upload_document(
    file: UploadFile = File(...),
    backend_type: str = Form("networkx"),
    session_mgr: SessionManager = Depends(get_session_manager),
) -> IngestJobResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are currently supported")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    job = session_mgr.start_ingest_job(
        pdf_bytes=content,
        filename=file.filename,
        backend_type=backend_type,
    )
    return IngestJobResponse(
        job_id=job.job_id,
        document_id=job.document_id,
        filename=job.filename,
        status=job.status,
        message=f"Uploaded and started processing '{file.filename}'",
    )


@router.get("/jobs/{job_id}", response_model=IngestJobStatus)
async def get_job_status(
    job_id: str,
    session_mgr: SessionManager = Depends(get_session_manager),
) -> IngestJobStatus:
    job = session_mgr.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return job


@router.get("", response_model=list[DocumentSummaryDto])
async def list_documents(
    session_mgr: SessionManager = Depends(get_session_manager),
) -> list[DocumentSummaryDto]:
    return session_mgr.list_documents()


@router.get("/{doc_id}", response_model=DocumentSummaryDto)
async def get_document(
    doc_id: str,
    session_mgr: SessionManager = Depends(get_session_manager),
) -> DocumentSummaryDto:
    doc = session_mgr.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")
    return doc.to_summary()


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    session_mgr: SessionManager = Depends(get_session_manager),
) -> dict[str, str]:
    success = session_mgr.delete_document(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")
    return {"message": f"Document '{doc_id}' deleted successfully"}


@router.get("/{doc_id}/tables", response_model=list[TableData])
async def get_document_tables(
    doc_id: str,
    session_mgr: SessionManager = Depends(get_session_manager),
) -> list[TableData]:
    doc = session_mgr.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")
    return doc.ingest_result.tables
