"""Story 3.5 — MCP Trigger Tool acceptance tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

FIXTURE_NEWSLETTER = (
    Path(__file__).parent.parent / "fixtures" / "newsletters" / "valid_three_papers.md"
)


# ---------------------------------------------------------------------------
# Scenario: trigger_newsletter_forum copies the newsletter file to SRF newsletters dir
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_trigger_copies_newsletter_to_srf_dir(tmp_path: Path) -> None:
    from srf.mcp.tools import trigger_newsletter_forum
    from srf.newsletter.models import CandidateForumConfig

    fake_config = CandidateForumConfig(
        topic="t", framing_question="q?", tension_axis="a",
        paper_refs=["2401.00001"], newsletter_slug="valid_three_papers",
        generated_at="2026-03-17T10:00:00+00:00",
    )

    with (
        patch("srf.mcp.tools.cluster_papers", return_value=[MagicMock(newsletter_slug="")]),
        patch("srf.mcp.tools.generate_candidate_config", return_value=fake_config),
        patch("srf.mcp.tools.save_candidate_configs", return_value=[tmp_path / "c1.json"]),
        patch("srf.mcp.tools._build_llm_client", return_value=MagicMock()),
    ):
        await trigger_newsletter_forum(
            source_path=str(FIXTURE_NEWSLETTER),
            workspace_root=str(tmp_path),
        )

    newsletters_dir = tmp_path / ".newsletters"
    assert (newsletters_dir / FIXTURE_NEWSLETTER.name).exists()
    # Original file unchanged
    assert FIXTURE_NEWSLETTER.exists()


# ---------------------------------------------------------------------------
# Scenario: trigger_newsletter_forum returns candidate config summaries on success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_trigger_returns_candidate_summaries(tmp_path: Path) -> None:
    from srf.mcp.tools import trigger_newsletter_forum
    from srf.newsletter.models import CandidateForumConfig

    fake_config = CandidateForumConfig(
        topic="efficiency vs alignment",
        framing_question="Does efficiency always degrade alignment?",
        tension_axis="efficiency vs alignment",
        paper_refs=["2401.00001", "2401.00002"],
        newsletter_slug="valid_three_papers",
        generated_at="2026-03-17T10:00:00+00:00",
    )
    saved_path = tmp_path / "c1.json"

    with (
        patch("srf.mcp.tools.cluster_papers", return_value=[MagicMock(newsletter_slug="")]),
        patch("srf.mcp.tools.generate_candidate_config", return_value=fake_config),
        patch("srf.mcp.tools.save_candidate_configs", return_value=[saved_path]),
        patch("srf.mcp.tools._build_llm_client", return_value=MagicMock()),
    ):
        result = await trigger_newsletter_forum(
            source_path=str(FIXTURE_NEWSLETTER),
            workspace_root=str(tmp_path),
        )

    assert result["status"] == "awaiting_approval"
    assert len(result["candidates"]) == 1
    candidate = result["candidates"][0]
    assert candidate["topic"] == "efficiency vs alignment"
    assert candidate["framing_question"] == "Does efficiency always degrade alignment?"
    assert candidate["paper_count"] == 2
    assert "path" in candidate


# ---------------------------------------------------------------------------
# Scenario: trigger_newsletter_forum does not advance beyond candidate generation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_trigger_does_not_advance_pipeline(tmp_path: Path) -> None:
    from srf.mcp.tools import trigger_newsletter_forum
    from srf.newsletter.models import CandidateForumConfig

    fake_config = CandidateForumConfig(
        topic="t", framing_question="q?", tension_axis="a",
        paper_refs=[], newsletter_slug="valid_three_papers",
        generated_at="2026-03-17T10:00:00+00:00",
    )

    with (
        patch("srf.mcp.tools.cluster_papers", return_value=[MagicMock(newsletter_slug="")]),
        patch("srf.mcp.tools.generate_candidate_config", return_value=fake_config),
        patch("srf.mcp.tools.save_candidate_configs", return_value=[tmp_path / "c1.json"]),
        patch("srf.mcp.tools._build_llm_client", return_value=MagicMock()),
    ):
        result = await trigger_newsletter_forum(
            source_path=str(FIXTURE_NEWSLETTER),
            workspace_root=str(tmp_path),
        )

    assert "forum_id" not in result
    assert result["status"] == "awaiting_approval"


# ---------------------------------------------------------------------------
# Scenario: trigger_newsletter_forum raises ToolError when source file does not exist
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_trigger_raises_tool_error_on_missing_source(tmp_path: Path) -> None:
    from srf.mcp.tools import trigger_newsletter_forum
    from srf.newsletter.models import ToolError

    missing = str(tmp_path / "no_such_file.md")
    with pytest.raises(ToolError, match=re.escape(missing)):
        await trigger_newsletter_forum(
            source_path=missing,
            workspace_root=str(tmp_path),
        )


# ---------------------------------------------------------------------------
# Scenario: trigger_newsletter_forum raises ToolError on duplicate slug
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_trigger_raises_tool_error_on_duplicate_slug(tmp_path: Path) -> None:
    from srf.mcp.tools import trigger_newsletter_forum
    from srf.newsletter.models import ToolError

    # Pre-populate the .newsletters directory with the same filename
    newsletters_dir = tmp_path / ".newsletters"
    newsletters_dir.mkdir(parents=True)
    (newsletters_dir / FIXTURE_NEWSLETTER.name).write_text("already here")

    with pytest.raises(ToolError, match="(?i)already"):
        await trigger_newsletter_forum(
            source_path=str(FIXTURE_NEWSLETTER),
            workspace_root=str(tmp_path),
        )
    # Original not overwritten
    assert (newsletters_dir / FIXTURE_NEWSLETTER.name).read_text() == "already here"


# ---------------------------------------------------------------------------
# Scenario: trigger_newsletter_forum is exposed as an MCP tool with correct schema
# ---------------------------------------------------------------------------

def test_mcp_tool_is_registered_with_correct_schema() -> None:
    from srf.mcp.tools import SRF_MCP_TOOLS

    names = [t["name"] for t in SRF_MCP_TOOLS]
    assert "trigger_newsletter_forum" in names

    tool = next(t for t in SRF_MCP_TOOLS if t["name"] == "trigger_newsletter_forum")
    params = tool["parameters"]["properties"]
    assert "source_path" in params
    assert "workspace_root" in params
    assert params["source_path"].get("type") == "string"
    assert "newsletter" in tool["description"].lower()
    assert "candidate" in tool["description"].lower()


# ---------------------------------------------------------------------------
# Scenario: trigger_newsletter_forum emits structured log entries
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_trigger_emits_structured_log_entries(tmp_path: Path) -> None:
    import structlog.testing

    from srf.mcp.tools import trigger_newsletter_forum
    from srf.newsletter.models import CandidateForumConfig

    fake_config = CandidateForumConfig(
        topic="t", framing_question="q?", tension_axis="a",
        paper_refs=["2401.00001"], newsletter_slug="valid_three_papers",
        generated_at="2026-03-17T10:00:00+00:00",
    )

    with (
        patch("srf.mcp.tools.cluster_papers", return_value=[MagicMock(newsletter_slug="")]),
        patch("srf.mcp.tools.generate_candidate_config", return_value=fake_config),
        patch("srf.mcp.tools.save_candidate_configs", return_value=[tmp_path / "c1.json"]),
        patch("srf.mcp.tools._build_llm_client", return_value=MagicMock()),
        structlog.testing.capture_logs() as logs,
    ):
        await trigger_newsletter_forum(
            source_path=str(FIXTURE_NEWSLETTER),
            workspace_root=str(tmp_path),
        )

    slug_logged = any("valid_three_papers" in str(log) for log in logs)
    count_logged = any("1" in str(log.get("candidate_count", "")) for log in logs)
    assert slug_logged
    assert count_logged


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

import re  # noqa: E402 (needed for re.escape in test above)
