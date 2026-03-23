"""Story 5.3 — prepare_paper_agent() unit tests."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from srf.agents.models import AgentAssignment
from srf.extraction.models import PaperContent


def _make_assignment(agent_id: str = "paper-agent-1") -> AgentAssignment:
    return AgentAssignment(
        agent_id=agent_id,
        role="paper_agent",
        arxiv_id="2401.00001",
    )


def _make_paper(full_text: str = "This is the full text of the paper.") -> PaperContent:
    return PaperContent(
        arxiv_id="2401.00001",
        pdf_path=None,
        full_text=full_text,
        abstract="This is the abstract.",
        page_count=1,
        extraction_status="ok",
    )


def _valid_artifact_json(agent_id: str = "paper-agent-1") -> str:
    return json.dumps({
        "agent_id": agent_id,
        "claimed_position": "The paper makes a strong empirical case for X.",
        "key_arguments": ["Argument one", "Argument two"],
        "anticipated_objections": ["Objection one"],
        "epistemic_confidence": 0.8,
    })


def _make_mock_tracker(response_text: str | None = None, span_id: str = "span-001") -> MagicMock:
    mock_result = MagicMock()
    mock_result.response_text = response_text or _valid_artifact_json()
    mock_result.span_id = span_id

    tracker = MagicMock()
    tracker.execute = AsyncMock(return_value=mock_result)
    return tracker


# ---------------------------------------------------------------------------
# Scenario: returns PreparationArtifact with all required fields
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prepare_paper_agent_returns_artifact_with_required_fields() -> None:
    from srf.agents.preparation import prepare_paper_agent

    assignment = _make_assignment()
    paper = _make_paper()
    tracker = _make_mock_tracker()
    config = MagicMock()
    config.paper_token_budget = 80000
    state: dict = {"trace_id": "t1"}

    result = await prepare_paper_agent(
        assignment=assignment,
        paper_content=paper,
        framing_question="Is X better than Y?",
        tracker=tracker,
        config=config,
        state=state,
        memory_block="",
    )

    assert result.agent_id == "paper-agent-1"
    assert isinstance(result.claimed_position, str) and result.claimed_position
    assert isinstance(result.key_arguments, list) and len(result.key_arguments) >= 2
    assert isinstance(result.anticipated_objections, list) and len(result.anticipated_objections) >= 1
    assert isinstance(result.epistemic_confidence, float)
    assert 0.0 <= result.epistemic_confidence <= 1.0


# ---------------------------------------------------------------------------
# Scenario: truncates paper text to SRF_PAPER_TOKEN_BUDGET
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prepare_paper_agent_truncates_long_paper_text() -> None:
    import structlog.testing

    from srf.agents.preparation import prepare_paper_agent

    budget = 100
    long_text = "A" * (budget + 500) + ". Extra text."
    paper = _make_paper(full_text=long_text)
    assignment = _make_assignment()
    tracker = _make_mock_tracker()
    config = MagicMock()
    config.paper_token_budget = budget
    state: dict = {}

    captured_messages: list = []

    async def capture_execute(**kwargs):
        captured_messages.extend(kwargs.get("messages", []))
        mock_result = MagicMock()
        mock_result.response_text = _valid_artifact_json()
        mock_result.span_id = "span-001"
        return mock_result

    tracker.execute = capture_execute

    with structlog.testing.capture_logs() as log_output:
        await prepare_paper_agent(
            assignment=assignment,
            paper_content=paper,
            framing_question="A question?",
            tracker=tracker,
            config=config,
            state=state,
            memory_block="",
        )

    user_messages = [m for m in captured_messages if m["role"] == "user"]
    assert user_messages, "No user messages captured"
    user_content = user_messages[0]["content"]
    # The paper text was "A" * (budget + 500) + ". Extra text." — after truncation it must
    # not contain the full original length of "A"s
    assert "A" * (budget + 500) not in user_content, (
        "Paper text was not truncated — full oversized text found in user content"
    )

    warning_events = [e for e in log_output if e.get("log_level") == "warning"]
    assert any("2401.00001" in str(e) for e in warning_events), (
        "Expected truncation WARNING with arxiv_id not found"
    )


# ---------------------------------------------------------------------------
# Scenario: empty memory_block renders without error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prepare_paper_agent_empty_memory_block() -> None:
    from srf.agents.preparation import prepare_paper_agent

    assignment = _make_assignment()
    paper = _make_paper()
    tracker = _make_mock_tracker()
    config = MagicMock()
    config.paper_token_budget = 80000
    state: dict = {}

    captured_messages: list = []

    async def capture_execute(**kwargs):
        captured_messages.extend(kwargs.get("messages", []))
        mock_result = MagicMock()
        mock_result.response_text = _valid_artifact_json()
        mock_result.span_id = "span-001"
        return mock_result

    tracker.execute = capture_execute

    result = await prepare_paper_agent(
        assignment=assignment,
        paper_content=paper,
        framing_question="A question?",
        tracker=tracker,
        config=config,
        state=state,
        memory_block="",
    )

    # No error raised
    assert result is not None
    # System message should not contain literal "{memory_block}" (it was rendered)
    system_messages = [m for m in captured_messages if m["role"] == "system"]
    assert system_messages
    assert "{memory_block}" not in system_messages[0]["content"]


# ---------------------------------------------------------------------------
# Scenario: calls tracker.execute with correct prompt_name and agent_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prepare_paper_agent_calls_tracker_execute_correctly() -> None:
    from srf.agents.preparation import prepare_paper_agent

    assignment = _make_assignment(agent_id="paper-agent-2")
    paper = _make_paper()
    tracker = _make_mock_tracker(span_id="span-xyz")
    config = MagicMock()
    config.paper_token_budget = 80000
    state: dict = {"trace_id": "t1"}

    await prepare_paper_agent(
        assignment=assignment,
        paper_content=paper,
        framing_question="A question?",
        tracker=tracker,
        config=config,
        state=state,
        memory_block="",
    )

    tracker.execute.assert_called_once()
    call_kwargs = tracker.execute.call_args.kwargs
    assert call_kwargs.get("prompt_name") == "agent.paper_preparation"
    assert call_kwargs.get("agent_id") == "paper-agent-2"
    assert state["last_span_id"] == "span-xyz"


# ---------------------------------------------------------------------------
# Scenario: tracker=None path calls call_provider_directly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prepare_paper_agent_tracker_none_uses_fallback() -> None:
    from unittest.mock import patch

    from srf.agents.preparation import prepare_paper_agent

    assignment = _make_assignment()
    paper = _make_paper()
    config = MagicMock()
    config.paper_token_budget = 80000
    state: dict = {}

    with patch(
        "srf.agents.preparation.call_provider_directly",
        new=AsyncMock(return_value=_valid_artifact_json()),
    ) as mock_fallback:
        result = await prepare_paper_agent(
            assignment=assignment,
            paper_content=paper,
            framing_question="A question?",
            tracker=None,
            config=config,
            state=state,
            memory_block="",
        )

    assert result is not None
    mock_fallback.assert_called_once()


# ---------------------------------------------------------------------------
# Scenario: raises PreparationError when LLM returns malformed JSON
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prepare_paper_agent_raises_on_malformed_json() -> None:
    from srf.agents.models import PreparationError
    from srf.agents.preparation import prepare_paper_agent

    assignment = _make_assignment()
    paper = _make_paper()
    tracker = _make_mock_tracker(response_text="not-json")
    config = MagicMock()
    config.paper_token_budget = 80000
    state: dict = {}

    with pytest.raises(PreparationError, match="parse"):
        await prepare_paper_agent(
            assignment=assignment,
            paper_content=paper,
            framing_question="A question?",
            tracker=tracker,
            config=config,
            state=state,
            memory_block="",
        )


# ---------------------------------------------------------------------------
# Scenario: paper_preparation prompt registered and contains required slots
# ---------------------------------------------------------------------------


def test_paper_preparation_prompt_has_required_slots() -> None:
    from srf.prompts.agents import AGENT_PROMPTS

    prompt = next((p for p in AGENT_PROMPTS if p["name"] == "agent.paper_preparation"), None)
    assert prompt is not None, "agent.paper_preparation not found in AGENT_PROMPTS"

    template = prompt["template_source"]
    assert "{paper_text}" in template
    assert "{framing_question}" in template
    assert "{memory_block}" in template


# ---------------------------------------------------------------------------
# BUG-008: tracker.execute() must include model field for PL /v1/executions/run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prepare_paper_agent_passes_model_to_tracker_execute() -> None:
    """prepare_paper_agent must pass model={provider, model_name} to tracker.execute().

    BUG-008: PL /v1/executions/run requires a model field. Our execute() calls
    were missing it, causing HTTP 500 KeyError: 'model' on every agent prep call.
    """
    from srf.agents.preparation import prepare_paper_agent

    assignment = _make_assignment(agent_id="paper-agent-1")
    paper = _make_paper()
    tracker = _make_mock_tracker(span_id="span-bug008")
    config = MagicMock()
    config.paper_token_budget = 80000
    config.llm_provider = "anthropic"
    config.llm_model = "claude-sonnet-4-6"
    state: dict = {"trace_id": "t1"}

    await prepare_paper_agent(
        assignment=assignment,
        paper_content=paper,
        framing_question="A question?",
        tracker=tracker,
        config=config,
        state=state,
        memory_block="",
    )

    call_kwargs = tracker.execute.call_args.kwargs
    assert "model" in call_kwargs, "tracker.execute() must include model kwarg (BUG-008)"
    assert call_kwargs["model"] == {"provider": "anthropic", "model_name": "claude-sonnet-4-6"}
