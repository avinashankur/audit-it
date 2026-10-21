"""Text chunking module preserving exact page citations for financial audit retrieval."""

import uuid
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.core.env import get_settings
from src.core.exceptions import ChunkingError
from src.core.logging import get_logger, profile_stage
from src.db.models.entities import TextChunk
from src.ingestion.pdf_parser import ParsedPage, detect_section_header

logger = get_logger(__name__)


def estimate_token_count(text: str) -> int:
    if not text:
        return 0
    # Standard heuristic: 1 token ≈ 4 characters or ~0.75 words
    char_est = len(text) / 4.0
    word_est = len(text.split()) * 1.3
    # Average of character and word heuristic for higher accuracy across tables and narrative
    return max(1, round((char_est + word_est) / 2.0))


class Chunker:
    """Recursively splits document text into semantic chunks while strictly preserving page citations."""

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        separators: list[str] | None = None,
    ) -> None:
        settings = get_settings()
        self.chunk_size = chunk_size if chunk_size is not None else settings.DEFAULT_CHUNK_SIZE
        self.chunk_overlap = chunk_overlap if chunk_overlap is not None else settings.DEFAULT_CHUNK_OVERLAP

        if self.chunk_size <= 0:
            raise ChunkingError(
                f"chunk_size must be positive, got {self.chunk_size}",
                details={"chunk_size": self.chunk_size},
            )
        if self.chunk_overlap < 0:
            raise ChunkingError(
                f"chunk_overlap cannot be negative, got {self.chunk_overlap}",
                details={"chunk_overlap": self.chunk_overlap},
            )
        if self.chunk_overlap >= self.chunk_size:
            raise ChunkingError(
                f"chunk_overlap ({self.chunk_overlap}) must be strictly less than chunk_size ({self.chunk_size})",
                details={"chunk_size": self.chunk_size, "chunk_overlap": self.chunk_overlap},
            )

        # Standard splitting hierarchy: Double newline (paragraphs) -> Single newline -> Sentences -> Words
        self.separators = separators or ["\n\n", "\n", ". ", "; ", ", ", " ", ""]
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=self.separators,
            length_function=len,
            is_separator_regex=False,
        )

    def chunk_page(
        self,
        doc_id: str,
        page_number: int,
        text: str,
        section_header: str | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> list[TextChunk]:
        """Split text of a single page into chunks, retaining page_number on all chunks."""
        if page_number < 1:
            raise ChunkingError(
                f"Page number must be >= 1, got {page_number}",
                details={"page_number": page_number},
            )

        stripped = text.strip() if text else ""
        if not stripped:
            return []

        # If text is already smaller than or equal to chunk_size, create a single chunk
        raw_chunks = (
            [stripped]
            if len(stripped) <= self.chunk_size
            else self.splitter.split_text(stripped)
        )

        chunks: list[TextChunk] = []
        current_section = section_header or detect_section_header(stripped)

        for idx, chunk_text in enumerate(raw_chunks):
            chunk_text = chunk_text.strip()
            if not chunk_text:
                continue

            # Check if this sub-chunk starts with a new section heading
            sub_header = detect_section_header(chunk_text)
            if sub_header:
                current_section = sub_header

            token_count = estimate_token_count(chunk_text)

            meta = {
                "page_number": page_number,
                "chunk_index_in_page": idx,
                "total_chunks_in_page": len(raw_chunks),
                "char_length": len(chunk_text),
            }
            if extra_metadata:
                meta.update(extra_metadata)

            chunk = TextChunk(
                chunk_id=str(uuid.uuid4()),
                doc_id=doc_id,
                text=chunk_text,
                page_number=page_number,
                section_header=current_section,
                token_count=token_count,
                metadata=meta,
            )
            chunks.append(chunk)

        return chunks

    @profile_stage("chunk_document")
    def chunk_document(
        self,
        doc_id: str,
        pages: list[tuple[int, str]] | list[ParsedPage],
        extra_metadata: dict[str, Any] | None = None,
    ) -> list[TextChunk]:
        """Chunk an entire document page-by-page while maintaining sequential chunk indices.

        Args:
            doc_id: Associated document identifier.
            pages: List of (page_num, text) tuples or ParsedPage objects.
            extra_metadata: Optional dictionary to merge into chunk metadata.

        Returns:
            list[TextChunk] with verified page citations and token counts.
        """
        all_chunks: list[TextChunk] = []
        global_idx = 0

        for page in pages:
            if isinstance(page, ParsedPage):
                p_num = page.page_number
                p_text = page.text
                p_section = page.section_header
            elif isinstance(page, (tuple, list)) and len(page) >= 2:
                p_num = int(page[0])
                p_text = str(page[1])
                p_section = None
            else:
                raise ChunkingError(
                    f"Unsupported page input element: {type(page).__name__}",
                    details={"element": str(page)},
                )

            page_chunks = self.chunk_page(
                doc_id=doc_id,
                page_number=p_num,
                text=p_text,
                section_header=p_section,
                extra_metadata=extra_metadata,
            )

            for chunk in page_chunks:
                chunk.metadata["global_chunk_index"] = global_idx
                global_idx += 1
                all_chunks.append(chunk)

        logger.info(
            f"Chunked document {doc_id} ({len(pages)} pages) into {len(all_chunks)} chunks "
            f"(chunk_size={self.chunk_size}, overlap={self.chunk_overlap})"
        )
        return all_chunks


def chunk_document(
    doc_id: str,
    pages: list[tuple[int, str]] | list[ParsedPage],
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[TextChunk]:
    """Functional helper for document chunking."""
    chunker = Chunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return chunker.chunk_document(doc_id=doc_id, pages=pages)
