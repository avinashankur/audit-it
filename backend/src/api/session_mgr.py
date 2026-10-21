"""Server-side session and document manager for AuditIt."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
import uuid

from fastapi import HTTPException

from src.api.schemas import DocumentSummaryDto, IngestJobStatus
from src.core.env import get_settings
from src.core.logging import get_logger
from src.db.graph import GraphStore
from src.ingestion import IngestionPipeline, IngestionResult
from src.reasoning.qa_service import QAService
from src.retrieval.hybrid_retriever import HybridRetriever
from src.retrieval.vector_store import VectorStore

logger = get_logger(__name__)


@dataclass
class DocumentContext:
    document_id: str
    filename: str
    size_kb: float
    ingest_result: IngestionResult
    graph_store: GraphStore
    vector_store: VectorStore
    retriever: HybridRetriever
    qa_service: QAService
    stats: dict[str, Any]
    uploaded_at: str
    status: str = "Ready"
    owner_id: str = "default"

    def to_summary(self) -> DocumentSummaryDto:
        return DocumentSummaryDto(
            document_id=self.document_id,
            filename=self.filename,
            size_kb=self.size_kb,
            total_pages=self.ingest_result.metadata.total_pages,
            chunks_count=len(self.ingest_result.chunks),
            tables_count=len(self.ingest_result.tables),
            metric_nodes_count=self.stats.get("metric_nodes", 0),
            disclosure_nodes_count=self.stats.get("disclosure_nodes", 0),
            causal_edges_count=self.stats.get("causal_edges", 0),
            uploaded_at=self.uploaded_at,
            status=self.status,
            owner_id=self.owner_id,
        )


class SessionManager:
    """Manages active document contexts, graph indices, and asynchronous ingestion jobs."""

    def __init__(self, max_active_jobs: int | None = None) -> None:
        self.documents: dict[str, DocumentContext] = {}
        self.jobs: dict[str, IngestJobStatus] = {}
        settings = get_settings()
        self.max_active_jobs: int = (
            max_active_jobs if max_active_jobs is not None else settings.MAX_ACTIVE_INGEST_JOBS
        )
        self._executor = ThreadPoolExecutor(max_workers=4)

    def get_active_job_count(self) -> int:
        """Count jobs currently in PROCESSING status."""
        return sum(1 for j in self.jobs.values() if j.status == "PROCESSING")

    def can_accept_job(self) -> bool:
        """Check if session manager has capacity for another concurrent ingestion job."""
        return self.get_active_job_count() < self.max_active_jobs

    def _prune_old_jobs(self, max_retained: int = 100) -> None:
        """Prune oldest completed or failed jobs if total job history exceeds max_retained."""
        finished_jobs = [
            (jid, j) for jid, j in self.jobs.items() if j.status in ("COMPLETED", "FAILED")
        ]
        if len(finished_jobs) > max_retained:
            to_remove = len(finished_jobs) - max_retained
            for jid, _ in finished_jobs[:to_remove]:
                self.jobs.pop(jid, None)

    def get_sample_dir(self) -> Path:
        """Find sample reports directory regardless of execution working directory."""
        candidates = [
            Path("data/sample_reports"),
            Path("backend/data/sample_reports"),
            Path(__file__).resolve().parent.parent.parent / "data" / "sample_reports",
        ]
        for p in candidates:
            if p.exists() and p.is_dir():
                return p
        return Path("data/sample_reports")

    def list_sample_reports(self) -> list[dict[str, Any]]:
        sample_dir = self.get_sample_dir()
        if not sample_dir.exists():
            return []
        samples = []
        for f in sorted(sample_dir.glob("*.pdf")):
            samples.append(
                {
                    "name": f.name,
                    "size_kb": round(f.stat().st_size / 1024, 1),
                }
            )
        return samples

    def get_job(self, job_id: str, owner_id: str | None = None) -> IngestJobStatus | None:
        job = self.jobs.get(job_id)
        if not job:
            return None
        if owner_id is not None and job.owner_id and job.owner_id != owner_id:
            return None
        return job

    def get_document(self, doc_id: str, owner_id: str | None = None) -> DocumentContext | None:
        doc = self.documents.get(doc_id)
        if not doc:
            return None
        if owner_id is not None and doc.owner_id != owner_id:
            return None
        return doc

    def list_documents(self, owner_id: str | None = None) -> list[DocumentSummaryDto]:
        if owner_id is not None:
            return [doc.to_summary() for doc in self.documents.values() if doc.owner_id == owner_id]
        return [doc.to_summary() for doc in self.documents.values()]

    def delete_document(self, doc_id: str, owner_id: str | None = None) -> bool:
        doc = self.documents.get(doc_id)
        if not doc:
            return False
        if owner_id is not None and doc.owner_id != owner_id:
            return False
        del self.documents[doc_id]
        return True

    def start_ingest_job(
        self,
        pdf_bytes: bytes,
        filename: str,
        backend_type: str = "networkx",
        owner_id: str = "default",
    ) -> IngestJobStatus:
        if not self.can_accept_job():
            raise HTTPException(
                status_code=429,
                detail=f"Server is at capacity: maximum concurrent ingestion jobs ({self.max_active_jobs}) reached. Please retry later.",
            )

        job_id = str(uuid.uuid4())
        doc_id = str(uuid.uuid4())
        job = IngestJobStatus(
            job_id=job_id,
            document_id=doc_id,
            filename=filename,
            status="PROCESSING",
            stage="parsing",
            progress=10,
            owner_id=owner_id,
        )
        self.jobs[job_id] = job

        self._executor.submit(
            self._process_document_task,
            job_id=job_id,
            doc_id=doc_id,
            pdf_bytes=pdf_bytes,
            filename=filename,
            backend_type=backend_type,
            owner_id=owner_id,
        )
        return job

    def _process_document_task(
        self,
        job_id: str,
        doc_id: str,
        pdf_bytes: bytes,
        filename: str,
        backend_type: str = "networkx",
        owner_id: str = "default",
    ) -> None:
        job = self.jobs[job_id]
        try:
            # 1. Parsing & Chunking & Tables
            job.stage = "parsing"
            job.progress = 25
            pipeline = IngestionPipeline()
            ingest_result = pipeline.process(
                pdf_bytes,
                filename=filename,
                save_to_disk=False,
            )
            ingest_result.metadata.doc_id = doc_id
            for chunk in ingest_result.chunks:
                chunk.doc_id = doc_id
            for table in ingest_result.tables:
                table.doc_id = doc_id

            # 2. Graph Construction
            job.stage = "graph"
            job.progress = 60
            backend_norm = "neo4j" if "neo4j" in backend_type.lower() else "networkx"
            settings = get_settings()
            neo4j_password = (
                settings.NEO4J_PASSWORD.get_secret_value() if settings.NEO4J_PASSWORD else None
            )
            graph_store = GraphStore.create(
                backend_type=backend_norm,
                neo4j_uri=settings.NEO4J_URI,
                neo4j_user=settings.NEO4J_USER,
                neo4j_password=neo4j_password,
            )
            graph_store.populate_from_ingestion(ingest_result)
            stats = graph_store.get_stats()

            # 3. Vector Indexing
            job.stage = "indexing"
            job.progress = 85
            vec_store = VectorStore()
            vec_store.add_chunks(ingest_result.chunks)

            # 4. Hybrid Retriever & QA
            retriever = HybridRetriever(vector_store=vec_store, graph_store=graph_store)
            qa_service = QAService(retriever=retriever)

            file_size_kb = round(len(pdf_bytes) / 1024, 1)
            doc_context = DocumentContext(
                document_id=doc_id,
                filename=filename,
                size_kb=file_size_kb,
                ingest_result=ingest_result,
                graph_store=graph_store,
                vector_store=vec_store,
                retriever=retriever,
                qa_service=qa_service,
                stats=stats,
                uploaded_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
                status="Ready",
                owner_id=owner_id,
            )
            self.documents[doc_id] = doc_context

            job.stage = "ready"
            job.progress = 100
            job.status = "COMPLETED"
            job.stats = stats
            self._prune_old_jobs()
            logger.info(f"Successfully processed document '{filename}' (ID: {doc_id})")

        except Exception as exc:
            logger.error(f"Failed processing document '{filename}': {exc}", exc_info=True)
            job.status = "FAILED"
            job.error = str(exc)
            job.stage = "failed"
            self._prune_old_jobs()


_session_manager = SessionManager()


def get_session_manager() -> SessionManager:
    return _session_manager
