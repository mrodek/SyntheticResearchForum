"""Lobster step script — agent preparation phase.

Reads paper extraction JSON from stdin, runs all agent preparations
concurrently, and writes preparation summary JSON to stdout.

Usage (Lobster):
    python scripts/run_preparation.py
    stdin:  $paper_extraction.json
    stdout: { forum_id, workspace_path, agents, preparation_status, ... }
"""

from __future__ import annotations

import json
import sys
from typing import Any

import structlog

from srf.agents.orchestrator import run_preparation
from srf.agents.roster import build_roster
from srf.config import SRFConfig
from srf.logging import configure_logging


def main() -> None:
    configure_logging(stream=sys.stderr)
    log = structlog.get_logger(__name__)

    stdin_data: dict[str, Any] = json.load(sys.stdin)

    try:
        output = _run_sync(stdin_data)
        print(json.dumps(output))
    except Exception as exc:
        log.error("run_preparation failed", error=str(exc))
        sys.exit(1)


def _run_sync(stdin_data: dict[str, Any]) -> dict[str, Any]:
    import asyncio

    return asyncio.run(_run(stdin_data))


async def _run(stdin_data: dict[str, Any]) -> dict[str, Any]:
    import structlog

    from srf.extraction.models import PaperContent
    from srf.observability import build_tracker
    from srf.workspace.models import ForumWorkspace

    log = structlog.get_logger(__name__)

    config = SRFConfig.from_env()
    tracker = build_tracker(config)

    workspace = ForumWorkspace.from_dict(stdin_data)

    papers_raw = stdin_data.get("papers", [])
    papers = [
        PaperContent(
            arxiv_id=p["arxiv_id"],
            pdf_path=None,
            full_text=p.get("full_text") or "",
            abstract=p.get("abstract") or "",
            page_count=p.get("page_count", 0),
            extraction_status=p.get("extraction_status", "ok"),
        )
        for p in papers_raw
    ]

    paper_abstracts = [p.abstract or "" for p in papers]
    paper_summaries = [p.abstract or "" for p in papers]  # summaries = abstracts for now

    state: dict[str, Any] = {
        "trace_id": stdin_data.get("trace_id", ""),
        "forum_id": workspace.forum_id,
    }

    roster = build_roster(workspace, papers)

    log.info(
        "starting agent preparation",
        forum_id=workspace.forum_id,
        agent_count=len([a for a in roster.agents if a.role == "paper_agent"]),
    )

    result = await run_preparation(
        roster=roster,
        workspace=workspace,
        paper_abstracts=paper_abstracts,
        paper_summaries=paper_summaries,
        framing_question=workspace.framing_question,
        tracker=tracker,
        config=config,
        state=state,
    )

    output = {
        **stdin_data,
        "forum_status": "preparation_complete",
        "agents": [a.to_dict() for a in result["roster"].agents],
        "preparation_status": result["preparation_status"],
    }
    return output


if __name__ == "__main__":
    main()
