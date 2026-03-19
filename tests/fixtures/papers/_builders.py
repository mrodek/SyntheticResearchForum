"""Factory functions for creating minimal PDF test fixtures."""

from __future__ import annotations

from pathlib import Path


def make_valid_paper_pdf(path: Path) -> None:
    """Create a minimal valid PDF with an Abstract section and body text."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.set_y(20)
    pdf.cell(0, 10, "A Test Paper on Multi-Agent Systems", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(4)
    pdf.cell(0, 10, "Abstract", new_x="LMARGIN", new_y="NEXT")
    pdf.multi_cell(
        0,
        8,
        "This paper examines the dynamics of multi-agent systems under adversarial pressure.",
    )
    pdf.ln(4)
    pdf.cell(0, 10, "1. Introduction", new_x="LMARGIN", new_y="NEXT")
    pdf.multi_cell(
        0,
        8,
        "Multi-agent systems have been studied extensively in recent years.",
    )
    pdf.output(str(path))


def make_image_only_pdf(path: Path) -> None:
    """Create a PDF with no embedded text (simulates a scanned/image-only document)."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    # No text content — page is blank, no extractable characters
    pdf.output(str(path))


def make_corrupt_pdf(path: Path) -> None:
    """Write a file with invalid PDF content."""
    path.write_bytes(b"this is definitely not a valid pdf file")
