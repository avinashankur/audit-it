"""PDF parsing module for per-page text extraction and financial section detection."""

import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from src.core.exceptions import PDFParseError
from src.core.logging import get_logger, profile_stage

logger = get_logger(__name__)

SECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"^(?:PART\s+[I|V|X]+[\.\s\-]*)?(?:ITEM\s+\d+[A-Z]?[\.\s\-]+[^\n]{3,120})",
        re.IGNORECASE | re.MULTILINE,
    ),
    re.compile(
        r"^(?:CONSOLIDATED\s+STATEMENTS?\s+OF\s+(?:OPERATIONS|INCOME|COMPREHENSIVE\s+INCOME|CASH\s+FLOWS|FINANCIAL\s+POSITION|SHAREHOLDERS['’]?\s+EQUITY))",
        re.IGNORECASE | re.MULTILINE,
    ),
    re.compile(
        r"^(?:CONSOLIDATED\s+BALANCE\s+SHEETS?)",
        re.IGNORECASE | re.MULTILINE,
    ),
    re.compile(
        r"^(?:NOTE\s+\d+[\.\s\-:]+[^\n]{3,120})",
        re.IGNORECASE | re.MULTILINE,
    ),
    re.compile(
        r"^(?:MANAGEMENT['’]?S\s+DISCUSSION\s+AND\s+ANALYSIS[^\n]{0,100})",
        re.IGNORECASE | re.MULTILINE,
    ),
]


@dataclass
class ParsedPage:

    page_number: int  # 1-indexed
    text: str
    char_count: int
    section_header: str | None = None


def normalize_pdf_text(text: str) -> str:
    if not text:
        return ""

    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # normalize line breaks
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")

    # normalize unicode spaces and dashes
    cleaned = cleaned.replace("\xa0", " ").replace("\u2013", "-").replace("\u2014", "--")
    cleaned = cleaned.replace("\u2018", "'").replace("\u2019", "'")
    cleaned = cleaned.replace("\u201c", '"').replace("\u201d", '"')

    lines = [re.sub(r"[ \t]+$", "", line) for line in cleaned.split("\n")]

    normalized = "\n".join(lines)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)

    return normalized.strip()


def detect_section_header(page_text: str) -> str | None:
    if not page_text:
        return None

    sample = page_text[:1000]
    for pattern in SECTION_PATTERNS:
        match = pattern.search(sample)
        if match:
            header = match.group(0).strip()
            header = re.sub(r"\s+", " ", header)
            return header

    return None


class PDFParser:

    def __init__(self, normalize: bool = True) -> None:
        self.normalize = normalize

    def _open_reader(self, source: str | Path | bytes | BinaryIO) -> PdfReader:
        # open a pdf reader
        try:
            if isinstance(source, (str, Path)):
                path = Path(source)
                if not path.exists():
                    raise PDFParseError(f"File not found: '{path}'", details={"path": str(path)})
                reader = PdfReader(str(path))
            elif isinstance(source, bytes):
                reader = PdfReader(io.BytesIO(source))
            elif hasattr(source, "read"):
                if hasattr(source, "seek"):
                    source.seek(0)
                reader = PdfReader(source)
            else:
                raise PDFParseError(
                    f"Unsupported PDF source type: {type(source).__name__}",
                    details={"type": str(type(source))},
                )

            if reader.is_encrypted:
                try:
                    # try emtpy string as the password
                    decrypt_status = reader.decrypt("")
                    if decrypt_status == 0:  # Failed to decrypt
                        raise PDFParseError("PDF is password protected and cannot be decrypted.")
                except Exception as dec_err:
                    raise PDFParseError(
                        f"PDF is password protected and could not be decrypted: {dec_err}"
                    ) from dec_err

            if len(reader.pages) == 0:
                raise PDFParseError("PDF document contains no pages.")

            return reader

        except PDFParseError:
            raise
        except PdfReadError as err:
            raise PDFParseError(f"Corrupt or unreadable PDF: {err}", details={"error": str(err)}) from err
        except Exception as exc:
            raise PDFParseError(f"Unexpected error opening PDF: {exc}", details={"error": str(exc)}) from exc

    @profile_stage("pdf_parse")
    def parse(self, source: str | Path | bytes | BinaryIO) -> list[ParsedPage]:
        reader = self._open_reader(source)
        total_pages = len(reader.pages)
        parsed_pages: list[ParsedPage] = []
        current_section: str | None = None

        logger.info(f"Parsing PDF document with {total_pages} page(s)...")

        for idx, page in enumerate(reader.pages):
            page_num = idx + 1
            try:
                raw_text = page.extract_text() or ""
            except Exception as page_err:
                logger.warning(f"Error extracting text from page {page_num}: {page_err}")
                raw_text = ""

            text = normalize_pdf_text(raw_text) if self.normalize else raw_text

            found_section = detect_section_header(text)
            if found_section:
                current_section = found_section

            parsed_page = ParsedPage(
                page_number=page_num,
                text=text,
                char_count=len(text),
                section_header=current_section,
            )
            parsed_pages.append(parsed_page)

        logger.info(
            f"Parsed {len(parsed_pages)} pages. "
            f"Total characters: {sum(p.char_count for p in parsed_pages)}"
        )
        return parsed_pages

    def parse_pdf_pages(self, source: str | Path | bytes | BinaryIO) -> list[tuple[int, str]]:
        # convenience method for pdf details such as page number etc
        parsed = self.parse(source)
        return [(p.page_number, p.text) for p in parsed]


def parse_pdf_pages(file_path: str | Path | bytes | BinaryIO) -> list[tuple[int, str]]:
    parser = PDFParser()
    return parser.parse_pdf_pages(file_path)
