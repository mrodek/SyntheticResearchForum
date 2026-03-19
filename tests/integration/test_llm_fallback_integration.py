"""Story 5.1 — call_provider_directly() integration test (real LLM provider).

Run with:
    SRF_LLM_PROVIDER=anthropic SRF_LLM_MODEL=claude-haiku-4-5-20251001 \
    SRF_LLM_API_KEY=sk-... pytest tests/integration/test_llm_fallback_integration.py -v
"""

from __future__ import annotations

import os

import pytest


@pytest.mark.skipif(
    not os.environ.get("SRF_LLM_PROVIDER"),
    reason="SRF_LLM_PROVIDER not set — skipping live LLM test",
)
@pytest.mark.asyncio
async def test_call_provider_directly_real_call() -> None:
    from srf.config import SRFConfig
    from srf.llm.fallback import call_provider_directly

    config = SRFConfig.from_env()
    result = await call_provider_directly(
        messages=[{"role": "user", "content": "Reply with the word PONG only."}],
        config=config,
    )

    assert "PONG" in result.upper()
