"""Story 6B.2 — Forum Debate Skill Documents acceptance tests.

Verifies structural requirements of SKILL.md and role documents.
Tests parse document content — they do not verify LLM behaviour.
"""

from __future__ import annotations

from pathlib import Path

import pytest

SKILL_DIR = Path("skills/run_forum_debate")
SKILL_MD = SKILL_DIR / "SKILL.md"
MODERATOR_MD = SKILL_DIR / "MODERATOR.md"
PAPER_AGENT_MD = SKILL_DIR / "PAPER_AGENT.md"
CHALLENGER_MD = SKILL_DIR / "CHALLENGER.md"
GUARDRAIL_MD = SKILL_DIR / "GUARDRAIL.md"

ROLE_DOCS = [MODERATOR_MD, PAPER_AGENT_MD, CHALLENGER_MD, GUARDRAIL_MD]


# ---------------------------------------------------------------------------
# Scenario: SKILL.md contains all required structural sections
# ---------------------------------------------------------------------------


def test_skill_md_contains_required_sections() -> None:
    content = SKILL_MD.read_text(encoding="utf-8")
    required = [
        "Parameters",
        "Inputs",
        "Debate Phases",
        "Turn Protocol",
        "Transcript Format",
        "Hard Limits",
        "Closing Protocol",
        "Error Handling",
    ]
    for section in required:
        assert section in content, f"SKILL.md missing section: {section}"


# ---------------------------------------------------------------------------
# Scenario: SKILL.md references all four role documents
# ---------------------------------------------------------------------------


def test_skill_md_references_all_role_documents() -> None:
    content = SKILL_MD.read_text(encoding="utf-8")
    for doc in ("MODERATOR.md", "PAPER_AGENT.md", "CHALLENGER.md", "GUARDRAIL.md"):
        assert doc in content, f"SKILL.md does not reference {doc}"


# ---------------------------------------------------------------------------
# Scenario: each role document defines Role, Constraints, and Output Format
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("doc_path", ROLE_DOCS, ids=lambda p: p.name)
def test_role_document_contains_required_sections(doc_path: Path) -> None:
    content = doc_path.read_text(encoding="utf-8")
    for section in ("Role", "Constraints", "Output Format"):
        assert section in content, f"{doc_path.name} missing section: {section}"


# ---------------------------------------------------------------------------
# Scenario: SKILL.md specifies the exact JSON structure for a transcript turn
# ---------------------------------------------------------------------------


def test_skill_md_specifies_transcript_turn_fields() -> None:
    content = SKILL_MD.read_text(encoding="utf-8")
    required_fields = ["turn_id", "speaker_id", "role", "phase", "content", "timestamp"]
    for field in required_fields:
        assert field in content, f"SKILL.md Transcript Format missing field: {field}"


# ---------------------------------------------------------------------------
# Scenario: SKILL.md specifies the DEBATE_CLOSED sentinel line format
# ---------------------------------------------------------------------------


def test_skill_md_specifies_debate_closed_sentinel() -> None:
    content = SKILL_MD.read_text(encoding="utf-8")
    assert "DEBATE_CLOSED" in content
    assert '"reason"' in content or "'reason'" in content, (
        "SKILL.md Closing Protocol must specify a 'reason' field in the sentinel"
    )


# ---------------------------------------------------------------------------
# Scenario: SKILL.md instructs the orchestrator to enforce hard limits
# ---------------------------------------------------------------------------


def test_skill_md_enforces_hard_limits() -> None:
    content = SKILL_MD.read_text(encoding="utf-8")
    assert "max_total_turns" in content, "SKILL.md Hard Limits must reference max_total_turns"
    assert "degraded" in content, (
        "SKILL.md Hard Limits must specify that degraded agents are excluded"
    )


# ---------------------------------------------------------------------------
# Scenario: GUARDRAIL.md specifies three signal levels and their triggers
# ---------------------------------------------------------------------------


def test_guardrail_md_specifies_signal_levels() -> None:
    content = GUARDRAIL_MD.read_text(encoding="utf-8")
    for level in ("ok", "warning", "critical"):
        assert level in content, f"GUARDRAIL.md missing signal level: {level}"
    assert "critical" in content
    # Must specify that critical triggers a Moderator re-routing
    assert "re-rout" in content.lower() or "reroute" in content.lower() or "re-route" in content.lower() or "moderator" in content.lower(), (
        "GUARDRAIL.md must specify that critical signal triggers Moderator re-routing"
    )


# ---------------------------------------------------------------------------
# Scenario: SKILL.md contains an explicit Error Handling section
# ---------------------------------------------------------------------------


def test_skill_md_error_handling_section_covers_required_cases() -> None:
    content = SKILL_MD.read_text(encoding="utf-8")
    assert "Error Handling" in content, "SKILL.md must contain an Error Handling section"
    for case in ("context", "subagent", "transcript", "report and stop"):
        assert case.lower() in content.lower(), (
            f"SKILL.md Error Handling must address: {case}"
        )


# ---------------------------------------------------------------------------
# Scenario: SKILL.md explicitly prohibits editing files under /data/srf/
# ---------------------------------------------------------------------------


def test_skill_md_prohibits_editing_data_srf() -> None:
    content = SKILL_MD.read_text(encoding="utf-8")
    assert "/data/srf/" in content, (
        "SKILL.md must explicitly prohibit editing files under /data/srf/"
    )
    assert "never edit" in content.lower() or "must not edit" in content.lower() or "must never edit" in content.lower(), (
        "SKILL.md must contain an explicit 'never edit /data/srf/' instruction"
    )
