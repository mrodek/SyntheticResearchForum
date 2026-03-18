"""Story 3.3 — Forum Config Generation acceptance tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
import structlog.testing

from tests.fixtures.newsletters._builders import make_cluster, make_signal

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_execute_result(response_text: str, span_id: str = "span-framing-001") -> MagicMock:
    result = MagicMock()
    result.response_text = response_text
    result.span_id = span_id
    return result


def _mock_tracker(response_text: str, span_id: str = "span-framing-001") -> MagicMock:
    """Mock tracker whose execute() returns a valid ExecutionResult and writes state."""

    async def _execute(**kwargs):
        state = kwargs.get("state", {})
        state["last_span_id"] = span_id
        return _mock_execute_result(response_text, span_id)

    tracker = MagicMock()
    tracker.execute = AsyncMock(side_effect=_execute)
    return tracker


def _mock_llm(response_content: str) -> MagicMock:
    """Fallback llm_client for tracker=None tests."""
    resp = MagicMock()
    resp.content = response_content
    llm = MagicMock()
    llm.complete = AsyncMock(return_value=resp)
    return llm


# ---------------------------------------------------------------------------
# Scenario: generate_candidate_config returns a CandidateForumConfig
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_returns_candidate_forum_config() -> None:
    from srf.newsletter.config_generator import generate_candidate_config
    from srf.newsletter.models import CandidateForumConfig

    cluster = make_cluster(
        tension_axis="efficiency vs alignment",
        signals=[make_signal("P1"), make_signal("P2"), make_signal("P3")],
    )
    framing = "Does optimising for efficiency inevitably erode alignment guarantees?"
    tracker = _mock_tracker(framing)

    result = await generate_candidate_config(cluster, tracker=tracker, state={"trace_id": "t1"})

    assert isinstance(result, CandidateForumConfig)
    assert result.topic  # non-empty, derived from tension
    assert result.framing_question == framing
    assert len(result.paper_refs) == 3
    assert result.generated_at  # ISO-8601 string


# ---------------------------------------------------------------------------
# Scenario: generate_candidate_config calls tracker.execute with the correct prompt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_calls_tracker_execute_with_correct_prompt() -> None:
    from srf.newsletter.config_generator import generate_candidate_config
    from srf.prompts.newsletter import FRAMING_QUESTION_PROMPT

    cluster = make_cluster(
        tension_axis="centralised vs distributed",
        signals=[make_signal("Alpha"), make_signal("Beta")],
    )

    captured_kwargs: list[dict] = []

    async def capturing_execute(**kwargs):
        captured_kwargs.append(kwargs)
        state = kwargs.get("state", {})
        state["last_span_id"] = "span-001"
        return _mock_execute_result("Is centralisation the right trade-off?")

    tracker = MagicMock()
    tracker.execute = AsyncMock(side_effect=capturing_execute)

    await generate_candidate_config(cluster, tracker=tracker, state={"trace_id": "t1"})

    assert len(captured_kwargs) == 1
    kw = captured_kwargs[0]
    assert kw["prompt_name"] == "newsletter.framing_question"
    assert kw["mode"] == "mode2"

    messages = kw["messages"]
    system_msg = next(m for m in messages if m["role"] == "system")
    user_msg = next(m for m in messages if m["role"] == "user")

    assert FRAMING_QUESTION_PROMPT in system_msg["content"]
    assert "Alpha" in user_msg["content"]
    assert "Beta" in user_msg["content"]
    assert "centralised vs distributed" in user_msg["content"]


# ---------------------------------------------------------------------------
# Scenario: generate_candidate_config writes last_span_id to state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_writes_last_span_id_to_state() -> None:
    from srf.newsletter.config_generator import generate_candidate_config

    cluster = make_cluster()
    state: dict = {"trace_id": "trace-001"}
    tracker = _mock_tracker("A framing question.", span_id="span-framing-001")

    await generate_candidate_config(cluster, tracker=tracker, state=state)

    assert state["last_span_id"] == "span-framing-001"


# ---------------------------------------------------------------------------
# Scenario: generate_candidate_config completes without error when tracker is None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_no_error_when_tracker_none() -> None:
    from srf.newsletter.config_generator import generate_candidate_config
    from srf.newsletter.models import CandidateForumConfig

    cluster = make_cluster()
    llm = _mock_llm("A valid framing question.")

    result = await generate_candidate_config(cluster, tracker=None, state={}, llm_client=llm)
    assert isinstance(result, CandidateForumConfig)


# ---------------------------------------------------------------------------
# Scenario: generate_candidate_config propagates execute() failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_propagates_execute_failure() -> None:
    """A failed tracker.execute() is a hard LLM failure — it propagates, not swallows."""
    from srf.newsletter.config_generator import generate_candidate_config

    import httpx

    cluster = make_cluster()

    async def raise_503(**_kwargs):
        resp = MagicMock()
        resp.status_code = 503
        raise httpx.HTTPStatusError("503", request=MagicMock(), response=resp)

    tracker = MagicMock()
    tracker.execute = AsyncMock(side_effect=raise_503)

    with pytest.raises(httpx.HTTPStatusError):
        await generate_candidate_config(
            cluster, tracker=tracker, state={"trace_id": "t1"}
        )


# ---------------------------------------------------------------------------
# Scenario: generate_candidate_config raises ConfigGenerationError on empty response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_raises_on_empty_llm_response() -> None:
    from srf.newsletter.config_generator import generate_candidate_config
    from srf.newsletter.models import ConfigGenerationError

    cluster = make_cluster()
    tracker = _mock_tracker("")

    with pytest.raises(ConfigGenerationError, match="(?i)empty"):
        await generate_candidate_config(cluster, tracker=tracker, state={})


# ---------------------------------------------------------------------------
# Scenario: framing question prompt is registered in the prompt registry
# ---------------------------------------------------------------------------


def test_framing_question_prompt_is_registered() -> None:
    from srf.prompts.newsletter import NEWSLETTER_PROMPTS

    names = [p["name"] for p in NEWSLETTER_PROMPTS]
    assert "newsletter.framing_question" in names

    framing_entry = next(p for p in NEWSLETTER_PROMPTS if p["name"] == "newsletter.framing_question")
    assert "{tension_axes}" in framing_entry["template_source"]
    assert "{paper_titles}" in framing_entry["template_source"]
