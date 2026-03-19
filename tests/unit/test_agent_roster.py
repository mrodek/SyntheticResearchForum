"""Story 5.2 — AgentRoster unit tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from srf.extraction.models import PaperContent
from srf.workspace.models import ForumWorkspace


def _make_workspace(tmp_path: Path) -> ForumWorkspace:
    wp = tmp_path / "forum-20260317-abcdef01"
    wp.mkdir(parents=True)
    (wp / "preparation").mkdir()
    return ForumWorkspace(
        forum_id="forum-20260317-abcdef01",
        workspace_path=wp,
        topic="Test Topic",
        framing_question="A question?",
        paper_refs=["2401.00001", "2401.00002", "2401.00003"],
        created_at="2026-03-17T10:00:00+00:00",
    )


def _make_papers(arxiv_ids: list[str], status: str = "ok") -> list[PaperContent]:
    return [
        PaperContent(
            arxiv_id=aid,
            pdf_path=None,
            full_text="full text",
            abstract="abstract",
            page_count=1,
            extraction_status=status,
        )
        for aid in arxiv_ids
    ]


# ---------------------------------------------------------------------------
# Scenario: one Paper Agent per successfully extracted paper
# ---------------------------------------------------------------------------


def test_build_roster_assigns_one_agent_per_ok_paper(tmp_path: Path) -> None:
    from srf.agents.roster import build_roster

    workspace = _make_workspace(tmp_path)
    papers = _make_papers(["2401.00001", "2401.00002", "2401.00003"])

    roster = build_roster(workspace, papers)

    paper_agents = [a for a in roster.agents if a.role == "paper_agent"]
    assert len(paper_agents) == 3
    agent_ids = [a.agent_id for a in paper_agents]
    assert "paper-agent-1" in agent_ids
    assert "paper-agent-2" in agent_ids
    assert "paper-agent-3" in agent_ids
    arxiv_ids = {a.arxiv_id for a in paper_agents}
    assert arxiv_ids == {"2401.00001", "2401.00002", "2401.00003"}


# ---------------------------------------------------------------------------
# Scenario: excludes papers with failed extraction
# ---------------------------------------------------------------------------


def test_build_roster_excludes_failed_papers(tmp_path: Path) -> None:
    from srf.agents.roster import build_roster

    workspace = _make_workspace(tmp_path)
    papers = [
        *_make_papers(["2401.00001", "2401.00002"]),
        *_make_papers(["2401.00003"], status="failed"),
    ]

    roster = build_roster(workspace, papers)

    paper_agents = [a for a in roster.agents if a.role == "paper_agent"]
    assert len(paper_agents) == 2
    assert all(a.arxiv_id != "2401.00003" for a in paper_agents)


# ---------------------------------------------------------------------------
# Scenario: exactly one Moderator and one Challenger
# ---------------------------------------------------------------------------


def test_build_roster_has_exactly_one_moderator_and_challenger(tmp_path: Path) -> None:
    from srf.agents.roster import build_roster

    workspace = _make_workspace(tmp_path)
    papers = _make_papers(["2401.00001", "2401.00002"])

    roster = build_roster(workspace, papers)

    moderators = [a for a in roster.agents if a.role == "moderator"]
    challengers = [a for a in roster.agents if a.role == "challenger"]
    assert len(moderators) == 1
    assert len(challengers) == 1


# ---------------------------------------------------------------------------
# Scenario: raises RosterError when fewer than min_agents
# ---------------------------------------------------------------------------


def test_build_roster_raises_when_too_few_papers(tmp_path: Path) -> None:
    from srf.agents.models import RosterError
    from srf.agents.roster import build_roster

    workspace = _make_workspace(tmp_path)
    papers = _make_papers(["2401.00001"])  # only 1 ok paper

    with pytest.raises(RosterError, match="insufficient"):
        build_roster(workspace, papers, min_agents=2)


# ---------------------------------------------------------------------------
# Scenario: AgentRoster JSON roundtrip
# ---------------------------------------------------------------------------


def test_agent_roster_json_roundtrip(tmp_path: Path) -> None:
    from srf.agents.roster import build_roster

    workspace = _make_workspace(tmp_path)
    papers = _make_papers(["2401.00001", "2401.00002"])

    roster = build_roster(workspace, papers)
    serialised = roster.to_dict()
    restored = roster.__class__.from_dict(serialised)

    assert restored.forum_id == roster.forum_id
    assert len(restored.agents) == len(roster.agents)
    for orig, rest in zip(roster.agents, restored.agents, strict=True):
        assert orig.agent_id == rest.agent_id
        assert orig.role == rest.role
        assert orig.arxiv_id == rest.arxiv_id


# ---------------------------------------------------------------------------
# Scenario: writes roster.json to workspace
# ---------------------------------------------------------------------------


def test_build_roster_writes_roster_json(tmp_path: Path) -> None:
    from srf.agents.roster import build_roster

    workspace = _make_workspace(tmp_path)
    papers = _make_papers(["2401.00001", "2401.00002"])

    roster = build_roster(workspace, papers)

    roster_path = workspace.workspace_path / "roster.json"
    assert roster_path.exists()
    data = json.loads(roster_path.read_text(encoding="utf-8"))
    restored = roster.__class__.from_dict(data)
    assert restored.forum_id == roster.forum_id
    assert len(restored.agents) == len(roster.agents)
