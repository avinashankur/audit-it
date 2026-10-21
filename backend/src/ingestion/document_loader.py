import hashlib
import io
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from pypdf import PdfReader

from src.core.exceptions import DocumentLoadError
from src.core.logging import get_logger, profile_stage
from src.db.models.entities import DocumentMetadata, DocumentStatus

logger = get_logger(__name__)

PDF_MAGIC_BYTES = b"%PDF-"
DEFAULT_CACHE_DIR = Path("data/cache")


@dataclass
class LoadedDocument:
    doc_id: str
    filename: str
    file_hash: str
    file_size_bytes: int
    content_bytes: bytes
    total_pages: int
    file_path: Path | None = None

    def to_metadata(self) -> DocumentMetadata:
        return DocumentMetadata(
            doc_id=self.doc_id,
            filename=self.filename,
            file_hash=self.file_hash,
            total_pages=max(1, self.total_pages),
            file_size_bytes=self.file_size_bytes,
            status=DocumentStatus.PENDING,
        )


class DocumentLoader:
    def __init__(self, cache_dir: str | Path | None = None) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR

    @staticmethod
    def compute_sha256(content: bytes) -> str:
        """computes sha for binary content"""
        hasher = hashlib.sha256()
        hasher.update(content)
        return hasher.hexdigest()

    def validate_pdf_bytes(self, content: bytes, filename: str) -> None:
        # ensure non empty content
        if not content or len(content) == 0:
            raise DocumentLoadError(
                f"Document '{filename}' is empty (0 bytes).",
                details={"filename": filename, "file_size": 0},
            )

        # Check for PDF header in the first 1024 bytes (some PDFs have leading BOM/whitespace)
        header_sample = content[:1024]
        if PDF_MAGIC_BYTES not in header_sample:
            raise DocumentLoadError(
                f"Document '{filename}' is not a valid PDF file (missing %PDF- header).",
                details={
                    "filename": filename,
                    "sample_bytes": header_sample[:20].decode(
                        "latin1", errors="replace"
                    ),
                },
            )

    def _inspect_pdf_pages(self, content: bytes, filename: str) -> int:
        """inspect page count using pypdf to fill metadata."""
        try:
            reader = PdfReader(io.BytesIO(content))
            return len(reader.pages)
        except Exception as exc:
            logger.warning(
                f"Could not read page count for '{filename}' during loading: {exc}"
            )
            return 1

    @profile_stage("document_load")
    def load(
        self,
        source: str | Path | bytes | BinaryIO,
        filename: str | None = None,
        save_to_disk: bool = False,
    ) -> LoadedDocument:
        resolved_filename = filename
        resolved_path: Path | None = None
        content_bytes: bytes

        if isinstance(source, (str, Path)):
            resolved_path = Path(source)
            if not resolved_path.exists():
                raise DocumentLoadError(
                    f"File not found: '{resolved_path}'",
                    details={"path": str(resolved_path)},
                )
            if not resolved_path.is_file():
                raise DocumentLoadError(
                    f"Specified path is not a file: '{resolved_path}'",
                    details={"path": str(resolved_path)},
                )
            resolved_filename = resolved_filename or resolved_path.name
            try:
                content_bytes = resolved_path.read_bytes()
            except OSError as exc:
                raise DocumentLoadError(
                    f"Failed to read file '{resolved_path}': {exc}",
                    details={"path": str(resolved_path), "error": str(exc)},
                ) from exc

        elif isinstance(source, bytes):
            content_bytes = source
            resolved_filename = resolved_filename or "document.pdf"

        elif hasattr(source, "read"):
            try:
                if hasattr(source, "seek"):
                    source.seek(0)
                content_bytes = source.read()

                if not isinstance(content_bytes, bytes):
                    raise DocumentLoadError("Stream must return bytes, not str.")
            except Exception as exc:
                raise DocumentLoadError(
                    f"Failed to read binary stream: {exc}",
                    details={"error": str(exc)},
                ) from exc
            resolved_filename = resolved_filename or getattr(
                source, "name", "document.pdf"
            )

        else:
            raise DocumentLoadError(
                f"Unsupported source type: {type(source).__name__}",
                details={"type": str(type(source))},
            )

        # Validate content
        self.validate_pdf_bytes(content_bytes, resolved_filename)

        file_hash = self.compute_sha256(content_bytes)
        file_size = len(content_bytes)
        doc_id = str(uuid.uuid4())
        total_pages = self._inspect_pdf_pages(content_bytes, resolved_filename)

        if save_to_disk:
            cached_path = self.cache_document(
                content_bytes, resolved_filename, file_hash
            )
            resolved_path = cached_path

        logger.info(
            f"Successfully loaded document '{resolved_filename}' (doc_id={doc_id}, "
            f"size={file_size} bytes, pages={total_pages}, hash={file_hash[:8]}...)"
        )

        return LoadedDocument(
            doc_id=doc_id,
            filename=resolved_filename,
            file_hash=file_hash,
            file_size_bytes=file_size,
            content_bytes=content_bytes,
            total_pages=total_pages,
            file_path=resolved_path,
        )

    def cache_document(
        self, content: bytes, filename: str, file_hash: str | None = None
    ) -> Path:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        h = file_hash or self.compute_sha256(content)
        safe_name = Path(filename).name
        target_path = self.cache_dir / f"{h[:16]}_{safe_name}"

        if not target_path.exists():
            target_path.write_bytes(content)
            logger.debug(f"Cached document to {target_path}")

        return target_path

    def get_cached_document(self, file_hash: str) -> Path | None:
        if not self.cache_dir.exists():
            return None
        matches = list(self.cache_dir.glob(f"{file_hash[:16]}_*"))
        return matches[0] if matches else None
