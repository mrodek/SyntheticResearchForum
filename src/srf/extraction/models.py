"""Extraction domain models shared by fetcher and extractor."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class FetchError(OSError):
    """Raised when a paper PDF cannot be written to disk."""


class ExtractionError(ValueError):
    """Raised when fewer than the minimum viable paper set can be extracted."""


@dataclass
class FetchResult:
    arxiv_id: str | None
    status: str  # "ok" | "failed" | "manual_review_required"
    pdf_path: Path | None
    error: str | None = None


@dataclass
class PaperContent:
    arxiv_id: str | None
    pdf_path: Path | None
    full_text: str | None
    abstract: str | None
    page_count: int
    extraction_status: str  # "ok" | "image_only" | "failed"
