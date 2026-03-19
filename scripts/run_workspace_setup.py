"""Lobster step: Forum Workspace Setup (Phase 4).

Reads:  JSON from stdin — { config_path: str, trace_id?: str }
Writes: JSON to stdout — { forum_id, workspace_path, paper_refs, topic,
                            framing_question, trace_id, forum_status }
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path


def main() -> int:
    from srf.logging import configure_logging
    configure_logging(stream=sys.stderr)

    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: invalid stdin JSON: {exc}", file=sys.stderr)
        return 1

    config_path_str = data.get("config_path")
    if not config_path_str:
        print("ERROR: stdin JSON missing required field 'config_path'", file=sys.stderr)
        return 1

    config_path = Path(config_path_str)
    if not config_path.exists():
        print(f"ERROR: config file not found: {config_path}", file=sys.stderr)
        return 1

    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR: cannot read config file {config_path}: {exc}", file=sys.stderr)
        return 1

    from srf.config import ConfigurationError, SRFConfig
    from srf.newsletter.models import CandidateForumConfig
    from srf.workspace.init import initialise_workspace
    from srf.workspace.models import WorkspaceError

    try:
        config = SRFConfig.from_env()
    except ConfigurationError as exc:
        print(f"ERROR: configuration error: {exc}", file=sys.stderr)
        return 1

    candidate = CandidateForumConfig(
        topic=raw["topic"],
        framing_question=raw["framing_question"],
        tension_axis=raw["tension_axis"],
        paper_refs=raw["paper_refs"],
        newsletter_slug=raw["newsletter_slug"],
        generated_at=raw["generated_at"],
    )

    try:
        workspace = initialise_workspace(candidate, config.workspace_root)
    except WorkspaceError as exc:
        print(f"ERROR: workspace error: {exc}", file=sys.stderr)
        return 1

    trace_id = data.get("trace_id") or f"trace-{uuid.uuid4().hex[:12]}"

    # Annotate state.json with trace_id
    state_path = workspace.workspace_path / "state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["trace_id"] = trace_id
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except OSError:
        pass

    output = {
        "forum_id": workspace.forum_id,
        "workspace_path": str(workspace.workspace_path),
        "paper_refs": workspace.paper_refs,
        "topic": workspace.topic,
        "framing_question": workspace.framing_question,
        "trace_id": trace_id,
        "forum_status": "workspace_ready",
    }

    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
