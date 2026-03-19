"""Lobster step: Paper Extraction (Phase 5).

Reads:  JSON from stdin — output of run_workspace_setup.py
Writes: JSON to stdout — previous fields + { papers: [...], forum_status }
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from srf.extraction.extractor import extract_papers_for_forum
from srf.extraction.fetcher import fetch_papers_for_forum


async def _run(data: dict) -> dict:
    from srf.config import SRFConfig
    from srf.newsletter.models import PrimarySignal

    config = SRFConfig.from_env()
    workspace_path = Path(data["workspace_path"])

    # Reconstruct PrimarySignal list from paper_refs (arxiv_ids or URLs)
    paper_refs: list[str] = data.get("paper_refs", [])
    signals = [
        PrimarySignal(
            title=ref,
            url=f"https://arxiv.org/abs/{ref}" if not ref.startswith("http") else ref,
            source="arxiv" if not ref.startswith("http") else "other",
            arxiv_id=ref if not ref.startswith("http") else None,
            technical_summary="",
            why_it_matters="",
        )
        for ref in paper_refs
    ]

    import httpx

    async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
        fetch_results = await fetch_papers_for_forum(
            signals=signals,
            workspace_path=workspace_path,
            http_client=client,
            delay_seconds=config.arxiv_delay_seconds,
        )

    paper_contents = extract_papers_for_forum(
        fetch_results, workspace_path, min_papers=config.min_papers
    )

    papers = [
        {
            "arxiv_id": pc.arxiv_id,
            "full_text": pc.full_text,
            "abstract": pc.abstract,
            "page_count": pc.page_count,
            "extraction_status": pc.extraction_status,
        }
        for pc in paper_contents
    ]

    output = {**data, "papers": papers, "forum_status": "extraction_complete"}

    # Write state.json checkpoint
    state_path = workspace_path / "state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["forum_status"] = "extraction_complete"
        state["extracted_paper_count"] = sum(
            1 for pc in paper_contents if pc.extraction_status == "ok"
        )
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except OSError:
        pass

    return output


def main() -> int:
    from srf.logging import configure_logging
    configure_logging(stream=sys.stderr)

    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: invalid stdin JSON: {exc}", file=sys.stderr)
        return 1

    from srf.extraction.models import ExtractionError

    try:
        output = asyncio.run(_run(data))
    except ExtractionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: unexpected error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
