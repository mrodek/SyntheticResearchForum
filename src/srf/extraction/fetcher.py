"""arXiv paper fetcher with rate limiting and retry logic."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

import httpx
import structlog

from srf.extraction.models import FetchError, FetchResult
from srf.newsletter.models import PrimarySignal

logger = structlog.get_logger(__name__)

_ARXIV_PDF_URL = "https://arxiv.org/pdf/{arxiv_id}"
_RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})


async def fetch_paper(
    arxiv_id: str,
    workspace_path: Path,
    http_client,
    sleep_fn: Callable = asyncio.sleep,
    max_retries: int = 3,
    delay_seconds: float = 3.0,
) -> FetchResult:
    """Download a paper PDF from arXiv and write it to workspace_path/papers/{arxiv_id}.pdf.

    Retries on 429 and 5xx responses up to max_retries times with delay_seconds between
    attempts. Raises FetchError if the papers directory cannot be written to.
    """
    url = _ARXIV_PDF_URL.format(arxiv_id=arxiv_id)
    papers_dir = workspace_path / "papers"
    papers_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = papers_dir / f"{arxiv_id}.pdf"

    last_error: str = ""
    for attempt in range(max_retries):
        try:
            response = await http_client.get(url)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            last_error = f"HTTP {status_code}"
            if status_code in _RETRYABLE_STATUSES and attempt < max_retries - 1:
                await sleep_fn(delay_seconds)
                continue
            logger.warning("fetch_paper_failed", arxiv_id=arxiv_id, error=last_error)
            return FetchResult(arxiv_id=arxiv_id, status="failed", pdf_path=None, error=last_error)
        except httpx.RequestError as exc:
            last_error = str(exc)
            if attempt < max_retries - 1:
                await sleep_fn(delay_seconds)
                continue
            logger.warning("fetch_paper_failed", arxiv_id=arxiv_id, error=last_error)
            return FetchResult(arxiv_id=arxiv_id, status="failed", pdf_path=None, error=last_error)

        try:
            pdf_path.write_bytes(response.content)
        except OSError as exc:
            raise FetchError(f"Cannot write PDF to {pdf_path}: {exc}") from exc

        logger.info("fetch_paper_ok", arxiv_id=arxiv_id, path=str(pdf_path))
        return FetchResult(arxiv_id=arxiv_id, status="ok", pdf_path=pdf_path)

    return FetchResult(arxiv_id=arxiv_id, status="failed", pdf_path=None, error=last_error)


async def fetch_paper_for_signal(
    signal: PrimarySignal,
    workspace_path: Path,
    http_client,
    sleep_fn: Callable = asyncio.sleep,
    max_retries: int = 3,
    delay_seconds: float = 3.0,
) -> FetchResult:
    """Fetch a paper for a PrimarySignal, skipping non-arXiv sources."""
    if signal.source != "arxiv" or signal.arxiv_id is None:
        logger.warning(
            "skipping_non_arxiv_paper",
            url=signal.url,
            source=signal.source,
        )
        return FetchResult(
            arxiv_id=None,
            status="manual_review_required",
            pdf_path=None,
        )

    return await fetch_paper(
        arxiv_id=signal.arxiv_id,
        workspace_path=workspace_path,
        http_client=http_client,
        sleep_fn=sleep_fn,
        max_retries=max_retries,
        delay_seconds=delay_seconds,
    )


async def fetch_papers_for_forum(
    signals: list[PrimarySignal],
    workspace_path: Path,
    http_client,
    sleep_fn: Callable = asyncio.sleep,
    delay_seconds: float = 3.0,
    max_retries: int = 3,
) -> list[FetchResult]:
    """Fetch all papers, sleeping delay_seconds between each request."""
    results: list[FetchResult] = []
    for i, signal in enumerate(signals):
        result = await fetch_paper_for_signal(
            signal=signal,
            workspace_path=workspace_path,
            http_client=http_client,
            sleep_fn=sleep_fn,
            max_retries=max_retries,
            delay_seconds=delay_seconds,
        )
        results.append(result)
        if i < len(signals) - 1:
            await sleep_fn(delay_seconds)
    return results
