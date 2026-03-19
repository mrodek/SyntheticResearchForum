"""Agent roster builder — assigns paper agents, moderator, and challenger."""

from __future__ import annotations

import json

import structlog

from srf.agents.models import AgentAssignment, AgentRoster, RosterError
from srf.extraction.models import PaperContent
from srf.workspace.models import ForumWorkspace

logger = structlog.get_logger(__name__)


def build_roster(
    workspace: ForumWorkspace,
    papers: list[PaperContent],
    min_agents: int = 2,
) -> AgentRoster:
    """Build an AgentRoster from successfully extracted papers.

    Assigns one paper-agent-{N} per ok paper, plus one Moderator and one
    Challenger. Writes roster.json to workspace_path/roster.json.

    Args:
        workspace:  ForumWorkspace containing forum_id and workspace_path.
        papers:     List of PaperContent; only extraction_status="ok" entries
                    are included.
        min_agents: Minimum ok papers required; raises RosterError if not met.

    Returns:
        AgentRoster with all assigned agents.

    Raises:
        RosterError: When fewer than min_agents papers have extraction_status="ok".
    """
    ok_papers = [p for p in papers if p.extraction_status == "ok"]

    if len(ok_papers) < min_agents:
        raise RosterError(
            f"insufficient papers for roster: {len(ok_papers)} ok papers available, "
            f"minimum required is {min_agents}"
        )

    agents: list[AgentAssignment] = []

    for idx, paper in enumerate(ok_papers, start=1):
        agents.append(
            AgentAssignment(
                agent_id=f"paper-agent-{idx}",
                role="paper_agent",
                arxiv_id=paper.arxiv_id,
            )
        )

    agents.append(AgentAssignment(agent_id="moderator", role="moderator", arxiv_id=None))
    agents.append(AgentAssignment(agent_id="challenger", role="challenger", arxiv_id=None))

    roster = AgentRoster(forum_id=workspace.forum_id, agents=agents)

    roster_path = workspace.workspace_path / "roster.json"
    roster_path.write_text(json.dumps(roster.to_dict(), indent=2), encoding="utf-8")

    logger.info(
        "roster built",
        forum_id=workspace.forum_id,
        paper_agents=len(ok_papers),
        total_agents=len(agents),
    )

    return roster
