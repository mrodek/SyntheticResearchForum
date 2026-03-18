"""SRF MCP tools — callable by Claude Desktop via the MCP protocol.

Tools in this module deliberately stop after candidate config generation.
No forum_id is assigned; no debate phases are initiated. The human gate
between Epic 3 and Epic 4 is enforced here.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

import structlog

from srf.newsletter.clustering import cluster_papers
from srf.newsletter.config_generator import generate_candidate_config
from srf.newsletter.models import ToolError
from srf.newsletter.parser import parse_newsletter
from srf.newsletter.persistence import save_candidate_configs

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Tool implementation
# ---------------------------------------------------------------------------


async def trigger_newsletter_forum(
    source_path: str,
    workspace_root: str | None = None,
    *,
    tracker: object | None = None,
) -> dict[str, Any]:
    """Copy a newsletter file into SRF and run the parse → cluster → generate pipeline.

    Returns a dict with:
        status: "awaiting_approval"
        candidates: list of {topic, framing_question, paper_count, path}

    Raises:
        ToolError: if source_path does not exist, or a duplicate slug is found.
    """
    src = Path(source_path)
    if not src.exists():
        raise ToolError(f"Source file not found: {source_path}")

    ws = Path(workspace_root or os.environ.get("SRF_WORKSPACE_ROOT", "/data/workspace"))
    newsletters_dir = ws / ".newsletters"
    newsletters_dir.mkdir(parents=True, exist_ok=True)

    dest = newsletters_dir / src.name
    if dest.exists():
        raise ToolError(
            f"Newsletter '{src.name}' already processed (slug already exists at {dest}). "
            "Delete the existing file to reprocess."
        )

    shutil.copy2(src, dest)
    newsletter_slug = src.stem.replace(" ", "_").lower()

    logger.info("newsletter trigger started", slug=newsletter_slug)

    # llm_client is the tracker=None fallback; replaced by call_provider_directly() in Epic 5.
    llm_client = None if tracker is not None else _build_llm_client()
    state: dict = {}

    doc = parse_newsletter(dest)
    clusters = await cluster_papers(
        doc, tracker=tracker, state=state, llm_client=llm_client
    )

    configs = []
    saved_paths = []
    for cluster in clusters:
        cluster.newsletter_slug = newsletter_slug
        config = await generate_candidate_config(
            cluster, tracker=tracker, state=state, llm_client=llm_client
        )
        configs.append(config)

    saved_paths = save_candidate_configs(configs, ws, newsletter_slug=newsletter_slug)

    candidates = [
        {
            "topic": config.topic,
            "framing_question": config.framing_question,
            "paper_count": len(config.paper_refs),
            "path": str(path),
        }
        for config, path in zip(configs, saved_paths, strict=True)
    ]

    logger.info(
        "newsletter trigger complete",
        slug=newsletter_slug,
        candidate_count=len(candidates),
    )

    return {
        "status": "awaiting_approval",
        "newsletter_slug": newsletter_slug,
        "candidates": candidates,
    }


def _build_llm_client() -> Any:
    """Build a minimal LLM client from environment config.

    Replaced by the full src/srf/llm/ client in Epic 5.
    """
    provider = os.environ.get("SRF_LLM_PROVIDER", "")
    if provider == "anthropic":
        try:
            import anthropic

            class _Client:
                def __init__(self) -> None:
                    self._ac = anthropic.AsyncAnthropic(
                        api_key=os.environ["SRF_LLM_API_KEY"]
                    )
                    self._model = os.environ["SRF_LLM_MODEL"]

                async def complete(self, messages: list[dict]) -> Any:
                    system = next(
                        (m["content"] for m in messages if m["role"] == "system"), ""
                    )
                    user = [m for m in messages if m["role"] != "system"]
                    resp = await self._ac.messages.create(
                        model=self._model,
                        max_tokens=1024,
                        system=system,
                        messages=user,
                    )
                    resp.content = resp.content[0].text
                    return resp

            return _Client()
        except ImportError:
            pass

    class _Stub:
        async def complete(self, _messages: list[dict]) -> Any:
            raise RuntimeError(
                "No LLM client configured. Set SRF_LLM_PROVIDER and SRF_LLM_API_KEY."
            )

    return _Stub()


# ---------------------------------------------------------------------------
# MCP tool registry — consumed by the MCP server at startup
# ---------------------------------------------------------------------------

SRF_MCP_TOOLS: list[dict[str, Any]] = [
    {
        "name": "trigger_newsletter_forum",
        "description": (
            "Copy a newsletter Markdown file into SRF and run the parse → cluster → "
            "generate pipeline to produce candidate forum configs for editorial review. "
            "Stops after candidate config generation — does not initiate debate phases."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "source_path": {
                    "type": "string",
                    "description": "Absolute path to the newsletter Markdown file in ResearchKG.",
                },
                "workspace_root": {
                    "type": "string",
                    "description": (
                        "Workspace root directory. Defaults to SRF_WORKSPACE_ROOT env var."
                    ),
                },
            },
            "required": ["source_path"],
        },
    }
]
