"""Integration test — real arXiv fetch for one paper.

Skipped unless SRF_RUN_INTEGRATION=1 is set to avoid hammering arXiv in CI.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("SRF_RUN_INTEGRATION") != "1",
    reason="Set SRF_RUN_INTEGRATION=1 to run live arXiv integration tests",
)


async def test_fetch_real_arxiv_paper(tmp_path: Path) -> None:
    import httpx

    from srf.extraction.fetcher import fetch_paper

    async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
        result = await fetch_paper(
            arxiv_id="2301.07041",  # a stable, small paper
            workspace_path=tmp_path,
            http_client=client,
            delay_seconds=3.0,
        )

    assert result.status == "ok", f"Fetch failed: {result.error}"
    assert result.pdf_path is not None
    assert result.pdf_path.exists()
    assert result.pdf_path.stat().st_size > 0
