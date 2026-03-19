"""PDF text extraction using pdfplumber."""

from __future__ import annotations

from pathlib import Path

import structlog

from srf.extraction.models import ExtractionError, FetchResult, PaperContent

logger = structlog.get_logger(__name__)


def extract_paper_content(
    pdf_path: Path,
    arxiv_id: str | None = None,
) -> PaperContent:
    """Extract full text and abstract from a PDF file.

    Returns a PaperContent with extraction_status:
    - "ok"          — text successfully extracted
    - "image_only"  — PDF opened but no embedded text found
    - "failed"      — PDF could not be opened or read
    """
    import pdfplumber

    try:
        with pdfplumber.open(pdf_path) as pdf:
            page_count = len(pdf.pages)
            texts = [page.extract_text() or "" for page in pdf.pages]
    except Exception as exc:
        logger.warning("extract_paper_failed", pdf_path=str(pdf_path), error=str(exc))
        return PaperContent(
            arxiv_id=arxiv_id,
            pdf_path=pdf_path,
            full_text=None,
            abstract=None,
            page_count=0,
            extraction_status="failed",
        )

    full_text = "\n".join(texts).strip()

    if not full_text:
        return PaperContent(
            arxiv_id=arxiv_id,
            pdf_path=pdf_path,
            full_text=None,
            abstract=None,
            page_count=page_count,
            extraction_status="image_only",
        )

    abstract = _extract_abstract(full_text)

    return PaperContent(
        arxiv_id=arxiv_id,
        pdf_path=pdf_path,
        full_text=full_text,
        abstract=abstract,
        page_count=page_count,
        extraction_status="ok",
    )


def extract_papers_for_forum(
    fetch_results: list[FetchResult],
    workspace_path: Path,
    min_papers: int = 2,
) -> list[PaperContent]:
    """Extract text for all fetched papers and enforce the minimum viable paper set.

    Raises:
        ExtractionError: if fewer than min_papers are successfully extracted.
    """
    contents: list[PaperContent] = []
    for result in fetch_results:
        if result.status != "ok" or result.pdf_path is None:
            contents.append(
                PaperContent(
                    arxiv_id=result.arxiv_id,
                    pdf_path=None,
                    full_text=None,
                    abstract=None,
                    page_count=0,
                    extraction_status="failed",
                )
            )
        else:
            contents.append(extract_paper_content(result.pdf_path, arxiv_id=result.arxiv_id))

    successful = sum(1 for c in contents if c.extraction_status == "ok")
    if successful < min_papers:
        raise ExtractionError(
            f"insufficient papers extracted: {successful} succeeded, "
            f"minimum required is {min_papers}."
        )

    return contents


def _extract_abstract(text: str) -> str | None:
    """Heuristic: find an 'Abstract' header and return the following paragraph."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.strip().lower() in ("abstract", "abstract:"):
            abstract_lines: list[str] = []
            for subsequent in lines[i + 1 :]:
                stripped = subsequent.strip()
                # Stop at the next likely section header (short title-case line)
                if stripped and len(stripped.split()) <= 4 and stripped[0].isupper():
                    break
                abstract_lines.append(subsequent)
            abstract = "\n".join(abstract_lines).strip()
            return abstract if abstract else None
    return None
