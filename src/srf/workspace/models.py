"""Workspace domain models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class WorkspaceError(OSError):
    """Raised when workspace initialisation or access fails."""


@dataclass
class ForumWorkspace:
    forum_id: str
    workspace_path: Path
    topic: str
    framing_question: str
    paper_refs: list[str]
    created_at: str  # ISO-8601

    def to_dict(self) -> dict:
        return {
            "forum_id": self.forum_id,
            "workspace_path": str(self.workspace_path),
            "topic": self.topic,
            "framing_question": self.framing_question,
            "paper_refs": self.paper_refs,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ForumWorkspace:
        return cls(
            forum_id=data["forum_id"],
            workspace_path=Path(data["workspace_path"]),
            topic=data["topic"],
            framing_question=data["framing_question"],
            paper_refs=data["paper_refs"],
            created_at=data["created_at"],
        )
