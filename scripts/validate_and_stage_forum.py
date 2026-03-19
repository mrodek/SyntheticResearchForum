"""Forum Staging Script.

Validates an approved CandidateForumConfig, assigns a forum_id, creates the
forum workspace directory, writes state.json, and outputs trigger JSON to
stdout for Lobster to consume as $trigger.json.

Usage (via OpenClaw review_forum_debate_format skill):
    python scripts/validate_and_stage_forum.py --config-path /path/to/config.json

Exit codes:
    0 — success; stdout is valid JSON with forum_id, workspace_path, trace_id
    1 — validation or I/O error; details in stderr
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import structlog

structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
)

log = structlog.get_logger(__name__)

_FORUM_ID_DATE_FMT = "%Y%m%d"


def _make_forum_id() -> str:
    date_part = datetime.now(tz=timezone.utc).strftime(_FORUM_ID_DATE_FMT)
    hex_part = uuid.uuid4().hex[:8]
    return f"forum-{date_part}-{hex_part}"


def _load_config(config_path: Path) -> dict:
    if not config_path.exists():
        log.error("config file not found", path=str(config_path))
        print(f"ERROR: config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        log.error("invalid config JSON", path=str(config_path), detail=str(exc))
        print(f"ERROR: invalid config: {exc}", file=sys.stderr)
        sys.exit(1)


def _validate_config(data: dict) -> None:
    paper_refs = data.get("paper_refs", [])
    if not paper_refs:
        log.error("no papers in config")
        print("ERROR: no papers — paper_refs must not be empty", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and stage a forum config.")
    parser.add_argument("--config-path", required=True, help="Path to CandidateForumConfig JSON")
    args = parser.parse_args()

    config_path = Path(args.config_path)
    data = _load_config(config_path)
    _validate_config(data)

    # Assign identifiers
    forum_id = _make_forum_id()
    trace_id = str(uuid.uuid4())

    # Create workspace directory for this forum
    workspace_root = Path(os.environ.get("OPENCLAW_WORKSPACE_DIR", "/data/workspace"))
    forum_workspace = workspace_root / "forum" / forum_id
    forum_workspace.mkdir(parents=True, exist_ok=True)

    # Write state.json
    state = {
        "forum_id": forum_id,
        "forum_status": "workspace_staged",
        "trace_id": trace_id,
        "config": data,
    }
    (forum_workspace / "state.json").write_text(
        json.dumps(state, indent=2), encoding="utf-8"
    )

    log.info(
        "forum staged",
        forum_id=forum_id,
        workspace=str(forum_workspace),
    )

    # Emit trigger JSON to stdout for Lobster / OpenClaw
    trigger = {
        "forum_id": forum_id,
        "workspace_path": str(forum_workspace),
        "trace_id": trace_id,
    }
    print(json.dumps(trigger), flush=True)


if __name__ == "__main__":
    main()
