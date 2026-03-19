"""Story 1.1.4 — OpenClaw Skills (MCP Tools) acceptance tests."""

from __future__ import annotations

from pathlib import Path

import yaml

_SKILLS_ROOT = Path("skills")

_SKILL_NAMES = (
    "trigger_newsletter_forum",
    "review_forum_debate_format",
    "approve_editorial_review",
)


def _parse_skill(name: str) -> tuple[dict, str]:
    """Return (frontmatter dict, body str) for a SKILL.md file."""
    path = _SKILLS_ROOT / name / "SKILL.md"
    assert path.exists(), f"Missing skill file: {path}"
    text = path.read_text(encoding="utf-8")
    # Extract YAML frontmatter between first pair of ---
    parts = text.split("---", 2)
    assert len(parts) >= 3, f"No YAML frontmatter found in {path}"
    fm = yaml.safe_load(parts[1])
    body = parts[2]
    return fm, body


# ---------------------------------------------------------------------------
# Scenario: trigger_newsletter_forum frontmatter is valid
# ---------------------------------------------------------------------------


def test_trigger_skill_has_valid_frontmatter() -> None:
    fm, _ = _parse_skill("trigger_newsletter_forum")
    assert fm.get("name") == "trigger_newsletter_forum"
    assert fm.get("description"), "description must be non-empty"


# ---------------------------------------------------------------------------
# Scenario: trigger_newsletter_forum references exec command and source_path
# ---------------------------------------------------------------------------


def test_trigger_skill_references_exec_and_source_path() -> None:
    _, body = _parse_skill("trigger_newsletter_forum")
    lower = body.lower()
    assert "exec" in lower or "scripts/parse_newsletter" in lower or "scripts/trigger_newsletter_forum" in lower
    assert "source_path" in body


# ---------------------------------------------------------------------------
# Scenario: review_forum_debate_format references staging script and Lobster
# ---------------------------------------------------------------------------


def test_review_skill_has_valid_frontmatter() -> None:
    fm, _ = _parse_skill("review_forum_debate_format")
    assert fm.get("name") == "review_forum_debate_format"
    assert fm.get("description"), "description must be non-empty"


def test_review_skill_references_staging_script_and_lobster() -> None:
    _, body = _parse_skill("review_forum_debate_format")
    assert "scripts/validate_and_stage_forum.py" in body
    assert "srf_forum" in body


# ---------------------------------------------------------------------------
# Scenario: approve_editorial_review references lobster resume and resume_token
# ---------------------------------------------------------------------------


def test_approve_skill_has_valid_frontmatter() -> None:
    fm, _ = _parse_skill("approve_editorial_review")
    assert fm.get("name") == "approve_editorial_review"
    assert fm.get("description"), "description must be non-empty"


def test_approve_skill_references_lobster_resume_and_token() -> None:
    _, body = _parse_skill("approve_editorial_review")
    lower = body.lower()
    assert "resume" in lower
    assert "resume_token" in body


# ---------------------------------------------------------------------------
# Scenario: all three skills have distinct names and descriptions >= 10 chars
# ---------------------------------------------------------------------------


def test_all_skills_have_distinct_names_and_long_descriptions() -> None:
    names = []
    for skill_name in _SKILL_NAMES:
        fm, _ = _parse_skill(skill_name)
        assert fm.get("name"), f"{skill_name}: name must not be empty"
        assert len(fm.get("description", "")) >= 10, (
            f"{skill_name}: description too short"
        )
        names.append(fm["name"])
    assert len(set(names)) == len(names), f"Skill names are not unique: {names}"
