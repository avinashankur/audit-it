from __future__ import annotations

import sys
from pathlib import Path

DEMO_FILENAME = "AuditIt Demo - Northwind Cloud FY2024.pdf"

PAGES: list[list[str]] = [
    [
        "AUDITIT DEMO REPORT",
        "",
        "Northwind Cloud Systems, Inc.",
        "Consolidated Financial Statements",
        "Fiscal Year 2024",
        "",
        "Prepared for product demonstration purposes",
        "All amounts in thousands except per share data",
    ],
    [
        "CONSOLIDATED STATEMENTS OF OPERATIONS",
        "(In thousands, except per share data)",
        "Line Item                        2024",
        "Revenue                       $18,420",
        "Cost of Sales                  $6,840",
        "Gross Margin                  $11,580",
        "Research and Development       $2,150",
        "SG&A                           $3,420",
        "Operating Expenses             $5,570",
        "Operating Income               $6,010",
        "Interest Expense                 $420",
        "Tax Expense                      $1,230",
        "Net Income                     $4,360",
    ],
    [
        "CONSOLIDATED BALANCE SHEETS - SELECTED DATA",
        "(In thousands)",
        "Line Item                        2024",
        "Current Assets                $12,400",
        "Current Liabilities            $5,200",
        "Working Capital                $7,200",
        "Total Debt                     $3,000",
        "Debt to Equity                   0.52",
    ],
    [
        "CONSOLIDATED CASH FLOW HIGHLIGHTS",
        "(In thousands)",
        "Line Item                        2024",
        "Net Cash from Operations       $5,560",
        "Net Change in Cash             $4,460",
    ],
    [
        "MANAGEMENT'S DISCUSSION AND ANALYSIS",
        "Fiscal Year 2024 Compared to Fiscal Year 2023",
        "",
        "Revenue was $18.4 million in 2024, an increase of 23.6% from $14.9 million in 2023.",
        "Revenue was driven by enterprise customer growth.",
        "Gross Margin was driven by Revenue.",
        "Gross Margin was offset by Cost of Sales.",
        "Operating Income was driven by Gross Margin.",
        "Operating Income was offset by Operating Expenses.",
        "Operating Income was offset by Research and Development.",
        "Net Income was driven by Operating Income.",
        "Net Income was offset by Interest Expense.",
        "Net Income was offset by Tax Expense.",
        "Working Capital was driven by Current Assets.",
        "Working Capital was offset by Current Liabilities.",
        "Debt to Equity was driven by Total Debt.",
        "Net Cash from Operations was driven by Operating Income.",
        "Net Change in Cash was driven by Net Cash from Operations.",
    ],
    [
        "NOTE 1 - REVENUE RECOGNITION",
        "",
        "Revenue is recognized when control of the subscription service is transferred to the customer.",
        "The Company's subscription arrangements are generally billed annually in advance.",
        "Revenue growth was supported by enterprise customer additions and expansion within existing accounts.",
    ],
    [
        "NOTE 2 - LIQUIDITY AND CAPITAL RESOURCES",
        "",
        "Liquidity discussion for fiscal 2024 follows.",
        "Working Capital was driven by Current Assets.",
        "Working Capital was offset by Current Liabilities.",
        "The Company believes its cash and cash equivalents are sufficient to fund operations for the next twelve months.",
        "Debt to Equity was driven by Total Debt.",
    ],
]


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _content(lines: list[str], font_size: int = 10) -> bytes:
    out = ["BT", f"/F1 {font_size} Tf", "72 740 Td"]
    for index, line in enumerate(lines):
        if index:
            out.append("0 -13 Td")
        out.append(f"({_escape(line)}) Tj")
    out.append("ET")
    return ("\n".join(out) + "\n").encode("latin-1")


def build_pdf(pages: list[list[str]]) -> bytes:
    objects: list[bytes] = [b"", b"", b""]
    catalog_id, pages_id, font_id = 1, 2, 3

    def add_object(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    page_ids: list[int] = []
    for lines in pages:
        content = _content(lines)
        content_id = add_object(
            b"<< /Length "
            + str(len(content)).encode()
            + b" >>\nstream\n"
            + content
            + b"endstream"
        )
        page_id = add_object(
            (
                f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 612 792] "
                f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>"
            ).encode()
        )
        page_ids.append(page_id)

    objects[font_id - 1] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>"
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[pages_id - 1] = (
        f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode()
    )
    objects[catalog_id - 1] = (
        f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode()
    )

    buffer = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(buffer))
        buffer.extend(f"{index} 0 obj\n".encode())
        buffer.extend(body)
        buffer.extend(b"\nendobj\n")

    xref_offset = len(buffer)
    buffer.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    buffer.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        buffer.extend(f"{offset:010d} 00000 n \n".encode())
    buffer.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode()
    )
    return bytes(buffer)


def main() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    output = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else backend_dir / "data" / "sample_reports" / DEMO_FILENAME
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(build_pdf(PAGES))
    print(output)


if __name__ == "__main__":
    main()
