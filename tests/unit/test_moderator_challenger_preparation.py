"""Story 5.4 — prepare_moderator() and prepare_challenger() unit tests."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from srf.agents.models import AgentAssignment, AgentRoster


def _make_roster() -> AgentRoster:
    return AgentRoster(
        forum_id="forum-20260317-abcdef01",
        agents=[
            AgentAssignment(agent_id="paper-agent-1", role="paper_agent", arxiv_id="2401.00001"),
            AgentAssignment(agent_id="paper-agent-2", role="paper_agent", arxiv_id="2401.00002"),
            AgentAssignment(agent_id="moderator", role="moderator", arxiv_id=None),
            AgentAssignment(agent_id="challenger", role="challenger", arxiv_id=None),
        ],
    )


def _valid_moderator_json() -> str:
    return json.dumps({
        "debate_agenda": ["Discuss methodology", "Compare results", "Evaluate implications"],
        "agent_profiles": [
            {"agent_id": "paper-agent-1", "assigned_paper": "2401.00001", "expected_position": "Pro X"},
            {"agent_id": "paper-agent-2", "assigned_paper": "2401.00002", "expected_position": "Pro Y"},
        ],
        "escalation_policy": "Redirect off-topic turns; summarise after 3 repetitive turns.",
    })


def _valid_challenger_json() -> str:
    return json.dumps({
        "skeptical_stance": "The empirical evidence for X is insufficient.",
        "challenge_angles": ["Methodology weakness", "Sample size concerns"],
        "anticipated_defenses": ["Authors control for confounders"],
    })


def _make_mock_tracker(response_text: str, span_id: str = "span-001") -> MagicMock:
    mock_result = MagicMock()
    mock_result.response_text = response_text
    mock_result.span_id = span_id

    tracker = MagicMock()
    tracker.execute = AsyncMock(return_value=mock_result)
    return tracker


# ---------------------------------------------------------------------------
# Scenario: prepare_moderator returns ModeratorBriefing with required fields
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prepare_moderator_returns_briefing_with_required_fields() -> None:
    from srf.agents.preparation import prepare_moderator

    roster = _make_roster()
    tracker = _make_mock_tracker(_valid_moderator_json())
    config = MagicMock()
    state: dict = {"trace_id": "t1"}

    result = await prepare_moderator(
        roster=roster,
        framing_question="Is X better than Y?",
        paper_summaries=["Summary of paper 1", "Summary of paper 2"],
        tracker=tracker,
        config=config,
        state=state,
        memory_block="",
    )

    assert isinstance(result.debate_agenda, list) and len(result.debate_agenda) >= 3
    assert isinstance(result.agent_profiles, list)
    assert len(result.agent_profiles) == 2  # one per paper agent in roster
    assert isinstance(result.escalation_policy, str) and result.escalation_policy


# ---------------------------------------------------------------------------
# Scenario: prepare_moderator uses paper summaries not full text
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prepare_moderator_uses_summaries_not_full_text() -> None:
    from srf.agents.preparation import prepare_moderator

    roster = _make_roster()
    captured_messages: list = []

    async def capture_execute(**kwargs):
        captured_messages.extend(kwargs.get("messages", []))
        mock_result = MagicMock()
        mock_result.response_text = _valid_moderator_json()
        mock_result.span_id = "span-001"
        return mock_result

    tracker = MagicMock()
    tracker.execute = capture_execute
    config = MagicMock()
    state: dict = {}

    await prepare_moderator(
        roster=roster,
        framing_question="A question?",
        paper_summaries=["Short summary A", "Short summary B"],
        tracker=tracker,
        config=config,
        state=state,
        memory_block="",
    )

    user_messages = [m for m in captured_messages if m["role"] == "user"]
    assert user_messages
    user_content = user_messages[0]["content"]
    assert "Short summary A" in user_content
    assert "Short summary B" in user_content
    assert "full_text" not in user_content


# ---------------------------------------------------------------------------
# Scenario: prepare_moderator calls tracker.execute with correct prompt_name
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prepare_moderator_calls_tracker_execute_correctly() -> None:
    from srf.agents.preparation import prepare_moderator

    roster = _make_roster()
    tracker = _make_mock_tracker(_valid_moderator_json(), span_id="span-mod-001")
    config = MagicMock()
    state: dict = {"trace_id": "t1"}

    await prepare_moderator(
        roster=roster,
        framing_question="A question?",
        paper_summaries=["Summary 1", "Summary 2"],
        tracker=tracker,
        config=config,
        state=state,
        memory_block="",
    )

    tracker.execute.assert_called_once()
    call_kwargs = tracker.execute.call_args.kwargs
    assert call_kwargs.get("prompt_name") == "agent.moderator_briefing"
    assert state["last_span_id"] == "span-mod-001"


# ---------------------------------------------------------------------------
# Scenario: prepare_challenger returns ChallengerPreparation with required fields
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prepare_challenger_returns_preparation_with_required_fields() -> None:
    from srf.agents.preparation import prepare_challenger

    roster = _make_roster()
    tracker = _make_mock_tracker(_valid_challenger_json())
    config = MagicMock()
    state: dict = {"trace_id": "t1"}

    result = await prepare_challenger(
        roster=roster,
        framing_question="Is X better than Y?",
        paper_abstracts=["Abstract of paper 1", "Abstract of paper 2"],
        tracker=tracker,
        config=config,
        state=state,
        memory_block="",
    )

    assert isinstance(result.skeptical_stance, str) and result.skeptical_stance
    assert isinstance(result.challenge_angles, list) and len(result.challenge_angles) >= 2
    assert isinstance(result.anticipated_defenses, list) and len(result.anticipated_defenses) >= 1


# ---------------------------------------------------------------------------
# Scenario: prepare_challenger calls tracker.execute with correct prompt_name
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prepare_challenger_calls_tracker_execute_correctly() -> None:
    from srf.agents.preparation import prepare_challenger

    roster = _make_roster()
    tracker = _make_mock_tracker(_valid_challenger_json(), span_id="span-chal-001")
    config = MagicMock()
    state: dict = {"trace_id": "t1"}

    await prepare_challenger(
        roster=roster,
        framing_question="A question?",
        paper_abstracts=["Abstract 1", "Abstract 2"],
        tracker=tracker,
        config=config,
        state=state,
        memory_block="",
    )

    tracker.execute.assert_called_once()
    call_kwargs = tracker.execute.call_args.kwargs
    assert call_kwargs.get("prompt_name") == "agent.challenger_preparation"
    assert state["last_span_id"] == "span-chal-001"


# ---------------------------------------------------------------------------
# Scenario: moderator_briefing prompt contains required slots
# ---------------------------------------------------------------------------


def test_moderator_briefing_prompt_has_required_slots() -> None:
    from srf.prompts.agents import AGENT_PROMPTS

    prompt = next((p for p in AGENT_PROMPTS if p["name"] == "agent.moderator_briefing"), None)
    assert prompt is not None, "agent.moderator_briefing not found in AGENT_PROMPTS"

    template = prompt["template_source"]
    assert "{framing_question}" in template
    assert "{paper_summaries}" in template
    assert "{agent_roster}" in template
    assert "{memory_block}" in template


# ---------------------------------------------------------------------------
# Scenario: challenger_preparation prompt contains required slots
# ---------------------------------------------------------------------------


def test_challenger_preparation_prompt_has_required_slots() -> None:
    from srf.prompts.agents import AGENT_PROMPTS

    prompt = next((p for p in AGENT_PROMPTS if p["name"] == "agent.challenger_preparation"), None)
    assert prompt is not None, "agent.challenger_preparation not found in AGENT_PROMPTS"

    template = prompt["template_source"]
    assert "{framing_question}" in template
    assert "{paper_abstracts}" in template
    assert "{memory_block}" in template
