"""Document management and ingestion routes."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from src.api.dependencies import get_session_id
from src.api.schemas import (
    DocumentSummaryDto,
    IngestJobResponse,
    IngestJobStatus,
)
from src.api.session_mgr import SessionManager, get_session_manager
from src.core.env import get_settings
from src.db.models.entities import TableData

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/upload", response_model=IngestJobResponse)
async def upload_document(
    file: UploadFile = File(...),
    backend_type: str = Form("networkx"),
    session_id: str = Depends(get_session_id),
    session_mgr: SessionManager = Depends(get_session_manager),
) -> IngestJobResponse:
    # 1. Reject if server is at capacity before reading body into memory
    if not session_mgr.can_accept_job():
        raise HTTPException(
            status_code=429,
            detail=f"Server is currently processing maximum concurrent ingestion jobs ({session_mgr.max_active_jobs}). Please retry later.",
        )

    # 2. Validate file extension
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are currently supported")

    # 3. Check declared size if available
    settings = get_settings()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    if file.size is not None and file.size > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Uploaded file exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB",
        )

    # 4. Stream read upload in bounded chunks to prevent memory exhaustion
    chunks: list[bytes] = []
    total_bytes = 0
    chunk_size = 64 * 1024

    while chunk := await file.read(chunk_size):
        total_bytes += len(chunk)
        if total_bytes > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Uploaded file exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB",
            )
        chunks.append(chunk)

    if total_bytes == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    content = b"".join(chunks)

    # 5. Validate PDF magic header
    if b"%PDF-" not in content[:1024]:
        raise HTTPException(
            status_code=400,
            detail="Invalid file format: file does not contain a valid PDF header",
        )

    job = session_mgr.start_ingest_job(
        pdf_bytes=content,
        filename=file.filename,
        backend_type=backend_type,
        owner_id=session_id,
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
    session_id: str = Depends(get_session_id),
    session_mgr: SessionManager = Depends(get_session_manager),
) -> IngestJobStatus:
    job = session_mgr.get_job(job_id, owner_id=session_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return job


@router.get("", response_model=list[DocumentSummaryDto])
async def list_documents(
    session_id: str = Depends(get_session_id),
    session_mgr: SessionManager = Depends(get_session_manager),
) -> list[DocumentSummaryDto]:
    return session_mgr.list_documents(owner_id=session_id)


@router.get("/{doc_id}", response_model=DocumentSummaryDto)
async def get_document(
    doc_id: str,
    session_id: str = Depends(get_session_id),
    session_mgr: SessionManager = Depends(get_session_manager),
) -> DocumentSummaryDto:
    doc = session_mgr.get_document(doc_id, owner_id=session_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")
    return doc.to_summary()


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    session_id: str = Depends(get_session_id),
    session_mgr: SessionManager = Depends(get_session_manager),
) -> dict[str, str]:
    success = session_mgr.delete_document(doc_id, owner_id=session_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")
    return {"message": f"Document '{doc_id}' deleted successfully"}


@router.get("/{doc_id}/tables", response_model=list[TableData])
async def get_document_tables(
    doc_id: str,
    session_id: str = Depends(get_session_id),
    session_mgr: SessionManager = Depends(get_session_manager),
) -> list[TableData]:
    doc = session_mgr.get_document(doc_id, owner_id=session_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")
    return doc.ingest_result.tables
