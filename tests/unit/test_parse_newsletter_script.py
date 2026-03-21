"""BUG-002 — parse_newsletter.py script call-signature and LLM client extraction tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

FIXTURES = Path(__file__).parent.parent / "fixtures" / "newsletters"


def _mock_llm(clustering_json: str, framing_question: str = "Is retrieval sufficient?") -> MagicMock:
    """Return a mock LLM client that alternates: clustering JSON, then framing question."""
    responses = iter([clustering_json, framing_question])

    class _FakeResult:
        def __init__(self, text: str) -> None:
            self.content = text

    async def _complete(messages: list[dict]) -> _FakeResult:
        return _FakeResult(next(responses))

    llm = MagicMock()
    llm.complete = AsyncMock(side_effect=_complete)
    return llm


# ---------------------------------------------------------------------------
# BUG-002 Scenario: run_pipeline does not raise TypeError from bad call signature
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_pipeline_calls_cluster_papers_correctly(tmp_path: Path) -> None:
    """cluster_papers and generate_candidate_config must be called with keyword args only."""
    from scripts.parse_newsletter import run_pipeline

    clustering = json.dumps({"collective vs individual": ["1. Evaluating Collective Behaviour of Hundreds of LLM Agents", "2. Cognitive Debt in AI-Augmented Research"]})

    llm = _mock_llm(clustering)
    # Should complete without TypeError
    result = await run_pipeline(
        newsletter_path=FIXTURES / "actual_format.md",
        workspace_root=tmp_path,
        dry_run=True,
        llm_client=llm,
        tracker=None,
    )
    assert isinstance(result, list)
    assert len(result) >= 1


# ---------------------------------------------------------------------------
# BUG-002 Scenario: _AnthropicClient.complete() returns .content as string, not list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("anthropic"),
    reason="anthropic package not installed",
)
async def test_anthropic_client_complete_returns_text_string() -> None:
    """_AnthropicClient must return an object whose .content is a plain str, not a list."""
    from unittest.mock import patch

    # Build a fake Anthropic async client whose messages.create returns a response
    fake_text = '{"axis": ["P1", "P2"]}'

    fake_content_block = MagicMock()
    fake_content_block.text = fake_text

    fake_response = MagicMock()
    fake_response.content = [fake_content_block]  # list, as Anthropic SDK returns

    fake_api = MagicMock()
    fake_api.messages.create = AsyncMock(return_value=fake_response)

    import os
    with (
        patch.dict(os.environ, {
            "SRF_LLM_PROVIDER": "anthropic",
            "SRF_LLM_API_KEY": "test-key",
            "SRF_LLM_MODEL": "claude-haiku-4-5-20251001",
        }),
        patch("anthropic.AsyncAnthropic", return_value=fake_api),
    ):
        from scripts.parse_newsletter import _build_stub_llm_client
        client = _build_stub_llm_client()

    result = await client.complete([{"role": "user", "content": "hello"}])
    assert isinstance(result.content, str), f"Expected str, got {type(result.content)}"
    assert result.content == fake_text
