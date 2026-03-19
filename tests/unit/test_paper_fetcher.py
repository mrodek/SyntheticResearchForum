"""Story 4.2 — arXiv Paper Fetcher acceptance tests."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from srf.newsletter.models import PrimarySignal


def _ok_response(content: bytes = b"%PDF-1.4 fake") -> MagicMock:
    r = MagicMock()
    r.status_code = 200
    r.content = content
    r.raise_for_status = MagicMock(return_value=None)
    return r


def _error_response(status_code: int) -> MagicMock:
    r = MagicMock()
    r.status_code = status_code
    r.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            f"HTTP {status_code}",
            request=MagicMock(),
            response=MagicMock(status_code=status_code),
        )
    )
    return r


# ---------------------------------------------------------------------------
# Scenario: fetch_paper downloads the PDF and writes it to the workspace
# ---------------------------------------------------------------------------


async def test_fetch_paper_writes_pdf_to_workspace(tmp_path: Path) -> None:
    from srf.extraction.fetcher import fetch_paper

    pdf_bytes = b"%PDF-1.4 fake content"
    mock_client = AsyncMock()
    mock_client.get.return_value = _ok_response(pdf_bytes)

    result = await fetch_paper(
        arxiv_id="2401.12345",
        workspace_path=tmp_path,
        http_client=mock_client,
    )

    pdf_path = tmp_path / "papers" / "2401.12345.pdf"
    assert pdf_path.exists()
    assert pdf_path.read_bytes() == pdf_bytes
    assert result.status == "ok"
    assert result.arxiv_id == "2401.12345"
    assert result.pdf_path == pdf_path


# ---------------------------------------------------------------------------
# Scenario: fetch_paper retries on HTTP 429 and succeeds on second attempt
# ---------------------------------------------------------------------------


async def test_fetch_paper_retries_on_429(tmp_path: Path) -> None:
    from srf.extraction.fetcher import fetch_paper

    slept: list[float] = []

    async def mock_sleep(seconds: float) -> None:
        slept.append(seconds)

    mock_client = AsyncMock()
    mock_client.get.side_effect = [_error_response(429), _ok_response()]

    result = await fetch_paper(
        arxiv_id="2401.12345",
        workspace_path=tmp_path,
        http_client=mock_client,
        sleep_fn=mock_sleep,
        max_retries=3,
    )

    assert mock_client.get.call_count == 2
    assert result.status == "ok"
    assert len(slept) == 1


# ---------------------------------------------------------------------------
# Scenario: fetch_paper returns "failed" after all retries exhausted
# ---------------------------------------------------------------------------


async def test_fetch_paper_returns_failed_after_all_retries(tmp_path: Path) -> None:
    from srf.extraction.fetcher import fetch_paper

    mock_client = AsyncMock()
    mock_client.get.return_value = _error_response(503)

    result = await fetch_paper(
        arxiv_id="2401.12345",
        workspace_path=tmp_path,
        http_client=mock_client,
        sleep_fn=AsyncMock(),
        max_retries=3,
    )

    assert mock_client.get.call_count == 3
    assert result.status == "failed"
    assert "503" in result.error


# ---------------------------------------------------------------------------
# Scenario: fetch_paper_for_signal skips non-arXiv sources
# ---------------------------------------------------------------------------


async def test_fetch_paper_for_signal_skips_non_arxiv(tmp_path: Path) -> None:
    from srf.extraction.fetcher import fetch_paper_for_signal

    signal = PrimarySignal(
        title="OSF Paper",
        url="https://osf.io/preprints/xyz",
        source="other",
        arxiv_id=None,
        technical_summary="...",
        why_it_matters="...",
    )
    mock_client = AsyncMock()

    result = await fetch_paper_for_signal(signal, tmp_path, mock_client)

    mock_client.get.assert_not_called()
    assert result.status == "manual_review_required"
    assert result.pdf_path is None


# ---------------------------------------------------------------------------
# Scenario: fetch_papers_for_forum respects the delay between requests
# ---------------------------------------------------------------------------


async def test_fetch_papers_for_forum_respects_delay(tmp_path: Path) -> None:
    from srf.extraction.fetcher import fetch_papers_for_forum

    mock_client = AsyncMock()
    mock_client.get.return_value = _ok_response()

    slept: list[float] = []

    async def mock_sleep(seconds: float) -> None:
        slept.append(seconds)

    signals = [
        PrimarySignal("P1", "u1", "arxiv", "2401.00001", "s1", "w1"),
        PrimarySignal("P2", "u2", "arxiv", "2401.00002", "s2", "w2"),
        PrimarySignal("P3", "u3", "arxiv", "2401.00003", "s3", "w3"),
    ]

    await fetch_papers_for_forum(
        signals=signals,
        workspace_path=tmp_path,
        http_client=mock_client,
        sleep_fn=mock_sleep,
        delay_seconds=1.0,
    )

    assert len(slept) >= 2
    assert all(s >= 1.0 for s in slept)


# ---------------------------------------------------------------------------
# Scenario: fetch_paper raises FetchError when workspace papers dir is not writable
# ---------------------------------------------------------------------------


@pytest.mark.skipif(os.name == "nt", reason="chmod read-only unreliable on Windows")
async def test_fetch_paper_raises_fetch_error_on_write_failure(tmp_path: Path) -> None:
    from srf.extraction.fetcher import fetch_paper
    from srf.extraction.models import FetchError

    papers_dir = tmp_path / "papers"
    papers_dir.mkdir()
    papers_dir.chmod(stat.S_IREAD | stat.S_IEXEC)

    try:
        mock_client = AsyncMock()
        mock_client.get.return_value = _ok_response()

        with pytest.raises(FetchError):
            await fetch_paper("2401.12345", tmp_path, mock_client)
    finally:
        papers_dir.chmod(stat.S_IRWXU)
