"""Story 5.5 — preparation integration tests (real LLM provider).

Run with:
    SRF_LLM_PROVIDER=anthropic SRF_LLM_MODEL=claude-haiku-4-5-20251001 \
    SRF_LLM_API_KEY=sk-... pytest tests/integration/test_preparation_integration.py -v
"""

from __future__ import annotations

import os

import pytest


@pytest.mark.skipif(
    not os.environ.get("SRF_LLM_PROVIDER"),
    reason="SRF_LLM_PROVIDER not set — skipping live preparation test",
)
@pytest.mark.asyncio
async def test_prepare_paper_agent_real_call(tmp_path) -> None:
    from srf.agents.models import AgentAssignment
    from srf.agents.preparation import prepare_paper_agent
    from srf.config import SRFConfig
    from srf.extraction.models import PaperContent

    config = SRFConfig.from_env()
    assignment = AgentAssignment(
        agent_id="paper-agent-1",
        role="paper_agent",
        arxiv_id="2401.00001",
    )
    paper = PaperContent(
        arxiv_id="2401.00001",
        pdf_path=None,
        full_text=(
            "Abstract: This paper presents a novel approach to machine learning. "
            "Introduction: We study the problem of efficient training. "
            "Conclusion: Our method improves accuracy by 10%."
        ),
        abstract="This paper presents a novel approach to machine learning.",
        page_count=3,
        extraction_status="ok",
    )

    result = await prepare_paper_agent(
        assignment=assignment,
        paper_content=paper,
        framing_question="Does this approach improve over baselines?",
        tracker=None,
        config=config,
        state={},
        memory_block="",
    )

    assert result.agent_id == "paper-agent-1"
    assert result.claimed_position
    assert len(result.key_arguments) >= 2
    assert len(result.anticipated_objections) >= 1
    assert 0.0 <= result.epistemic_confidence <= 1.0
