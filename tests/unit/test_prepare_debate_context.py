"""Story 6B.1 — Debate Context Document acceptance tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest  # noqa: F401

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_state(
    tmp_path: Path,
    forum_id: str,
    agents: list[dict],
    *,
    topic: str = "AI Epistemic Integrity",
    framing_question: str = "Can retrieval augment reasoning?",
    tension_axis: str = "retrieval vs. parametric memory",
    max_total_turns: int | None = None,
    max_turns_per_agent: int | None = None,
    max_rounds: int | None = None,
) -> Path:
    """Write state.json to a forum workspace and return its path."""
    workspace_path = tmp_path / "forum" / forum_id
    workspace_path.mkdir(parents=True, exist_ok=True)
    (workspace_path / "preparation").mkdir(exist_ok=True)
    (workspace_path / "transcripts").mkdir(exist_ok=True)

    state: dict = {
        "forum_id": forum_id,
        "forum_status": "preparation_complete",
        "trace_id": "trace-test-001",
        "config": {
            "topic": topic,
            "framing_question": framing_question,
            "tension_axis": tension_axis,
        },
        "agents": agents,
    }
    if max_total_turns is not None:
        state["max_total_turns"] = max_total_turns
    if max_turns_per_agent is not None:
        state["max_turns_per_agent"] = max_turns_per_agent
    if max_rounds is not None:
        state["max_rounds"] = max_rounds

    state_path = workspace_path / "state.json"
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return workspace_path


def _write_artifact(workspace_path: Path, agent_id: str) -> Path:
    """Write a minimal preparation artifact.json for an agent."""
    artifact_dir = workspace_path / "preparation" / agent_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / "artifact.json"
    artifact_path.write_text(
        json.dumps({"agent_id": agent_id, "status": "ok"}), encoding="utf-8"
    )
    return artifact_path


def _make_ok_paper_agent(agent_id: str, arxiv_id: str = "2401.00001") -> dict:
    return {"agent_id": agent_id, "role": "paper_agent", "status": "ok", "arxiv_id": arxiv_id}


def _make_degraded_paper_agent(agent_id: str) -> dict:
    return {"agent_id": agent_id, "role": "paper_agent", "status": "degraded", "arxiv_id": None}


def _make_moderator(status: str = "ok") -> dict:
    return {"agent_id": "moderator", "role": "moderator", "status": status, "arxiv_id": None}


def _make_challenger(status: str = "ok") -> dict:
    return {"agent_id": "challenger", "role": "challenger", "status": status, "arxiv_id": None}


# ---------------------------------------------------------------------------
# Scenario: prepare_debate_context writes a well-formed JSON document
# ---------------------------------------------------------------------------


def test_prepare_debate_context_writes_json_to_workspace(tmp_path: Path) -> None:
    from scripts.prepare_debate_context import prepare_debate_context

    forum_id = "forum-20260322-test0001"
    agents = [
        _make_ok_paper_agent("paper-agent-1"),
        _make_ok_paper_agent("paper-agent-2"),
        _make_moderator(),
        _make_challenger(),
    ]
    workspace_path = _make_state(tmp_path, forum_id, agents)
    _write_artifact(workspace_path, "paper-agent-1")
    _write_artifact(workspace_path, "paper-agent-2")
    _write_artifact(workspace_path, "moderator")
    _write_artifact(workspace_path, "challenger")

    result_path = prepare_debate_context(forum_id, tmp_path)

    assert result_path == workspace_path / "debate_context.json"
    assert result_path.exists()

    context = json.loads(result_path.read_text(encoding="utf-8"))
    assert context["forum_id"] == forum_id
    assert context["framing_question"] == "Can retrieval augment reasoning?"
    assert context["topic"] == "AI Epistemic Integrity"
    assert context["tension_axis"] == "retrieval vs. parametric memory"


# ---------------------------------------------------------------------------
# Scenario: debate_context includes one entry per agent with artifact_path for ok agents
# ---------------------------------------------------------------------------


def test_prepare_debate_context_agent_entries(tmp_path: Path) -> None:
    from scripts.prepare_debate_context import prepare_debate_context

    forum_id = "forum-20260322-test0002"
    agents = [
        _make_ok_paper_agent("paper-agent-1"),
        _make_ok_paper_agent("paper-agent-2"),
        _make_degraded_paper_agent("paper-agent-3"),
        _make_moderator(),
        _make_challenger(),
    ]
    workspace_path = _make_state(tmp_path, forum_id, agents)
    _write_artifact(workspace_path, "paper-agent-1")
    _write_artifact(workspace_path, "paper-agent-2")
    _write_artifact(workspace_path, "moderator")
    _write_artifact(workspace_path, "challenger")
    # paper-agent-3 is degraded — no artifact written

    result_path = prepare_debate_context(forum_id, tmp_path)
    context = json.loads(result_path.read_text(encoding="utf-8"))

    assert len(context["agents"]) == 5

    by_id = {a["agent_id"]: a for a in context["agents"]}

    # ok agents have artifact_path pointing to an existing file
    assert "artifact_path" in by_id["paper-agent-1"]
    assert Path(by_id["paper-agent-1"]["artifact_path"]).exists()
    assert "artifact_path" in by_id["paper-agent-2"]

    # degraded agent has no artifact_path
    assert by_id["paper-agent-3"]["status"] == "degraded"
    assert "artifact_path" not in by_id["paper-agent-3"]


# ---------------------------------------------------------------------------
# Scenario: debate_context includes hard limits from state.json
# ---------------------------------------------------------------------------


def test_prepare_debate_context_includes_hard_limits(tmp_path: Path) -> None:
    from scripts.prepare_debate_context import prepare_debate_context

    forum_id = "forum-20260322-test0003"
    agents = [
        _make_ok_paper_agent("paper-agent-1"),
        _make_ok_paper_agent("paper-agent-2"),
        _make_moderator(),
        _make_challenger(),
    ]
    workspace_path = _make_state(
        tmp_path, forum_id, agents,
        max_total_turns=30,
        max_turns_per_agent=8,
        max_rounds=4,
    )
    _write_artifact(workspace_path, "paper-agent-1")
    _write_artifact(workspace_path, "paper-agent-2")
    _write_artifact(workspace_path, "moderator")
    _write_artifact(workspace_path, "challenger")

    result_path = prepare_debate_context(forum_id, tmp_path)
    context = json.loads(result_path.read_text(encoding="utf-8"))

    assert context["limits"]["max_total_turns"] == 30
    assert context["limits"]["max_turns_per_agent"] == 8
    assert context["limits"]["max_rounds"] == 4


# ---------------------------------------------------------------------------
# Scenario: debate_context uses defaults when limits absent from state.json
# ---------------------------------------------------------------------------


def test_prepare_debate_context_uses_default_limits(tmp_path: Path) -> None:
    from scripts.prepare_debate_context import prepare_debate_context

    forum_id = "forum-20260322-test0004"
    agents = [_make_ok_paper_agent("paper-agent-1"), _make_ok_paper_agent("paper-agent-2")]
    workspace_path = _make_state(tmp_path, forum_id, agents)
    _write_artifact(workspace_path, "paper-agent-1")
    _write_artifact(workspace_path, "paper-agent-2")

    result_path = prepare_debate_context(forum_id, tmp_path)
    context = json.loads(result_path.read_text(encoding="utf-8"))

    assert context["limits"]["max_total_turns"] == 30
    assert context["limits"]["max_turns_per_agent"] == 8
    assert context["limits"]["max_rounds"] == 4


# ---------------------------------------------------------------------------
# Scenario: debate_context includes transcript_path and closed_sentinel
# ---------------------------------------------------------------------------


def test_prepare_debate_context_transcript_path_and_sentinel(tmp_path: Path) -> None:
    from scripts.prepare_debate_context import prepare_debate_context

    forum_id = "forum-20260322-test0005"
    agents = [_make_ok_paper_agent("paper-agent-1"), _make_ok_paper_agent("paper-agent-2")]
    workspace_path = _make_state(tmp_path, forum_id, agents)
    _write_artifact(workspace_path, "paper-agent-1")
    _write_artifact(workspace_path, "paper-agent-2")

    result_path = prepare_debate_context(forum_id, tmp_path)
    context = json.loads(result_path.read_text(encoding="utf-8"))

    expected_transcript = str(workspace_path / "transcripts" / "transcript.jsonl")
    assert context["transcript_path"] == expected_transcript
    assert context["closed_sentinel"] == "DEBATE_CLOSED"


# ---------------------------------------------------------------------------
# Scenario: raises DebateContextError when fewer than 2 ok Paper Agents
# ---------------------------------------------------------------------------


def test_prepare_debate_context_raises_on_insufficient_ok_agents(tmp_path: Path) -> None:
    from scripts.prepare_debate_context import DebateContextError, prepare_debate_context

    forum_id = "forum-20260322-test0006"
    agents = [
        _make_ok_paper_agent("paper-agent-1"),
        _make_degraded_paper_agent("paper-agent-2"),
        _make_moderator(),
    ]
    workspace_path = _make_state(tmp_path, forum_id, agents)
    _write_artifact(workspace_path, "paper-agent-1")
    _write_artifact(workspace_path, "moderator")

    with pytest.raises(DebateContextError, match="(?i)insufficient"):
        prepare_debate_context(forum_id, tmp_path)


# ---------------------------------------------------------------------------
# Scenario: raises DebateContextError when a required artifact file is missing
# ---------------------------------------------------------------------------


def test_prepare_debate_context_raises_on_missing_artifact(tmp_path: Path) -> None:
    from scripts.prepare_debate_context import DebateContextError, prepare_debate_context

    forum_id = "forum-20260322-test0007"
    agents = [
        _make_ok_paper_agent("paper-agent-1"),
        _make_ok_paper_agent("paper-agent-2"),
    ]
    workspace_path = _make_state(tmp_path, forum_id, agents)
    _write_artifact(workspace_path, "paper-agent-1")
    # paper-agent-2 artifact intentionally not written

    with pytest.raises(DebateContextError, match="paper-agent-2"):
        prepare_debate_context(forum_id, tmp_path)


# ---------------------------------------------------------------------------
# Scenario: raises DebateContextError when state.json is missing
# ---------------------------------------------------------------------------


def test_prepare_debate_context_raises_on_missing_state_json(tmp_path: Path) -> None:
    from scripts.prepare_debate_context import DebateContextError, prepare_debate_context

    forum_id = "forum-20260322-test0008"
    # Create workspace dir but no state.json
    (tmp_path / "forum" / forum_id).mkdir(parents=True)

    with pytest.raises(DebateContextError, match="state.json"):
        prepare_debate_context(forum_id, tmp_path)
