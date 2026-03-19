"""Story 5.5 — run_preparation.py script acceptance tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from srf.agents.models import AgentAssignment, AgentRoster


def _make_paper_extraction_output(tmp_path: Path) -> dict:
    workspace_path = tmp_path / "forum" / "forum-20260317-abcdef01"
    workspace_path.mkdir(parents=True)
    (workspace_path / "preparation").mkdir()
    (workspace_path / "papers").mkdir()
    state = {
        "forum_id": "forum-20260317-abcdef01",
        "forum_status": "extraction_complete",
        "created_at": "2026-03-17T10:00:00+00:00",
    }
    (workspace_path / "state.json").write_text(json.dumps(state), encoding="utf-8")
    papers = [
        {
            "arxiv_id": "2401.00001",
            "abstract": "Abstract one.",
            "full_text": "Full text one.",
            "extraction_status": "ok",
        },
        {
            "arxiv_id": "2401.00002",
            "abstract": "Abstract two.",
            "full_text": "Full text two.",
            "extraction_status": "ok",
        },
    ]
    return {
        "forum_id": "forum-20260317-abcdef01",
        "workspace_path": str(workspace_path),
        "paper_refs": ["2401.00001", "2401.00002"],
        "topic": "Test Topic",
        "framing_question": "A question?",
        "created_at": "2026-03-17T10:00:00+00:00",
        "trace_id": "trace-abc123",
        "forum_status": "extraction_complete",
        "papers": papers,
    }


def _make_roster() -> AgentRoster:
    return AgentRoster(
        forum_id="forum-20260317-abcdef01",
        agents=[
            AgentAssignment(agent_id="paper-agent-1", role="paper_agent", arxiv_id="2401.00001"),
            AgentAssignment(agent_id="paper-agent-2", role="paper_agent", arxiv_id="2401.00002"),
            AgentAssignment(agent_id="moderator", role="moderator", arxiv_id=None),
            AgentAssignment(agent_id="challenger", role="challenger", arxiv_id=None),
        ],
    )


def _make_orch_result() -> dict:
    return {
        "preparation_status": "complete",
        "agent_count": 2,
        "roster": _make_roster(),
    }


# ---------------------------------------------------------------------------
# Scenario: _run exits 0 and emits preparation summary JSON
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_preparation_exits_0_with_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SRF_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("SRF_LLM_MODEL", "claude-sonnet-4-6")
    monkeypatch.setenv("SRF_LLM_API_KEY", "test-key")
    monkeypatch.setenv("SRF_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.delenv("PROMPTLEDGER_API_URL", raising=False)
    monkeypatch.delenv("PROMPTLEDGER_API_KEY", raising=False)

    stdin_data = _make_paper_extraction_output(tmp_path)

    with (
        patch("scripts.run_preparation.build_roster", return_value=_make_roster()),
        patch(
            "scripts.run_preparation.run_preparation",
            new=AsyncMock(return_value=_make_orch_result()),
        ),
    ):
        from scripts.run_preparation import _run as prep_run

        output = await prep_run(stdin_data)

    assert "agents" in output
    assert output["forum_status"] == "preparation_complete"


# ---------------------------------------------------------------------------
# Scenario: srf_forum.yaml agent_preparation step wired to run_preparation.py
# ---------------------------------------------------------------------------


def test_srf_forum_yaml_agent_preparation_step_wired() -> None:
    import yaml

    yaml_path = Path("workflows/srf_forum.yaml")
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))

    step = next((s for s in data["steps"] if s["id"] == "agent_preparation"), None)
    assert step is not None, "agent_preparation step not found in srf_forum.yaml"
    assert step["command"] == "python scripts/run_preparation.py"
    assert step["stdin"] == "$paper_extraction.json"
