"""Story 5.1 — call_provider_directly() unit tests."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from srf.config import ConfigurationError, SRFConfig


def _make_config(provider: str = "anthropic") -> SRFConfig:
    return SRFConfig(
        llm_provider=provider,
        llm_model="test-model",
        llm_api_key="test-key",
        workspace_root=__import__("pathlib").Path("/tmp/workspace"),
        log_level="INFO",
        promptledger_enabled=False,
        promptledger_api_url=None,
        promptledger_api_key=None,
        arxiv_delay_seconds=3.0,
        min_papers=2,
        paper_token_budget=80000,
        max_prep_retries=3,
    )


# ---------------------------------------------------------------------------
# Scenario: anthropic provider returns response text
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_provider_directly_anthropic_returns_text() -> None:
    config = _make_config(provider="anthropic")

    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="Hello")]

    mock_client = MagicMock()
    mock_client.messages = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_message)

    mock_anthropic = MagicMock()
    mock_anthropic.AsyncAnthropic.return_value = mock_client

    with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
        from srf.llm.fallback import call_provider_directly

        result = await call_provider_directly(
            messages=[{"role": "user", "content": "hi"}],
            config=config,
        )

    assert result == "Hello"


# ---------------------------------------------------------------------------
# Scenario: openai provider returns response text
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_provider_directly_openai_returns_text() -> None:
    config = _make_config(provider="openai")

    mock_choice = MagicMock()
    mock_choice.message.content = "Hello"

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    mock_openai = MagicMock()
    mock_openai.AsyncOpenAI.return_value = mock_client

    with patch.dict(sys.modules, {"openai": mock_openai}):
        from srf.llm.fallback import call_provider_directly

        result = await call_provider_directly(
            messages=[{"role": "user", "content": "hi"}],
            config=config,
        )

    assert result == "Hello"


# ---------------------------------------------------------------------------
# Scenario: unsupported provider raises ConfigurationError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_provider_directly_unsupported_provider_raises() -> None:
    # Bypass SRFConfig validation by building directly
    config = SRFConfig(
        llm_provider="unsupported_provider",
        llm_model="test-model",
        llm_api_key="test-key",
        workspace_root=__import__("pathlib").Path("/tmp/workspace"),
        log_level="INFO",
        promptledger_enabled=False,
        promptledger_api_url=None,
        promptledger_api_key=None,
        arxiv_delay_seconds=3.0,
        min_papers=2,
        paper_token_budget=80000,
        max_prep_retries=3,
    )

    from srf.llm.fallback import call_provider_directly

    with pytest.raises(ConfigurationError, match="unsupported_provider"):
        await call_provider_directly(
            messages=[{"role": "user", "content": "hi"}],
            config=config,
        )


# ---------------------------------------------------------------------------
# Scenario: provider 5xx raises LLMError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_provider_directly_raises_llm_error_on_api_error() -> None:
    config = _make_config(provider="anthropic")

    mock_client = MagicMock()
    mock_client.messages = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=Exception("Status 500: internal server error"))

    mock_anthropic = MagicMock()
    mock_anthropic.AsyncAnthropic.return_value = mock_client

    with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
        from srf.llm.fallback import LLMError, call_provider_directly

        with pytest.raises(LLMError, match="500"):
            await call_provider_directly(
                messages=[{"role": "user", "content": "hi"}],
                config=config,
            )


# ---------------------------------------------------------------------------
# Scenario: non-configured provider SDK not imported at module top level
# ---------------------------------------------------------------------------


def test_fallback_module_does_not_import_openai_at_top_level() -> None:
    """When fallback.py is imported, only the configured provider's SDK is used
    lazily inside the function body — never at module import time."""
    # Remove cached module to force fresh import inspection
    for mod_name in list(sys.modules.keys()):
        if "srf.llm" in mod_name:
            del sys.modules[mod_name]

    # Ensure openai is not already imported
    openai_was_present = "openai" in sys.modules

    import srf.llm.fallback  # noqa: F401  # trigger module load

    # After importing the module itself (not calling functions), openai should
    # not have been newly imported unless it was already present
    if not openai_was_present:
        assert "openai" not in sys.modules, (
            "fallback.py imported 'openai' at module level — it must be lazy-imported"
        )


def test_fallback_module_does_not_import_anthropic_at_top_level() -> None:
    for mod_name in list(sys.modules.keys()):
        if "srf.llm" in mod_name:
            del sys.modules[mod_name]

    anthropic_was_present = "anthropic" in sys.modules

    import srf.llm.fallback  # noqa: F401

    if not anthropic_was_present:
        assert "anthropic" not in sys.modules, (
            "fallback.py imported 'anthropic' at module level — it must be lazy-imported"
        )
