"""Story 6B.1 — Prepare debate_context.json for the OpenClaw debate skill.

Reads state.json and preparation artifacts from the forum workspace,
validates that enough agents are ready, and writes debate_context.json
as a single validated starting point for the run_forum_debate skill.

Standalone — no srf package imports. All I/O is plain JSON and filesystem.

Usage (called by run_debate_bridge.py):
    from scripts.prepare_debate_context import prepare_debate_context
    context_path = prepare_debate_context(forum_id, workspace_root)

Exit codes (when invoked as CLI):
    0 — success; debate_context.json path printed to stdout
    1 — DebateContextError; details in stderr
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Public exception
# ---------------------------------------------------------------------------

_DEFAULT_MAX_TOTAL_TURNS = 30
_DEFAULT_MAX_TURNS_PER_AGENT = 8
_DEFAULT_MAX_ROUNDS = 4
_MIN_OK_PAPER_AGENTS = 2


class DebateContextError(ValueError):
    """Raised when debate_context.json cannot be prepared due to a validation failure."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def prepare_debate_context(forum_id: str, workspace_root: Path) -> Path:
    """Validate the forum workspace and write debate_context.json.

    Args:
        forum_id:       Forum identifier (e.g. "forum-20260322-abc12345").
        workspace_root: Root workspace directory (e.g. /data/workspace).

    Returns:
        Path to the written debate_context.json.

    Raises:
        DebateContextError: if state.json is missing/malformed, fewer than
            _MIN_OK_PAPER_AGENTS agents are ready, or an ok agent's artifact
            file is absent.
    """
    workspace_path = workspace_root / "forum" / forum_id
    state = _load_state(workspace_path)

    forum_meta = _extract_forum_metadata(state, forum_id)
    agents = _build_agent_entries(state, workspace_path)
    limits = _extract_limits(state)

    transcript_path = workspace_path / "transcripts" / "transcript.jsonl"

    context = {
        "forum_id": forum_meta["forum_id"],
        "topic": forum_meta["topic"],
        "framing_question": forum_meta["framing_question"],
        "tension_axis": forum_meta["tension_axis"],
        "agents": agents,
        "limits": limits,
        "transcript_path": str(transcript_path),
        "closed_sentinel": "DEBATE_CLOSED",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    output_path = workspace_path / "debate_context.json"
    output_path.write_text(json.dumps(context, indent=2), encoding="utf-8")
    return output_path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_state(workspace_path: Path) -> dict:
    state_path = workspace_path / "state.json"
    if not state_path.exists():
        raise DebateContextError(
            f"state.json not found at {state_path}. "
            "Ensure the preparation phase completed successfully."
        )
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DebateContextError(f"state.json is not valid JSON: {exc}") from exc


def _extract_forum_metadata(state: dict, forum_id: str) -> dict:
    config = state.get("config", {})
    return {
        "forum_id": forum_id,
        "topic": config.get("topic") or state.get("topic", ""),
        "framing_question": config.get("framing_question") or state.get("framing_question", ""),
        "tension_axis": config.get("tension_axis") or state.get("tension_axis", ""),
    }


def _build_agent_entries(state: dict, workspace_path: Path) -> list[dict]:
    agents_raw: list[dict] = state.get("agents", [])

    ok_paper_agents = [
        a for a in agents_raw
        if a.get("role") == "paper_agent" and a.get("status") == "ok"
    ]
    if len(ok_paper_agents) < _MIN_OK_PAPER_AGENTS:
        raise DebateContextError(
            f"Insufficient ok Paper Agents: need at least {_MIN_OK_PAPER_AGENTS}, "
            f"got {len(ok_paper_agents)}. Check preparation phase output."
        )

    entries = []
    for agent in agents_raw:
        agent_id = agent["agent_id"]
        role = agent["role"]
        status = agent.get("status", "ok")

        entry: dict = {"agent_id": agent_id, "role": role, "status": status}

        if status == "ok":
            artifact_path = workspace_path / "preparation" / agent_id / "artifact.json"
            if not artifact_path.exists():
                raise DebateContextError(
                    f"Preparation artifact missing for agent {agent_id}: {artifact_path}. "
                    "Agent is marked ok but artifact file was not written."
                )
            entry["artifact_path"] = str(artifact_path)

        entries.append(entry)

    return entries


def _extract_limits(state: dict) -> dict:
    return {
        "max_total_turns": state.get("max_total_turns", _DEFAULT_MAX_TOTAL_TURNS),
        "max_turns_per_agent": state.get("max_turns_per_agent", _DEFAULT_MAX_TURNS_PER_AGENT),
        "max_rounds": state.get("max_rounds", _DEFAULT_MAX_ROUNDS),
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare debate_context.json for a forum workspace."
    )
    parser.add_argument("--forum-id", required=True, help="Forum identifier")
    parser.add_argument(
        "--workspace-root",
        default="/data/workspace",
        help="Workspace root directory (default: /data/workspace)",
    )
    args = parser.parse_args()

    try:
        output_path = prepare_debate_context(args.forum_id, Path(args.workspace_root))
        print(str(output_path))
    except DebateContextError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
