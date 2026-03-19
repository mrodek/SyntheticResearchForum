"""Story 4.1 — Forum Workspace Initialisation acceptance tests."""

from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path
from unittest.mock import patch

import pytest

from srf.newsletter.models import CandidateForumConfig


def _make_config() -> CandidateForumConfig:
    return CandidateForumConfig(
        topic="Multi-Agent Systems Under Stress",
        framing_question="Can multi-agent systems maintain epistemic integrity?",
        tension_axis="coordination vs. autonomy",
        paper_refs=["2401.12345", "2401.67890"],
        newsletter_slug="issue_5",
        generated_at="2026-03-17T10:00:00Z",
    )


# ---------------------------------------------------------------------------
# Scenario: initialise_workspace returns a ForumWorkspace with a valid forum_id
# ---------------------------------------------------------------------------


def test_initialise_workspace_returns_valid_forum_id(tmp_path: Path) -> None:
    from srf.workspace.init import initialise_workspace

    result = initialise_workspace(_make_config(), tmp_path)
    assert re.match(r"^forum-\d{8}-[0-9a-f]{8}$", result.forum_id)


# ---------------------------------------------------------------------------
# Scenario: workspace_path equals workspace_root/forum/{forum_id}
# ---------------------------------------------------------------------------


def test_initialise_workspace_path_is_under_forum_dir(tmp_path: Path) -> None:
    from srf.workspace.init import initialise_workspace

    result = initialise_workspace(_make_config(), tmp_path)
    assert result.workspace_path == tmp_path / "forum" / result.forum_id


# ---------------------------------------------------------------------------
# Scenario: initialise_workspace creates the canonical subdirectory structure
# ---------------------------------------------------------------------------


def test_initialise_workspace_creates_subdirectories(tmp_path: Path) -> None:
    from srf.workspace.init import initialise_workspace

    result = initialise_workspace(_make_config(), tmp_path)
    for subdir in ("preparation", "transcripts", "synthesis", "logs", "papers"):
        assert (result.workspace_path / subdir).is_dir(), f"Missing subdir: {subdir}"


# ---------------------------------------------------------------------------
# Scenario: initialise_workspace writes state.json with status "workspace_ready"
# ---------------------------------------------------------------------------


def test_initialise_workspace_writes_state_json(tmp_path: Path) -> None:
    from srf.workspace.init import initialise_workspace

    result = initialise_workspace(_make_config(), tmp_path)
    state_path = result.workspace_path / "state.json"
    assert state_path.exists()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["forum_id"] == result.forum_id
    assert state["forum_status"] == "workspace_ready"
    assert "created_at" in state


# ---------------------------------------------------------------------------
# Scenario: raises WorkspaceError when workspace root is not writable
# ---------------------------------------------------------------------------


@pytest.mark.skipif(os.name == "nt", reason="chmod read-only unreliable on Windows")
def test_initialise_workspace_raises_on_unwritable_root(tmp_path: Path) -> None:
    from srf.workspace.init import initialise_workspace
    from srf.workspace.models import WorkspaceError

    readonly = tmp_path / "readonly"
    readonly.mkdir()
    readonly.chmod(stat.S_IREAD | stat.S_IEXEC)

    try:
        with pytest.raises(WorkspaceError, match=str(readonly)):
            initialise_workspace(_make_config(), readonly)
    finally:
        readonly.chmod(stat.S_IRWXU)


# ---------------------------------------------------------------------------
# Scenario: raises WorkspaceError when a forum with the same id already exists
# ---------------------------------------------------------------------------


def test_initialise_workspace_raises_on_duplicate_forum_id(tmp_path: Path) -> None:
    from srf.workspace.init import initialise_workspace
    from srf.workspace.models import WorkspaceError

    fixed_id = "forum-20260317-abcdef01"
    (tmp_path / "forum" / fixed_id).mkdir(parents=True)

    with patch("srf.workspace.init._generate_forum_id", return_value=fixed_id), pytest.raises(WorkspaceError, match="already exists"):
        initialise_workspace(_make_config(), tmp_path)


# ---------------------------------------------------------------------------
# Scenario: ForumWorkspace serialises to and from JSON without data loss
# ---------------------------------------------------------------------------


def test_forum_workspace_serialises_roundtrip(tmp_path: Path) -> None:
    from srf.workspace.init import initialise_workspace
    from srf.workspace.models import ForumWorkspace

    result = initialise_workspace(_make_config(), tmp_path)
    data = result.to_dict()
    restored = ForumWorkspace.from_dict(data)

    assert restored.forum_id == result.forum_id
    assert restored.workspace_path == result.workspace_path
    assert restored.paper_refs == result.paper_refs
    assert restored.created_at == result.created_at
