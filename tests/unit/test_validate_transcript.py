"""Story 6B.3 — Transcript Validator acceptance tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REQUIRED_TURN_FIELDS = {"turn_id", "speaker_id", "role", "phase", "content", "timestamp"}


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_turn(
    turn_id: str,
    speaker_id: str = "paper-agent-1",
    role: str = "paper_agent",
    phase: str = "position",
    content: str = "This is a debate turn.",
    timestamp: str = "2026-03-22T10:00:00Z",
) -> dict:
    return {
        "turn_id": turn_id,
        "speaker_id": speaker_id,
        "role": role,
        "phase": phase,
        "content": content,
        "timestamp": timestamp,
    }


def _make_sentinel(reason: str = "moderator_closed", total_turns: int = 6) -> dict:
    return {
        "type": "DEBATE_CLOSED",
        "reason": reason,
        "total_turns": total_turns,
        "timestamp": "2026-03-22T10:30:00Z",
    }


def _write_transcript(tmp_path: Path, turns: list[dict], *, closed: bool = True) -> Path:
    transcript_path = tmp_path / "transcript.jsonl"
    lines = [json.dumps(t) for t in turns]
    if closed:
        lines.append(json.dumps(_make_sentinel(total_turns=len(turns))))
    transcript_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return transcript_path


# ---------------------------------------------------------------------------
# Scenario: returns TranscriptSummary for a well-formed transcript
# ---------------------------------------------------------------------------


def test_validate_transcript_returns_summary_for_well_formed_transcript(tmp_path: Path) -> None:
    from scripts.validate_transcript import validate_transcript

    turns = [_make_turn(f"t-{i:04d}") for i in range(1, 7)]
    path = _write_transcript(tmp_path, turns, closed=True)

    summary = validate_transcript(path)

    assert summary.turn_count == 6
    assert summary.debate_status == "closed"
    assert summary.close_reason == "moderator_closed"


# ---------------------------------------------------------------------------
# Scenario: raises TranscriptError when DEBATE_CLOSED sentinel is absent
# ---------------------------------------------------------------------------


def test_validate_transcript_raises_when_sentinel_absent(tmp_path: Path) -> None:
    from scripts.validate_transcript import TranscriptError, validate_transcript

    turns = [_make_turn(f"t-{i:04d}") for i in range(1, 5)]
    path = _write_transcript(tmp_path, turns, closed=False)

    with pytest.raises(TranscriptError, match="(?i)closed"):
        validate_transcript(path)


# ---------------------------------------------------------------------------
# Scenario: raises TranscriptError when any line is not valid JSON
# ---------------------------------------------------------------------------


def test_validate_transcript_raises_on_malformed_json_line(tmp_path: Path) -> None:
    from scripts.validate_transcript import TranscriptError, validate_transcript

    turns = [_make_turn(f"t-{i:04d}") for i in range(1, 5)]
    lines = [json.dumps(t) for t in turns]
    lines.insert(2, "this is not json {{")
    lines.append(json.dumps(_make_sentinel()))
    path = tmp_path / "transcript.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(TranscriptError, match="(?i)line 3"):
        validate_transcript(path)


# ---------------------------------------------------------------------------
# Scenario: raises TranscriptError when a turn is missing required fields
# ---------------------------------------------------------------------------


def test_validate_transcript_raises_on_missing_required_field(tmp_path: Path) -> None:
    from scripts.validate_transcript import TranscriptError, validate_transcript

    turn = _make_turn("t-0001")
    del turn["speaker_id"]
    path = _write_transcript(tmp_path, [turn, _make_turn("t-0002")], closed=True)

    with pytest.raises(TranscriptError, match="speaker_id"):
        validate_transcript(path)


# ---------------------------------------------------------------------------
# Scenario: returns speaker breakdown in TranscriptSummary
# ---------------------------------------------------------------------------


def test_validate_transcript_returns_speaker_breakdown(tmp_path: Path) -> None:
    from scripts.validate_transcript import validate_transcript

    turns = [
        _make_turn("t-0001", speaker_id="paper-agent-1"),
        _make_turn("t-0002", speaker_id="paper-agent-1"),
        _make_turn("t-0003", speaker_id="paper-agent-1"),
        _make_turn("t-0004", speaker_id="paper-agent-2"),
        _make_turn("t-0005", speaker_id="paper-agent-2"),
        _make_turn("t-0006", speaker_id="challenger", role="challenger"),
    ]
    path = _write_transcript(tmp_path, turns, closed=True)

    summary = validate_transcript(path)

    assert summary.turns_by_speaker["paper-agent-1"] == 3
    assert summary.turns_by_speaker["paper-agent-2"] == 2
    assert summary.turns_by_speaker["challenger"] == 1


# ---------------------------------------------------------------------------
# Scenario: raises TranscriptError when transcript file does not exist
# ---------------------------------------------------------------------------


def test_validate_transcript_raises_when_file_absent(tmp_path: Path) -> None:
    from scripts.validate_transcript import TranscriptError, validate_transcript

    missing = tmp_path / "transcript.jsonl"

    with pytest.raises(TranscriptError, match="(?i)not found"):
        validate_transcript(missing)


# ---------------------------------------------------------------------------
# Scenario: moderator turns are counted separately, not in turns_by_speaker
# ---------------------------------------------------------------------------


def test_validate_transcript_counts_moderator_turns_separately(tmp_path: Path) -> None:
    from scripts.validate_transcript import validate_transcript

    turns = [
        _make_turn("t-0001", speaker_id="moderator", role="moderator"),
        _make_turn("t-0002", speaker_id="paper-agent-1"),
        _make_turn("t-0003", speaker_id="paper-agent-2"),
        _make_turn("t-0004", speaker_id="paper-agent-1"),
    ]
    path = _write_transcript(tmp_path, turns, closed=True)

    summary = validate_transcript(path)

    assert summary.turn_count == 4
    assert summary.turns_by_speaker.get("paper-agent-1") == 2
    assert summary.turns_by_speaker.get("paper-agent-2") == 1
    # moderator turns are in turn_count but tracked separately
    assert summary.moderator_turn_count == 1
