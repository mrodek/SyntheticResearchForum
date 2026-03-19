"""Story 4.3 — PDF Text Extraction acceptance tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def valid_pdf(tmp_path: Path) -> Path:
    from tests.fixtures.papers._builders import make_valid_paper_pdf

    p = tmp_path / "valid.pdf"
    make_valid_paper_pdf(p)
    return p


@pytest.fixture
def image_only_pdf(tmp_path: Path) -> Path:
    from tests.fixtures.papers._builders import make_image_only_pdf

    p = tmp_path / "image_only.pdf"
    make_image_only_pdf(p)
    return p


@pytest.fixture
def corrupt_pdf(tmp_path: Path) -> Path:
    from tests.fixtures.papers._builders import make_corrupt_pdf

    p = tmp_path / "corrupt.pdf"
    make_corrupt_pdf(p)
    return p


# ---------------------------------------------------------------------------
# Scenario: extract_paper_content returns PaperContent with non-empty full_text
# ---------------------------------------------------------------------------


def test_extract_paper_content_returns_full_text(valid_pdf: Path) -> None:
    from srf.extraction.extractor import extract_paper_content

    result = extract_paper_content(valid_pdf)
    assert result.full_text is not None
    assert len(result.full_text) > 0
    assert result.extraction_status == "ok"
    assert result.page_count > 0


# ---------------------------------------------------------------------------
# Scenario: extract_paper_content populates abstract when detectable
# ---------------------------------------------------------------------------


def test_extract_paper_content_populates_abstract(valid_pdf: Path) -> None:
    from srf.extraction.extractor import extract_paper_content

    result = extract_paper_content(valid_pdf)
    assert result.abstract is not None
    assert len(result.abstract) > 0
    assert result.abstract in result.full_text


# ---------------------------------------------------------------------------
# Scenario: extract_paper_content returns "image_only" for a scanned PDF
# ---------------------------------------------------------------------------


def test_extract_paper_content_image_only(image_only_pdf: Path) -> None:
    from srf.extraction.extractor import extract_paper_content

    result = extract_paper_content(image_only_pdf)
    assert result.extraction_status == "image_only"
    assert result.full_text is None


# ---------------------------------------------------------------------------
# Scenario: extract_paper_content returns "failed" and logs warning for corrupt PDF
# ---------------------------------------------------------------------------


def test_extract_paper_content_corrupt_returns_failed(corrupt_pdf: Path) -> None:
    from srf.extraction.extractor import extract_paper_content

    result = extract_paper_content(corrupt_pdf)
    assert result.extraction_status == "failed"
    assert result.full_text is None


# ---------------------------------------------------------------------------
# Scenario: extract_paper_content does not raise when the PDF is missing
# ---------------------------------------------------------------------------


def test_extract_paper_content_missing_file_returns_failed(tmp_path: Path) -> None:
    from srf.extraction.extractor import extract_paper_content

    result = extract_paper_content(tmp_path / "nonexistent.pdf")
    assert result.extraction_status == "failed"
    assert result.full_text is None


# ---------------------------------------------------------------------------
# Scenario: extract_papers_for_forum returns one PaperContent per FetchResult
# ---------------------------------------------------------------------------


def test_extract_papers_for_forum_returns_all_results(tmp_path: Path) -> None:
    from srf.extraction.extractor import extract_papers_for_forum
    from srf.extraction.models import FetchResult
    from tests.fixtures.papers._builders import make_valid_paper_pdf

    papers_dir = tmp_path / "papers"
    papers_dir.mkdir()

    pdf1 = papers_dir / "2401.00001.pdf"
    pdf2 = papers_dir / "2401.00002.pdf"
    pdf3 = papers_dir / "2401.00003.pdf"
    make_valid_paper_pdf(pdf1)
    make_valid_paper_pdf(pdf2)
    make_valid_paper_pdf(pdf3)

    fetch_results = [
        FetchResult(arxiv_id="2401.00001", status="ok", pdf_path=pdf1),
        FetchResult(arxiv_id="2401.00002", status="ok", pdf_path=pdf2),
        FetchResult(arxiv_id="2401.00003", status="ok", pdf_path=pdf3),
        FetchResult(arxiv_id="2401.00004", status="failed", pdf_path=None, error="HTTP 503"),
    ]

    results = extract_papers_for_forum(fetch_results, tmp_path, min_papers=2)

    assert len(results) == 4
    assert sum(1 for r in results if r.extraction_status == "ok") == 3
    assert sum(1 for r in results if r.extraction_status == "failed") == 1


# ---------------------------------------------------------------------------
# Scenario: extract_papers_for_forum raises ExtractionError when too few succeed
# ---------------------------------------------------------------------------


def test_extract_papers_for_forum_raises_when_too_few_succeed(tmp_path: Path) -> None:
    from srf.extraction.extractor import extract_papers_for_forum
    from srf.extraction.models import ExtractionError, FetchResult

    fetch_results = [
        FetchResult(arxiv_id="2401.00001", status="ok", pdf_path=tmp_path / "nonexistent.pdf"),
        FetchResult(arxiv_id="2401.00002", status="failed", pdf_path=None, error="503"),
    ]

    with pytest.raises(ExtractionError, match="insufficient"):
        extract_papers_for_forum(fetch_results, tmp_path, min_papers=2)
