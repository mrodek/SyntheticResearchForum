"""Shared pytest fixtures for the SRF test suite."""

import os

import pytest


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove all SRF_ and PROMPTLEDGER_ env vars for isolation."""
    for key in list(os.environ.keys()):
        if key.startswith(("SRF_", "PROMPTLEDGER_")):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture
def minimal_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set the minimum required SRF env vars (no PromptLedger)."""
    monkeypatch.setenv("SRF_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("SRF_LLM_MODEL", "claude-sonnet-4-6")
    monkeypatch.setenv("SRF_LLM_API_KEY", "test-api-key")
    monkeypatch.delenv("PROMPTLEDGER_API_URL", raising=False)
    monkeypatch.delenv("PROMPTLEDGER_API_KEY", raising=False)
    monkeypatch.delenv("SRF_WORKSPACE_ROOT", raising=False)
    monkeypatch.delenv("SRF_LOG_LEVEL", raising=False)
