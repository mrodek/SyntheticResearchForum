"""Story 1.4 — PromptLedger Observability integration test.

Requires live PROMPTLEDGER_API_URL and PROMPTLEDGER_API_KEY env vars.
Skipped automatically when those vars are absent.
"""

from __future__ import annotations

import os

import pytest

_PL_CONFIGURED = bool(
    os.environ.get("PROMPTLEDGER_API_URL") and os.environ.get("PROMPTLEDGER_API_KEY")
)


@pytest.mark.skipif(not _PL_CONFIGURED, reason="PromptLedger not configured")
@pytest.mark.asyncio
async def test_register_prompts_integration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario: register_prompts calls register_code_prompts when tracker is provided.

    Requires a live PromptLedger instance.
    """
    from srf.config import SRFConfig
    from srf.observability import build_tracker, register_prompts

    monkeypatch.setenv("SRF_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("SRF_LLM_MODEL", "claude-sonnet-4-6")
    monkeypatch.setenv("SRF_LLM_API_KEY", "test-key")

    config = SRFConfig.from_env()
    tracker = build_tracker(config)
    assert tracker is not None, "Expected a live tracker"

    try:
        from promptledger_client.models import RegistrationPayload  # type: ignore[import]

        payloads = [
            RegistrationPayload(
                name="srf.integration.test_prompt",
                template_source="You are a test agent. Respond with: OK",
                description="Integration test probe prompt",
                owner_team="SRF",
            )
        ]
    except ImportError:
        pytest.skip("promptledger-client SDK not installed")

    # Should not raise; response indicates registered or unchanged
    await register_prompts(tracker=tracker, prompts=payloads)
