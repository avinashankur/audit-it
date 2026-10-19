
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from src.core.logging import get_logger, profile_stage
from src.core.models import DocumentMetadata, DocumentStatus, TableData, TextChunk
from src.ingestion.chunker import Chunker, chunk_document, estimate_token_count
from src.ingestion.document_loader import DocumentLoader, LoadedDocument
from src.ingestion.pdf_parser import (
    ParsedPage,
    PDFParser,
    detect_section_header,
    normalize_pdf_text,
    parse_pdf_pages,
)
from src.ingestion.table_extractor import (
    TableExtractor,
    extract_tables_from_pages,
    format_markdown_table,
)

logger = get_logger(__name__)


@dataclass
class IngestionResult:
    metadata: DocumentMetadata
    pages: list[ParsedPage]
    chunks: list[TextChunk]
    tables: list[TableData]


class IngestionPipeline:
    def __init__(
        self,
        loader: DocumentLoader | None = None,
        parser: PDFParser | None = None,
        chunker: Chunker | None = None,
        table_extractor: TableExtractor | None = None,
    ) -> None:
        self.loader = loader or DocumentLoader()
        self.parser = parser or PDFParser()
        self.chunker = chunker or Chunker()
        self.table_extractor = table_extractor or TableExtractor()

    @profile_stage("ingestion_pipeline")
    def process(
        self,
        source: str | Path | bytes | BinaryIO,
        filename: str | None = None,
        save_to_disk: bool = False,
    ) -> IngestionResult:
        # load and validate
        loaded = self.loader.load(source, filename=filename, save_to_disk=save_to_disk)
        metadata = loaded.to_metadata()
        metadata.status = DocumentStatus.PARSING

        # parse pdf
        pages = self.parser.parse(loaded.content_bytes)
        metadata.total_pages = max(1, len(pages))

        # extract tables
        tables = self.table_extractor.extract_tables_from_pages(
            doc_id=loaded.doc_id,
            pages=pages,
        )

        # chunk text by making sure we preserve the page
        chunks = self.chunker.chunk_document(
            doc_id=loaded.doc_id,
            pages=pages,
            extra_metadata={"filename": loaded.filename, "file_hash": loaded.file_hash},
        )

        metadata.status = DocumentStatus.INDEXED

        logger.info(
            f"Ingestion complete for '{loaded.filename}': "
            f"{len(pages)} pages, {len(chunks)} chunks, {len(tables)} tables."
        )

        return IngestionResult(
            metadata=metadata,
            pages=pages,
            chunks=chunks,
            tables=tables,
        )


def ingest_document(
    source: str | Path | bytes | BinaryIO,
    filename: str | None = None,
    save_to_disk: bool = False,
) -> IngestionResult:
    pipeline = IngestionPipeline()
    return pipeline.process(source, filename=filename, save_to_disk=save_to_disk)


__all__ = [
    "Chunker",
    "DocumentLoader",
    "IngestionPipeline",
    "IngestionResult",
    "LoadedDocument",
    "PDFParser",
    "ParsedPage",
    "TableExtractor",
    "chunk_document",
    "detect_section_header",
    "estimate_token_count",
    "extract_tables_from_pages",
    "format_markdown_table",
    "ingest_document",
    "normalize_pdf_text",
    "parse_pdf_pages",
]
