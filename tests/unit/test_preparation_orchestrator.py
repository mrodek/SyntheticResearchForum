"""Story 5.5 — run_preparation() orchestrator unit tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from srf.agents.models import AgentAssignment, AgentRoster, PreparationError
from srf.agents.preparation import ChallengerPreparation, ModeratorBriefing, PreparationArtifact
from srf.workspace.models import ForumWorkspace


def _make_workspace(tmp_path: Path) -> ForumWorkspace:
    wp = tmp_path / "forum-20260317-abcdef01"
    wp.mkdir(parents=True)
    (wp / "preparation").mkdir()
    state = {"forum_id": "forum-20260317-abcdef01", "forum_status": "extraction_complete"}
    (wp / "state.json").write_text(json.dumps(state), encoding="utf-8")
    return ForumWorkspace(
        forum_id="forum-20260317-abcdef01",
        workspace_path=wp,
        topic="Test Topic",
        framing_question="A question?",
        paper_refs=["2401.00001", "2401.00002", "2401.00003"],
        created_at="2026-03-17T10:00:00+00:00",
    )


def _make_roster(n_paper_agents: int = 3) -> AgentRoster:
    agents = [
        AgentAssignment(
            agent_id=f"paper-agent-{i + 1}",
            role="paper_agent",
            arxiv_id=f"2401.{i:05d}",
        )
        for i in range(n_paper_agents)
    ]
    agents.append(AgentAssignment(agent_id="moderator", role="moderator", arxiv_id=None))
    agents.append(AgentAssignment(agent_id="challenger", role="challenger", arxiv_id=None))
    return AgentRoster(forum_id="forum-20260317-abcdef01", agents=agents)


def _make_valid_artifact(agent_id: str) -> PreparationArtifact:
    return PreparationArtifact(
        agent_id=agent_id,
        claimed_position="Position",
        key_arguments=["Arg1", "Arg2"],
        anticipated_objections=["Objection1"],
        epistemic_confidence=0.8,
    )


def _make_valid_moderator_briefing() -> ModeratorBriefing:
    return ModeratorBriefing(
        debate_agenda=["Item1", "Item2", "Item3"],
        agent_profiles=[{"agent_id": "paper-agent-1"}],
        escalation_policy="Redirect off-topic turns.",
    )


def _make_valid_challenger_prep() -> ChallengerPreparation:
    return ChallengerPreparation(
        skeptical_stance="Evidence is weak.",
        challenge_angles=["Angle1", "Angle2"],
        anticipated_defenses=["Defense1"],
    )


# ---------------------------------------------------------------------------
# Scenario: all preparations succeed — artifacts written + state.json updated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_preparation_success_writes_artifacts_and_updates_state(tmp_path: Path) -> None:
    from srf.agents.orchestrator import run_preparation

    workspace = _make_workspace(tmp_path)
    roster = _make_roster(n_paper_agents=2)
    config = MagicMock()
    config.max_prep_retries = 3
    config.paper_token_budget = 80000
    state: dict = {"trace_id": "t1"}

    paper_abstracts = ["Abstract 1", "Abstract 2"]
    paper_summaries = ["Summary 1", "Summary 2"]

    with (
        patch(
            "srf.agents.orchestrator.prepare_paper_agent",
            new=AsyncMock(side_effect=lambda assignment, **kw: _make_valid_artifact(assignment.agent_id)),
        ),
        patch(
            "srf.agents.orchestrator.prepare_moderator",
            new=AsyncMock(return_value=_make_valid_moderator_briefing()),
        ),
        patch(
            "srf.agents.orchestrator.prepare_challenger",
            new=AsyncMock(return_value=_make_valid_challenger_prep()),
        ),
    ):
        result = await run_preparation(
            roster=roster,
            workspace=workspace,
            paper_abstracts=paper_abstracts,
            paper_summaries=paper_summaries,
            framing_question="A question?",
            tracker=None,
            config=config,
            state=state,
        )

    assert result["preparation_status"] == "complete"
    assert result["agent_count"] >= 2

    state_data = json.loads((workspace.workspace_path / "state.json").read_text())
    assert state_data["forum_status"] == "preparation_complete"
    assert "prepared_agent_count" in state_data

    for agent in roster.agents:
        if agent.role == "paper_agent":
            artifact_path = workspace.workspace_path / "preparation" / agent.agent_id / "artifact.json"
            assert artifact_path.exists(), f"artifact.json missing for {agent.agent_id}"


# ---------------------------------------------------------------------------
# Scenario: retry on paper agent failure — succeeds on 3rd attempt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_preparation_retries_failed_paper_agent(tmp_path: Path) -> None:
    from srf.agents.orchestrator import run_preparation

    workspace = _make_workspace(tmp_path)
    roster = _make_roster(n_paper_agents=2)
    config = MagicMock()
    config.max_prep_retries = 3
    config.paper_token_budget = 80000
    state: dict = {"trace_id": "t1"}

    call_counts: dict[str, int] = {}

    async def flaky_prepare(assignment, **kw):
        aid = assignment.agent_id
        call_counts[aid] = call_counts.get(aid, 0) + 1
        if aid == "paper-agent-1" and call_counts[aid] < 3:
            raise PreparationError("transient failure")
        return _make_valid_artifact(aid)

    with (
        patch("srf.agents.orchestrator.prepare_paper_agent", new=flaky_prepare),
        patch(
            "srf.agents.orchestrator.prepare_moderator",
            new=AsyncMock(return_value=_make_valid_moderator_briefing()),
        ),
        patch(
            "srf.agents.orchestrator.prepare_challenger",
            new=AsyncMock(return_value=_make_valid_challenger_prep()),
        ),
    ):
        result = await run_preparation(
            roster=roster,
            workspace=workspace,
            paper_abstracts=["Abs1", "Abs2"],
            paper_summaries=["Sum1", "Sum2"],
            framing_question="Q?",
            tracker=None,
            config=config,
            state=state,
        )

    assert call_counts.get("paper-agent-1") == 3
    paper_agent_statuses = {
        a.agent_id: a.status
        for a in result["roster"].agents
        if a.role == "paper_agent"
    }
    assert paper_agent_statuses["paper-agent-1"] == "ok"


# ---------------------------------------------------------------------------
# Scenario: marks agent degraded after retries exhausted; still proceeds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_preparation_marks_agent_degraded_after_retries_exhausted(tmp_path: Path) -> None:
    import structlog.testing

    from srf.agents.orchestrator import run_preparation

    workspace = _make_workspace(tmp_path)
    roster = _make_roster(n_paper_agents=3)
    config = MagicMock()
    config.max_prep_retries = 2
    config.paper_token_budget = 80000
    state: dict = {"trace_id": "t1"}

    async def always_fail_agent1(assignment, **kw):
        if assignment.agent_id == "paper-agent-1":
            raise PreparationError("always fails")
        return _make_valid_artifact(assignment.agent_id)

    with (
        patch("srf.agents.orchestrator.prepare_paper_agent", new=always_fail_agent1),
        patch(
            "srf.agents.orchestrator.prepare_moderator",
            new=AsyncMock(return_value=_make_valid_moderator_briefing()),
        ),
        patch(
            "srf.agents.orchestrator.prepare_challenger",
            new=AsyncMock(return_value=_make_valid_challenger_prep()),
        ),
        structlog.testing.capture_logs() as log_output,
    ):
        result = await run_preparation(
            roster=roster,
            workspace=workspace,
            paper_abstracts=["A1", "A2", "A3"],
            paper_summaries=["S1", "S2", "S3"],
            framing_question="Q?",
            tracker=None,
            config=config,
            state=state,
            min_agents=2,
        )

    agent1 = next(a for a in result["roster"].agents if a.agent_id == "paper-agent-1")
    assert agent1.status == "degraded"

    warning_events = [e for e in log_output if e.get("log_level") == "warning"]
    assert any("paper-agent-1" in str(e) for e in warning_events)


# ---------------------------------------------------------------------------
# Scenario: raises OrchestrationError when degraded drops below min_agents
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_preparation_raises_when_below_min_agents(tmp_path: Path) -> None:
    from srf.agents.models import OrchestrationError
    from srf.agents.orchestrator import run_preparation

    workspace = _make_workspace(tmp_path)
    roster = _make_roster(n_paper_agents=2)
    config = MagicMock()
    config.max_prep_retries = 1
    config.paper_token_budget = 80000
    state: dict = {}

    with (
        patch(
            "srf.agents.orchestrator.prepare_paper_agent",
            new=AsyncMock(side_effect=PreparationError("always fails")),
        ),
        patch(
            "srf.agents.orchestrator.prepare_moderator",
            new=AsyncMock(return_value=_make_valid_moderator_briefing()),
        ),
        patch(
            "srf.agents.orchestrator.prepare_challenger",
            new=AsyncMock(return_value=_make_valid_challenger_prep()),
        ),
        pytest.raises(OrchestrationError, match="insufficient"),
    ):
        await run_preparation(
            roster=roster,
            workspace=workspace,
            paper_abstracts=["A1", "A2"],
            paper_summaries=["S1", "S2"],
            framing_question="Q?",
            tracker=None,
            config=config,
            state=state,
            min_agents=2,
        )


# ---------------------------------------------------------------------------
# Scenario: moderator failure aborts with OrchestrationError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_preparation_aborts_on_moderator_failure(tmp_path: Path) -> None:
    from srf.agents.models import OrchestrationError
    from srf.agents.orchestrator import run_preparation

    workspace = _make_workspace(tmp_path)
    roster = _make_roster(n_paper_agents=2)
    config = MagicMock()
    config.max_prep_retries = 2
    config.paper_token_budget = 80000
    state: dict = {}

    with (
        patch(
            "srf.agents.orchestrator.prepare_paper_agent",
            new=AsyncMock(side_effect=lambda assignment, **kw: _make_valid_artifact(assignment.agent_id)),
        ),
        patch(
            "srf.agents.orchestrator.prepare_moderator",
            new=AsyncMock(side_effect=PreparationError("moderator LLM failure")),
        ),
        patch(
            "srf.agents.orchestrator.prepare_challenger",
            new=AsyncMock(return_value=_make_valid_challenger_prep()),
        ),
        pytest.raises(OrchestrationError, match="[Mm]oderator"),
    ):
        await run_preparation(
            roster=roster,
            workspace=workspace,
            paper_abstracts=["A1", "A2"],
            paper_summaries=["S1", "S2"],
            framing_question="Q?",
            tracker=None,
            config=config,
            state=state,
        )
