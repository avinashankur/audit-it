
import re
import uuid

from src.core.logging import get_logger, profile_stage
from src.core.models import TableData
from src.ingestion.pdf_parser import ParsedPage

logger = get_logger(__name__)

# Numeric / currency token pattern common in financial statements (e.g., $ 1,234, (567), 12.5%, 2024, -)
NUMERIC_CELL_PATTERN = re.compile(
    r"^[\$€£]?\s*\(?-?\d+(?:,\d{3})*(?:\.\d+)?\)?%?$|^[-—–]$|^\$$"
)

# Pattern identifying period or year headers (e.g., 2024, FY24, Q3)
YEAR_HEADER_PATTERN = re.compile(r"\b(?:20\d\d|19\d\d|Q[1-4]|FY\d\d)\b", re.IGNORECASE)

# Common statement title patterns
TITLE_PATTERNS = [
    re.compile(
        r"^(CONSOLIDATED\s+STATEMENTS?\s+OF\s+[^\n]+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(CONSOLIDATED\s+BALANCE\s+SHEETS?)",
        re.IGNORECASE,
    ),
    re.compile(
        r"^((?:SCHEDULE|STATEMENT|SUMMARY)\s+OF\s+[^\n]+)",
        re.IGNORECASE,
    ),
]


def is_financial_number(cell: str) -> bool:
    clean = cell.strip()
    return bool(NUMERIC_CELL_PATTERN.match(clean))


def format_markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    clean_headers = [h.replace("|", "\\|").strip() or "-" for h in headers]
    num_cols = len(clean_headers)

    header_line = "| " + " | ".join(clean_headers) + " |"
    separator_line = "| " + " | ".join([":---" if i == 0 else "---:" for i in range(num_cols)]) + " |"

    row_lines: list[str] = []
    for row in rows:
        clean_row = [str(c).replace("|", "\\|").strip() for c in row]
        if len(clean_row) < num_cols:
            clean_row.extend([""] * (num_cols - len(clean_row)))
        else:
            clean_row = clean_row[:num_cols]
        row_lines.append("| " + " | ".join(clean_row) + " |")

    return "\n".join([header_line, separator_line] + row_lines)


class TableExtractor:
    # isolate financial statements from other statements

    def __init__(self, min_rows: int = 2, min_cols: int = 2) -> None:
        self.min_rows = min_rows
        self.min_cols = min_cols

    def _split_line_columns(self, line: str) -> list[str]:
        stripped = line.strip()
        if not stripped:
            return []

        if "|" in line and line.count("|") >= 2:
            parts = [p.strip() for p in line.split("|")]
            if parts and not parts[0]:
                parts.pop(0)
            if parts and not parts[-1]:
                parts.pop()
            return parts

        # Split on 2+ spaces, tabs, or space followed by currency symbol after a number/paren
        parts = re.split(r"\s{2,}|\t|(?<=[0-9\)])\s+(?=[\$€£])", stripped)
        return [p.strip() for p in parts if p.strip()]

    def _detect_preceding_title(self, lines: list[str], start_idx: int) -> str | None:
        for back_idx in range(max(0, start_idx - 4), start_idx):
            candidate = lines[back_idx].strip()
            if not candidate:
                continue
            for pattern in TITLE_PATTERNS:
                m = pattern.search(candidate)
                if m:
                    return m.group(1).strip()
            # If line is 80 words or short and uppercase or title-case without numbers, treat as title
            if 3 < len(candidate) < 80 and not any(is_financial_number(tok) for tok in candidate.split()):
                if candidate.isupper() or candidate.istitle():
                    return candidate
        return None

    def _has_future_table_rows(self, lines: list[str], current_idx: int, lookahead: int = 3) -> bool:
        for offset in range(1, lookahead + 1):
            check_idx = current_idx + offset
            if check_idx >= len(lines):
                break
            cols = self._split_line_columns(lines[check_idx])
            if len(cols) >= self.min_cols and any(is_financial_number(c) for c in cols[1:]):
                return True
        return False

    def extract_tables_from_text(
        self,
        text: str,
        doc_id: str,
        page_number: int,
    ) -> list[TableData]:
        
        if not text:
            return []

        lines = text.split("\n")
        table_blocks: list[list[tuple[int, list[str]]]] = []
        current_block: list[tuple[int, list[str]]] = []

        for line_idx, line in enumerate(lines):
            cols = self._split_line_columns(line)
            is_num_row = len(cols) >= self.min_cols and any(is_financial_number(c) for c in cols[1:])
            is_period_header = len(cols) >= self.min_cols and any(
                YEAR_HEADER_PATTERN.search(c) for c in cols[1:]
            )

            if is_num_row or is_period_header:
                current_block.append((line_idx, cols))
            elif current_block and self._has_future_table_rows(lines, line_idx):
                if cols and len(cols) == 1:
                    current_block.append((line_idx, cols))
            else:
                if len(current_block) >= self.min_rows:
                    table_blocks.append(current_block)
                current_block = []

        if len(current_block) >= self.min_rows:
            table_blocks.append(current_block)

        extracted_tables: list[TableData] = []

        for block in table_blocks:
            start_line_idx = block[0][0]
            block_rows = [cols for _, cols in block]

            title = self._detect_preceding_title(lines, start_line_idx)

            max_cols = max(len(r) for r in block_rows)
            if max_cols < self.min_cols:
                continue

            first_row = block_rows[0]
            has_explicit_headers = False
            headers: list[str] = []

            if any(YEAR_HEADER_PATTERN.search(c) for c in first_row[1:]):
                headers = first_row
                block_rows = block_rows[1:]
                has_explicit_headers = True

            if not has_explicit_headers and start_line_idx > 0:
                prev_line = lines[start_line_idx - 1]
                prev_cols = self._split_line_columns(prev_line)
                if len(prev_cols) >= 2 and any(
                    YEAR_HEADER_PATTERN.search(c)
                    or re.search(r"\b(?:December|September|March|June|Year|Period)\b", c, re.IGNORECASE)
                    for c in prev_cols
                ):
                    headers = prev_cols
                    if len(headers) < max_cols:
                        headers = ["Line Item"] + headers
                    has_explicit_headers = True

            if not has_explicit_headers:
                headers = ["Line Item"] + [f"Period {i}" for i in range(1, max_cols)]

            if len(headers) < max_cols:
                headers.extend([f"Col {i+1}" for i in range(len(headers), max_cols)])
            headers = headers[:max_cols]
            if not headers:
                headers = ["Item"]

            normalized_rows: list[list[str]] = []
            for r in block_rows:
                if not r:
                    continue
                row_copy = list(r)
                if len(row_copy) < max_cols:
                    row_copy.extend([""] * (max_cols - len(row_copy)))
                normalized_rows.append(row_copy[:max_cols])

            if not normalized_rows:
                continue

            markdown = format_markdown_table(headers, normalized_rows)

            try:
                table = TableData(
                    table_id=str(uuid.uuid4()),
                    doc_id=doc_id,
                    page_number=page_number,
                    title=title,
                    headers=headers,
                    rows=normalized_rows,
                    markdown=markdown,
                )
                extracted_tables.append(table)
            except Exception as err:
                logger.warning(f"Error creating TableData model on page {page_number}: {err}")

        return extracted_tables

    @profile_stage("table_extraction")
    def extract_tables_from_pages(
        self,
        doc_id: str,
        pages: list[tuple[int, str]] | list[ParsedPage],
    ) -> list[TableData]:
        all_tables: list[TableData] = []

        for page in pages:
            if isinstance(page, ParsedPage):
                p_num = page.page_number
                p_text = page.text
            elif isinstance(page, (tuple, list)) and len(page) >= 2:
                p_num = int(page[0])
                p_text = str(page[1])
            else:
                continue

            page_tables = self.extract_tables_from_text(p_text, doc_id=doc_id, page_number=p_num)
            all_tables.extend(page_tables)

        logger.info(f"Extracted {len(all_tables)} financial table(s) from document {doc_id}")
        return all_tables


def extract_tables_from_pages(
    doc_id: str,
    pages: list[tuple[int, str]] | list[ParsedPage],
) -> list[TableData]:
    extractor = TableExtractor()
    return extractor.extract_tables_from_pages(doc_id=doc_id, pages=pages)
