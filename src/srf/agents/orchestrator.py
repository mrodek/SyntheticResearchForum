"""Parallel preparation orchestrator — fans out all agent preparations via asyncio.gather()."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog

from srf.agents.models import AgentRoster, OrchestrationError, PreparationError
from srf.agents.preparation import (
    PreparationArtifact,
    prepare_challenger,
    prepare_moderator,
    prepare_paper_agent,
)
from srf.config import SRFConfig
from srf.workspace.models import ForumWorkspace

logger = structlog.get_logger(__name__)

_DEFAULT_MAX_PREP_RETRIES = 3
_DEFAULT_MIN_AGENTS = 2


async def run_preparation(
    roster: AgentRoster,
    workspace: ForumWorkspace,
    paper_abstracts: list[str],
    paper_summaries: list[str],
    framing_question: str,
    *,
    tracker: object | None,
    config: SRFConfig,
    state: dict[str, Any],
    min_agents: int = _DEFAULT_MIN_AGENTS,
) -> dict[str, Any]:
    """Run all agent preparations concurrently.

    Fans out Paper Agent preparations via asyncio.gather(). Moderator and
    Challenger run concurrently with paper agents. Moderator failure aborts;
    Challenger failure degrades gracefully; Paper Agent failure marks degraded
    after retries exhausted.

    Args:
        roster:           AgentRoster with all assigned agents.
        workspace:        ForumWorkspace for writing artifacts and state.
        paper_abstracts:  Paper abstracts for the Challenger.
        paper_summaries:  Paper summaries for the Moderator.
        framing_question: Forum framing question.
        tracker:          AsyncPromptLedgerClient or None.
        config:           SRFConfig.
        state:            Mutable state dict.
        min_agents:       Minimum ok paper agents required to proceed.

    Returns:
        Dict with preparation_status, agent_count, and updated roster.

    Raises:
        OrchestrationError: Moderator failure or insufficient ok paper agents.
    """
    max_retries = getattr(config, "max_prep_retries", _DEFAULT_MAX_PREP_RETRIES)

    paper_assignments = [a for a in roster.agents if a.role == "paper_agent"]

    # Build per-paper-content mapping: agent_id → PaperContent index
    # paper_abstracts is indexed same as paper_agents in roster order
    paper_agent_tasks = [
        _prepare_paper_agent_with_retry(
            assignment=assignment,
            paper_abstract=paper_abstracts[idx] if idx < len(paper_abstracts) else "",
            framing_question=framing_question,
            workspace=workspace,
            tracker=tracker,
            config=config,
            state=state,
            max_retries=max_retries,
        )
        for idx, assignment in enumerate(paper_assignments)
    ]

    moderator_task = _prepare_moderator_with_retry(
        roster=roster,
        framing_question=framing_question,
        paper_summaries=paper_summaries,
        workspace=workspace,
        tracker=tracker,
        config=config,
        state=state,
        max_retries=max_retries,
    )

    challenger_task = _prepare_challenger_with_retry(
        roster=roster,
        framing_question=framing_question,
        paper_abstracts=paper_abstracts,
        workspace=workspace,
        tracker=tracker,
        config=config,
        state=state,
        max_retries=max_retries,
    )

    # Fan out all preparations concurrently
    results = await asyncio.gather(
        *paper_agent_tasks,
        moderator_task,
        challenger_task,
        return_exceptions=True,
    )

    paper_results = results[: len(paper_assignments)]
    moderator_result = results[len(paper_assignments)]
    challenger_result = results[len(paper_assignments) + 1]

    # Check moderator — failure aborts
    if isinstance(moderator_result, Exception):
        raise OrchestrationError(
            f"Moderator preparation failed after {max_retries} retries: {moderator_result}"
        )

    # Update paper agent statuses
    ok_count = 0
    for assignment, result in zip(paper_assignments, paper_results, strict=True):
        if isinstance(result, Exception):
            assignment.status = "degraded"
            logger.warning(
                "paper agent preparation failed",
                agent_id=assignment.agent_id,
                error=str(result),
            )
        else:
            assignment.status = "ok"
            ok_count += 1

    # Enforce min_agents threshold
    if ok_count < min_agents:
        raise OrchestrationError(
            f"insufficient agents prepared: {ok_count} ok, minimum required is {min_agents}"
        )

    # Challenger degrades gracefully
    if isinstance(challenger_result, Exception):
        challenger_assignment = next(
            (a for a in roster.agents if a.role == "challenger"), None
        )
        if challenger_assignment:
            challenger_assignment.status = "degraded"
        logger.warning(
            "challenger preparation failed — proceeding without challenger",
            error=str(challenger_result),
        )
    else:
        challenger_assignment = next(
            (a for a in roster.agents if a.role == "challenger"), None
        )
        if challenger_assignment:
            challenger_assignment.status = "ok"

    moderator_assignment = next((a for a in roster.agents if a.role == "moderator"), None)
    if moderator_assignment:
        moderator_assignment.status = "ok"

    # Update state.json
    state_path = workspace.workspace_path / "state.json"
    state_data = json.loads(state_path.read_text(encoding="utf-8"))
    state_data["forum_status"] = "preparation_complete"
    state_data["prepared_agent_count"] = ok_count
    state_path.write_text(json.dumps(state_data, indent=2), encoding="utf-8")

    logger.info(
        "preparation complete",
        forum_id=workspace.forum_id,
        ok_agents=ok_count,
        total_paper_agents=len(paper_assignments),
    )

    return {
        "preparation_status": "complete",
        "agent_count": ok_count,
        "roster": roster,
    }


# ---------------------------------------------------------------------------
# Internal retry helpers
# ---------------------------------------------------------------------------


async def _prepare_paper_agent_with_retry(
    assignment,
    paper_abstract: str,
    framing_question: str,
    workspace: ForumWorkspace,
    tracker: object | None,
    config: SRFConfig,
    state: dict[str, Any],
    max_retries: int,
) -> PreparationArtifact:
    """Call prepare_paper_agent with retry; write artifact.json on success."""
    from srf.extraction.models import PaperContent

    # Build a minimal PaperContent from the abstract
    paper_content = PaperContent(
        arxiv_id=assignment.arxiv_id,
        pdf_path=None,
        full_text=paper_abstract,
        abstract=paper_abstract,
        page_count=0,
        extraction_status="ok",
    )

    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            artifact = await prepare_paper_agent(
                assignment=assignment,
                paper_content=paper_content,
                framing_question=framing_question,
                tracker=tracker,
                config=config,
                state=state,
                memory_block="",
            )
            # Write artifact to workspace
            artifact_dir = workspace.workspace_path / "preparation" / assignment.agent_id
            artifact_dir.mkdir(parents=True, exist_ok=True)
            (artifact_dir / "artifact.json").write_text(
                json.dumps(artifact.to_dict(), indent=2), encoding="utf-8"
            )
            return artifact
        except PreparationError as exc:
            last_exc = exc
            if attempt < max_retries:
                logger.warning(
                    "paper agent preparation attempt failed — retrying",
                    agent_id=assignment.agent_id,
                    attempt=attempt,
                    error=str(exc),
                )

    raise last_exc  # type: ignore[misc]


async def _prepare_moderator_with_retry(
    roster: AgentRoster,
    framing_question: str,
    paper_summaries: list[str],
    workspace: ForumWorkspace,
    tracker: object | None,
    config: SRFConfig,
    state: dict[str, Any],
    max_retries: int,
):
    """Call prepare_moderator with retry; write artifact.json on success."""
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            briefing = await prepare_moderator(
                roster=roster,
                framing_question=framing_question,
                paper_summaries=paper_summaries,
                tracker=tracker,
                config=config,
                state=state,
                memory_block="",
            )
            artifact_dir = workspace.workspace_path / "preparation" / "moderator"
            artifact_dir.mkdir(parents=True, exist_ok=True)
            (artifact_dir / "artifact.json").write_text(
                json.dumps(briefing.to_dict(), indent=2), encoding="utf-8"
            )
            return briefing
        except PreparationError as exc:
            last_exc = exc
            if attempt < max_retries:
                logger.warning(
                    "moderator preparation attempt failed — retrying",
                    attempt=attempt,
                    error=str(exc),
                )

    raise last_exc  # type: ignore[misc]


async def _prepare_challenger_with_retry(
    roster: AgentRoster,
    framing_question: str,
    paper_abstracts: list[str],
    workspace: ForumWorkspace,
    tracker: object | None,
    config: SRFConfig,
    state: dict[str, Any],
    max_retries: int,
):
    """Call prepare_challenger with retry; write artifact.json on success."""
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            prep = await prepare_challenger(
                roster=roster,
                framing_question=framing_question,
                paper_abstracts=paper_abstracts,
                tracker=tracker,
                config=config,
                state=state,
                memory_block="",
            )
            artifact_dir = workspace.workspace_path / "preparation" / "challenger"
            artifact_dir.mkdir(parents=True, exist_ok=True)
            (artifact_dir / "artifact.json").write_text(
                json.dumps(prep.to_dict(), indent=2), encoding="utf-8"
            )
            return prep
        except PreparationError as exc:
            last_exc = exc
            if attempt < max_retries:
                logger.warning(
                    "challenger preparation attempt failed — retrying",
                    attempt=attempt,
                    error=str(exc),
                )

    raise last_exc  # type: ignore[misc]
