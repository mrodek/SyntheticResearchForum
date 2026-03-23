"""Story 4.4 — run_workspace_setup.py acceptance tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).parent.parent.parent / "scripts" / "run_workspace_setup.py"


def _run(stdin_data: dict, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    import os

    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)

    return subprocess.run(
        [sys.executable, str(_SCRIPT)],
        input=json.dumps(stdin_data),
        capture_output=True,
        text=True,
        env=env,
    )


@pytest.fixture
def candidate_config_file(tmp_path: Path) -> Path:
    config = {
        "topic": "Test Debate Topic",
        "framing_question": "Is coordination possible at scale?",
        "tension_axis": "autonomy vs. control",
        "paper_refs": ["2401.00001", "2401.00002"],
        "newsletter_slug": "issue_5",
        "generated_at": "2026-03-17T10:00:00Z",
    }
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


_BASE_ENV = {
    "SRF_LLM_PROVIDER": "anthropic",
    "SRF_LLM_MODEL": "claude-sonnet-4-6",
    "SRF_LLM_API_KEY": "test-key",
}


# ---------------------------------------------------------------------------
# Scenario: exits 0 and writes forum_id to stdout JSON
# ---------------------------------------------------------------------------


def test_run_workspace_setup_exits_0_and_emits_forum_id(
    tmp_path: Path,
    candidate_config_file: Path,
) -> None:
    result = _run(
        {"config_path": str(candidate_config_file)},
        extra_env={**_BASE_ENV, "SRF_WORKSPACE_ROOT": str(tmp_path)},
    )
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert "forum_id" in output
    assert "workspace_path" in output
    assert output["forum_id"].startswith("forum-")


# ---------------------------------------------------------------------------
# Scenario: exits 1 and writes error to stderr when config_path is missing
# ---------------------------------------------------------------------------


def test_run_workspace_setup_exits_1_on_missing_config(tmp_path: Path) -> None:
    result = _run(
        {"config_path": str(tmp_path / "nonexistent.json")},
        extra_env={**_BASE_ENV, "SRF_WORKSPACE_ROOT": str(tmp_path)},
    )
    assert result.returncode == 1
    assert result.stderr.strip() != ""


# ---------------------------------------------------------------------------
# Scenario: writes state.json checkpoint before exiting
# ---------------------------------------------------------------------------


def test_run_workspace_setup_writes_state_json(
    tmp_path: Path,
    candidate_config_file: Path,
) -> None:
    result = _run(
        {"config_path": str(candidate_config_file)},
        extra_env={**_BASE_ENV, "SRF_WORKSPACE_ROOT": str(tmp_path)},
    )
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    state_path = Path(output["workspace_path"]) / "state.json"
    assert state_path.exists()
    state = json.loads(state_path.read_text())
    assert state["forum_status"] == "workspace_ready"


# ---------------------------------------------------------------------------
# BUG-007: output must include created_at for ForumWorkspace.from_dict()
# ---------------------------------------------------------------------------


def test_run_workspace_setup_output_includes_created_at(
    tmp_path: Path,
    candidate_config_file: Path,
) -> None:
    """run_workspace_setup.py must emit created_at in its stdout JSON.

    BUG-007: ForumWorkspace.from_dict() does data['created_at'] which KeyErrors
    because run_workspace_setup.py never includes created_at in its output.
    """
    result = _run(
        {"config_path": str(candidate_config_file)},
        extra_env={**_BASE_ENV, "SRF_WORKSPACE_ROOT": str(tmp_path)},
    )
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert "created_at" in output, "output must include created_at (ISO-8601)"
    # Verify it looks like an ISO timestamp
    assert "T" in output["created_at"] or "Z" in output["created_at"], (
        f"created_at must be ISO-8601, got: {output['created_at']}"
    )
