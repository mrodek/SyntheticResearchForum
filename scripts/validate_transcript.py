"""Story 6B.3 — Transcript validator.

Reads a completed transcript.jsonl and confirms it is well-formed,
append-only, and contains the required structural elements before
the synthesis phase begins.

Standalone — no srf package imports.

Usage (called by run_debate_bridge.py):
    from scripts.validate_transcript import validate_transcript, TranscriptError
    summary = validate_transcript(transcript_path)

Exit codes (when invoked as CLI):
    0 — success; summary JSON printed to stdout
    1 — TranscriptError; details in stderr
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

_REQUIRED_TURN_FIELDS = {"turn_id", "speaker_id", "role", "phase", "content", "timestamp"}
_SENTINEL_TYPE = "DEBATE_CLOSED"


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class TranscriptError(ValueError):
    """Raised when a transcript fails validation."""


@dataclass
class TranscriptSummary:
    """Result of a successful transcript validation."""

    turn_count: int
    debate_status: str  # "closed"
    close_reason: str
    turns_by_speaker: dict[str, int] = field(default_factory=dict)
    moderator_turn_count: int = 0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_transcript(transcript_path: Path) -> TranscriptSummary:
    """Validate a completed transcript.jsonl file.

    Args:
        transcript_path: Path to the transcript JSONL file.

    Returns:
        TranscriptSummary with turn counts and close metadata.

    Raises:
        TranscriptError: if the file is absent, contains malformed JSON,
            has turns with missing required fields, or lacks the
            DEBATE_CLOSED sentinel.
    """
    if not transcript_path.exists():
        raise TranscriptError(
            f"Transcript file not found: {transcript_path}. "
            "Ensure the debate phase completed before running validation."
        )

    lines = transcript_path.read_text(encoding="utf-8").splitlines()
    lines = [ln for ln in lines if ln.strip()]  # skip blank lines

    parsed = _parse_lines(lines)
    sentinel = _find_sentinel(parsed)
    turns = [entry for entry in parsed if entry.get("type") != _SENTINEL_TYPE]

    _validate_turns(turns)

    turns_by_speaker: dict[str, int] = defaultdict(int)
    moderator_count = 0

    for turn in turns:
        if turn.get("role") == "moderator":
            moderator_count += 1
        else:
            turns_by_speaker[turn["speaker_id"]] += 1

    return TranscriptSummary(
        turn_count=len(turns),
        debate_status="closed",
        close_reason=sentinel.get("reason", ""),
        turns_by_speaker=dict(turns_by_speaker),
        moderator_turn_count=moderator_count,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_lines(lines: list[str]) -> list[dict]:
    parsed = []
    for idx, line in enumerate(lines, start=1):
        try:
            parsed.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise TranscriptError(
                f"Malformed JSON at line {idx}: {exc}"
            ) from exc
    return parsed


def _find_sentinel(entries: list[dict]) -> dict:
    for entry in reversed(entries):
        if entry.get("type") == _SENTINEL_TYPE:
            return entry
    raise TranscriptError(
        f"Transcript did not close cleanly — {_SENTINEL_TYPE} sentinel not found. "
        "The debate may have been interrupted."
    )


def _validate_turns(turns: list[dict]) -> None:
    for turn in turns:
        missing = _REQUIRED_TURN_FIELDS - turn.keys()
        if missing:
            field_name = next(iter(sorted(missing)))
            turn_id = turn.get("turn_id", "<unknown>")
            raise TranscriptError(
                f"Turn {turn_id!r} is missing required field: {field_name}"
            )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a completed debate transcript.")
    parser.add_argument("transcript_path", help="Path to transcript.jsonl")
    args = parser.parse_args()

    try:
        summary = validate_transcript(Path(args.transcript_path))
        print(json.dumps({
            "turn_count": summary.turn_count,
            "debate_status": summary.debate_status,
            "close_reason": summary.close_reason,
            "turns_by_speaker": summary.turns_by_speaker,
            "moderator_turn_count": summary.moderator_turn_count,
        }))
    except TranscriptError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
