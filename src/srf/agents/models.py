"""Agent domain models."""

from __future__ import annotations

from dataclasses import dataclass, field


class RosterError(ValueError):
    """Raised when a valid roster cannot be built from available papers."""


class PreparationError(ValueError):
    """Raised when agent preparation fails (e.g., malformed LLM response)."""


class OrchestrationError(RuntimeError):
    """Raised when the preparation orchestrator cannot meet minimum agent requirements."""


@dataclass
class AgentAssignment:
    """A single agent in the roster."""

    agent_id: str
    role: str  # "paper_agent" | "moderator" | "challenger"
    arxiv_id: str | None  # None for moderator and challenger
    status: str = "pending"  # "pending" | "ok" | "failed" | "degraded"

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "role": self.role,
            "arxiv_id": self.arxiv_id,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict) -> AgentAssignment:
        return cls(
            agent_id=data["agent_id"],
            role=data["role"],
            arxiv_id=data.get("arxiv_id"),
            status=data.get("status", "pending"),
        )


@dataclass
class AgentRoster:
    """Complete set of agents for a forum run."""

    forum_id: str
    agents: list[AgentAssignment] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "forum_id": self.forum_id,
            "agents": [a.to_dict() for a in self.agents],
        }

    @classmethod
    def from_dict(cls, data: dict) -> AgentRoster:
        return cls(
            forum_id=data["forum_id"],
            agents=[AgentAssignment.from_dict(a) for a in data.get("agents", [])],
        )
