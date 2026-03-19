"""Forum workspace initialisation."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import structlog

from srf.newsletter.models import CandidateForumConfig
from srf.workspace.models import ForumWorkspace, WorkspaceError

logger = structlog.get_logger(__name__)

_SUBDIRS = ("preparation", "transcripts", "synthesis", "logs", "papers")


def _generate_forum_id() -> str:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"forum-{today}-{uuid.uuid4().hex[:8]}"


def initialise_workspace(
    config: CandidateForumConfig,
    workspace_root: Path,
) -> ForumWorkspace:
    """Assign a forum_id, create the workspace directory tree, and write state.json.

    Raises:
        WorkspaceError: if the workspace root is not writable or the forum already exists.
    """
    forum_id = _generate_forum_id()
    workspace_path = workspace_root / "forum" / forum_id

    if workspace_path.exists():
        raise WorkspaceError(
            f"Forum workspace already exists at {workspace_path}. Refusing to overwrite."
        )

    try:
        workspace_path.mkdir(parents=True, exist_ok=False)
    except PermissionError as exc:
        raise WorkspaceError(
            f"Cannot create workspace under {workspace_root}: permission denied."
        ) from exc
    except FileExistsError as exc:
        raise WorkspaceError(
            f"Forum workspace already exists at {workspace_path}."
        ) from exc

    for subdir in _SUBDIRS:
        (workspace_path / subdir).mkdir()

    created_at = datetime.now(timezone.utc).isoformat()

    state = {
        "forum_id": forum_id,
        "forum_status": "workspace_ready",
        "created_at": created_at,
        "topic": config.topic,
        "framing_question": config.framing_question,
        "paper_refs": config.paper_refs,
        "newsletter_slug": config.newsletter_slug,
    }
    (workspace_path / "state.json").write_text(
        json.dumps(state, indent=2), encoding="utf-8"
    )

    logger.info(
        "workspace_initialised",
        forum_id=forum_id,
        workspace_path=str(workspace_path),
    )

    return ForumWorkspace(
        forum_id=forum_id,
        workspace_path=workspace_path,
        topic=config.topic,
        framing_question=config.framing_question,
        paper_refs=config.paper_refs,
        created_at=created_at,
    )
