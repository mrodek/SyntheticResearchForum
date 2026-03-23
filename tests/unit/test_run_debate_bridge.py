"""Story 6B.4 — Bridge Script & Pipeline Integration acceptance tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_stdin(tmp_path: Path, forum_id: str) -> dict:
    """Minimal stdin JSON as produced by run_preparation.py."""
    workspace_path = tmp_path / "forum" / forum_id
    return {
        "forum_id": forum_id,
        "workspace_path": str(workspace_path),
        "trace_id": "trace-test-001",
        "topic": "AI Epistemic Integrity",
        "framing_question": "Can retrieval augment reasoning?",
        "agents": [
            {"agent_id": "paper-agent-1", "role": "paper_agent", "status": "ok", "arxiv_id": "2401.00001"},
            {"agent_id": "paper-agent-2", "role": "paper_agent", "status": "ok", "arxiv_id": "2401.00002"},
            {"agent_id": "moderator", "role": "moderator", "status": "ok", "arxiv_id": None},
            {"agent_id": "challenger", "role": "challenger", "status": "ok", "arxiv_id": None},
        ],
        "preparation_status": "complete",
    }


def _make_workspace(tmp_path: Path, forum_id: str) -> Path:
    """Create workspace with state.json and preparation artifacts."""
    workspace_path = tmp_path / "forum" / forum_id
    for subdir in ("preparation", "transcripts", "synthesis", "logs"):
        (workspace_path / subdir).mkdir(parents=True, exist_ok=True)

    state = {
        "forum_id": forum_id,
        "forum_status": "preparation_complete",
        "trace_id": "trace-test-001",
        "config": {
            "topic": "AI Epistemic Integrity",
            "framing_question": "Can retrieval augment reasoning?",
            "tension_axis": "retrieval vs. parametric memory",
        },
    }
    (workspace_path / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")

    for agent_id in ("paper-agent-1", "paper-agent-2", "moderator", "challenger"):
        artifact_dir = workspace_path / "preparation" / agent_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / "artifact.json").write_text(
            json.dumps({"agent_id": agent_id, "status": "ok"}), encoding="utf-8"
        )

    return workspace_path


def _write_closed_transcript(workspace_path: Path, turn_count: int = 4) -> Path:
    """Write a well-formed closed transcript to the workspace."""
    transcript_path = workspace_path / "transcripts" / "transcript.jsonl"
    lines = []
    for i in range(1, turn_count + 1):
        lines.append(json.dumps({
            "turn_id": f"t-{i:04d}",
            "speaker_id": "paper-agent-1",
            "role": "paper_agent",
            "phase": "position",
            "content": f"Turn {i} content.",
            "timestamp": "2026-03-22T10:00:00Z",
        }))
    lines.append(json.dumps({
        "type": "DEBATE_CLOSED",
        "reason": "moderator_closed",
        "total_turns": turn_count,
        "timestamp": "2026-03-22T10:30:00Z",
    }))
    transcript_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return transcript_path


def _mock_openclaw_response() -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.ok = True
    return resp


# ---------------------------------------------------------------------------
# Scenario: calls prepare_debate_context before triggering OpenClaw
# ---------------------------------------------------------------------------


def test_bridge_calls_prepare_debate_context_before_api(tmp_path: Path) -> None:
    from scripts.run_debate_bridge import run_bridge

    forum_id = "forum-20260322-bridge01"
    workspace_path = _make_workspace(tmp_path, forum_id)
    stdin_data = _make_stdin(tmp_path, forum_id)
    _write_closed_transcript(workspace_path)

    with patch("requests.post", return_value=_mock_openclaw_response()):
        result = run_bridge(
            stdin_data,
            workspace_root=tmp_path,
            openclaw_url="http://localhost:8080",
            openclaw_token="test-token",
            poll_timeout_seconds=5,
            poll_interval_seconds=0.01,
        )

    assert (workspace_path / "debate_context.json").exists(), (
        "debate_context.json must be written before OpenClaw is triggered"
    )
    assert result["forum_id"] == forum_id


# ---------------------------------------------------------------------------
# Scenario: exits 0 and writes transcript metadata to stdout JSON
# ---------------------------------------------------------------------------


def test_bridge_returns_transcript_metadata_on_success(tmp_path: Path) -> None:
    from scripts.run_debate_bridge import run_bridge

    forum_id = "forum-20260322-bridge02"
    workspace_path = _make_workspace(tmp_path, forum_id)
    stdin_data = _make_stdin(tmp_path, forum_id)
    _write_closed_transcript(workspace_path, turn_count=6)

    with patch("requests.post", return_value=_mock_openclaw_response()):
        result = run_bridge(
            stdin_data,
            workspace_root=tmp_path,
            openclaw_url="http://localhost:8080",
            openclaw_token="test-token",
            poll_timeout_seconds=5,
            poll_interval_seconds=0.01,
        )

    assert result["forum_id"] == forum_id
    assert "transcript_path" in result
    assert result["turn_count"] == 6
    assert result["debate_status"] == "closed"


# ---------------------------------------------------------------------------
# Scenario: raises when transcript does not close within timeout
# ---------------------------------------------------------------------------


def test_bridge_raises_on_timeout(tmp_path: Path) -> None:
    from scripts.run_debate_bridge import DebateBridgeError, run_bridge

    forum_id = "forum-20260322-bridge03"
    _make_workspace(tmp_path, forum_id)
    stdin_data = _make_stdin(tmp_path, forum_id)
    # No transcript written — sentinel never appears

    with patch("requests.post", return_value=_mock_openclaw_response()), \
            pytest.raises(DebateBridgeError, match="(?i)timeout"):
        run_bridge(
            stdin_data,
            workspace_root=tmp_path,
            openclaw_url="http://localhost:8080",
            openclaw_token="test-token",
            poll_timeout_seconds=1,
            poll_interval_seconds=0.01,
        )


# ---------------------------------------------------------------------------
# Scenario: raises when validate_transcript raises TranscriptError
# ---------------------------------------------------------------------------


def test_bridge_raises_on_invalid_transcript(tmp_path: Path) -> None:
    from scripts.run_debate_bridge import DebateBridgeError, run_bridge

    forum_id = "forum-20260322-bridge04"
    workspace_path = _make_workspace(tmp_path, forum_id)
    stdin_data = _make_stdin(tmp_path, forum_id)

    # Write a transcript with sentinel but malformed turn
    transcript_path = workspace_path / "transcripts" / "transcript.jsonl"
    transcript_path.write_text(
        'not valid json\n'
        + json.dumps({"type": "DEBATE_CLOSED", "reason": "moderator_closed", "total_turns": 1, "timestamp": "2026-03-22T10:00:00Z"})
        + "\n",
        encoding="utf-8",
    )

    with patch("requests.post", return_value=_mock_openclaw_response()), \
            pytest.raises(DebateBridgeError, match="(?i)transcript"):
        run_bridge(
            stdin_data,
            workspace_root=tmp_path,
            openclaw_url="http://localhost:8080",
            openclaw_token="test-token",
            poll_timeout_seconds=5,
            poll_interval_seconds=0.01,
        )


# ---------------------------------------------------------------------------
# Scenario: passes OPENCLAW_GATEWAY_TOKEN in Authorization header
# ---------------------------------------------------------------------------


def test_bridge_sends_authorization_header(tmp_path: Path) -> None:
    from scripts.run_debate_bridge import run_bridge

    forum_id = "forum-20260322-bridge05"
    workspace_path = _make_workspace(tmp_path, forum_id)
    stdin_data = _make_stdin(tmp_path, forum_id)
    _write_closed_transcript(workspace_path)

    captured_headers: list[dict] = []

    def _capture_post(url, *, json=None, headers=None, **kwargs):
        captured_headers.append(headers or {})
        return _mock_openclaw_response()

    with patch("requests.post", side_effect=_capture_post):
        run_bridge(
            stdin_data,
            workspace_root=tmp_path,
            openclaw_url="http://localhost:8080",
            openclaw_token="secret-gateway-token",
            poll_timeout_seconds=5,
            poll_interval_seconds=0.01,
        )

    assert len(captured_headers) == 1
    assert captured_headers[0].get("Authorization") == "Bearer secret-gateway-token"


# ---------------------------------------------------------------------------
# Scenario: srf_forum.yaml debate step uses run_debate_bridge.py
# ---------------------------------------------------------------------------


def test_workflow_debate_step_uses_bridge_script() -> None:
    workflow_path = Path("workflows/srf_forum.yaml")
    data = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    debate_step = next(s for s in data["steps"] if s["id"] == "debate")
    assert "run_debate_bridge.py" in debate_step["command"]
    assert debate_step.get("stdin") == "$agent_preparation.json"


# ---------------------------------------------------------------------------
# BUG-004: workspace_setup must not reference non-existent $trigger step
# ---------------------------------------------------------------------------


def test_srf_forum_yaml_workspace_setup_does_not_reference_trigger_step() -> None:
    """workspace_setup must use $LOBSTER_ARGS_JSON, not a non-existent $trigger step.

    BUG-004: stdin: $trigger.json references a step that doesn't exist.
    Initial workflow input must be accessed via $LOBSTER_ARGS_JSON env var.
    """
    workflow_path = Path("workflows/srf_forum.yaml")
    data = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    ws_step = next(s for s in data["steps"] if s["id"] == "workspace_setup")
    assert ws_step.get("stdin") != "$trigger.json", (
        "workspace_setup must not reference non-existent $trigger step via stdin"
    )
    cmd = ws_step.get("command", "") or ws_step.get("run", "")
    assert "LOBSTER_ARGS_JSON" in cmd, (
        "workspace_setup command must pipe $LOBSTER_ARGS_JSON to the script"
    )


# ---------------------------------------------------------------------------
# BUG-004: all Python steps must use absolute paths
# ---------------------------------------------------------------------------


def test_srf_forum_yaml_python_steps_use_absolute_paths() -> None:
    """Steps calling Python scripts must use /data/venv/bin/python and /data/srf/scripts/.

    BUG-004: bare 'python scripts/...' fails because Lobster cwd is the OpenClaw
    gateway working directory, not /data/srf, and system python is not the venv.
    """
    workflow_path = Path("workflows/srf_forum.yaml")
    data = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    for step in data["steps"]:
        cmd = step.get("command", "") or step.get("run", "")
        if "python" in cmd and "placeholder" not in cmd:
            assert "/data/venv/bin/python" in cmd, (
                f"Step '{step['id']}' must use /data/venv/bin/python, got: {cmd}"
            )
            assert "/data/srf/scripts/" in cmd, (
                f"Step '{step['id']}' must use /data/srf/scripts/ absolute path, got: {cmd}"
            )
