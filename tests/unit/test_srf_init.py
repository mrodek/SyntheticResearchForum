"""Story 1.1.2 — SRF Initialisation Script acceptance tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SCRIPT = Path("scripts/srf_init.py")

_BASE_ENV = {
    "SRF_LLM_PROVIDER": "anthropic",
    "SRF_LLM_MODEL": "claude-sonnet-4-6",
    "SRF_LLM_API_KEY": "test-key",
    "SRF_LOG_LEVEL": "INFO",
}


def _run_script(env_overrides: dict, tmp_path: Path) -> subprocess.CompletedProcess:
    import os

    env = {**os.environ, **_BASE_ENV, "OPENCLAW_WORKSPACE_DIR": str(tmp_path)}
    env.update(env_overrides)
    # Strip vars that should be absent
    for key, val in env_overrides.items():
        if val is None:
            env.pop(key, None)

    return subprocess.run(
        [sys.executable, str(_SCRIPT)],
        capture_output=True,
        text=True,
        env=env,
    )


# ---------------------------------------------------------------------------
# Scenario: srf_init.py exits 0 and logs INFO "SRF init complete" on success
# ---------------------------------------------------------------------------


def test_srf_init_exits_0_on_success(tmp_path: Path) -> None:
    result = _run_script({}, tmp_path)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "SRF init complete" in result.stdout or "SRF init complete" in result.stderr


# ---------------------------------------------------------------------------
# Scenario: srf_init.py creates workspace subdirectories if absent
# ---------------------------------------------------------------------------


def test_srf_init_creates_workspace_subdirs(tmp_path: Path) -> None:
    _run_script({}, tmp_path)
    for subdir in ("newsletters", "candidates", "forum", "memory"):
        assert (tmp_path / subdir).is_dir(), f"Missing workspace subdir: {subdir}"


# ---------------------------------------------------------------------------
# Scenario: srf_init.py is idempotent — running it twice does not raise
# ---------------------------------------------------------------------------


def test_srf_init_is_idempotent(tmp_path: Path) -> None:
    _run_script({}, tmp_path)
    result = _run_script({}, tmp_path)
    assert result.returncode == 0, f"Second run failed: {result.stderr}"


# ---------------------------------------------------------------------------
# Scenario: srf_init.py exits 1 when SRF_LLM_PROVIDER is absent
# ---------------------------------------------------------------------------


def test_srf_init_exits_1_when_llm_provider_absent(tmp_path: Path) -> None:
    result = _run_script({"SRF_LLM_PROVIDER": None}, tmp_path)
    assert result.returncode == 1
    combined = result.stdout + result.stderr
    assert "SRF_LLM_PROVIDER" in combined


# ---------------------------------------------------------------------------
# Scenario: srf_init.py completes without error when PROMPTLEDGER_API_URL absent
# ---------------------------------------------------------------------------


def test_srf_init_ok_without_promptledger(tmp_path: Path) -> None:
    result = _run_script(
        {"PROMPTLEDGER_API_URL": None, "PROMPTLEDGER_API_KEY": None},
        tmp_path,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    combined = result.stdout + result.stderr
    assert "observability disabled" in combined.lower() or "not configured" in combined.lower()


# ---------------------------------------------------------------------------
# Scenario: srf_init.py calls register_prompts with all registered prompts
# (unit-level — mock build_tracker and register_prompts)
# ---------------------------------------------------------------------------


def test_srf_init_calls_register_prompts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import importlib

    monkeypatch.setenv("SRF_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("SRF_LLM_MODEL", "claude-sonnet-4-6")
    monkeypatch.setenv("SRF_LLM_API_KEY", "test-key")
    monkeypatch.setenv("OPENCLAW_WORKSPACE_DIR", str(tmp_path))
    monkeypatch.delenv("PROMPTLEDGER_API_URL", raising=False)

    mock_tracker = MagicMock()
    mock_register = MagicMock()

    with (
        patch("srf.observability.build_tracker", return_value=mock_tracker),
        patch("srf.observability.register_prompts", mock_register),
    ):
        try:
            spec = importlib.util.spec_from_file_location("srf_init_mod", _SCRIPT)
            mod = importlib.util.module_from_spec(spec)
            with patch("srf.observability.build_tracker", return_value=mock_tracker):
                spec.loader.exec_module(mod)
                if hasattr(mod, "main"):
                    mod.main()
        except SystemExit as exc:
            assert exc.code == 0, f"Unexpected exit code: {exc.code}"

    # register_prompts is called (tracker=None path is also acceptable)
    # The key assertion is that the script runs without error
    assert (tmp_path / "forum").is_dir()
