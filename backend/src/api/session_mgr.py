"""Server-side session and document manager for AuditIt."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
import uuid

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
        )


class SessionManager:
    """Manages active document contexts, graph indices, and asynchronous ingestion jobs."""

    def __init__(self) -> None:
        self.documents: dict[str, DocumentContext] = {}
        self.jobs: dict[str, IngestJobStatus] = {}
        self._executor = ThreadPoolExecutor(max_workers=4)

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

    def get_job(self, job_id: str) -> IngestJobStatus | None:
        return self.jobs.get(job_id)

    def get_document(self, doc_id: str) -> DocumentContext | None:
        return self.documents.get(doc_id)

    def list_documents(self) -> list[DocumentSummaryDto]:
        return [doc.to_summary() for doc in self.documents.values()]

    def delete_document(self, doc_id: str) -> bool:
        if doc_id in self.documents:
            del self.documents[doc_id]
            return True
        return False

    def start_ingest_job(
        self,
        pdf_bytes: bytes,
        filename: str,
        backend_type: str = "networkx",
    ) -> IngestJobStatus:
        job_id = str(uuid.uuid4())
        doc_id = str(uuid.uuid4())
        job = IngestJobStatus(
            job_id=job_id,
            document_id=doc_id,
            filename=filename,
            status="PROCESSING",
            stage="parsing",
            progress=10,
        )
        self.jobs[job_id] = job

        self._executor.submit(
            self._process_document_task,
            job_id=job_id,
            doc_id=doc_id,
            pdf_bytes=pdf_bytes,
            filename=filename,
            backend_type=backend_type,
        )
        return job

    def _process_document_task(
        self,
        job_id: str,
        doc_id: str,
        pdf_bytes: bytes,
        filename: str,
        backend_type: str = "networkx",
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
            )
            self.documents[doc_id] = doc_context

            job.stage = "ready"
            job.progress = 100
            job.status = "COMPLETED"
            job.stats = stats
            logger.info(f"Successfully processed document '{filename}' (ID: {doc_id})")

        except Exception as exc:
            logger.error(f"Failed processing document '{filename}': {exc}", exc_info=True)
            job.status = "FAILED"
            job.error = str(exc)
            job.stage = "failed"


_session_manager = SessionManager()


def get_session_manager() -> SessionManager:
    return _session_manager
