"""Story 1.4 — PromptLedger Observability Module unit tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


def _make_config(
    monkeypatch: pytest.MonkeyPatch,
    pl_url: str | None = None,
    pl_key: str | None = None,
) -> SRFConfig:  # noqa: F821
    from srf.config import SRFConfig

    monkeypatch.setenv("SRF_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("SRF_LLM_MODEL", "claude-sonnet-4-6")
    monkeypatch.setenv("SRF_LLM_API_KEY", "test-key")

    if pl_url:
        monkeypatch.setenv("PROMPTLEDGER_API_URL", pl_url)
    else:
        monkeypatch.delenv("PROMPTLEDGER_API_URL", raising=False)

    if pl_key:
        monkeypatch.setenv("PROMPTLEDGER_API_KEY", pl_key)
    else:
        monkeypatch.delenv("PROMPTLEDGER_API_KEY", raising=False)

    monkeypatch.delenv("SRF_WORKSPACE_ROOT", raising=False)
    monkeypatch.delenv("SRF_LOG_LEVEL", raising=False)

    return SRFConfig.from_env()


# ---------------------------------------------------------------------------
# Scenario: tracker is None when PROMPTLEDGER_API_URL is absent
# ---------------------------------------------------------------------------

def test_build_tracker_returns_none_when_url_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from srf.observability import build_tracker

    config = _make_config(monkeypatch, pl_url=None, pl_key=None)
    tracker = build_tracker(config)
    assert tracker is None


# ---------------------------------------------------------------------------
# Scenario: tracker is an AsyncPromptLedgerClient when both PL vars are set
# ---------------------------------------------------------------------------

def test_build_tracker_returns_client_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from srf.observability import build_tracker

    mock_client_cls = MagicMock(return_value=MagicMock())

    # Patch the import so we don't need the real SDK installed
    mock_module = MagicMock()
    mock_module.AsyncPromptLedgerClient = mock_client_cls
    monkeypatch.setitem(__import__("sys").modules, "promptledger_client", mock_module)

    config = _make_config(
        monkeypatch, pl_url="https://pl.example.com", pl_key="pl-key"
    )
    tracker = build_tracker(config)
    assert tracker is not None
    mock_client_cls.assert_called_once_with(
        base_url="https://pl.example.com", api_key="pl-key"
    )


# ---------------------------------------------------------------------------
# Scenario: build_tracker logs a warning and returns None if SDK import fails
# ---------------------------------------------------------------------------

def test_build_tracker_returns_none_on_import_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    # Remove any cached promptledger_client module so the import fails
    monkeypatch.delitem(sys.modules, "promptledger_client", raising=False)

    # Ensure the import actually fails
    import builtins
    original_import = builtins.__import__

    def mock_import(name: str, *args, **kwargs):
        if name == "promptledger_client":
            raise ImportError("SDK not installed")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    from srf.observability import build_tracker

    config = _make_config(
        monkeypatch, pl_url="https://pl.example.com", pl_key="pl-key"
    )
    tracker = build_tracker(config)
    assert tracker is None


# ---------------------------------------------------------------------------
# Scenario: register_prompts is a no-op when tracker is None
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_prompts_noop_when_tracker_none() -> None:
    from srf.observability import register_prompts

    # Should return without error, no calls made
    await register_prompts(tracker=None, prompts=[])


# ---------------------------------------------------------------------------
# Scenario: register_prompts calls register_code_prompts when tracker is provided
# Unit-level: mock tracker, no live network
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_prompts_calls_tracker() -> None:
    from srf.observability import register_prompts

    mock_tracker = AsyncMock()
    mock_tracker.register_code_prompts = AsyncMock()

    payloads = [MagicMock()]
    await register_prompts(tracker=mock_tracker, prompts=payloads)

    mock_tracker.register_code_prompts.assert_awaited_once_with(payloads)
