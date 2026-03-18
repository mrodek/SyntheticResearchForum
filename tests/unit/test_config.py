"""Story 1.2 — Configuration Module acceptance tests."""

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load(monkeypatch: pytest.MonkeyPatch, **overrides: str | None) -> "SRFConfig":  # noqa: F821
    """Import fresh SRFConfig and call from_env() with patched environment."""
    from srf.config import SRFConfig

    # Provide sensible defaults then apply overrides
    defaults = {
        "SRF_LLM_PROVIDER": "anthropic",
        "SRF_LLM_MODEL": "claude-sonnet-4-6",
        "SRF_LLM_API_KEY": "test-key",
        "PROMPTLEDGER_API_URL": None,
        "PROMPTLEDGER_API_KEY": None,
        "SRF_WORKSPACE_ROOT": None,
        "SRF_LOG_LEVEL": None,
    }
    defaults.update(overrides)

    for key, value in defaults.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)

    return SRFConfig.from_env()


# ---------------------------------------------------------------------------
# Scenario: config loads successfully when all required vars are set
# ---------------------------------------------------------------------------

def test_config_loads_with_all_required_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _load(
        monkeypatch,
        SRF_LLM_PROVIDER="anthropic",
        SRF_LLM_MODEL="claude-sonnet-4-6",
        SRF_LLM_API_KEY="sk-ant-test",
        SRF_WORKSPACE_ROOT="/tmp/workspace",
        SRF_LOG_LEVEL="DEBUG",
    )
    assert config.llm_provider == "anthropic"
    assert config.llm_model == "claude-sonnet-4-6"
    assert config.llm_api_key == "sk-ant-test"
    assert config.workspace_root == Path("/tmp/workspace")
    assert config.log_level == "DEBUG"


# ---------------------------------------------------------------------------
# Scenario: config raises on missing required vars
# ---------------------------------------------------------------------------

def test_config_raises_on_missing_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    from srf.config import ConfigurationError

    with pytest.raises(ConfigurationError, match="SRF_LLM_PROVIDER"):
        _load(monkeypatch, SRF_LLM_PROVIDER=None)


def test_config_raises_on_missing_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from srf.config import ConfigurationError

    with pytest.raises(ConfigurationError, match="SRF_LLM_API_KEY"):
        _load(monkeypatch, SRF_LLM_API_KEY=None)


def test_config_raises_on_missing_model(monkeypatch: pytest.MonkeyPatch) -> None:
    from srf.config import ConfigurationError

    with pytest.raises(ConfigurationError, match="SRF_LLM_MODEL"):
        _load(monkeypatch, SRF_LLM_MODEL=None)


# ---------------------------------------------------------------------------
# Scenario: config raises on unrecognised SRF_LLM_PROVIDER
# ---------------------------------------------------------------------------

def test_config_raises_on_unknown_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    from srf.config import ConfigurationError

    with pytest.raises(ConfigurationError, match="unknown_provider"):
        _load(monkeypatch, SRF_LLM_PROVIDER="unknown_provider")


# ---------------------------------------------------------------------------
# Scenario: PromptLedger config is optional
# ---------------------------------------------------------------------------

def test_promptledger_optional_when_both_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _load(monkeypatch, PROMPTLEDGER_API_URL=None, PROMPTLEDGER_API_KEY=None)
    assert config.promptledger_enabled is False
    assert config.promptledger_api_url is None
    assert config.promptledger_api_key is None


# ---------------------------------------------------------------------------
# Scenario: PromptLedger requires both vars or neither
# ---------------------------------------------------------------------------

def test_promptledger_raises_when_only_url_set(monkeypatch: pytest.MonkeyPatch) -> None:
    from srf.config import ConfigurationError

    with pytest.raises(ConfigurationError, match="PROMPTLEDGER"):
        _load(
            monkeypatch,
            PROMPTLEDGER_API_URL="https://pl.example.com",
            PROMPTLEDGER_API_KEY=None,
        )


def test_promptledger_raises_when_only_key_set(monkeypatch: pytest.MonkeyPatch) -> None:
    from srf.config import ConfigurationError

    with pytest.raises(ConfigurationError, match="PROMPTLEDGER"):
        _load(
            monkeypatch,
            PROMPTLEDGER_API_URL=None,
            PROMPTLEDGER_API_KEY="pl-key",
        )


# ---------------------------------------------------------------------------
# Scenario: SRF_LOG_LEVEL defaults to INFO when absent
# ---------------------------------------------------------------------------

def test_log_level_defaults_to_info(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _load(monkeypatch, SRF_LOG_LEVEL=None)
    assert config.log_level == "INFO"


# ---------------------------------------------------------------------------
# Scenario: SRF_WORKSPACE_ROOT defaults when absent
# ---------------------------------------------------------------------------

def test_workspace_root_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _load(monkeypatch, SRF_WORKSPACE_ROOT=None)
    assert config.workspace_root == Path("/data/workspace")
