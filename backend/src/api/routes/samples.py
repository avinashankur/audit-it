"""Sample reports routes."""

from fastapi import APIRouter, Depends, HTTPException

from src.api.schemas import IngestJobResponse, SampleReportDto
from src.api.session_mgr import SessionManager, get_session_manager

router = APIRouter(prefix="/samples", tags=["Samples"])


@router.get("", response_model=list[SampleReportDto])
async def list_sample_reports(
    session_mgr: SessionManager = Depends(get_session_manager),
) -> list[SampleReportDto]:
    samples = session_mgr.list_sample_reports()
    return [SampleReportDto(**s) for s in samples]


@router.post("/{filename}/load", response_model=IngestJobResponse)
async def load_sample_report(
    filename: str,
    backend_type: str = "networkx",
    session_mgr: SessionManager = Depends(get_session_manager),
) -> IngestJobResponse:
    sample_dir = session_mgr.get_sample_dir()
    file_path = sample_dir / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"Sample report '{filename}' not found in {sample_dir}",
        )

    pdf_bytes = file_path.read_bytes()
    job = session_mgr.start_ingest_job(
        pdf_bytes=pdf_bytes,
        filename=filename,
        backend_type=backend_type,
    )
    return IngestJobResponse(
        job_id=job.job_id,
        document_id=job.document_id,
        filename=job.filename,
        status=job.status,
        message=f"Started ingestion for sample report '{filename}'",
    )
